import asyncpg
import logging
import os
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None

DATABASE_URL_DEFAULT = "postgresql://llmpricing:llmpricing@db:5432/llmpricing"


async def init_pool() -> bool:
    global _pool
    dsn = os.environ.get("DATABASE_URL", DATABASE_URL_DEFAULT)
    try:
        _pool = await asyncpg.create_pool(dsn, min_size=2, max_size=10, command_timeout=10)
        await _ensure_schema()
        logger.info("Database pool initialized")
        return True
    except Exception:
        logger.exception("Failed to connect to PostgreSQL; history will be unavailable")
        _pool = None
        return False


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


async def _ensure_schema() -> None:
    async with _pool.acquire() as conn:
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


def is_available() -> bool:
    return _pool is not None


async def insert_history_batch(
    platform: str, models: list[dict], recorded_at: datetime
) -> None:
    if not _pool:
        return
    records = [
        (platform, m["provider"], m["model"], m["input_price"], m["output_price"], recorded_at)
        for m in models
    ]
    try:
        async with _pool.acquire() as conn:
            await conn.copy_records_to_table(
                "price_history",
                records=records,
                columns=["platform", "provider", "model", "input_price", "output_price", "recorded_at"],
            )
    except Exception:
        logger.exception("Failed to insert history batch (%s, %d models)", platform, len(models))


async def query_history(
    provider: str,
    model: str,
    platform: str | None = None,
    window: timedelta = timedelta(days=7),
    max_points: int = 1008,
) -> dict[str, list[dict]]:
    if not _pool:
        return {}
    cutoff = datetime.now(timezone.utc) - window
    try:
        async with _pool.acquire() as conn:
            if platform:
                rows = await conn.fetch(
                    """
                    SELECT platform, input_price, output_price, recorded_at
                    FROM price_history
                    WHERE provider = $1 AND model = $2 AND platform = $3 AND recorded_at >= $4
                    ORDER BY recorded_at ASC
                    LIMIT $5
                    """,
                    provider, model, platform, cutoff, max_points,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT platform, input_price, output_price, recorded_at
                    FROM price_history
                    WHERE provider = $1 AND model = $2 AND recorded_at >= $3
                    ORDER BY recorded_at ASC
                    LIMIT $4
                    """,
                    provider, model, cutoff, max_points,
                )
    except Exception:
        logger.exception("Failed to query history for %s/%s", provider, model)
        return {}

    result: dict[str, list[dict]] = {}
    for row in rows:
        plat = row["platform"]
        result.setdefault(plat, []).append({
            "timestamp": row["recorded_at"].isoformat(),
            "input_price": row["input_price"],
            "output_price": row["output_price"],
        })
    return result


async def cleanup_old_history(window: timedelta = timedelta(days=7)) -> int:
    if not _pool:
        return 0
    cutoff = datetime.now(timezone.utc) - window
    try:
        async with _pool.acquire() as conn:
            result = await conn.execute("DELETE FROM price_history WHERE recorded_at < $1", cutoff)
            deleted = int(result.split()[-1])
            if deleted:
                logger.info("Cleaned up %d old history rows", deleted)
            return deleted
    except Exception:
        logger.exception("Failed to clean up old history")
        return 0
