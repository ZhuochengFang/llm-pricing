# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LLM Pricing Dashboard — a web app that displays and compares pricing across major AI providers. Prices are fetched live from the OpenRouter API and fall back to static data in `pricing_data.py`.

## Development Commands

```bash
# Install dependencies (use a venv)
cd backend && pip install -r requirements.txt

# Run the dev server (from backend/)
cd backend && uvicorn main:app --reload --port 8000

# Run with Docker
docker compose up --build
```

The app serves on port 8000. Frontend is accessed at `/`, API at `/api/*`.

## Architecture

**Backend** (FastAPI, Python 3.12):
- `backend/main.py` — FastAPI app with lifespan. Endpoints: `GET /api/prices`, `GET /api/status`, `POST /api/refresh`, `GET /api/export` (Excel download). Mounts `frontend/` as `/static` and serves `index.html` as a catch-all.
- `backend/pricing_data.py` — In-memory pricing store. Contains static fallback data (`PRICING_DATA`) and mutable state (`_live_data`) updated by the fetcher. No database.
- `backend/price_fetcher.py` — Async fetcher that pulls models from OpenRouter (`/api/v1/models`), filters to known providers via `PROVIDER_MAP`, and normalizes pricing to $/1M tokens.

**Frontend** (vanilla HTML/CSS/JS, no build step):
- `frontend/index.html`, `frontend/script.js`, `frontend/style.css`
- Fetches `/api/prices`, renders a sortable/filterable table. Refresh button triggers `/api/refresh` then auto-downloads an Excel export.

**Scheduling**: APScheduler refreshes prices every 6 hours (`REFRESH_INTERVAL_HOURS`). Initial fetch happens at startup.

**Deployment**: Dockerfile copies `backend/` to `/app` and `frontend/` to `/app/static/`. The `docker-compose.yml` exposes port 8000 with a named volume for `/app/data`.

## Key Details

- No test suite exists.
- No database — all pricing data is held in module-level globals in `pricing_data.py`.
- The root `index.html` is unrelated to the project (appears to be a cached Google page).
- `Python-3.10.14.tgz` at the root is a vendored archive, not used by the app (Dockerfile uses `python:3.12-slim`).
- Supported providers: OpenAI, Anthropic, Google, DeepSeek, Mistral, Meta.
