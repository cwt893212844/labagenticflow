"""Fetch LLM API pricing from OpenRouter and write data/models.json."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import typer

from model_selector import DEFAULT_RULES, diff_models, load_rules, select_models
from price_history import DEFAULT_HISTORY_PATH, append_snapshot

app = typer.Typer(add_completion=False, no_args_is_help=True)

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RULES_PATH = DEFAULT_RULES
DEFAULT_OUTPUT = ROOT / "data" / "models.json"
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"


async def fetch_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    max_retries: int = 4,
) -> dict[str, Any]:
    delay = 1.0
    last_error: Exception | None = None

    for attempt in range(max_retries):
        try:
            response = await client.get(url, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt == max_retries - 1:
                break
            await asyncio.sleep(delay)
            delay *= 2

    raise RuntimeError(f"Failed to fetch {url} after {max_retries} attempts") from last_error


def load_previous_models(output_path: Path) -> list[dict[str, Any]] | None:
    if not output_path.exists():
        return None
    try:
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        return payload.get("models")
    except (json.JSONDecodeError, OSError):
        return None


async def run_fetch(rules_path: Path, output_path: Path) -> dict[str, Any]:
    rules = load_rules(rules_path)
    previous = load_previous_models(output_path)
    history_path = DEFAULT_HISTORY_PATH

    async with httpx.AsyncClient(
        headers={"User-Agent": "LabAgenticFlow/1.0 (+https://labagenticflow.com)"},
    ) as client:
        payload = await fetch_json(client, OPENROUTER_MODELS_URL)

    openrouter_models = payload.get("data", [])
    models, warnings = select_models(openrouter_models, rules)

    if not models:
        raise RuntimeError("No models selected — relax selection_rules.json or check OpenRouter API")

    changes = diff_models(previous, models)
    now = datetime.now(timezone.utc)
    dataset: dict[str, Any] = {
        "version": now.strftime("%Y.%m.%d"),
        "last_updated": now.isoformat().replace("+00:00", "Z"),
        "source": "openrouter",
        "source_url": OPENROUTER_MODELS_URL,
        "selection": "auto",
        "model_count": len(models),
        "models": models,
        "changes": changes,
    }

    if warnings:
        dataset["warnings"] = warnings

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(dataset, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    history = append_snapshot(models, now, history_path)

    return {
        "ok": True,
        "output": str(output_path),
        "model_count": len(models),
        "last_updated": dataset["last_updated"],
        "added": len(changes["added"]),
        "removed": len(changes["removed"]),
        "updated": len(changes["updated"]),
        "warnings": warnings,
        "changes": changes,
        "history": history,
    }


@app.command()
def main(
    rules: Path = typer.Option(DEFAULT_RULES_PATH, "--rules", "-r", help="Auto-selection rules JSON"),
    output: Path = typer.Option(DEFAULT_OUTPUT, "--output", "-o", help="Generated models.json path"),
    json_out: bool = typer.Option(False, "--json", help="Print structured result to stdout"),
) -> None:
    """Discover models from OpenRouter, auto-select, and write models.json."""
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
        typer.echo(f"Wrote {result['model_count']} models → {result['output']}")
        typer.echo(
            f"Changes: +{result['added']} added, -{result['removed']} removed, ~{result['updated']} updated"
        )
        hist = result.get("history") or {}
        if hist.get("written"):
            typer.echo(
                f"History: {hist.get('action')} snapshot for {hist.get('date')} "
                f"({hist.get('snapshot_count')} days on record)"
            )
        else:
            typer.echo(f"History: unchanged for {hist.get('date', 'today')}")
        if result["warnings"]:
            typer.echo(f"Warnings ({len(result['warnings'])}):", err=True)
            for warning in result["warnings"]:
                typer.echo(f"  - {warning}", err=True)


if __name__ == "__main__":
    app()
