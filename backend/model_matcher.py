import re


MANUAL_ALIASES: dict[tuple[str, str], str] = {
    ("DeepSeek", "deepseek-reasoner"): "deepseek-r1",
    ("DeepSeek", "deepseek-v3"): "deepseek-chat",
    ("DeepSeek", "deepseek-v3.1"): "deepseek-chat-v3.1",
    ("DeepSeek", "deepseek-v3-1"): "deepseek-chat-v3.1",
    ("DeepSeek", "deepseek-v3-0324"): "deepseek-chat-v3-0324",
    ("DeepSeek", "deepseek-v3-250324"): "deepseek-chat-v3-0324",
}


def normalize_model_name(name: str) -> str:
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
    aliased = MANUAL_ALIASES.get((provider, model), model)
    normalized = normalize_model_name(aliased)
    if aliased == model:
        aliased2 = MANUAL_ALIASES.get((provider, normalized), normalized)
        if aliased2 != normalized:
            return normalize_model_name(aliased2)
    return normalized


def build_alias_map(
    or_models: list[dict], yw_models: list[dict]
) -> dict[tuple[str, str], dict[str, str]]:
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
