import csv
import logging
import os
from datetime import date, datetime, timedelta
from pathlib import Path

from pricing_data import get_prices

logger = logging.getLogger(__name__)

CSV_HEADERS = ["Provider", "Model", "Input $/1M tokens", "Output $/1M tokens", "Context Window"]


def export_daily_csv(data_dir: str) -> str | None:
    """Write today's pricing snapshot to a dated CSV file. Returns the path, or None if it already exists."""
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
            writer.writerow([r["provider"], r["model"], r["input_price"], r["output_price"], r["context_window"]])

    logger.info("Exported %d models to %s", len(rows), filepath)
    return str(filepath)


def cleanup_old_csv(data_dir: str, max_age_days: int = 7) -> list[str]:
    """Delete CSV files older than max_age_days. Returns list of deleted filenames."""
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
