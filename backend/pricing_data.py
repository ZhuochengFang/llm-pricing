import json
import os
import re
from datetime import datetime, timezone, timedelta
from typing import Optional

PRICING_DATA = [
    # OpenAI
    {"provider": "OpenAI", "model": "gpt-4o", "input_price": 2.50, "output_price": 10.00, "context_window": 128000},
    {"provider": "OpenAI", "model": "gpt-4o-mini", "input_price": 0.15, "output_price": 0.60, "context_window": 128000},
    {"provider": "OpenAI", "model": "gpt-4-turbo", "input_price": 10.00, "output_price": 30.00, "context_window": 128000},
    {"provider": "OpenAI", "model": "o1", "input_price": 15.00, "output_price": 60.00, "context_window": 200000},
    {"provider": "OpenAI", "model": "o1-mini", "input_price": 3.00, "output_price": 12.00, "context_window": 128000},
    {"provider": "OpenAI", "model": "o3-mini", "input_price": 1.10, "output_price": 4.40, "context_window": 200000},
    # Anthropic
    {"provider": "Anthropic", "model": "claude-opus-4", "input_price": 15.00, "output_price": 75.00, "context_window": 200000},
    {"provider": "Anthropic", "model": "claude-sonnet-4", "input_price": 3.00, "output_price": 15.00, "context_window": 200000},
    {"provider": "Anthropic", "model": "claude-haiku-3.5", "input_price": 0.80, "output_price": 4.00, "context_window": 200000},
    # DeepSeek
    {"provider": "DeepSeek", "model": "deepseek-v3", "input_price": 0.27, "output_price": 1.10, "context_window": 128000},
    {"provider": "DeepSeek", "model": "deepseek-r1", "input_price": 0.55, "output_price": 2.19, "context_window": 128000},
    {"provider": "DeepSeek", "model": "deepseek-v4-pro", "input_price": 0.44, "output_price": 0.87, "context_window": 1048576},
    {"provider": "DeepSeek", "model": "deepseek-v4-flash", "input_price": 0.10, "output_price": 0.20, "context_window": 1048576},
    # Google
    {"provider": "Google", "model": "gemini-2.0-flash", "input_price": 0.10, "output_price": 0.40, "context_window": 1000000},
    {"provider": "Google", "model": "gemini-2.0-pro", "input_price": 1.25, "output_price": 10.00, "context_window": 2000000},
    {"provider": "Google", "model": "gemini-1.5-pro", "input_price": 1.25, "output_price": 5.00, "context_window": 2000000},
    # Mistral
    {"provider": "Mistral", "model": "mistral-large", "input_price": 2.00, "output_price": 6.00, "context_window": 128000},
    {"provider": "Mistral", "model": "mistral-small", "input_price": 0.10, "output_price": 0.30, "context_window": 128000},
    {"provider": "Mistral", "model": "codestral", "input_price": 0.30, "output_price": 0.90, "context_window": 256000},
    # Meta (via cloud providers)
    {"provider": "Meta", "model": "llama-3.3-70b", "input_price": 0.59, "output_price": 0.79, "context_window": 128000},
    {"provider": "Meta", "model": "llama-3.1-405b", "input_price": 3.00, "output_price": 3.00, "context_window": 128000},
    {"provider": "Meta", "model": "llama-3.1-8b", "input_price": 0.05, "output_price": 0.08, "context_window": 128000},
    # Qwen (千问)
    {"provider": "Qwen", "model": "qwen3.7-max", "input_price": 1.48, "output_price": 4.43, "context_window": 1000000},
    {"provider": "Qwen", "model": "qwen3.7-plus", "input_price": 0.32, "output_price": 1.28, "context_window": 1000000},
    {"provider": "Qwen", "model": "qwen3.6-max-preview", "input_price": 1.04, "output_price": 6.24, "context_window": 262144},
    {"provider": "Qwen", "model": "qwen3.6-plus", "input_price": 0.33, "output_price": 1.95, "context_window": 1000000},
    {"provider": "Qwen", "model": "qwen3.6-flash", "input_price": 0.19, "output_price": 1.13, "context_window": 1000000},
]

# Mutable state for live pricing
_live_data: list[dict] = []
_updated_at: str = datetime.now(timezone.utc).isoformat()
_source: str = "static"
_history: dict[tuple[str, str], list[dict]] = {}
_history_window = timedelta(days=7)
_history_max_points = 1008
_slug_re = re.compile(r"[^a-z0-9]+")


def _slugify(value: str) -> str:
    slug = _slug_re.sub("-", value.lower()).strip("-")
    return slug or "model"


