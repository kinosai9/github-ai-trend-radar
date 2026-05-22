"""Markdown report rendering."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, PackageLoader, select_autoescape

from github_ai_trend_radar.storage.files import ensure_directory


def render_markdown(report: dict[str, Any]) -> str:
    env = Environment(
        loader=PackageLoader("github_ai_trend_radar", "renderers/templates"),
        autoescape=select_autoescape(default=False),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("report.md.j2")
    return template.render(report=report)


def write_markdown_report(report: dict[str, Any], output_path: str | Path) -> Path:
    target = Path(output_path)
    ensure_directory(target.parent)
    target.write_text(render_markdown(report), encoding="utf-8")
    return target
