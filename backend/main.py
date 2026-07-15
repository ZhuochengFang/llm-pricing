import asyncio
import io
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.responses import StreamingResponse
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from openpyxl import Workbook

from pricing_data import get_history, get_history_by_slug, get_prices, get_status, update_prices, record_current_history, save_history, load_history
from price_fetcher import fetch_prices
from csv_exporter import export_daily_csv, cleanup_old_csv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REFRESH_INTERVAL_MINUTES = 10
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

scheduler = AsyncIOScheduler()


def _write_refresh_log(success: bool, model_count: int = 0, error_msg: str = ""):
    """Write refresh result to the log file and generate an error file on failure."""
    os.makedirs(DATA_DIR, exist_ok=True)
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y-%m-%d %H:%M:%S UTC")

    # Always append to the main refresh log
    log_path = os.path.join(DATA_DIR, "refresh.log")
    if success:
        line = f"[{timestamp}] SUCCESS — refreshed {model_count} models\n"
    else:
        line = f"[{timestamp}] FAILED — {error_msg}\n"
    with open(log_path, "a") as f:
        f.write(line)

    # On failure, also create a separate error log file
    if not success:
        error_filename = f"error_{now.strftime('%Y%m%d_%H%M%S')}.log"
        error_path = os.path.join(DATA_DIR, error_filename)
        with open(error_path, "w") as f:
            f.write(f"Refresh failed at {timestamp}\n")
            f.write(f"Error: {error_msg}\n")


async def refresh_prices(record_history: bool = False):
    logger.info("Refreshing prices from OpenRouter...")
    models = await fetch_prices()
    if models:
        update_prices(models, record_history=record_history)
        logger.info("Prices updated: %d models", len(models))
        return True, len(models)
    else:
        logger.warning("Refresh returned no data; keeping previous prices")
        # 即使 OpenRouter 获取失败，也用当前数据（上次的 live 或静态兜底）记录历史
        if record_history:
            record_current_history()
            logger.info("Recorded history from current data (fallback)")
        return False, 0


async def scheduled_refresh():
    """Wrapper for scheduled refresh that also writes to the log."""
    success, count = await refresh_prices(record_history=True)
    _write_refresh_log(success, count, "No data returned from OpenRouter" if not success else "")
    # 无论成功与否都保存历史（失败时 record_current_history 已在 refresh_prices 中调用）
    save_history(DATA_DIR)


def daily_csv_task():
    export_daily_csv(DATA_DIR)
    cleanup_old_csv(DATA_DIR)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: load persisted history, fetch initial prices and start scheduler
    os.makedirs(DATA_DIR, exist_ok=True)
    load_history(DATA_DIR)
    success, count = await refresh_prices(record_history=True)
    _write_refresh_log(success, count, "No data returned from OpenRouter" if not success else "")
    save_history(DATA_DIR)
    daily_csv_task()
    scheduler.add_job(
        scheduled_refresh,
        "interval",
        minutes=REFRESH_INTERVAL_MINUTES,
        id="price_refresh",
    )
    scheduler.add_job(daily_csv_task, "cron", hour=0, minute=5, id="daily_csv")
    scheduler.start()
    logger.info(
        "Scheduler started (refresh every %d min, daily CSV at 00:05)",
        REFRESH_INTERVAL_MINUTES,
    )
    yield
    # Shutdown
    scheduler.shutdown()


app = FastAPI(title="LLM Pricing Dashboard", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/api/prices")
def prices(provider: Optional[str] = Query(None)):
    return get_prices(provider)


@app.get("/api/status")
def status():
    return get_status()


@app.post("/api/refresh")
async def manual_refresh():
    success, count = await refresh_prices(record_history=True)
    _write_refresh_log(success, count, "No data returned from OpenRouter" if not success else "")
    if success:
        save_history(DATA_DIR)
    return get_status()


@app.get("/api/export")
def export_excel(provider: Optional[str] = Query(None)):
    rows = get_prices(provider)
    wb = Workbook()
    ws = wb.active
    ws.title = "LLM Pricing"
    headers = ["Provider", "Model", "Input $/1M tokens", "Output $/1M tokens", "Context Window"]
    ws.append(headers)
    for col in range(1, len(headers) + 1):
        ws.cell(row=1, column=col).font = ws.cell(row=1, column=col).font.copy(bold=True)
    for r in rows:
        ws.append([r["provider"], r["model"], r["input_price"], r["output_price"], r["context_window"]])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=llm_pricing.xlsx"},
    )


@app.get("/api/history")
def history(provider: str = Query(...), model: str = Query(...)):
    return get_history(provider, model)


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
