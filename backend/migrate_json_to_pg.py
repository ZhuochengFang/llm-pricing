"""
一次性迁移脚本：将 JSON 格式的价格历史数据导入 PostgreSQL。

用法：
    python migrate_json_to_pg.py [path/to/price_history.json]

若不指定路径则默认读取 data/price_history.json。
JSON 键格式为 "platform|provider|model" 或 "provider|model"（默认 platform 为 openrouter）。
需要设置 DATABASE_URL 环境变量，或使用默认连接字符串。
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
