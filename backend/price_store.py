import sqlite3
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

DB_PATH = os.environ.get("PRICE_DB_PATH", os.path.join(os.path.dirname(__file__), "daily_prices.db"))


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            input_price REAL NOT NULL,
            output_price REAL NOT NULL,
            context_window INTEGER NOT NULL,
            UNIQUE(date, provider, model)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_date ON daily_prices(date)")
    conn.commit()
    conn.close()


def record_daily_prices(pricing_data: list[dict]):
    """Record today's prices. Skips if already recorded for today."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    conn = _get_conn()
    for entry in pricing_data:
        conn.execute(
            """INSERT OR IGNORE INTO daily_prices (date, provider, model, input_price, output_price, context_window)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (today, entry["provider"], entry["model"],
             entry["input_price"], entry["output_price"], entry["context_window"])
        )
    conn.commit()
    conn.close()


def seed_history(pricing_data: list[dict], days: int = 7):
    """Seed the database with historical snapshots using current prices.
    Only seeds dates that have no records yet."""
    conn = _get_conn()
    today = datetime.now(timezone.utc).date()
    for i in range(days, 0, -1):
        date_str = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        for entry in pricing_data:
            conn.execute(
                """INSERT OR IGNORE INTO daily_prices (date, provider, model, input_price, output_price, context_window)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (date_str, entry["provider"], entry["model"],
                 entry["input_price"], entry["output_price"], entry["context_window"])
            )
    conn.commit()
    conn.close()


def get_prices_7day(provider: Optional[str] = None, model: Optional[str] = None) -> list[dict]:
    """Get daily price snapshots for the last 7 days, grouped by model."""
    conn = _get_conn()
    cutoff = (datetime.now(timezone.utc).date() - timedelta(days=7)).strftime("%Y-%m-%d")

    query = "SELECT * FROM daily_prices WHERE date >= ?"
    params: list = [cutoff]

    if provider:
        query += " AND LOWER(provider) = LOWER(?)"
        params.append(provider)
    if model:
        query += " AND LOWER(model) = LOWER(?)"
        params.append(model)

    query += " ORDER BY date ASC"

    rows = conn.execute(query, params).fetchall()
    conn.close()

    # Group by provider+model
    grouped: dict[str, dict] = {}
    for row in rows:
        key = row["provider"] + ":" + row["model"]
        if key not in grouped:
            grouped[key] = {
                "provider": row["provider"],
                "model": row["model"],
                "daily_prices": []
            }
        grouped[key]["daily_prices"].append({
            "date": row["date"],
            "input_price": row["input_price"],
            "output_price": row["output_price"],
        })

    return list(grouped.values())


def has_records() -> bool:
    """Check if the database has any records."""
    conn = _get_conn()
    count = conn.execute("SELECT COUNT(*) FROM daily_prices").fetchone()[0]
    conn.close()
    return count > 0
