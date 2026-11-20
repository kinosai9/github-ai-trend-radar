"""Run summary helpers for CI diagnostics and PushPlus footer status."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from github_ai_trend_radar.renderers.pushplus_summary import select_push_projects
from github_ai_trend_radar.storage.files import load_json, save_json


_STATUS_SEVERITY = {"success": 0, "partial_success": 1, "failed": 2}


def _combined_status(previous: str | None, current: str) -> str:
    """Never let a later notification step hide a prior partial failure."""
    prior = previous or "success"
    return prior if _STATUS_SEVERITY.get(prior, 2) >= _STATUS_SEVERITY.get(current, 2) else current


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
    target = Path(output_dir) / f"{report_date}-{period}-run-summary.json"
    existing = load_json(target) if target.exists() else {}
    report = report or {}
    stats = report.get("stats", {}) if isinstance(report.get("stats"), dict) else {}
    overview = report.get("overview_enrichment", {}) if isinstance(report.get("overview_enrichment"), dict) else {}
    report_enrichment = report.get("report_enrichment", {}) if isinstance(report.get("report_enrichment"), dict) else {}
    watchlist_queue = report.get("watchlist_queue", {}) if isinstance(report.get("watchlist_queue"), dict) else {}
    selected = select_push_projects(report)
    sections = report.get("sections", {})
    payload = {
        "period": period,
        "report_date": report_date,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": _combined_status(existing.get("status") if isinstance(existing, dict) else None, status),
        "sources": report.get("data_sources", []),
        "counts": {
            "collection": stats.get("collection_counts", {}),
            "scored_buckets": stats.get("bucket_counts", {}),
            "report_sections": {key: len(sections.get(key, [])) for key in selected},
            "push_sections": {key: len(items) for key, items in selected.items()},
            "push_selected": sum(len(items) for items in selected.values()),
        },
        "llm": {
            "project_analysis": report.get("llm", {}),
            "report_card_enrichment": {
                "enabled": bool(report_enrichment.get("enabled")),
                "candidate_count": int(report_enrichment.get("candidate_count", 0) or 0),
                "ok_count": int(report_enrichment.get("ok_count", 0) or 0),
                "failed_count": int(report_enrichment.get("failed_count", 0) or 0),
                "attempts": report_enrichment.get("attempts", []),
            },
            "report_editorial": {
                "enabled": bool(overview.get("enabled")),
                "status": "ok" if overview.get("ok") else "failed" if overview.get("failed") else "fallback" if overview.get("fallback") else "skipped",
                "diagnostic": overview.get("diagnostic", {}),
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
            **(existing.get("timing_seconds", {}) if isinstance(existing, dict) else {}),
            **(timing_seconds or {}),
        },
        "warnings": list(dict.fromkeys((existing.get("warnings", []) if isinstance(existing, dict) else []) + (warnings or []))),
        "errors": list(dict.fromkeys((existing.get("errors", []) if isinstance(existing, dict) else []) + (errors or []))),
    }
    return save_json(payload, target)


def load_run_summary(output_dir: str | Path, period: str, report_date: str) -> dict[str, Any] | None:
    path = Path(output_dir) / f"{report_date}-{period}-run-summary.json"
    if not path.exists():
        return None
    return load_json(path)
