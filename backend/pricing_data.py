from datetime import datetime, timezone
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
]

# Mutable state for live pricing
_live_data: list[dict] = []
_updated_at: str = datetime.now(timezone.utc).isoformat()
_source: str = "static"


def update_prices(new_data: list[dict]) -> None:
    global _live_data, _updated_at, _source
    _live_data = new_data
    _updated_at = datetime.now(timezone.utc).isoformat()
    _source = "live"


def get_prices(provider: Optional[str] = None) -> list[dict]:
    data = _live_data if _live_data else PRICING_DATA
    if provider:
        data = [m for m in data if m["provider"].lower() == provider.lower()]
    return [{"updated_at": _updated_at, "source": _source, **entry} for entry in data]


def get_status() -> dict:
    return {
        "source": _source,
        "updated_at": _updated_at,
        "model_count": len(_live_data) if _live_data else len(PRICING_DATA),
    }
