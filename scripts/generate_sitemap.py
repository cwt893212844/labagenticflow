"""Generate sitemap.xml from static pages and models.json."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

import typer

app = typer.Typer(add_completion=False, no_args_is_help=True)

ROOT = Path(__file__).resolve().parent.parent
MODELS_PATH = ROOT / "data" / "models.json"
SITEMAP_PATH = ROOT / "sitemap.xml"
BASE = "https://www.labagenticflow.com"

STATIC_PAGES: list[tuple[str, str, str]] = [
    ("/", "daily", "1.0"),
    ("/mcp.html", "weekly", "0.9"),
    ("/compare.html", "weekly", "0.9"),
    ("/model.html", "weekly", "0.85"),
    ("/tools/index.html", "weekly", "0.8"),
    ("/tools/json-formatter.html", "monthly", "0.7"),
    ("/tools/jwt-decoder.html", "monthly", "0.7"),
    ("/tools/yaml-convert.html", "monthly", "0.7"),
    ("/sources.html", "monthly", "0.6"),
    ("/changelog.html", "daily", "0.5"),
    ("/privacy.html", "yearly", "0.3"),
]


def load_models(path: Path) -> list[dict]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("models") or []


def url_entry(loc: str, lastmod: str, changefreq: str, priority: str) -> str:
    return f"""  <url>
    <loc>{escape(loc)}</loc>
    <lastmod>{lastmod}</lastmod>
    <changefreq>{changefreq}</changefreq>
    <priority>{priority}</priority>
  </url>"""


def generate_sitemap(models_path: Path = MODELS_PATH, output_path: Path = SITEMAP_PATH) -> dict:
    lastmod = date.today().isoformat()
    models = load_models(models_path)

    entries = [url_entry(f"{BASE}{path}", lastmod, freq, pri) for path, freq, pri in STATIC_PAGES]

    for model in models:
        mid = model.get("id")
        if not mid:
            continue
        loc = f"{BASE}/model.html?m={mid}"
        entries.append(url_entry(loc, lastmod, "weekly", "0.75"))

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(entries)
        + "\n</urlset>\n"
    )
    output_path.write_text(xml, encoding="utf-8")

    return {
        "ok": True,
        "output": str(output_path),
        "url_count": len(entries),
        "model_urls": len(models),
        "lastmod": lastmod,
    }


@app.command()
def main(
    models: Path = typer.Option(MODELS_PATH, "--models", "-m"),
    output: Path = typer.Option(SITEMAP_PATH, "--output", "-o"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    result = generate_sitemap(models, output)
    if json_out:
        typer.echo(json.dumps(result, indent=2))
    else:
        typer.echo(f"Wrote {result['url_count']} URLs to {result['output']}")


if __name__ == "__main__":
    app()
