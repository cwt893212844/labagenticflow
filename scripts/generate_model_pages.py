"""Generate static /model/{slug}.html pages from models.json for SEO."""

from __future__ import annotations

import html
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import typer

app = typer.Typer(add_completion=False, no_args_is_help=True)

ROOT = Path(__file__).resolve().parent.parent
MODELS_PATH = ROOT / "data" / "models.json"
ARCHIVE_PATH = ROOT / "data" / "model_archive.json"
MODEL_DIR = ROOT / "model"
BASE = "https://www.labagenticflow.com"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def fmt_ctx(ctx: Any) -> str:
    try:
        n = int(ctx)
    except (TypeError, ValueError):
        return "—"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}".rstrip("0").rstrip(".") + "M"
    if n >= 1000:
        return f"{n // 1000}K"
    return str(n)


def shell_links(base: str = "../") -> str:
    return f"""    <header class="site-header">
      <a href="{base}index.html" class="logo" aria-label="LabAgenticFlow home">
        <div class="logo-mark" aria-hidden="true"></div>
        <span class="logo-text">Lab<em>Agentic</em>Flow</span>
      </a>
      <nav class="header-nav" aria-label="Site">
        <a href="{base}index.html">Calculator</a>
        <a href="{base}compare.html">Compare</a>
        <a href="{base}model.html" aria-current="page">Models</a>
        <a href="{base}mcp.html">MCP</a>
        <a href="{base}tools/index.html">Tools</a>
        <a href="{base}sources.html">Sources</a>
      </nav>
    </header>"""


def page_head(
    *,
    title: str,
    description: str,
    canonical: str,
    base: str = "../",
    json_ld: dict[str, Any] | None = None,
) -> str:
    ld = ""
    if json_ld:
        ld = (
            '\n  <script type="application/ld+json">'
            + json.dumps(json_ld, ensure_ascii=False, separators=(",", ":"))
            + "</script>"
        )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="description" content="{html.escape(description)}" />
  <title>{html.escape(title)}</title>
  <link rel="canonical" href="{html.escape(canonical)}" />
  <meta property="og:title" content="{html.escape(title)}" />
  <meta property="og:description" content="{html.escape(description)}" />
  <meta property="og:url" content="{html.escape(canonical)}" />
  <meta property="og:type" content="website" />
  <link rel="icon" href="{base}assets/favicon.svg" type="image/svg+xml" />
  <meta name="theme-color" content="#06090f" />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=IBM+Plex+Mono:wght@400;500;600&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="{base}assets/site-base.css" />
  <link rel="stylesheet" href="{base}assets/model-page.css" />{ld}
</head>"""


def render_active_page(model: dict[str, Any], last_updated: str) -> str:
    mid = model["id"]
    name = model.get("name") or mid
    provider = model.get("provider") or ""
    oid = model.get("openrouter_id") or ""
    inp = model.get("input")
    out = model.get("output")
    ctx = fmt_ctx(model.get("context"))
    canonical = f"{BASE}/model/{mid}"
    title = f"{name} API pricing — LabAgenticFlow"
    description = (
        f"{name} ({provider}) API pricing via OpenRouter: "
        f"${inp}/M input, ${out}/M output, {ctx} context. "
        f"Workload cost estimates on LabAgenticFlow."
    )
    json_ld = {
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        "name": name,
        "applicationCategory": "DeveloperApplication",
        "operatingSystem": "Any",
        "url": canonical,
        "offers": {
            "@type": "Offer",
            "priceCurrency": "USD",
            "price": str(inp),
            "description": f"Input ${inp}/M tokens; output ${out}/M tokens (OpenRouter)",
        },
        "provider": {"@type": "Organization", "name": provider},
    }
    tags = model.get("tags") or []
    tag_html = "".join(
        f'<span class="cap-chip">{html.escape(str(t))}</span>' for t in tags[:8]
    )
    updated = last_updated[:10] if last_updated else date.today().isoformat()

    return f"""{page_head(title=title, description=description, canonical=canonical, json_ld=json_ld)}
