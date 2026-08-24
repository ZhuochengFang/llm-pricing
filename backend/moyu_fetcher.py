"""
魔芋平台 (moyu.info) 价格抓取器。

与云雾类似，使用 one-api/new-api 体系的 model_ratio 换算价格（¥/1M tokens）。
区别：API 需要登录认证，供应商通过 vendor_id 映射识别。
"""

import os
import re
import time
import traceback
import httpx
import logging

logger = logging.getLogger(__name__)

MOYU_API_URL = os.environ.get("MOYU_API_URL", "https://uat.moyu.info")
MOYU_USERNAME = os.environ.get("MOYU_USERNAME", "")
MOYU_PASSWORD = os.environ.get("MOYU_PASSWORD", "")
MOYU_PROXY = os.environ.get("MOYU_PROXY", "")

VENDOR_NAME_MAP = {
    "OpenAI": "OpenAI",
    "Anthropic": "Anthropic",
    "Google": "Google",
    "Gemini": "Google",
    "DeepSeek": "DeepSeek",
    "Mistral": "Mistral",
    "Meta": "Meta",
    "阿里巴巴": "Qwen",
    "Qwen": "Qwen",
    "xAI": "Grok",
    "Grok": "Grok",
    "Grok (xAI)": "Grok",
    "MiniMax": "MiniMax",
    "Minimax": "MiniMax",
    "字节跳动": "ByteDance",
    "即梦": "Jimeng",
    "智谱": "Zhipu",
    "小米": "Xiaomi",
    "Moonshot": "Moonshot",
    "月之暗面": "Moonshot",
    "快手": "Kuaishou",
}

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
    (re.compile(r"^kling-"), "Kuaishou"),
    (re.compile(r"^kimi-"), "Moonshot"),
]

_TYPE_MAP = {0: "text", 1: "text", 2: "image", 3: "video"}


_cached_token: str | None = None
_cached_quota_per_unit: int | None = None


def _detect_provider_by_name(model_name: str) -> str | None:
    lower = model_name.lower()
    for pattern, provider in PROVIDER_PATTERNS:
        if pattern.search(lower):
            return provider
    return None


