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
    update_prices, update_yunwu_prices, record_current_history,
    save_history, load_history,
)
from price_fetcher import fetch_prices
from yunwu_fetcher import fetch_yunwu_prices
from csv_exporter import export_daily_csv, cleanup_old_csv

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


async def refresh_prices(record_history: bool = False):
    logger.info("Refreshing prices from OpenRouter...")
    models = await fetch_prices()
    if models:
        try:
            update_prices(models, record_history=record_history)
        except Exception as e:
            logger.exception("update_prices failed: %s", e)
            raise RuntimeError(f"update_prices failed: {e}") from e
        logger.info("Prices updated: %d models", len(models))
        return True, len(models)
    else:
        logger.warning("Refresh returned no data; keeping previous prices")
        # 即使 OpenRouter 获取失败，也用当前数据（上次的 live 或静态兜底）记录历史
        if record_history:
            try:
                record_current_history()
            except Exception as e:
                logger.exception("record_current_history failed: %s", e)
                raise RuntimeError(f"record_current_history failed: {e}") from e
            logger.info("Recorded history from current data (fallback)")
        return False, 0


async def refresh_yunwu_prices(record_history: bool = False):
    logger.info("Refreshing prices from Yunwu...")
    models = await fetch_yunwu_prices()
    if models:
        try:
            update_yunwu_prices(models, record_history=record_history)
        except Exception as e:
            logger.exception("update_yunwu_prices failed: %s", e)
            raise RuntimeError(f"update_yunwu_prices failed: {e}") from e
        logger.info("Yunwu prices updated: %d models", len(models))
        return True, len(models)
    else:
        logger.warning("Yunwu refresh returned no data")
        return False, 0


async def refresh_all(record_history: bool = False, source: str = _SOURCE_SCHEDULED):
    """Refresh prices from all platforms concurrently."""
    results = await asyncio.gather(
        refresh_prices(record_history=record_history),
        refresh_yunwu_prices(record_history=record_history),
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

    save_history(DATA_DIR)


async def scheduled_refresh():
    """定时刷新，写入日志并保存历史。"""
    try:
        await refresh_all(record_history=True, source=_SOURCE_SCHEDULED)
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
    # 启动：加载持久化历史、获取初始价格、启动定时任务
    os.makedirs(DATA_DIR, exist_ok=True)
    load_history(DATA_DIR)
    await refresh_all(record_history=True, source=_SOURCE_STARTUP)
    daily_csv_task()
    # 每日中国时间 09:00–22:00 每小时整点刷新价格（UTC 01:00–14:00）
    scheduler.add_job(
        scheduled_refresh,
        "cron",
        hour=arithmetic_sequence(1, 14),
        id="price_refresh",
        misfire_grace_time=300,  # 允许最多 5 分钟延迟仍执行，避免因事件循环抖动而跳过
    )
    scheduler.add_job(daily_csv_task, "cron", hour=0, minute=5, id="daily_csv",
                      misfire_grace_time=300)
    scheduler.start()
    logger.info("Scheduler started (price refresh hourly 09:00–22:00 CST, daily CSV at 00:05)")
    yield
    # 关闭调度器
    scheduler.shutdown()


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
    await refresh_all(record_history=True, source=_SOURCE_MANUAL)
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
def history(provider: str = Query(...), model: str = Query(...),
            platform: Optional[str] = Query(None)):
    return get_history(provider, model, platform)


@app.get("/api/history/{slug}")
def history_by_slug(slug: str):
    result = get_history_by_slug(slug)
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
