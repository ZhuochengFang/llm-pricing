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

PRICE_HISTORY = [
    # OpenAI
    {"provider": "OpenAI", "model": "gpt-4o", "history": [
        {"date": "2024-05-13", "input_price": 5.00, "output_price": 15.00},
        {"date": "2024-10-02", "input_price": 2.50, "output_price": 10.00},
    ]},
    {"provider": "OpenAI", "model": "gpt-4o-mini", "history": [
        {"date": "2024-07-18", "input_price": 0.15, "output_price": 0.60},
    ]},
    {"provider": "OpenAI", "model": "gpt-4-turbo", "history": [
        {"date": "2024-04-09", "input_price": 10.00, "output_price": 30.00},
    ]},
    {"provider": "OpenAI", "model": "o1", "history": [
        {"date": "2024-12-17", "input_price": 15.00, "output_price": 60.00},
    ]},
    {"provider": "OpenAI", "model": "o1-mini", "history": [
        {"date": "2024-09-12", "input_price": 3.00, "output_price": 12.00},
    ]},
    {"provider": "OpenAI", "model": "o3-mini", "history": [
        {"date": "2025-01-31", "input_price": 1.10, "output_price": 4.40},
    ]},
    # Anthropic
    {"provider": "Anthropic", "model": "claude-opus-4", "history": [
        {"date": "2024-03-04", "input_price": 15.00, "output_price": 75.00},
    ]},
    {"provider": "Anthropic", "model": "claude-sonnet-4", "history": [
        {"date": "2024-06-20", "input_price": 3.00, "output_price": 15.00},
        {"date": "2024-10-22", "input_price": 3.00, "output_price": 15.00},
    ]},
    {"provider": "Anthropic", "model": "claude-haiku-3.5", "history": [
        {"date": "2024-10-22", "input_price": 1.00, "output_price": 5.00},
        {"date": "2025-02-24", "input_price": 0.80, "output_price": 4.00},
    ]},
    # DeepSeek
    {"provider": "DeepSeek", "model": "deepseek-v3", "history": [
        {"date": "2024-12-26", "input_price": 0.27, "output_price": 1.10},
    ]},
    {"provider": "DeepSeek", "model": "deepseek-r1", "history": [
        {"date": "2025-01-20", "input_price": 0.55, "output_price": 2.19},
    ]},
    # Google
    {"provider": "Google", "model": "gemini-2.0-flash", "history": [
        {"date": "2025-02-05", "input_price": 0.10, "output_price": 0.40},
    ]},
    {"provider": "Google", "model": "gemini-2.0-pro", "history": [
        {"date": "2025-03-25", "input_price": 1.25, "output_price": 10.00},
    ]},
    {"provider": "Google", "model": "gemini-1.5-pro", "history": [
        {"date": "2024-05-14", "input_price": 3.50, "output_price": 10.50},
        {"date": "2024-10-01", "input_price": 1.25, "output_price": 5.00},
    ]},
    # Mistral
    {"provider": "Mistral", "model": "mistral-large", "history": [
        {"date": "2024-02-26", "input_price": 4.00, "output_price": 12.00},
        {"date": "2024-07-24", "input_price": 2.00, "output_price": 6.00},
    ]},
    {"provider": "Mistral", "model": "mistral-small", "history": [
        {"date": "2024-09-18", "input_price": 0.20, "output_price": 0.60},
        {"date": "2025-01-30", "input_price": 0.10, "output_price": 0.30},
    ]},
    {"provider": "Mistral", "model": "codestral", "history": [
        {"date": "2024-05-29", "input_price": 0.30, "output_price": 0.90},
    ]},
    # Meta
    {"provider": "Meta", "model": "llama-3.3-70b", "history": [
        {"date": "2024-12-06", "input_price": 0.59, "output_price": 0.79},
    ]},
    {"provider": "Meta", "model": "llama-3.1-405b", "history": [
        {"date": "2024-07-23", "input_price": 5.00, "output_price": 5.00},
        {"date": "2024-11-15", "input_price": 3.00, "output_price": 3.00},
    ]},
    {"provider": "Meta", "model": "llama-3.1-8b", "history": [
        {"date": "2024-07-23", "input_price": 0.05, "output_price": 0.08},
    ]},
]

_updated_at = datetime.now(timezone.utc).isoformat()


def get_prices(provider: Optional[str] = None) -> list[dict]:
    data = PRICING_DATA
    if provider:
        data = [m for m in data if m["provider"].lower() == provider.lower()]
    return [{"updated_at": _updated_at, **entry} for entry in data]


def get_price_history(provider: Optional[str] = None, model: Optional[str] = None) -> list[dict]:
    data = PRICE_HISTORY
    if provider:
        data = [m for m in data if m["provider"].lower() == provider.lower()]
    if model:
        data = [m for m in data if m["model"].lower() == model.lower()]
    return data
