# Copilot Instructions for `llm-pricing`

## Build, test, and lint commands

- Install backend dependencies:
  - `cd backend && pip install -r requirements.txt`
- Run the app locally (FastAPI + static frontend on port 8000):
  - `cd backend && uvicorn main:app --reload --port 8000`
- Run with Docker:
  - `docker compose up --build`

Automated test and lint commands are not configured in this repository right now, and there is no single-test command to run.

## High-level architecture

- This is a FastAPI backend plus a static vanilla JS frontend (no frontend build step).
- `backend/main.py` owns app startup/lifecycle and API surface:
  - `GET /api/prices` returns model pricing (optionally filtered by provider).
  - `GET /api/status` returns source/last-updated/model-count metadata.
  - `POST /api/refresh` fetches new data from OpenRouter and updates in-memory state.
  - `GET /api/export` generates and streams an Excel file.
- Data flow:
  1. `price_fetcher.fetch_prices()` calls OpenRouter `/api/v1/models`, filters providers via `PROVIDER_MAP`, normalizes prices to USD per 1M tokens.
  2. `pricing_data.update_prices()` stores live data in module-level globals.
  3. `pricing_data.get_prices()` serves live data if available, otherwise static fallback `PRICING_DATA`.
- Scheduling:
  - APScheduler runs a 6-hour refresh job and a daily CSV snapshot job (`csv_exporter.py`).
  - Refresh results are appended to `backend/data/refresh.log`; failures also create timestamped `error_*.log`.
- Frontend (`frontend/script.js`) consumes `/api/prices`, renders sortable/filterable rows, and on refresh triggers `/api/refresh` then downloads `/api/export`.
- Static serving:
  - Docker copies `frontend/` to `/app/static/`.
  - FastAPI mounts `/static` and serves `static/index.html` for catch-all routes.

## Key conventions specific to this codebase

- Treat `backend/pricing_data.py` as the single source of pricing state in-process:
  - Keep fallback prices in `PRICING_DATA`.
  - Keep runtime/live values in `_live_data`, `_updated_at`, `_source`.
  - Do not introduce DB-backed pricing state unless the project direction changes.
- Provider naming is normalized to display labels (`OpenAI`, `Anthropic`, `Google`, `DeepSeek`, `Mistral`, `Meta`) through `PROVIDER_MAP` in `price_fetcher.py`; keep that mapping and frontend badge naming aligned.
- `price_fetcher._parse_model()` intentionally drops unusable variants:
  - Requires model id format `provider/model`.
  - Skips model variants containing `:` (free/nitro/floor).
  - Requires both prompt/completion prices and context length.
- API payload rows include metadata (`updated_at`, `source`) on each entry; frontend status rendering depends on this shape.
- The project’s active frontend is under `frontend/`; do not use the repository-root `index.html` for app changes.
