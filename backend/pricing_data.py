import re
from datetime import datetime, timezone
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


def _rebuild_alias_map() -> None:
    global _alias_map
    or_data = _live_data if _live_data else PRICING_DATA
    _alias_map = build_alias_map(or_data, _yunwu_data)


def update_prices(new_data: list[dict]) -> None:
    global _live_data, _updated_at, _source
    _live_data = new_data
    now = datetime.now(timezone.utc)
    _updated_at = now.isoformat()
    _source = "live"
    _rebuild_alias_map()


def update_yunwu_prices(new_data: list[dict]) -> None:
    global _yunwu_data, _yunwu_updated_at, _yunwu_source
    _yunwu_data = new_data
    now = datetime.now(timezone.utc)
    _yunwu_updated_at = now.isoformat()
    _yunwu_source = "live"
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


async def get_history(provider: str, model: str, platform: Optional[str] = None) -> dict:
    from database import query_history, is_available

    if not is_available():
        return {}

    target_canon = _canonical(provider, model)
    all_models = {model}
    for entry in (_live_data if _live_data else PRICING_DATA) + _yunwu_data:
        if entry["provider"] == provider and _canonical(provider, entry["model"]) == target_canon:
            all_models.add(entry["model"])

    merged: dict[str, list[dict]] = {}
    for m in all_models:
        partial = await query_history(provider, m, platform)
        for plat, points in partial.items():
            merged.setdefault(plat, []).extend(points)

    result: dict[str, list[dict]] = {}
    for plat, points in merged.items():
        seen: set[str] = set()
        unique = []
        points.sort(key=lambda p: p["timestamp"])
        for p in points:
            if p["timestamp"] not in seen:
                seen.add(p["timestamp"])
                unique.append(p)
        if unique:
            result[plat] = unique

    return result


async def get_history_by_slug(slug: str) -> dict | None:
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
        "history": await get_history(provider, model),
    }
