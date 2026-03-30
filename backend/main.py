import asyncio
import io
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.responses import StreamingResponse
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from openpyxl import Workbook

from pricing_data import get_prices, get_status, update_prices
from price_fetcher import fetch_prices

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REFRESH_INTERVAL_HOURS = 6

scheduler = AsyncIOScheduler()


async def refresh_prices():
    logger.info("Refreshing prices from OpenRouter...")
    models = await fetch_prices()
    if models:
        update_prices(models)
        logger.info("Prices updated: %d models", len(models))
    else:
        logger.warning("Refresh returned no data; keeping previous prices")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: fetch initial prices and start scheduler
    await refresh_prices()
    scheduler.add_job(refresh_prices, "interval", hours=REFRESH_INTERVAL_HOURS, id="price_refresh")
    scheduler.start()
    logger.info("Scheduler started (refresh every %dh)", REFRESH_INTERVAL_HOURS)
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
    await refresh_prices()
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
