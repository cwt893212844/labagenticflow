"""Auto-select comparable LLM models from OpenRouter API responses."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

DEFAULT_RULES = Path(__file__).resolve().parent.parent / "data" / "selection_rules.json"


def load_rules(path: Path = DEFAULT_RULES) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _compile(patterns: list[str]) -> re.Pattern[str]:
    return re.compile("|".join(patterns), re.I)


def per_million_usd(price: str | float | int) -> float:
    return round(float(price) * 1_000_000, 6)


def family_key(oid: str) -> tuple[str, str]:
    provider, name = oid.split("/", 1)
    name = re.sub(r":free$", "", name)
    name = re.sub(r"-(fast|high)$", "", name)
    name = re.sub(r"-\d{4}-\d{2}-\d{2}.*$", "", name)
    name = re.sub(r"-\d{2}-\d{2}$", "", name)
    base = re.sub(r"-\d+(?:\.\d+)+$", "", name)
    base = re.sub(r"-\d+$", "", base)
    return provider, base


def version_tuple(oid: str) -> tuple[int, ...]:
    _, name = oid.split("/", 1)
    nums = [tuple(int(x) for x in m.split(".")) for m in re.findall(r"(\d+(?:\.\d+)*)", name)]
    return nums[-1] if nums else (0,)


def slug_id(oid: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", oid.lower()).strip("-")


def display_name(remote: dict[str, Any]) -> str:
    raw = remote.get("name") or remote["id"]
    return re.sub(r"^[A-Za-z0-9+ .]+:\s*", "", raw)


def infer_tags(remote: dict[str, Any]) -> list[str]:
    arch = remote.get("architecture") or {}
    ins = arch.get("input_modalities") or []
    tags: list[str] = []
    if "image" in ins or "file" in ins:
        tags.append("vision")
    params = remote.get("supported_parameters") or []
    if "tools" in params or "tool_choice" in params:
        tags.append("tools")
    return tags


def format_provider_name(provider_key: str, rules: dict[str, Any]) -> str:
    overrides = rules.get("provider_display") or {}
    if provider_key in overrides:
        return overrides[provider_key]

    known = {
        "openai": "OpenAI",
        "anthropic": "Anthropic",
        "google": "Google",
        "deepseek": "DeepSeek",
        "mistralai": "Mistral",
        "meta-llama": "Meta (via API)",
        "x-ai": "xAI",
        "cohere": "Cohere",
        "amazon": "AWS",
        "qwen": "Alibaba",
        "z-ai": "Z.ai",
        "moonshotai": "Moonshot",
        "minimax": "MiniMax",
        "baidu": "Baidu",
        "bytedance": "ByteDance",
        "tencent": "Tencent",
        "perplexity": "Perplexity",
        "microsoft": "Microsoft",
    }
    if provider_key in known:
        return known[provider_key]

    return provider_key.replace("-", " ").title()


def provider_allowed(provider_key: str, rules: dict[str, Any]) -> bool:
    blocked = set(rules.get("blocked_providers") or [])
    if provider_key in blocked or provider_key.startswith("~"):
        return False

    mode = rules.get("provider_mode", "allowlist")
    if mode == "auto":
        return True

    allowed = set(rules.get("allowed_providers") or [])
    return provider_key in allowed


def is_candidate(remote: dict[str, Any], rules: dict[str, Any]) -> bool:
    mid = remote["id"]
    provider_key = mid.split("/", 1)[0]
    if not provider_allowed(provider_key, rules):
        return False

    exclude_id = _compile(rules["exclude_id_patterns"])
    exclude_name = _compile(rules["exclude_name_patterns"])
    legacy = _compile(rules["legacy_id_patterns"])

    if exclude_id.search(mid):
        return False
    if exclude_name.search(remote.get("name", "")):
        return False
    if legacy.search(mid.split("/", 1)[1]):
        return False

    pricing = remote.get("pricing") or {}
    try:
        prompt = float(pricing["prompt"])
        completion = float(pricing["completion"])
    except (KeyError, TypeError, ValueError):
        return False
    if prompt <= 0 or completion <= 0:
        return False

    arch = remote.get("architecture") or {}
    outs = arch.get("output_modalities") or []
    if outs and "text" not in outs:
        return False

    if (remote.get("context_length") or 0) < rules["min_context_length"]:
        return False

    return True


def score_model(remote: dict[str, Any], rules: dict[str, Any]) -> float:
    oid = remote["id"].lower()
    slug = oid.split("/", 1)[1]
    flagship = _compile(rules["flagship_id_patterns"])
    niche = _compile(rules["niche_id_patterns"])

    s = 0.0
    if flagship.search(slug):
        s += 20.0
    if niche.search(slug):
        s -= 8.0
    if re.search(r"-fast$|-high$", oid):
        s -= 4.0
    s += min((remote.get("context_length") or 0) / 200_000, 3.0)
    s += (remote.get("created") or 0) / 1e9
    return s


def pick_family_representative(group: list[dict[str, Any]]) -> dict[str, Any]:
    def sort_key(remote: dict[str, Any]) -> tuple[Any, ...]:
        oid = remote["id"]
        is_variant = 1 if re.search(r"-(fast|high)$", oid) else 0
        return (version_tuple(oid), -is_variant, remote.get("created") or 0)

    return max(group, key=sort_key)


def resolve_benchmark_link(openrouter_id: str, rules: dict[str, Any]) -> dict[str, str] | None:
    flagship = _compile(rules["flagship_id_patterns"])
    model_slug = openrouter_id.split("/", 1)[1]
    if not flagship.search(model_slug):
        return None
    for entry in rules.get("benchmark_links", []):
        if re.search(entry["pattern"], openrouter_id, re.I):
            return {
                "benchmark_url": entry["url"],
                "benchmark_source": entry.get("source", "benchmarks"),
            }
    return None


def to_output_model(remote: dict[str, Any], rules: dict[str, Any]) -> dict[str, Any]:
    provider_key = remote["id"].split("/")[0]
    pricing = remote["pricing"]
    model: dict[str, Any] = {
        "id": slug_id(remote["id"]),
        "name": display_name(remote),
        "provider": format_provider_name(provider_key, rules),
        "input": per_million_usd(pricing["prompt"]),
        "output": per_million_usd(pricing["completion"]),
        "context": int(remote["context_length"]),
        "tags": infer_tags(remote),
        "openrouter_id": remote["id"],
        "pricing_source": "openrouter",
        "score": round(score_model(remote, rules), 2),
    }
    bench = resolve_benchmark_link(remote["id"], rules)
    if bench:
        model.update(bench)
    return model


def select_models(
    openrouter_models: list[dict[str, Any]],
    rules: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    rules = rules or load_rules()
    warnings: list[str] = []

    candidates = [m for m in openrouter_models if is_candidate(m, rules)]
    if not candidates:
        return [], ["No models matched selection rules"]

    families: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for remote in candidates:
        families.setdefault(family_key(remote["id"]), []).append(remote)

    representatives = [pick_family_representative(group) for group in families.values()]

    by_provider: dict[str, list[dict[str, Any]]] = {}
    for remote in representatives:
        provider = remote["id"].split("/")[0]
        by_provider.setdefault(provider, []).append(remote)

    min_score = float(rules.get("min_score", 0))
    per_provider_max = int(rules.get("per_provider_max", 5))
    global_max = int(rules.get("global_max", 50))

    picked_remotes: list[dict[str, Any]] = []
    for provider in sorted(by_provider):
        ranked = sorted(by_provider[provider], key=lambda m: score_model(m, rules), reverse=True)
        kept = 0
        for remote in ranked:
            if score_model(remote, rules) < min_score:
                continue
            picked_remotes.append(remote)
            kept += 1
            if kept >= per_provider_max:
                break

    picked_remotes.sort(key=lambda m: score_model(m, rules), reverse=True)
    if len(picked_remotes) > global_max:
        dropped = picked_remotes[global_max:]
        picked_remotes = picked_remotes[:global_max]
        warnings.append(f"Trimmed {len(dropped)} models to global_max={global_max}")

    models = [to_output_model(remote, rules) for remote in picked_remotes]
    models.sort(key=lambda m: (m["provider"], m["name"].lower()))

    for model in models:
        model.pop("score", None)

    active_providers = sorted({m["openrouter_id"].split("/")[0] for m in models})
    if mode := rules.get("provider_mode"):
        warnings.append(f"provider_mode={mode}; {len(active_providers)} providers in catalog")

    return models, warnings


def diff_models(
    previous: list[dict[str, Any]] | None,
    current: list[dict[str, Any]],
) -> dict[str, list[dict[str, str]]]:
    if not previous:
        return {
            "added": [{"id": m["id"], "name": m["name"], "openrouter_id": m["openrouter_id"]} for m in current],
            "removed": [],
            "updated": [],
        }

    prev_by_or = {m["openrouter_id"]: m for m in previous}
    curr_by_or = {m["openrouter_id"]: m for m in current}

    added = [
        {"id": m["id"], "name": m["name"], "openrouter_id": m["openrouter_id"]}
        for oid, m in curr_by_or.items()
        if oid not in prev_by_or
    ]
    removed = [
        {"id": m["id"], "name": m["name"], "openrouter_id": m["openrouter_id"]}
        for oid, m in prev_by_or.items()
        if oid not in curr_by_or
    ]

    updated: list[dict[str, str]] = []
    for oid, curr in curr_by_or.items():
        prev = prev_by_or.get(oid)
        if not prev:
            continue
        changes: list[str] = []
        if prev.get("name") != curr.get("name"):
            changes.append(f"name: {prev.get('name')} → {curr.get('name')}")
        if prev.get("input") != curr.get("input"):
            changes.append(f"input: {prev.get('input')} → {curr.get('input')}")
        if prev.get("output") != curr.get("output"):
            changes.append(f"output: {prev.get('output')} → {curr.get('output')}")
        if changes:
            updated.append(
                {
                    "id": curr["id"],
                    "openrouter_id": oid,
                    "changes": "; ".join(changes),
                }
            )

    return {"added": added, "removed": removed, "updated": updated}
