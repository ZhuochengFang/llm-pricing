import re
import httpx
import logging

logger = logging.getLogger(__name__)

YUNWU_API = "https://yunwu.ai/api/pricing"

PROVIDER_PATTERNS = [
    (re.compile(r"^(gpt-|o[1-9]-|o[1-9]$|chatgpt-)"), "OpenAI"),
    (re.compile(r"^claude-"), "Anthropic"),
    (re.compile(r"^gemini-"), "Google"),
    (re.compile(r"^deepseek-"), "DeepSeek"),
    (re.compile(r"^(mistral-|codestral|pixtral|ministral)"), "Mistral"),
    (re.compile(r"^(llama-|meta-)"), "Meta"),
    (re.compile(r"^qwen"), "Qwen"),
]

# In the one-api/new-api ecosystem: model_ratio=1 ≈ $2/1M input tokens
BASE_RATE_PER_MILLION = 2.0


def _detect_provider(model_name: str) -> str | None:
    for pattern, provider in PROVIDER_PATTERNS:
        if pattern.search(model_name):
            return provider
    return None


def _parse_model(entry: dict) -> dict | None:
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
    """Fetch live pricing from Yunwu. Returns list of model dicts or empty list on failure."""
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
