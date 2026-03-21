from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import Optional
from pricing_data import get_prices


app = FastAPI(title="LLM Pricing Dashboard")


@app.get("/api/prices")
def prices(provider: Optional[str] = Query(None)):
    return get_prices(provider)


app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/{full_path:path}")
def serve_frontend(full_path: str):
    return FileResponse("static/index.html")
