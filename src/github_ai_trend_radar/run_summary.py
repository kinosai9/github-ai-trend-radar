"""Run summary helpers for CI diagnostics and PushPlus footer status."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from github_ai_trend_radar.storage.files import load_json, save_json


def write_run_summary(
    *,
    output_dir: str | Path,
    period: str,
    report_date: str,
    report: dict[str, Any] | None = None,
    status: str = "success",
    pages_url: str = "",
    pushplus_status: str = "skipped",
    warnings: list[str] | None = None,
    errors: list[str] | None = None,
    timing_seconds: dict[str, float] | None = None,
) -> Path:
    report = report or {}
    stats = report.get("stats", {}) if isinstance(report.get("stats"), dict) else {}
    overview = report.get("overview_enrichment", {}) if isinstance(report.get("overview_enrichment"), dict) else {}
    watchlist_queue = report.get("watchlist_queue", {}) if isinstance(report.get("watchlist_queue"), dict) else {}
    payload = {
        "period": period,
        "report_date": report_date,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "sources": report.get("data_sources", []),
        "llm": {
            "project_analysis": report.get("llm", {}),
            "report_editorial": {
                "enabled": bool(overview.get("enabled")),
                "status": "ok" if overview.get("ok") else "failed" if overview.get("failed") else "fallback" if overview.get("fallback") else "skipped",
            },
        },
        "quality_gate": stats.get("quality_gate", {"pass": 0, "warn": 0, "block": 0}),
        "watchlist": {
            "queue_generated": bool(watchlist_queue.get("file") or "items" in watchlist_queue),
            "queue_count": int(watchlist_queue.get("count", 0) or 0),
            "queue_file": watchlist_queue.get("file", ""),
        },
        "reports": {
            "html": f"data/reports/{report_date}-{period}-report.html",
            "markdown": f"data/reports/{report_date}-{period}-report.md",
            "pages_url": pages_url,
        },
        "pushplus": {
            "enabled": pushplus_status != "skipped",
            "status": pushplus_status,
        },
        "timing_seconds": {
            "collect": 0,
            "score": 0,
            "llm_project": 0,
            "report_enrich": 0,
            "report_editorial": 0,
            "render": 0,
            "build_site": 0,
            "pushplus": 0,
            **(timing_seconds or {}),
        },
        "warnings": warnings or [],
        "errors": errors or [],
    }
    return save_json(payload, Path(output_dir) / f"{report_date}-{period}-run-summary.json")


def load_run_summary(output_dir: str | Path, period: str, report_date: str) -> dict[str, Any] | None:
    path = Path(output_dir) / f"{report_date}-{period}-run-summary.json"
    if not path.exists():
        return None
    return load_json(path)
