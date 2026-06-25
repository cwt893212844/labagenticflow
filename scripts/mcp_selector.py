"""Select and enrich curated MCP servers from the official registry."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import quote

DEFAULT_RULES = Path(__file__).resolve().parent.parent / "data" / "mcp_selection_rules.json"

HTTP_REMOTE_TYPES = {"streamable-http", "http", "sse"}


def load_rules(path: Path = DEFAULT_RULES) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_repo_url(url: str | None) -> str | None:
    if not url:
        return None
    return url.rstrip("/").removesuffix(".git")


def infer_transport(server: dict[str, Any]) -> list[str]:
    transports: set[str] = set()

    for pkg in server.get("packages") or []:
        transport = (pkg.get("transport") or {}).get("type")
        if transport:
            transports.add("http" if transport in HTTP_REMOTE_TYPES else transport)
        elif pkg.get("registryType"):
            transports.add("stdio")

    for remote in server.get("remotes") or []:
        remote_type = remote.get("type")
        if not remote_type:
            continue
        transports.add("http" if remote_type in HTTP_REMOTE_TYPES else remote_type)

    return sorted(transports) or ["stdio"]


def registry_repo_url(server: dict[str, Any]) -> str | None:
    repo = server.get("repository") or {}
    return normalize_repo_url(repo.get("url"))


def normalize_repo_url(url: str | None) -> str | None:
    if not url:
        return None
    return url.rstrip("/").removesuffix(".git").lower()


def github_owner_repo(url: str | None) -> str | None:
    if not url or "github.com/" not in url:
        return None
    tail = url.split("github.com/", 1)[1].split("/tree", 1)[0].strip("/")
    parts = tail.split("/")
    if len(parts) >= 2:
        return f"{parts[0]}/{parts[1]}".lower()
    return None


def monorepo_slug(url: str | None) -> str | None:
    if not url or "/src/" not in url:
        return None
    return url.split("/src/", 1)[1].split("/", 1)[0].lower()


def repo_match_score(repo_hint: str | None, candidate_repo: str | None) -> int:
    if not repo_hint or not candidate_repo:
        return 0

    hint = normalize_repo_url(repo_hint) or ""
    cand = normalize_repo_url(candidate_repo) or ""
    if not hint or not cand:
        return 0
    if hint == cand:
        return 100

    hint_owner_repo = github_owner_repo(repo_hint)
    cand_owner_repo = github_owner_repo(candidate_repo)
    if hint_owner_repo and hint_owner_repo == cand_owner_repo:
        return 90

    if hint_owner_repo and hint_owner_repo in cand:
        return 70

    hint_slug = monorepo_slug(repo_hint)
    if hint_slug and hint_slug in cand:
        return 40

    if hint in cand or cand in hint:
        return 30

    return 0


def pick_search_match(
    candidates: list[dict[str, Any]],
    *,
    prefer_name: str | None = None,
    repo_hint: str | None = None,
    min_score: int = 30,
) -> dict[str, Any] | None:
    if not candidates:
        return None

    if prefer_name:
        for item in candidates:
            if item["server"].get("name") == prefer_name:
                return item

    if repo_hint:
        scored = [
            (repo_match_score(repo_hint, registry_repo_url(item["server"])), item)
            for item in candidates
        ]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        if scored[0][0] >= min_score:
            return scored[0][1]
        return None

    return candidates[0]


def derive_registry_queries(pin: dict[str, Any]) -> list[str]:
    if pin.get("registry_resolve") != "repo":
        return []

    queries: list[str] = []
    if pin.get("registry_search"):
        queries.append(str(pin["registry_search"]))

    repo = pin.get("repo_url") or ""
    owner_repo = github_owner_repo(repo)
    if owner_repo:
        queries.append(owner_repo)

    seen: set[str] = set()
    ordered: list[str] = []
    for query in queries:
        key = query.lower().strip()
        if key and key not in seen:
            seen.add(key)
            ordered.append(query)
    return ordered


def merge_server(
    pin: dict[str, Any],
    registry_entry: dict[str, Any] | None,
) -> dict[str, Any]:
    server: dict[str, Any] = {
        "id": pin["id"],
        "name": pin["name"],
        "publisher": pin["publisher"],
        "origin": pin["origin"],
        "category": pin["category"],
        "transport": list(pin.get("transport") or ["stdio"]),
        "description": pin["description"],
    }

    repo_url = pin.get("repo_url")
    if repo_url:
        server["repo_url"] = repo_url
    if pin.get("featured"):
        server["featured"] = True

    if not registry_entry:
        return server

    reg_server = registry_entry["server"]
    reg_meta = registry_entry.get("_meta") or {}
    official = reg_meta.get("io.modelcontextprotocol.registry/official") or {}

    if official.get("status") == "deleted":
        return server

    registry_name = reg_server.get("name")
    if registry_name:
        server["registry_name"] = registry_name
    if reg_server.get("version"):
        server["registry_version"] = reg_server["version"]

    reg_repo = registry_repo_url(reg_server)
    repo_score = repo_match_score(pin.get("repo_url"), reg_repo)

    if reg_server.get("description") and repo_score >= 90:
        server["description"] = reg_server["description"].strip()

    if reg_repo and repo_score >= 90:
        server["repo_url"] = reg_repo

    reg_transport = infer_transport(reg_server)
    if reg_transport:
        server["transport"] = sorted(set(server.get("transport") or []) | set(reg_transport))

    server["registry_synced"] = True
    return server


def diff_servers(
    previous: list[dict[str, Any]] | None,
    current: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    prev_by_id = {item["id"]: item for item in (previous or [])}
    curr_by_id = {item["id"]: item for item in current}

    added = [curr_by_id[item_id] for item_id in sorted(curr_by_id.keys() - prev_by_id.keys())]
    removed = [prev_by_id[item_id] for item_id in sorted(prev_by_id.keys() - curr_by_id.keys())]

    updated: list[dict[str, Any]] = []
    for item_id in sorted(curr_by_id.keys() & prev_by_id.keys()):
        old = prev_by_id[item_id]
        new = curr_by_id[item_id]
        changes: list[str] = []
        for field in ("description", "repo_url", "registry_version"):
            if old.get(field) != new.get(field):
                changes.append(f"{field}: {old.get(field)!r} → {new.get(field)!r}")
        if old.get("transport") != new.get("transport"):
            changes.append(f"transport: {old.get('transport')!r} → {new.get('transport')!r}")
        if changes:
            updated.append({"id": item_id, "name": new.get("name"), "changes": "; ".join(changes)})

    return {"added": added, "removed": removed, "updated": updated}


def validate_scenarios(scenarios: list[dict[str, Any]], servers: list[dict[str, Any]]) -> list[str]:
    warnings: list[str] = []
    server_ids = {item["id"] for item in servers}
    for scenario in scenarios:
        for mcp_id in scenario.get("mcp_ids") or []:
            if mcp_id not in server_ids:
                warnings.append(f"Scenario {scenario['id']} references missing server id {mcp_id!r}")
    return warnings
