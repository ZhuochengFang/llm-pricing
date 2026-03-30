import httpx
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

OPENROUTER_API = "https://openrouter.ai/api/v1/models"

PROVIDER_MAP = {
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "google": "Google",
    "deepseek": "DeepSeek",
    "mistralai": "Mistral",
    "mistral": "Mistral",
    "meta-llama": "Meta",
    "meta": "Meta",
}


def _parse_model(entry: dict) -> dict | None:
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
    """Fetch live pricing from OpenRouter. Returns list of model dicts or empty list on failure."""
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
