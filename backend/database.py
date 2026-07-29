"""
PostgreSQL 数据库模块。

职责：
- 管理 asyncpg 连接池的创建与关闭
- 自动建表（price_history）和索引
- 批量写入价格历史记录
- 按供应商/模型/平台查询历史数据（默认 7 天窗口）
- 定期清理过期历史数据
"""

import asyncpg
import logging
import os
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None  # 模块级连接池

DATABASE_URL_DEFAULT = "postgresql://llmpricing:llmpricing@db:5432/llmpricing"


async def init_pool() -> bool:
    """创建数据库连接池并确保表结构存在。"""
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
    """关闭连接池并释放资源。"""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


async def _ensure_schema() -> None:
    """确保 price_history 表和索引存在（幂等操作）。"""
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
    """使用 COPY 协议批量写入价格历史记录。"""
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
    """查询指定模型的价格历史，按平台分组返回。默认 7 天窗口，最多 1008 个数据点。"""
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
    """删除超过保留窗口（默认 7 天）的历史记录，返回删除行数。"""
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
