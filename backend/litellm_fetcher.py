"""
LiteLLM 官方定价抓取器。

从 LiteLLM 社区维护的定价数据库拉取各厂商官方 API 定价，
作为 "Official" 平台数据源提供厂商直接定价参考（¥/1M tokens）。
"""

import os
import re
import time
import traceback
import httpx
import logging

logger = logging.getLogger(__name__)

LITELLM_URL = (
    "https://raw.githubusercontent.com/BerriAI/litellm/main/"
    "model_prices_and_context_window.json"
)
LITELLM_PROXY = os.environ.get("LITELLM_PROXY", "")
USD_TO_CNY = 7.13

PROVIDER_MAP = {
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "gemini": "Google",
    "deepseek": "DeepSeek",
    "mistral": "Mistral",
    "xai": "Grok",
    "minimax": "MiniMax",
    "dashscope": "Qwen",
    "zai": "Zhipu",
}

_KNOWN_PREFIXES = {
    "gemini", "deepseek", "mistral", "xai", "minimax", "dashscope", "zai",
    "openai", "anthropic",
}

MODE_MAP = {
    "chat": "text",
    "completion": "text",
    "responses": "text",
    "image_generation": "image",
}

_RESOLUTION_RE = re.compile(r"^\d+-x-\d+/|^(low|medium|high|standard|hd)/")
_FT_PREFIX = "ft:"


def _parse_model(key: str, entry: dict) -> dict | None:
    if key == "sample_spec":
        return None
    if key.startswith(_FT_PREFIX):
        return None
    if _RESOLUTION_RE.match(key):
        return None

    litellm_provider = entry.get("litellm_provider", "")
    provider = PROVIDER_MAP.get(litellm_provider)
    if not provider:
        return None

    mode = entry.get("mode", "")
    model_type = MODE_MAP.get(mode)
    if not model_type:
        return None

    input_cost = entry.get("input_cost_per_token")
    output_cost = entry.get("output_cost_per_token")
    if not input_cost or input_cost <= 0:
        return None
    if output_cost is None:
        output_cost = 0

    model_name = key
    if "/" in key:
        prefix, rest = key.split("/", 1)
        if prefix in _KNOWN_PREFIXES:
            model_name = rest

    context_window = entry.get("max_input_tokens") or entry.get("max_tokens") or 0

    return {
        "provider": provider,
        "model": model_name,
        "input_price": round(float(input_cost) * 1_000_000 * USD_TO_CNY, 2),
        "output_price": round(float(output_cost) * 1_000_000 * USD_TO_CNY, 2),
        "context_window": context_window,
        "model_type": model_type,
    }


async def fetch_litellm_prices() -> list[dict]:
    start = time.monotonic()
    proxy = LITELLM_PROXY or os.environ.get("HTTPS_PROXY") or None
    try:
        async with httpx.AsyncClient(timeout=60, proxy=proxy) as client:
            resp = await client.get(LITELLM_URL)
            elapsed = time.monotonic() - start
            resp.raise_for_status()
            data = resp.json()

        models = []
        seen: dict[tuple[str, str], int] = {}
        for key, entry in data.items():
            if not isinstance(entry, dict):
                continue
            parsed = _parse_model(key, entry)
            if not parsed:
                continue
            dedup_key = (parsed["provider"], parsed["model"])
            if dedup_key in seen:
                continue
            seen[dedup_key] = len(models)
            models.append(parsed)

        if models:
            logger.info("Fetched %d models from LiteLLM (%.1fs)", len(models), elapsed)
            return models
        else:
            logger.warning("LiteLLM returned data but no usable models after filtering (%.1fs)", elapsed)
            return []
    except httpx.HTTPStatusError as e:
        elapsed = time.monotonic() - start
        body_preview = e.response.text[:500] if e.response else "(no response body)"
        logger.error("LiteLLM HTTP error %s for %s (%.1fs)\nResponse body: %s",
                     e.response.status_code, LITELLM_URL, elapsed, body_preview)
        return []
    except httpx.ConnectError as e:
        elapsed = time.monotonic() - start
        logger.error("LiteLLM connection failed for %s (%.1fs): %s\n%s",
                     LITELLM_URL, elapsed, e, traceback.format_exc())
        return []
    except httpx.TimeoutException as e:
        elapsed = time.monotonic() - start
        logger.error("LiteLLM request timed out for %s (%.1fs): %s",
                     LITELLM_URL, elapsed, e)
        return []
    except Exception as e:
        elapsed = time.monotonic() - start
        logger.error("LiteLLM unexpected error for %s (%.1fs): %s\n%s",
                     LITELLM_URL, elapsed, e, traceback.format_exc())
        return []
