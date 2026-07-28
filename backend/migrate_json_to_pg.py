"""
One-time migration: price_history.json -> PostgreSQL.

Usage:
    python migrate_json_to_pg.py [path/to/price_history.json]

Defaults to data/price_history.json if no argument given.
Expects DATABASE_URL env var or uses the default connection string.
"""
import asyncio
import json
import sys
import os
from datetime import datetime

import asyncpg

DATABASE_URL_DEFAULT = "postgresql://llmpricing:llmpricing@db:5432/llmpricing"


async def migrate(json_path: str):
    dsn = os.environ.get("DATABASE_URL", DATABASE_URL_DEFAULT)
    conn = await asyncpg.connect(dsn)

    await conn.execute("""
        CREATE TABLE IF NOT EXISTS price_history (
            id           BIGSERIAL PRIMARY KEY,
            platform     VARCHAR(20)  NOT NULL,
            provider     VARCHAR(50)  NOT NULL,
            model        VARCHAR(200) NOT NULL,
            input_price  DOUBLE PRECISION NOT NULL,
            output_price DOUBLE PRECISION NOT NULL,
            recorded_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
        )
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS ix_history_lookup
            ON price_history (provider, model, platform, recorded_at DESC)
    """)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS ix_history_cleanup
            ON price_history (recorded_at)
    """)

    with open(json_path) as f:
        raw = json.load(f)

    records = []
    for key, points in raw.items():
        parts = key.split("|")
        if len(parts) == 3:
            platform, provider, model = parts
        elif len(parts) == 2:
            platform = "openrouter"
            provider, model = parts
        else:
            continue
        for p in points:
            try:
                ts = datetime.fromisoformat(p["timestamp"])
                records.append((
                    platform, provider, model,
                    p["input_price"], p["output_price"], ts,
                ))
            except (KeyError, ValueError):
                continue

    await conn.copy_records_to_table(
        "price_history",
        records=records,
        columns=["platform", "provider", "model", "input_price", "output_price", "recorded_at"],
    )
    print(f"Migrated {len(records)} records from {len(raw)} model keys")
    await conn.close()


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data/price_history.json"
    asyncio.run(migrate(path))
