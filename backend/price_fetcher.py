"""
OpenRouter 价格抓取器。

从 OpenRouter API (openrouter.ai/api/v1/models) 拉取所有模型数据，
通过 PROVIDER_MAP 过滤已知厂商，将价格归一化为 $/1M tokens。
"""

import time
import traceback
import httpx
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

OPENROUTER_API = "https://openrouter.ai/api/v1/models"

# OpenRouter 模型 ID 前缀 → 显示用供应商名
PROVIDER_MAP = {
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "google": "Google",
    "deepseek": "DeepSeek",
    "mistralai": "Mistral",
    "mistral": "Mistral",
    "meta-llama": "Meta",
    "meta": "Meta",
    "qwen": "Qwen",
    "x-ai": "Grok",
    "minimax": "MiniMax",
    "bytedance": "ByteDance",
    "bytedance-seed": "ByteDance",
    "z-ai": "Zhipu",
}


def _detect_model_type(entry: dict) -> str:
    """根据 architecture.output_modalities 判断模型类型。"""
    out_mods = entry.get("architecture", {}).get("output_modalities", [])
    if "image" in out_mods:
        return "image"
    if "audio" in out_mods:
        return "video"
    return "text"


def _parse_model(entry: dict) -> dict | None:
    """解析单个 OpenRouter 模型条目，跳过免费/nitro/floor 变体（含 ':' 的模型名）。"""
    model_id = entry.get("id", "")
    parts = model_id.split("/", 1)
    if len(parts) != 2:
        return None

    slug, model_name = parts

    # Skip free/nitro/floor variants
    if ":" in model_name:
        return None

    provider = PROVIDER_MAP.get(slug.lower())
    if not provider:
        return None

    pricing = entry.get("pricing", {})
    prompt_price = pricing.get("prompt")
    completion_price = pricing.get("completion")
    if prompt_price is None or completion_price is None:
        return None

    try:
        input_per_million = float(prompt_price) * 1_000_000
        output_per_million = float(completion_price) * 1_000_000
    except (ValueError, TypeError):
        return None

    context_window = entry.get("context_length", 0)
    if not context_window:
        return None

    return {
        "provider": provider,
        "model": model_name,
        "input_price": round(input_per_million, 2),
        "output_price": round(output_per_million, 2),
        "context_window": context_window,
        "model_type": _detect_model_type(entry),
    }


async def fetch_prices() -> list[dict]:
    """从 OpenRouter 拉取实时定价，按 (供应商, 模型名) 去重后返回。"""
    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(OPENROUTER_API)
            elapsed = time.monotonic() - start
            resp.raise_for_status()
            data = resp.json().get("data", [])

        models = []
        seen = set()
        for entry in data:
            parsed = _parse_model(entry)
            if parsed:
                key = (parsed["provider"], parsed["model"])
                if key not in seen:
                    seen.add(key)
                    models.append(parsed)

        if models:
            logger.info("Fetched %d models from OpenRouter (%.1fs)", len(models), elapsed)
            return models
        else:
            logger.warning("OpenRouter returned data (%d raw entries) but no usable models after filtering (%.1fs)",
                           len(data), elapsed)
            return []
    except httpx.HTTPStatusError as e:
        elapsed = time.monotonic() - start
        body_preview = e.response.text[:500] if e.response else "(no response body)"
        logger.error("OpenRouter HTTP error %s for %s (%.1fs)\nResponse body: %s",
                     e.response.status_code, OPENROUTER_API, elapsed, body_preview)
        return []
    except httpx.ConnectError as e:
        elapsed = time.monotonic() - start
        logger.error("OpenRouter connection failed for %s (%.1fs): %s\n%s",
                     OPENROUTER_API, elapsed, e, traceback.format_exc())
        return []
    except httpx.TimeoutException as e:
        elapsed = time.monotonic() - start
        logger.error("OpenRouter request timed out for %s (%.1fs): %s",
                     OPENROUTER_API, elapsed, e)
        return []
    except Exception as e:
        elapsed = time.monotonic() - start
        logger.error("OpenRouter unexpected error for %s (%.1fs): %s\n%s",
                     OPENROUTER_API, elapsed, e, traceback.format_exc())
        return []
