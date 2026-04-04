import asyncio
import io
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.responses import StreamingResponse
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from openpyxl import Workbook

from pricing_data import get_prices, get_status, update_prices
from price_fetcher import fetch_prices
from csv_exporter import export_daily_csv, cleanup_old_csv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REFRESH_INTERVAL_HOURS = 6
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


async def refresh_prices():
    logger.info("Refreshing prices from OpenRouter...")
    models = await fetch_prices()
    if models:
        update_prices(models)
        logger.info("Prices updated: %d models", len(models))
        return True, len(models)
    else:
        logger.warning("Refresh returned no data; keeping previous prices")
        return False, 0


async def scheduled_refresh():
    """Wrapper for scheduled refresh that also writes to the log."""
    success, count = await refresh_prices()
    _write_refresh_log(success, count, "No data returned from OpenRouter" if not success else "")


def daily_csv_task():
    export_daily_csv(DATA_DIR)
    cleanup_old_csv(DATA_DIR)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: fetch initial prices and start scheduler
    success, count = await refresh_prices()
    _write_refresh_log(success, count, "No data returned from OpenRouter" if not success else "")
    os.makedirs(DATA_DIR, exist_ok=True)
    daily_csv_task()
    scheduler.add_job(scheduled_refresh, "interval", hours=REFRESH_INTERVAL_HOURS, id="price_refresh")
    scheduler.add_job(daily_csv_task, "cron", hour=0, minute=5, id="daily_csv")
    scheduler.start()
    logger.info("Scheduler started (refresh every %dh, daily CSV at 00:05)", REFRESH_INTERVAL_HOURS)
    yield
    # Shutdown
    scheduler.shutdown()


app = FastAPI(title="LLM Pricing Dashboard", lifespan=lifespan)


@app.get("/api/prices")
def prices(provider: Optional[str] = Query(None)):
    return get_prices(provider)


@app.get("/api/status")
def status():
    return get_status()


@app.post("/api/refresh")
async def manual_refresh():
    success, count = await refresh_prices()
    _write_refresh_log(success, count, "No data returned from OpenRouter" if not success else "")
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


app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/{full_path:path}")
def serve_frontend(full_path: str):
    return FileResponse("static/index.html")