def _build_slug_index(data: list[dict]) -> dict[tuple[str, str], str]:
    counts: dict[str, int] = {}
    for entry in data:
        base = _slugify(entry["model"])
        counts[base] = counts.get(base, 0) + 1

    index: dict[tuple[str, str], str] = {}
    for entry in data:
        base = _slugify(entry["model"])
        if counts[base] == 1:
            slug = base
        else:
            slug = f"{_slugify(entry['provider'])}-{base}"
        index[(entry["provider"], entry["model"])] = slug
    return index


def _prune_history(points: list[dict], now: datetime) -> list[dict]:
    cutoff = now - _history_window
    kept = []
    for point in points:
        ts = point.get("_ts")
        if ts and ts >= cutoff:
            kept.append(point)
    if len(kept) > _history_max_points:
        kept = kept[-_history_max_points:]
    return kept


def update_prices(new_data: list[dict], record_history: bool = False) -> None:
    global _live_data, _updated_at, _source, _history
    _live_data = new_data
    now = datetime.now(timezone.utc)
    _updated_at = now.isoformat()
    _source = "live"
    if record_history:
        for entry in new_data:
            key = (entry["provider"], entry["model"])
            series = _history.get(key, [])
            series.append(
                {
                    "_ts": now,
                    "timestamp": now.isoformat(),
                    "input_price": entry["input_price"],
                    "output_price": entry["output_price"],
                }
            )
            _history[key] = _prune_history(series, now)
        for key, series in list(_history.items()):
            trimmed = _prune_history(series, now)
            if trimmed:
                _history[key] = trimmed
            else:
                _history.pop(key, None)


def get_prices(provider: Optional[str] = None) -> list[dict]:
    all_data = _live_data if _live_data else PRICING_DATA
    data = all_data
    if provider:
        data = [m for m in data if m["provider"].lower() == provider.lower()]
    slug_index = _build_slug_index(all_data)
    return [
        {
            "updated_at": _updated_at,
            "source": _source,
            "slug": slug_index[(entry["provider"], entry["model"])],
            **entry,
        }
        for entry in data
    ]


def get_status() -> dict:
    return {
        "source": _source,
        "updated_at": _updated_at,
        "model_count": len(_live_data) if _live_data else len(PRICING_DATA),
    }


def record_current_history() -> None:
    """用当前数据（live 或 static 兜底）记录一个历史快照，即使没有新的 API 数据。"""
    global _history
    data = _live_data if _live_data else PRICING_DATA
    now = datetime.now(timezone.utc)
    for entry in data:
        key = (entry["provider"], entry["model"])
        series = _history.get(key, [])
        series.append(
            {
                "_ts": now,
                "timestamp": now.isoformat(),
                "input_price": entry["input_price"],
                "output_price": entry["output_price"],
            }
        )
        _history[key] = _prune_history(series, now)


def get_history(provider: str, model: str) -> list[dict]:
    key = (provider, model)
    series = _history.get(key, [])
    if series:
        now = datetime.now(timezone.utc)
        trimmed = _prune_history(series, now)
        if trimmed:
            _history[key] = trimmed
            series = trimmed
        else:
            _history.pop(key, None)
            series = []
    return [
        {
            "timestamp": point["timestamp"],
            "input_price": point["input_price"],
            "output_price": point["output_price"],
        }
        for point in series
    ]


def get_history_by_slug(slug: str) -> dict | None:
    data = _live_data if _live_data else PRICING_DATA
    slug_index = _build_slug_index(data)
    slug_map = {value: key for key, value in slug_index.items()}
    match = slug_map.get(slug)
    if not match:
        return None
    provider, model = match
    return {
        "provider": provider,
        "model": model,
        "history": get_history(provider, model),
    }


def save_history(data_dir: str) -> None:
    os.makedirs(data_dir, exist_ok=True)
    path = os.path.join(data_dir, "price_history.json")
    serializable = {}
    for (provider, model), points in _history.items():
        key = f"{provider}|{model}"
        serializable[key] = [
            {
                "timestamp": p["timestamp"],
                "input_price": p["input_price"],
                "output_price": p["output_price"],
            }
            for p in points
        ]
    tmp_path = path + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(serializable, f)
    os.replace(tmp_path, path)


def load_history(data_dir: str) -> None:
    global _history
    path = os.path.join(data_dir, "price_history.json")
    if not os.path.exists(path):
        return
    try:
        with open(path) as f:
            raw = json.load(f)
    except (json.JSONDecodeError, OSError):
        return
    now = datetime.now(timezone.utc)
    for key, points in raw.items():
        parts = key.split("|", 1)
        if len(parts) != 2:
            continue
        provider, model = parts
        restored = []
        for p in points:
            try:
                ts = datetime.fromisoformat(p["timestamp"])
                restored.append({
                    "_ts": ts,
                    "timestamp": p["timestamp"],
                    "input_price": p["input_price"],
                    "output_price": p["output_price"],
                })
            except (KeyError, ValueError):
                continue
        restored = _prune_history(restored, now)
        if restored:
            _history[(provider, model)] = restored
