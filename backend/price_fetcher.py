"""
OpenRouter 价格抓取器。

从 OpenRouter API (openrouter.ai/api/v1/models) 拉取所有模型数据，
通过 PROVIDER_MAP 过滤已知厂商，将价格归一化为 $/1M tokens。
"""

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
}


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
    }


async def fetch_prices() -> list[dict]:
    """从 OpenRouter 拉取实时定价，按 (供应商, 模型名) 去重后返回。"""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(OPENROUTER_API)
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
            logger.info("Fetched %d models from OpenRouter", len(models))
            return models
        else:
            logger.warning("OpenRouter returned no usable models")
            return []
    except Exception as e:
        logger.error("Failed to fetch from OpenRouter: %s", e)
        return []
