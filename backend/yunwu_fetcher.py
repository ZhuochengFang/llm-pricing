"""
云雾 AI 平台 (yunwu.ai) 价格抓取器。

从云雾 API 拉取模型定价数据，通过正则匹配识别供应商，
将 one-api/new-api 体系的 model_ratio 换算为 $/1M tokens。
"""

import os
import re
import time
import traceback
import httpx
import logging

logger = logging.getLogger(__name__)

YUNWU_API = "https://yunwu.ai/api/pricing"
YUNWU_PROXY = os.environ.get("YUNWU_PROXY", "")

# 根据模型名前缀识别供应商的正则规则
PROVIDER_PATTERNS = [
    (re.compile(r"^(gpt-|o[1-9]-|o[1-9]$|chatgpt-)"), "OpenAI"),
    (re.compile(r"^claude-"), "Anthropic"),
    (re.compile(r"^gemini-"), "Google"),
    (re.compile(r"^deepseek-"), "DeepSeek"),
    (re.compile(r"^(mistral-|codestral|pixtral|ministral)"), "Mistral"),
    (re.compile(r"^(llama-|meta-)"), "Meta"),
    (re.compile(r"^qwen"), "Qwen"),
    (re.compile(r"^grok-"), "Grok"),
    (re.compile(r"^(minimax-|abab-)"), "MiniMax"),
    (re.compile(r"^(doubao-|Doubao-)"), "ByteDance"),
    (re.compile(r"^jimeng-"), "Jimeng"),
    (re.compile(r"^(glm-|chatglm-)"), "Zhipu"),
]

# one-api/new-api 体系中 model_ratio=1 约等于 $2/1M 输入 tokens
BASE_RATE_PER_MILLION = 2.0


def _detect_provider(model_name: str) -> str | None:
    """根据模型名前缀匹配供应商，无法识别时返回 None。"""
    for pattern, provider in PROVIDER_PATTERNS:
        if pattern.search(model_name):
            return provider
    return None


_TYPE_MAP = {
    "chat": "text", "text": "text", "文本": "text",
    "图像": "image",
    "音视频": "video",
}


def _parse_model(entry: dict) -> dict | None:
    """解析单个云雾模型条目：过滤不可用模型，根据 quota_type 计算价格。"""
    model_name = entry.get("model_name", "")
    if not model_name or not entry.get("available", False):
        return None

    raw_type = entry.get("model_type", "")
    model_type = _TYPE_MAP.get(raw_type)
    if not model_type:
        return None

    provider = _detect_provider(model_name)
    if not provider:
        return None

    model_ratio = entry.get("model_ratio", 0)
    completion_ratio = entry.get("completion_ratio", 1)
    quota_type = entry.get("quota_type", 0)

    if quota_type == 0:
        if model_ratio <= 0:
            return None
        input_price = round(model_ratio * BASE_RATE_PER_MILLION, 2)
        output_price = round(model_ratio * completion_ratio * BASE_RATE_PER_MILLION, 2)
    else:
        model_price = entry.get("model_price", 0)
        if model_price <= 0:
            return None
        input_price = round(model_price, 2)
        output_price = round(model_price * completion_ratio, 2)

    return {
        "provider": provider,
        "model": model_name,
        "input_price": input_price,
        "output_price": output_price,
        "context_window": 0,
        "model_type": model_type,
    }


async def fetch_yunwu_prices() -> list[dict]:
    """从云雾 AI 平台拉取实时定价，按 (供应商, 模型名) 去重后返回。"""
    start = time.monotonic()
    proxy = YUNWU_PROXY or None
    try:
        async with httpx.AsyncClient(timeout=30, proxy=proxy) as client:
            resp = await client.get(YUNWU_API)
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
            logger.info("Fetched %d models from Yunwu (%.1fs)", len(models), elapsed)
            return models
        else:
            logger.warning("Yunwu returned data (%d raw entries) but no usable models after filtering (%.1fs)",
                           len(data), elapsed)
            return []
    except httpx.HTTPStatusError as e:
        elapsed = time.monotonic() - start
        body_preview = e.response.text[:500] if e.response else "(no response body)"
        logger.error("Yunwu HTTP error %s for %s (%.1fs)\nResponse body: %s",
                     e.response.status_code, YUNWU_API, elapsed, body_preview)
        return []
    except httpx.ConnectError as e:
        elapsed = time.monotonic() - start
        logger.error("Yunwu connection failed for %s (%.1fs): %s\n%s",
                     YUNWU_API, elapsed, e, traceback.format_exc())
        return []
    except httpx.TimeoutException as e:
        elapsed = time.monotonic() - start
        logger.error("Yunwu request timed out for %s (%.1fs): %s",
                     YUNWU_API, elapsed, e)
        return []
    except Exception as e:
        elapsed = time.monotonic() - start
        logger.error("Yunwu unexpected error for %s (%.1fs): %s\n%s",
                     YUNWU_API, elapsed, e, traceback.format_exc())
        return []
