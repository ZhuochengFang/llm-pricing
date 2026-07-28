import asyncio
import io
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.responses import StreamingResponse
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from openpyxl import Workbook

from pricing_data import (
    get_history, get_history_by_slug, get_prices, get_status,
    update_prices, update_yunwu_prices, PRICING_DATA,
)
import pricing_data
from price_fetcher import fetch_prices
from yunwu_fetcher import fetch_yunwu_prices
from csv_exporter import export_daily_csv, cleanup_old_csv
from database import init_pool, close_pool, insert_history_batch, cleanup_old_history

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

scheduler = AsyncIOScheduler()
CHINA_TZ = timezone(timedelta(hours=8))

# 触发来源标签
_SOURCE_SCHEDULED = "SCHEDULED"   # 定时刷新
_SOURCE_MANUAL = "MANUAL"         # 用户通过网页 Refresh 按钮手动触发
_SOURCE_STARTUP = "STARTUP"       # 应用启动时首次加载


def _write_refresh_log(success: bool, model_count: int = 0, error_msg: str = "",
                       source: str = _SOURCE_SCHEDULED, platform: str = "openrouter"):
    """Write refresh result to the log file and generate an error file on failure."""
    os.makedirs(DATA_DIR, exist_ok=True)
    now = datetime.now(CHINA_TZ)
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S CST")

    # 追加到主刷新日志
    log_path = os.path.join(DATA_DIR, "refresh.log")
    tag = f"[{source}]" if platform == "openrouter" else f"[{source}:{platform}]"
    if success:
        line = f"[{timestamp}] {tag} SUCCESS — refreshed {model_count} models\n"
    else:
        line = f"[{timestamp}] {tag} FAILED — {error_msg}\n"
    with open(log_path, "a") as f:
        f.write(line)

    # 失败时额外生成独立的错误日志文件
    if not success:
        error_filename = f"error_{now.strftime('%Y%m%d_%H%M%S')}_{platform}.log"
        error_path = os.path.join(DATA_DIR, error_filename)
        with open(error_path, "w") as f:
            f.write(f"Refresh failed at {timestamp} ({platform})\n")
            f.write(f"Error: {error_msg}\n")


async def refresh_prices():
    logger.info("Refreshing prices from OpenRouter...")
    models = await fetch_prices()
    if models:
        try:
            update_prices(models)
        except Exception as e:
            logger.exception("update_prices failed: %s", e)
            raise RuntimeError(f"update_prices failed: {e}") from e
        now = datetime.now(timezone.utc)
        await insert_history_batch("openrouter", models, now)
        logger.info("Prices updated: %d models", len(models))
        return True, len(models)
    else:
        logger.warning("Refresh returned no data; keeping previous prices")
        now = datetime.now(timezone.utc)
        fallback = pricing_data._live_data if pricing_data._live_data else PRICING_DATA
        await insert_history_batch("openrouter", fallback, now)
        logger.info("Recorded history from current data (fallback)")
        return False, 0


async def refresh_yunwu_prices():
    logger.info("Refreshing prices from Yunwu...")
    models = await fetch_yunwu_prices()
    if models:
        try:
            update_yunwu_prices(models)
        except Exception as e:
            logger.exception("update_yunwu_prices failed: %s", e)
            raise RuntimeError(f"update_yunwu_prices failed: {e}") from e
        now = datetime.now(timezone.utc)
        await insert_history_batch("yunwu", models, now)
        logger.info("Yunwu prices updated: %d models", len(models))
        return True, len(models)
    else:
        logger.warning("Yunwu refresh returned no data")
        return False, 0


async def refresh_all(source: str = _SOURCE_SCHEDULED):
    """Refresh prices from all platforms concurrently."""
    results = await asyncio.gather(
        refresh_prices(),
        refresh_yunwu_prices(),
        return_exceptions=True,
    )

    or_result = results[0]
    yw_result = results[1]

    if isinstance(or_result, Exception):
        _write_refresh_log(False, 0, str(or_result), source=source, platform="openrouter")
    else:
        or_ok, or_count = or_result
        _write_refresh_log(or_ok, or_count,
                           "No data returned from OpenRouter" if not or_ok else "",
                           source=source, platform="openrouter")

    if isinstance(yw_result, Exception):
        _write_refresh_log(False, 0, str(yw_result), source=source, platform="yunwu")
    else:
        yw_ok, yw_count = yw_result
        _write_refresh_log(yw_ok, yw_count,
                           "No data returned from Yunwu" if not yw_ok else "",
                           source=source, platform="yunwu")


