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


def pick_search_match(
    candidates: list[dict[str, Any]],
    *,
    prefer_name: str | None = None,
    repo_hint: str | None = None,
) -> dict[str, Any] | None:
    if not candidates:
        return None

    if prefer_name:
        for item in candidates:
            if item["server"].get("name") == prefer_name:
                return item

    if repo_hint:
        hint = repo_hint.lower()
        for item in candidates:
            repo = registry_repo_url(item["server"])
            if repo and hint in repo.lower():
                return item

    return candidates[0]


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

    if reg_server.get("description"):
        server["description"] = reg_server["description"].strip()

    reg_repo = registry_repo_url(reg_server)
    if reg_repo:
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
