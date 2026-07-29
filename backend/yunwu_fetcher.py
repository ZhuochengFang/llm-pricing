"""
云雾 AI 平台 (yunwu.ai) 价格抓取器。

从云雾 API 拉取模型定价数据，通过正则匹配识别供应商，
将 one-api/new-api 体系的 model_ratio 换算为 $/1M tokens。
"""

import re
import httpx
import logging

logger = logging.getLogger(__name__)

YUNWU_API = "https://yunwu.ai/api/pricing"

# 根据模型名前缀识别供应商的正则规则
PROVIDER_PATTERNS = [
    (re.compile(r"^(gpt-|o[1-9]-|o[1-9]$|chatgpt-)"), "OpenAI"),
    (re.compile(r"^claude-"), "Anthropic"),
    (re.compile(r"^gemini-"), "Google"),
    (re.compile(r"^deepseek-"), "DeepSeek"),
    (re.compile(r"^(mistral-|codestral|pixtral|ministral)"), "Mistral"),
    (re.compile(r"^(llama-|meta-)"), "Meta"),
    (re.compile(r"^qwen"), "Qwen"),
]

# one-api/new-api 体系中 model_ratio=1 约等于 $2/1M 输入 tokens
BASE_RATE_PER_MILLION = 2.0


def _detect_provider(model_name: str) -> str | None:
    """根据模型名前缀匹配供应商，无法识别时返回 None。"""
    for pattern, provider in PROVIDER_PATTERNS:
        if pattern.search(model_name):
            return provider
    return None


def _parse_model(entry: dict) -> dict | None:
    """解析单个云雾模型条目：过滤不可用/非文本模型，根据 quota_type 计算价格。"""
    model_name = entry.get("model_name", "")
    if not model_name or not entry.get("available", False):
        return None

    model_type = entry.get("model_type", "")
    if model_type not in ("chat", "text", "文本"):
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
    }


async def fetch_yunwu_prices() -> list[dict]:
    """从云雾 AI 平台拉取实时定价，按 (供应商, 模型名) 去重后返回。"""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(YUNWU_API)
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
            logger.info("Fetched %d models from Yunwu", len(models))
            return models
        else:
            logger.warning("Yunwu returned no usable models")
            return []
    except Exception as e:
        logger.error("Failed to fetch from Yunwu: %s", e)
        return []