async def _login(proxy: str | None) -> str | None:
    """登录魔芋平台获取 access_token。"""
    global _cached_token
    if not MOYU_USERNAME or not MOYU_PASSWORD:
        logger.error("Moyu credentials not configured (MOYU_USERNAME / MOYU_PASSWORD)")
        return None
    try:
        async with httpx.AsyncClient(timeout=30, proxy=proxy) as client:
            resp = await client.post(
                f"{MOYU_API_URL}/api/user/login",
                json={"username": MOYU_USERNAME, "password": MOYU_PASSWORD},
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("success") and data.get("data", {}).get("access_token"):
                _cached_token = data["data"]["access_token"]
                logger.info("Moyu login successful (user: %s)", MOYU_USERNAME)
                return _cached_token
            logger.error("Moyu login failed: %s", data.get("message", "unknown error"))
            return None
    except Exception as e:
        logger.error("Moyu login error: %s", e)
        return None


async def _fetch_quota_per_unit(proxy: str | None) -> int:
    """从 /api/status 获取 quota_per_unit，用于计算正确的基准费率。"""
    global _cached_quota_per_unit
    if _cached_quota_per_unit is not None:
        return _cached_quota_per_unit
    try:
        async with httpx.AsyncClient(timeout=15, proxy=proxy) as client:
            resp = await client.get(f"{MOYU_API_URL}/api/status")
            resp.raise_for_status()
            data = resp.json().get("data", resp.json())
            qpu = int(data.get("quota_per_unit", 500000))
            if qpu > 0:
                _cached_quota_per_unit = qpu
                logger.info("Moyu quota_per_unit: %d", qpu)
                return qpu
    except Exception as e:
        logger.warning("Failed to fetch Moyu quota_per_unit, using default 500000: %s", e)
    _cached_quota_per_unit = 500000
    return 500000


def _calc_base_rate(quota_per_unit: int) -> float:
    return 1_000_000 / quota_per_unit


def _parse_model(entry: dict, vendor_map: dict[int, str], base_rate: float) -> dict | None:
    model_name = entry.get("model_name", "")
    if not model_name:
        return None

    model_type = _TYPE_MAP.get(entry.get("model_type"))
    if not model_type:
        return None

    vendor_id = entry.get("vendor_id")
    provider = None
    if vendor_id and vendor_id in vendor_map:
        raw_vendor = vendor_map[vendor_id]
        provider = VENDOR_NAME_MAP.get(raw_vendor)
    if not provider:
        provider = _detect_provider_by_name(model_name)
    if not provider:
        return None

    model_ratio = entry.get("model_ratio", 0)
    completion_ratio = entry.get("completion_ratio", 1)
    quota_type = entry.get("quota_type", 0)

    if quota_type == 0:
        if model_ratio <= 0:
            return None
        input_price = round(model_ratio * base_rate, 4)
        output_price = round(model_ratio * completion_ratio * base_rate, 4)
    else:
        model_price = entry.get("model_price", 0)
        if model_price <= 0:
            return None
        input_price = round(model_price * base_rate, 4)
        output_price = round(model_price * completion_ratio * base_rate, 4)

    return {
        "provider": provider,
        "model": model_name.lower(),
        "input_price": input_price,
        "output_price": output_price,
        "context_window": 0,
        "model_type": model_type,
    }


async def fetch_moyu_prices() -> list[dict]:
    """从魔芋平台拉取实时定价，按 (供应商, 模型名) 去重后返回。"""
    global _cached_token
    start = time.monotonic()
    proxy = MOYU_PROXY or None

    try:
        token = _cached_token
        if not token:
            token = await _login(proxy)
            if not token:
                return []

        quota_per_unit = await _fetch_quota_per_unit(proxy)
        base_rate = _calc_base_rate(quota_per_unit)

        async with httpx.AsyncClient(timeout=30, proxy=proxy) as client:
            headers = {"Authorization": f"Bearer {token}"}
            resp = await client.get(f"{MOYU_API_URL}/api/pricing", headers=headers)

            if resp.status_code == 401:
                logger.info("Moyu token expired, re-logging in")
                token = await _login(proxy)
                if not token:
                    return []
                headers = {"Authorization": f"Bearer {token}"}
                resp = await client.get(f"{MOYU_API_URL}/api/pricing", headers=headers)

            elapsed = time.monotonic() - start
            resp.raise_for_status()
            body = resp.json()
            raw_data = body.get("data", [])

            vendor_map: dict[int, str] = {}
            for v in body.get("vendors", []):
                vid = v.get("id")
                vname = v.get("name", "")
                if vid and vname:
                    vendor_map[vid] = vname

        models = []
        seen = set()
        for entry in raw_data:
            parsed = _parse_model(entry, vendor_map, base_rate)
            if parsed:
                key = (parsed["provider"], parsed["model"])
                if key not in seen:
                    seen.add(key)
                    models.append(parsed)

        if models:
            logger.info("Fetched %d models from Moyu (%.1fs)", len(models), elapsed)
            return models
        else:
            logger.warning("Moyu returned data (%d raw entries) but no usable models after filtering (%.1fs)",
                           len(raw_data), elapsed)
            return []
    except httpx.HTTPStatusError as e:
        elapsed = time.monotonic() - start
        body_preview = e.response.text[:500] if e.response else "(no response body)"
        logger.error("Moyu HTTP error %s (%.1fs)\nResponse body: %s",
                     e.response.status_code, elapsed, body_preview)
        return []
    except httpx.ConnectError as e:
        elapsed = time.monotonic() - start
        logger.error("Moyu connection failed (%.1fs): %s\n%s",
                     elapsed, e, traceback.format_exc())
        return []
    except httpx.TimeoutException as e:
        elapsed = time.monotonic() - start
        logger.error("Moyu request timed out (%.1fs): %s", elapsed, e)
        return []
    except Exception as e:
        elapsed = time.monotonic() - start
        logger.error("Moyu unexpected error (%.1fs): %s\n%s",
                     elapsed, e, traceback.format_exc())
        return []
