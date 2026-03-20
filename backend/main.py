from contextlib import asynccontextmanager
from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import Optional
from pricing_data import get_prices, get_price_history, PRICING_DATA
from price_store import init_db, record_daily_prices, seed_history, get_prices_7day, has_records


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize DB and record today's prices
    init_db()
    if not has_records():
        seed_history(PRICING_DATA, days=7)
    record_daily_prices(PRICING_DATA)
    yield


app = FastAPI(title="LLM Pricing Dashboard", lifespan=lifespan)


@app.get("/api/prices")
def prices(provider: Optional[str] = Query(None)):
    return get_prices(provider)


@app.get("/api/price-history")
def price_history(provider: Optional[str] = Query(None), model: Optional[str] = Query(None)):
    return get_price_history(provider, model)


@app.get("/api/prices-7day")
def prices_7day(provider: Optional[str] = Query(None), model: Optional[str] = Query(None)):
    return get_prices_7day(provider, model)


app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/{full_path:path}")
def serve_frontend(full_path: str):
    return FileResponse("static/index.html")