<body data-base="../" data-model-id="{html.escape(mid)}">
  <div class="shell shell--wide">
{shell_links()}
    <div id="page-root">
      <section class="model-hero">
        <div>
          <p class="doc-eyebrow">Model pricing</p>
          <h1>{html.escape(name)}</h1>
          <p class="model-provider">{html.escape(provider)}</p>
          <p class="model-id">{html.escape(oid)}</p>
          <div class="model-tags">{tag_html}</div>
        </div>
        <div class="hero-cost">
          <p class="hero-cost-label">Input / output</p>
          <p class="hero-cost-value">${html.escape(str(inp))}/M</p>
          <p class="hero-cost-sub">${html.escape(str(out))}/M out</p>
        </div>
      </section>
      <div class="stat-grid">
        <div class="stat-cell"><p class="stat-label">Input</p><p class="stat-value">${html.escape(str(inp))}/M</p></div>
        <div class="stat-cell"><p class="stat-label">Output</p><p class="stat-value">${html.escape(str(out))}/M</p></div>
        <div class="stat-cell"><p class="stat-label">Context</p><p class="stat-value">{html.escape(ctx)}</p></div>
        <div class="stat-cell"><p class="stat-label">Updated</p><p class="stat-value">{html.escape(updated)}</p></div>
      </div>
      <p class="doc-lead" style="margin-top:24px">
        Compare workload cost in the
        <a href="../index.html?model={html.escape(mid)}">calculator</a>
        or <a href="../compare.html?models={html.escape(mid)}">side-by-side compare</a>.
        Rates from OpenRouter.
      </p>
    </div>
    <footer class="site-footer">
      <p class="footer-note" id="footer-note">Estimates only. Verify before production use.</p>
      <div class="footer-links">
        <a href="../index.html">Calculator</a> · <a href="../compare.html">Compare</a> · <a href="../model.html">All models</a>
      </div>
    </footer>
  </div>
  <script src="../assets/laf-calc.js"></script>
  <script src="../assets/model-page.js"></script>
</body>
</html>
"""


def render_tombstone(entry: dict[str, Any]) -> str:
    mid = entry["id"]
    name = entry.get("name") or mid
    provider = entry.get("provider") or ""
    inp = entry.get("input")
    out = entry.get("output")
    ctx = fmt_ctx(entry.get("context"))
    archived_at = entry.get("archived_at", "")[:10]
    canonical = f"{BASE}/model/{mid}"
    title = f"{name} API pricing (archived) — LabAgenticFlow"
    description = (
        f"{name} was previously listed on LabAgenticFlow. "
        f"Last known OpenRouter rates: ${inp}/M in, ${out}/M out. "
        f"Browse the current model catalog for live pricing."
    )
    return f"""{page_head(title=title, description=description, canonical=canonical)}
<body data-base="../" data-model-id="{html.escape(mid)}" data-archived="true">
  <div class="shell shell--wide">
{shell_links()}
    <div id="page-root">
      <section class="model-hero">
        <div>
          <p class="doc-eyebrow">Archived model</p>
          <h1>{html.escape(name)}</h1>
          <p class="model-provider">{html.escape(provider)}</p>
          <p class="model-id">{html.escape(mid)}</p>
          <p class="model-archived-banner">
            This model is no longer in the active catalog
            {f"(archived {html.escape(archived_at)})" if archived_at else ""}.
            Last known rates are shown below. See the
            <a href="../model.html">current model index</a>.
          </p>
        </div>
      </section>
      <div class="stat-grid">
        <div class="stat-cell"><p class="stat-label">Input (last)</p><p class="stat-value">${html.escape(str(inp))}/M</p></div>
        <div class="stat-cell"><p class="stat-label">Output (last)</p><p class="stat-value">${html.escape(str(out))}/M</p></div>
        <div class="stat-cell"><p class="stat-label">Context</p><p class="stat-value">{html.escape(ctx)}</p></div>
        <div class="stat-cell"><p class="stat-label">Status</p><p class="stat-value">Archived</p></div>
      </div>
    </div>
    <footer class="site-footer">
      <p class="footer-note">Historical snapshot. Not a live rate.</p>
      <div class="footer-links">
        <a href="../model.html">All models</a> · <a href="../index.html">Calculator</a>
      </div>
    </footer>
  </div>
