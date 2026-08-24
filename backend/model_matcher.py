"""
跨平台模型名称匹配器。

不同平台对同一模型的命名可能不同（如 OpenRouter 用 deepseek-chat，
云雾用 deepseek-v3），本模块将它们归一化到同一个规范名称 (canonical)，
使得前端可以将同一模型在不同平台的价格并排展示。
"""

import re


# 手动维护的别名映射：(供应商, 原始模型名) → 规范名称
MANUAL_ALIASES: dict[tuple[str, str], str] = {
    ("DeepSeek", "deepseek-reasoner"): "deepseek-r1",
    ("DeepSeek", "deepseek-v3"): "deepseek-chat",
    ("DeepSeek", "deepseek-v3.1"): "deepseek-chat-v3.1",
    ("DeepSeek", "deepseek-v3-1"): "deepseek-chat-v3.1",
    ("DeepSeek", "deepseek-v3-0324"): "deepseek-chat-v3-0324",
    ("DeepSeek", "deepseek-v3-250324"): "deepseek-chat-v3-0324",
}


def normalize_model_name(name: str) -> str:
    """规范化模型名称：去除日期后缀、统一分隔符、移除 -instruct 等变体标记。"""
    s = name
    s = re.sub(r"-\d{4}-\d{2}-\d{2}$", "", s)
    s = re.sub(r"-\d{8}$", "", s)
    s = re.sub(r"-\d{6}$", "", s)
    s = re.sub(r"-\d{2}-\d{2}$", "", s)
    s = re.sub(r"-\d{4}$", "", s)
    s = re.sub(r"(\d)-(\d)", r"\1.\2", s)
    s = re.sub(r"-instruct$", "", s)
    s = re.sub(r"-think$", "-thinking", s)
    return s


def _canonical(provider: str, model: str) -> str:
    """获取模型的规范名称：先查手动别名，再执行自动规范化。"""
    aliased = MANUAL_ALIASES.get((provider, model), model)
    normalized = normalize_model_name(aliased)
    if aliased == model:
        aliased2 = MANUAL_ALIASES.get((provider, normalized), normalized)
        if aliased2 != normalized:
            return normalize_model_name(aliased2)
    return normalized


def build_alias_map(
    or_models: list[dict], yw_models: list[dict],
    lt_models: list[dict] | None = None,
    my_models: list[dict] | None = None,
) -> dict[tuple[str, str], dict[str, str]]:
    """
    构建跨平台模型别名映射。

    将各平台的模型按 (供应商, 规范名) 分组，
    对同时出现在多个平台的模型，建立多向映射（每个平台取最短名称作为代表）。
    """
    index: dict[tuple[str, str], dict[str, list[str]]] = {}

    for m in or_models:
        prov = m["provider"]
        norm = _canonical(prov, m["model"])
        index.setdefault((prov, norm), {}).setdefault("openrouter", []).append(
            m["model"]
        )

    for m in yw_models:
        prov = m["provider"]
        norm = _canonical(prov, m["model"])
        index.setdefault((prov, norm), {}).setdefault("yunwu", []).append(m["model"])

    if lt_models:
        for m in lt_models:
            prov = m["provider"]
            norm = _canonical(prov, m["model"])
            index.setdefault((prov, norm), {}).setdefault("official", []).append(
                m["model"]
            )

    if my_models:
        for m in my_models:
            prov = m["provider"]
            norm = _canonical(prov, m["model"])
            index.setdefault((prov, norm), {}).setdefault("moyu", []).append(
                m["model"]
            )

    alias_map: dict[tuple[str, str], dict[str, str]] = {}
    for (_prov, _norm), plat_names in index.items():
        if len(plat_names) < 2:
            continue
        best: dict[str, str] = {}
        for plat, names in plat_names.items():
            best[plat] = min(names, key=len)
        for names in plat_names.values():
            for name in names:
                alias_map[(_prov, name)] = best

    return alias_map
