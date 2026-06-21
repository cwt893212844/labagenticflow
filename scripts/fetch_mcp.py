"""Fetch curated MCP servers from the official registry and write data/mcp.json."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
import typer

from mcp_selector import (
    DEFAULT_RULES,
    diff_servers,
    load_rules,
    merge_server,
    pick_search_match,
    validate_scenarios,
)

app = typer.Typer(add_completion=False, no_args_is_help=True)

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "data" / "mcp.json"
USER_AGENT = "LabAgenticFlow/1.0 (+https://labagenticflow.com)"


async def fetch_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    max_retries: int = 4,
) -> dict[str, Any]:
    delay = 1.0
    last_error: Exception | None = None

    for attempt in range(max_retries):
        try:
            response = await client.get(url, params=params, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt == max_retries - 1:
                break
            await asyncio.sleep(delay)
            delay *= 2

    raise RuntimeError(f"Failed to fetch {url} after {max_retries} attempts") from last_error


async def fetch_registry_server(
    client: httpx.AsyncClient,
    registry_url: str,
    registry_name: str,
) -> dict[str, Any] | None:
    encoded = quote(registry_name, safe="")
    url = f"{registry_url.rstrip('/')}/v0.1/servers/{encoded}/versions/latest"
    try:
        payload = await fetch_json(client, url, max_retries=3)
    except RuntimeError:
        return None

    server = payload.get("server")
    if not server:
        return None
    return {"server": server, "_meta": payload.get("_meta") or {}}


async def search_registry(
    client: httpx.AsyncClient,
    registry_url: str,
    query: str,
) -> list[dict[str, Any]]:
    url = f"{registry_url.rstrip('/')}/v0.1/servers"
    try:
        payload = await fetch_json(
            client,
            url,
            params={"search": query, "limit": 10, "version": "latest"},
            max_retries=3,
        )
    except RuntimeError:
        return []
    return payload.get("servers") or []


async def resolve_pin(
    client: httpx.AsyncClient,
    registry_url: str,
    pin: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    registry_name = pin.get("registry_name")
    if registry_name:
        entry = await fetch_registry_server(client, registry_url, registry_name)
        if entry:
            return entry, None
        return None, f"{pin['id']}: registry name not found ({registry_name})"

    registry_search = pin.get("registry_search")
    if registry_search:
        candidates = await search_registry(client, registry_url, registry_search)
        entry = pick_search_match(
            candidates,
            prefer_name=pin.get("registry_name"),
            repo_hint=pin.get("repo_url"),
        )
        if entry:
            return entry, None
        return None, f"{pin['id']}: registry search returned no match ({registry_search})"

    return None, None


def load_previous_servers(output_path: Path) -> list[dict[str, Any]] | None:
    if not output_path.exists():
        return None
    try:
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        return payload.get("servers")
    except (json.JSONDecodeError, OSError):
        return None


async def run_fetch(rules_path: Path, output_path: Path) -> dict[str, Any]:
    rules = load_rules(rules_path)
    registry_url = rules.get("registry_url", "https://registry.modelcontextprotocol.io")
    pins = rules.get("pins") or []
    scenarios = rules.get("scenarios") or []

    if not pins:
        raise RuntimeError("No pins defined in mcp_selection_rules.json")

    previous = load_previous_servers(output_path)
    warnings: list[str] = []
    servers: list[dict[str, Any]] = []
    registry_hits = 0

    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}) as client:
        semaphore = asyncio.Semaphore(6)

        async def process_pin(pin: dict[str, Any]) -> dict[str, Any]:
            nonlocal registry_hits
            async with semaphore:
                entry, warn = await resolve_pin(client, registry_url, pin)
            if warn:
                warnings.append(warn)
            if entry:
                registry_hits += 1
            return merge_server(pin, entry)

        servers = list(await asyncio.gather(*(process_pin(pin) for pin in pins)))

    warnings.extend(validate_scenarios(scenarios, servers))

    changes = diff_servers(previous, servers)
    now = datetime.now(timezone.utc)

    dataset: dict[str, Any] = {
        "version": now.strftime("%Y.%m.%d"),
        "last_updated": now.isoformat().replace("+00:00", "Z"),
        "source": "mcp-registry",
        "source_url": registry_url,
        "selection": "auto",
        "source_note": (
            "Curated pins from mcp_selection_rules.json, enriched from the official MCP Registry "
            "where available. Not a full registry mirror."
        ),
        "server_count": len(servers),
        "registry_hits": registry_hits,
        "scenarios": scenarios,
        "servers": servers,
        "changes": changes,
    }

    if warnings:
        dataset["warnings"] = warnings

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(dataset, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return {
        "ok": True,
        "output": str(output_path),
        "server_count": len(servers),
        "registry_hits": registry_hits,
        "last_updated": dataset["last_updated"],
        "added": len(changes["added"]),
        "removed": len(changes["removed"]),
        "updated": len(changes["updated"]),
        "warnings": warnings,
        "changes": changes,
    }


@app.command()
def main(
    rules: Path = typer.Option(DEFAULT_RULES, "--rules", "-r", help="MCP selection rules JSON"),
    output: Path = typer.Option(DEFAULT_OUTPUT, "--output", "-o", help="Generated mcp.json path"),
    json_out: bool = typer.Option(False, "--json", help="Print structured result to stdout"),
) -> None:
    """Resolve curated MCP pins against the official registry and write mcp.json."""
    try:
        result = asyncio.run(run_fetch(rules, output))
    except Exception as exc:
        if json_out:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        else:
            typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if json_out:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        typer.echo(f"Wrote {result['server_count']} servers → {result['output']}")
        typer.echo(f"Registry hits: {result['registry_hits']}/{result['server_count']}")
        typer.echo(
            f"Changes: +{result['added']} added, -{result['removed']} removed, ~{result['updated']} updated"
        )
        if result["warnings"]:
            typer.echo(f"Warnings ({len(result['warnings'])}):", err=True)
            for warning in result["warnings"]:
                typer.echo(f"  - {warning}", err=True)


if __name__ == "__main__":
    app()