</body>
</html>
"""


def archive_snapshot(model: dict[str, Any], when: str) -> dict[str, Any]:
    return {
        "id": model["id"],
        "name": model.get("name"),
        "provider": model.get("provider"),
        "openrouter_id": model.get("openrouter_id"),
        "input": model.get("input"),
        "output": model.get("output"),
        "context": model.get("context"),
        "archived_at": when,
    }


def generate_model_pages(
    models_path: Path = MODELS_PATH,
    out_dir: Path = MODEL_DIR,
    archive_path: Path = ARCHIVE_PATH,
) -> dict[str, Any]:
    payload = load_json(models_path)
    models: list[dict[str, Any]] = payload.get("models") or []
    last_updated = payload.get("last_updated") or datetime.now(timezone.utc).isoformat()
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    active_ids = {m["id"] for m in models if m.get("id")}
    archive = load_json(archive_path)
    entries: dict[str, Any] = dict(archive.get("models") or {})
    last_active = {m["id"]: m for m in (archive.get("last_active") or []) if m.get("id")}

    # Resurrected models leave the archive
    for mid in list(entries.keys()):
        if mid in active_ids:
            entries.pop(mid, None)

    # Models that left the catalog since last run → tombstone with last known rates
    for mid, prev in last_active.items():
        if mid not in active_ids and mid not in entries:
            entries[mid] = archive_snapshot(prev, now)

    # Also catch HTML files / changes.removed without last_active (first run edge cases)
    out_dir.mkdir(parents=True, exist_ok=True)
    existing = {p.stem for p in out_dir.glob("*.html")}
    removed_by_id = {
        item["id"]: item
        for item in (payload.get("changes") or {}).get("removed") or []
        if item.get("id")
    }
    for mid in existing - active_ids:
        if mid in entries:
            continue
        if mid in last_active:
            entries[mid] = archive_snapshot(last_active[mid], now)
            continue
        meta = removed_by_id.get(mid) or {}
        entries[mid] = {
            "id": mid,
            "name": meta.get("name") or mid,
            "provider": "",
            "openrouter_id": meta.get("openrouter_id") or "",
            "input": "—",
            "output": "—",
            "context": None,
            "archived_at": now,
        }

    written_active = 0
    for model in models:
        mid = model.get("id")
        if not mid:
            continue
        path = out_dir / f"{mid}.html"
        path.write_text(render_active_page(model, last_updated), encoding="utf-8")
        written_active += 1

    written_tomb = 0
    for mid, entry in entries.items():
        if mid in active_ids:
            continue
        path = out_dir / f"{mid}.html"
        path.write_text(render_tombstone(entry), encoding="utf-8")
        written_tomb += 1

    # Remove HTML for neither active nor archived (shouldn't happen)
    keep = active_ids | set(entries.keys())
    removed_files = 0
    for path in out_dir.glob("*.html"):
        if path.stem not in keep:
            path.unlink()
            removed_files += 1

    archive_payload = {
        "updated_at": now,
        "models": entries,
        "last_active": [
            {
                "id": m["id"],
                "name": m.get("name"),
                "provider": m.get("provider"),
                "openrouter_id": m.get("openrouter_id"),
                "input": m.get("input"),
                "output": m.get("output"),
                "context": m.get("context"),
            }
            for m in models
            if m.get("id")
        ],
    }
    archive_path.write_text(json.dumps(archive_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    return {
        "ok": True,
        "active_pages": written_active,
        "tombstone_pages": written_tomb,
        "removed_files": removed_files,
        "archive_count": len(entries),
        "output_dir": str(out_dir),
    }


@app.command()
def main(
    models: Path = typer.Option(MODELS_PATH, "--models", "-m"),
    output: Path = typer.Option(MODEL_DIR, "--output", "-o"),
    archive: Path = typer.Option(ARCHIVE_PATH, "--archive"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    result = generate_model_pages(models, output, archive)
    if json_out:
        typer.echo(json.dumps(result, indent=2))
    else:
        typer.echo(
            f"Wrote {result['active_pages']} active + {result['tombstone_pages']} tombstone pages → {result['output_dir']}"
        )


if __name__ == "__main__":
    app()
