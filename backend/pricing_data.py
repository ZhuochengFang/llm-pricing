import json
import os
import re
from datetime import datetime, timezone, timedelta
from typing import Optional

from model_matcher import build_alias_map, _canonical

_PROVIDER_ORDER = {
    "OpenAI": 0, "Anthropic": 1, "Google": 2, "DeepSeek": 3,
    "Mistral": 4, "Meta": 5, "Qwen": 6,
}

_PLATFORM_ORDER = {"openrouter": 0, "yunwu": 1}

_version_split_re = re.compile(r"^(.*?[-.]?)(\d+(?:\.\d+)*)([-.].*)?$")


def _extract_version(name: str) -> tuple[str, str, tuple]:
    m = _version_split_re.match(name)
    if m:
        prefix = m.group(1).rstrip("-.")
        version = tuple(float(x) for x in m.group(2).split("."))
        suffix = (m.group(3) or "").lstrip("-.")
    else:
        prefix = name
        version = (0,)
        suffix = ""
    return prefix, suffix, version


def _sort_key(entry: dict) -> tuple:
    provider = entry["provider"]
    platform = entry.get("platform", "openrouter")
    model = entry["model"]
    alias = _alias_map.get((provider, model))
    if alias and "openrouter" in alias:
        canon = _canonical(provider, alias["openrouter"])
    else:
        canon = _canonical(provider, model)
    prefix, suffix, version = _extract_version(canon)
    return (
        _PROVIDER_ORDER.get(provider, 99),
        prefix,
        suffix,
        version,
        _PLATFORM_ORDER.get(platform, 99),
    )


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

PLATFORMS = ("openrouter", "yunwu")

_live_data: list[dict] = []
_yunwu_data: list[dict] = []
_updated_at: str = datetime.now(timezone.utc).isoformat()
_yunwu_updated_at: str = ""
_source: str = "static"
_yunwu_source: str = "none"
_alias_map: dict[tuple[str, str], dict[str, str]] = {}

# History keyed by (platform, provider, model)
_history: dict[tuple[str, str, str], list[dict]] = {}
_history_window = timedelta(days=7)
_history_max_points = 1008
_slug_re = re.compile(r"[^a-z0-9]+")


def _slugify(value: str) -> str:
    slug = _slug_re.sub("-", value.lower()).strip("-")
    return slug or "model"


def _build_slug_index(data: list[dict]) -> dict[tuple[str, str], str]:
    unique_models: dict[tuple[str, str], dict] = {}
    for entry in data:
        key = (entry["provider"], entry["model"])
        if key not in unique_models:
            unique_models[key] = entry

    counts: dict[str, int] = {}
    for entry in unique_models.values():
        base = _slugify(entry["model"])
        counts[base] = counts.get(base, 0) + 1

    index: dict[tuple[str, str], str] = {}
    for (provider, model), entry in unique_models.items():
        base = _slugify(model)
        if counts[base] == 1:
            slug = base
        else:
            slug = f"{_slugify(provider)}-{base}"
        index[(provider, model)] = slug
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


def _record_history_for(data: list[dict], platform: str, now: datetime) -> None:
    global _history
    for entry in data:
        key = (platform, entry["provider"], entry["model"])
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


def _rebuild_alias_map() -> None:
    global _alias_map
    or_data = _live_data if _live_data else PRICING_DATA
    _alias_map = build_alias_map(or_data, _yunwu_data)


def update_prices(new_data: list[dict], record_history: bool = False) -> None:
    global _live_data, _updated_at, _source, _history
    _live_data = new_data
    now = datetime.now(timezone.utc)
    _updated_at = now.isoformat()
    _source = "live"
    if record_history:
        _record_history_for(new_data, "openrouter", now)
        for key, series in list(_history.items()):
            trimmed = _prune_history(series, now)
            if trimmed:
                _history[key] = trimmed
            else:
                _history.pop(key, None)
    _rebuild_alias_map()