async def scheduled_refresh():
    """定时刷新，写入日志。"""
    try:
        await refresh_all(source=_SOURCE_SCHEDULED)
    except Exception as e:
        logger.exception("Scheduled refresh crashed: %s", e)
        try:
            _write_refresh_log(False, 0, f"Exception: {e}", source=_SOURCE_SCHEDULED)
        except Exception:
            logger.exception("Failed to write refresh log after crash")


def daily_csv_task():
    export_daily_csv(DATA_DIR)
    cleanup_old_csv(DATA_DIR)

def arithmetic_sequence(start, end, step=1):
    """生成等差数列字符串"""
    return ','.join(str(i) for i in range(start, end + 1, step))


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(DATA_DIR, exist_ok=True)

    db_ok = await init_pool()
    if not db_ok:
        logger.warning("Starting without database — history unavailable")

    await refresh_all(source=_SOURCE_STARTUP)
    daily_csv_task()
    # 每日中国时间 09:00–22:00 每小时整点刷新价格（UTC 01:00–14:00）
    scheduler.add_job(
        scheduled_refresh,
        "cron",
        hour=arithmetic_sequence(1, 14),
        id="price_refresh",
        misfire_grace_time=300,
    )
    scheduler.add_job(daily_csv_task, "cron", hour=0, minute=5, id="daily_csv",
                      misfire_grace_time=300)
    scheduler.add_job(cleanup_old_history, "cron", hour=3, minute=0,
                      id="history_cleanup", misfire_grace_time=300)
    scheduler.start()
    logger.info("Scheduler started (price refresh hourly 09:00–22:00 CST, daily CSV at 00:05, history cleanup at 03:00 UTC)")
    yield
    scheduler.shutdown()
    await close_pool()


app = FastAPI(title="LLM Pricing Dashboard", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/api/prices")
def prices(provider: Optional[str] = Query(None), platform: Optional[str] = Query(None)):
    return get_prices(provider, platform)


@app.get("/api/status")
def status():
    return get_status()


@app.post("/api/refresh")
async def manual_refresh():
    await refresh_all(source=_SOURCE_MANUAL)
    return get_status()


@app.get("/api/export")
def export_excel(provider: Optional[str] = Query(None), platform: Optional[str] = Query(None)):
    rows = get_prices(provider, platform)
    wb = Workbook()
    ws = wb.active
    ws.title = "LLM Pricing"
    headers = ["Platform", "Provider", "Model", "Input $/1M tokens", "Output $/1M tokens", "Context Window"]
    ws.append(headers)
    for col in range(1, len(headers) + 1):
        ws.cell(row=1, column=col).font = ws.cell(row=1, column=col).font.copy(bold=True)
    for r in rows:
        ctx = r["context_window"] if r["context_window"] else ""
        ws.append([r["platform"], r["provider"], r["model"], r["input_price"], r["output_price"], ctx])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=llm_pricing.xlsx"},
    )


@app.get("/api/history")
async def history(provider: str = Query(...), model: str = Query(...),
            platform: Optional[str] = Query(None)):
    return await get_history(provider, model, platform)


@app.get("/api/history/{slug}")
async def history_by_slug(slug: str):
    result = await get_history_by_slug(slug)
    if not result:
        return JSONResponse(status_code=404, content={"detail": "Unknown model slug"})
    return result


@app.get("/history")
def history_page():
    return FileResponse("static/history.html")


@app.get("/{slug}")
def history_slug_page(slug: str):
    return FileResponse("static/history.html")


@app.get("/{full_path:path}")
def serve_frontend(full_path: str):
    return FileResponse("static/index.html")
