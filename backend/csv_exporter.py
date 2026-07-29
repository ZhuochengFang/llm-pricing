"""
每日 CSV 快照导出器。

每天 00:05 自动导出当日定价数据到 data/ 目录（llm_prices_YYYY-MM-DD.csv），
并清理超过 7 天的旧文件。
"""

import csv
import logging
import os
from datetime import date, datetime, timedelta
from pathlib import Path

from pricing_data import get_prices

logger = logging.getLogger(__name__)

CSV_HEADERS = ["Platform", "Provider", "Model", "Input $/1M tokens", "Output $/1M tokens", "Context Window"]


def export_daily_csv(data_dir: str) -> str | None:
    """导出当日定价快照为 CSV 文件。如果当日文件已存在则跳过，返回文件路径或 None。"""
    today = date.today().isoformat()
    filepath = Path(data_dir) / f"llm_prices_{today}.csv"

    if filepath.exists():
        logger.info("CSV for %s already exists, skipping", today)
        return None

    rows = get_prices()
    with open(filepath, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADERS)
        for r in rows:
            ctx = r["context_window"] if r.get("context_window") else ""
            writer.writerow([r.get("platform", ""), r["provider"], r["model"], r["input_price"], r["output_price"], ctx])

    logger.info("Exported %d models to %s", len(rows), filepath)
    return str(filepath)


def cleanup_old_csv(data_dir: str, max_age_days: int = 7) -> list[str]:
    """删除超过指定天数的旧 CSV 文件，返回被删除的文件名列表。"""
    cutoff = date.today() - timedelta(days=max_age_days)
    deleted = []

    for f in Path(data_dir).glob("llm_prices_*.csv"):
        try:
            # Extract date from filename: llm_prices_YYYY-MM-DD.csv
            date_str = f.stem.replace("llm_prices_", "")
            file_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            continue

        if file_date < cutoff:
            f.unlink()
            deleted.append(f.name)
            logger.info("Deleted old CSV: %s", f.name)

    return deleted