def update_yunwu_prices(new_data: list[dict], record_history: bool = False) -> None:
    global _yunwu_data, _yunwu_updated_at, _yunwu_source, _history
    _yunwu_data = new_data
    now = datetime.now(timezone.utc)
    _yunwu_updated_at = now.isoformat()
    _yunwu_source = "live"
    if record_history:
        _record_history_for(new_data, "yunwu", now)
        for key, series in list(_history.items()):
            if key[0] == "yunwu":
                trimmed = _prune_history(series, now)
                if trimmed:
                    _history[key] = trimmed
                else:
                    _history.pop(key, None)
    _rebuild_alias_map()


def get_prices(provider: Optional[str] = None, platform: Optional[str] = None) -> list[dict]:
    or_data = _live_data if _live_data else PRICING_DATA
    or_entries = [{"platform": "openrouter", **e} for e in or_data]
    yw_entries = [{"platform": "yunwu", **e} for e in _yunwu_data]
    all_data = or_entries + yw_entries

    if provider:
        all_data = [m for m in all_data if m["provider"].lower() == provider.lower()]
    if platform:
        all_data = [m for m in all_data if m["platform"].lower() == platform.lower()]

    all_data.sort(key=_sort_key)

    slug_index = _build_slug_index(all_data)

    result = []
    for entry in all_data:
        p = entry["platform"]
        result.append(
            {
                "updated_at": _updated_at if p == "openrouter" else _yunwu_updated_at,
                "source": _source if p == "openrouter" else _yunwu_source,
                "slug": slug_index[(entry["provider"], entry["model"])],
                **entry,
            }
        )
    return result


def get_status() -> dict:
    or_count = len(_live_data) if _live_data else len(PRICING_DATA)
    yw_count = len(_yunwu_data)
    return {
        "source": _source,
        "updated_at": _updated_at,
        "model_count": or_count,
        "yunwu_source": _yunwu_source,
        "yunwu_updated_at": _yunwu_updated_at,
        "yunwu_model_count": yw_count,
    }


def record_current_history() -> None:
    global _history
    data = _live_data if _live_data else PRICING_DATA
    now = datetime.now(timezone.utc)
    _record_history_for(data, "openrouter", now)
    if _yunwu_data:
        _record_history_for(_yunwu_data, "yunwu", now)


def get_history(provider: str, model: str, platform: Optional[str] = None) -> dict:
    """Return history grouped by platform for a given (provider, model).

    Uses canonical name matching to find history recorded under any alias
    of the model, not just the current name.
    """
    now = datetime.now(timezone.utc)
    result: dict[str, list[dict]] = {}
    platforms = [platform] if platform else list(PLATFORMS)
    target_canon = _canonical(provider, model)

    for plat in platforms:
        merged: list[dict] = []
        for (h_plat, h_prov, h_model), series in _history.items():
            if h_plat == plat and h_prov == provider and _canonical(h_prov, h_model) == target_canon:
                merged.extend(series)

        if not merged:
            continue

        merged.sort(key=lambda p: p.get("_ts") or datetime.min.replace(tzinfo=timezone.utc))
        seen_ts: set[str] = set()
        unique: list[dict] = []
        for p in merged:
            ts = p["timestamp"]
            if ts not in seen_ts:
                seen_ts.add(ts)
                unique.append(p)

        trimmed = _prune_history(unique, now)
        if trimmed:
            result[plat] = [
                {
                    "timestamp": p["timestamp"],
                    "input_price": p["input_price"],
                    "output_price": p["output_price"],
                }
                for p in trimmed
            ]
    return result


def get_history_by_slug(slug: str) -> dict | None:
    all_data = (_live_data if _live_data else PRICING_DATA) + _yunwu_data
    slug_index = _build_slug_index(all_data)
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
    for (platform, provider, model), points in _history.items():
        key = f"{platform}|{provider}|{model}"
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
        parts = key.split("|")
        if len(parts) == 3:
            platform, provider, model = parts
        elif len(parts) == 2:
            # Backward compatibility: old format "provider|model" → openrouter
            platform = "openrouter"
            provider, model = parts
        else:
            continue
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
            _history[(platform, provider, model)] = restored
