"""Append-only daily price snapshots for charting (collected, not yet displayed)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
DEFAULT_RETENTION_DAYS = 365
DEFAULT_HISTORY_PATH = Path(__file__).resolve().parent.parent / "data" / "price_history.json"


def _empty_history() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "source": "openrouter",
        "retention_days": DEFAULT_RETENTION_DAYS,
        "snapshots": [],
    }


def load_history(path: Path = DEFAULT_HISTORY_PATH) -> dict[str, Any]:
    if not path.exists():
        return _empty_history()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return _empty_history()
    if not isinstance(payload.get("snapshots"), list):
        return _empty_history()
    return payload


def prices_from_models(models: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    return {
        m["id"]: {"input": m["input"], "output": m["output"]}
        for m in models
        if "id" in m and "input" in m and "output" in m
    }


def _trim_snapshots(history: dict[str, Any]) -> int:
    retention = int(history.get("retention_days") or DEFAULT_RETENTION_DAYS)
    cutoff = (datetime.now(timezone.utc).date() - timedelta(days=retention)).isoformat()
    before = len(history["snapshots"])
    history["snapshots"] = [s for s in history["snapshots"] if s.get("date", "") >= cutoff]
    return before - len(history["snapshots"])


def append_snapshot(
    models: list[dict[str, Any]],
    fetched_at: datetime,
    path: Path = DEFAULT_HISTORY_PATH,
) -> dict[str, Any]:
    """Record one UTC-day snapshot. Idempotent when prices are unchanged."""
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=timezone.utc)
    else:
        fetched_at = fetched_at.astimezone(timezone.utc)

    date = fetched_at.date().isoformat()
    prices = prices_from_models(models)
    history = load_history(path)

    snapshot = {
        "date": date,
        "fetched_at": fetched_at.isoformat().replace("+00:00", "Z"),
        "model_count": len(prices),
        "prices": prices,
    }

    snapshots: list[dict[str, Any]] = history["snapshots"]
    existing = next((i for i, s in enumerate(snapshots) if s.get("date") == date), None)

    action = "appended"
    if existing is not None:
        prev = snapshots[existing]
        if prev.get("prices") == prices:
            return {
                "written": False,
                "date": date,
                "snapshot_count": len(snapshots),
                "action": "unchanged",
                "path": str(path),
            }
        snapshots[existing] = snapshot
        action = "updated"
    else:
        snapshots.append(snapshot)
        snapshots.sort(key=lambda s: s.get("date", ""))

    trimmed = _trim_snapshots(history)
    history["last_snapshot"] = date
    history["snapshot_count"] = len(snapshots)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(history, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    return {
        "written": True,
        "date": date,
        "action": action,
        "snapshot_count": len(snapshots),
        "trimmed": trimmed,
        "path": str(path),
    }
