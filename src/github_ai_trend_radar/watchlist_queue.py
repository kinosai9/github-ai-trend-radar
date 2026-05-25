"""Watchlist queue helpers for reports and GitHub Issue handoff."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import yaml

from github_ai_trend_radar.storage.files import save_json

QUEUE_LABELS = ("watchlist", "pending-review")


def repo_url_from_env() -> str:
    explicit = os.getenv("SITE_REPO_URL") or os.getenv("GITHUB_REPOSITORY_URL")
    if explicit:
        return explicit.rstrip("/")
    repository = os.getenv("GITHUB_REPOSITORY")
    server = os.getenv("GITHUB_SERVER_URL", "https://github.com")
    if repository:
        return f"{server.rstrip('/')}/{repository}"
    return ""


def build_watchlist_queue(report: dict[str, Any], *, max_items: int = 10) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for section in ("breakout", "deep_research", "long_term"):
        for item in report.get("sections", {}).get(section, []):
            if len(items) >= max_items:
                return items
            if not is_queue_candidate(item):
                continue
            queue_item = {
                "repo": item.get("repo_full_name", ""),
                "html_url": item.get("html_url", ""),
                "source_report": f"{report.get('generated_at', '')[:10]}-{report.get('period', 'daily')}",
                "source_section": section,
                "recommended_action": item.get("recommended_action", ""),
                "topics": item.get("matched_focus_topics", []),
                "radar_score": item.get("radar_score"),
                "llm_adjusted_score": item.get("llm_adjusted_score"),
                "quality_gate": (item.get("quality_gate") or {}).get("level", "pass")
                if isinstance(item.get("quality_gate"), dict)
                else "pass",
                "reason": item.get("reason_to_watch") or item.get("summary") or "",
            }
            items.append(queue_item)
    return items


def is_queue_candidate(item: dict[str, Any]) -> bool:
    action = item.get("recommended_action")
    if action not in {"deep_research", "try_locally", "read"}:
        return False
    gate = item.get("quality_gate", {}) if isinstance(item.get("quality_gate"), dict) else {}
    if gate.get("level") == "block":
        return False
    noise = item.get("noise", {}) if isinstance(item.get("noise"), dict) else {}
    if noise.get("is_noise") is True:
        return False
    if item.get("topic_match_confidence") == "weak":
        return False
    score = item.get("llm_adjusted_score", item.get("radar_score", 0)) or 0
    try:
        return float(score) >= 0.45
    except (TypeError, ValueError):
        return False


def attach_issue_links(report: dict[str, Any], *, repo_url: str | None = None) -> dict[str, Any]:
    repo_url = (repo_url if repo_url is not None else repo_url_from_env()).rstrip("/")
    queue = build_watchlist_queue(report)
    by_repo = {item["repo"]: item for item in queue}
    for section in ("breakout", "deep_research", "long_term"):
        for item in report.get("sections", {}).get(section, []):
            queue_item = by_repo.get(item.get("repo_full_name"))
            if not queue_item:
                item["watchlist_queue_eligible"] = False
                continue
            item["watchlist_queue_eligible"] = True
            item["watchlist_local_command"] = (
                f"python -m github_ai_trend_radar.main deep-research --repo {item.get('repo_full_name')} --open"
            )
            if repo_url:
                item["watchlist_issue_url"] = build_issue_url(repo_url, queue_item)
    report["watchlist_queue"] = {"count": len(queue), "items": queue, "repo_url": repo_url}
    return report


def write_watchlist_queue(report: dict[str, Any], output_dir: str | Path = "data/watchlist_queue") -> Path:
    queue = report.get("watchlist_queue", {}).get("items", []) if isinstance(report.get("watchlist_queue"), dict) else []
    period = report.get("period", "daily")
    day = str(report.get("generated_at", ""))[:10]
    return save_json(
        {"period": period, "report_date": day, "generated_at": report.get("generated_at"), "items": queue},
        Path(output_dir) / f"{day}-{period}-watchlist-queue.json",
    )


def build_issue_url(repo_url: str, item: dict[str, Any], labels: tuple[str, ...] = QUEUE_LABELS) -> str:
    title = f"Watchlist: {item.get('repo', '')}"
    body = issue_body_yaml(item)
    return f"{repo_url.rstrip('/')}/issues/new?{urlencode({'title': title, 'body': body, 'labels': ','.join(labels)})}"


def issue_body_yaml(item: dict[str, Any]) -> str:
    payload = {
        "repo": item.get("repo", ""),
        "html_url": item.get("html_url", ""),
        "source_report": item.get("source_report", ""),
        "source_section": item.get("source_section", ""),
        "recommended_action": item.get("recommended_action", ""),
        "topics": item.get("topics", []),
        "radar_score": item.get("radar_score"),
        "llm_adjusted_score": item.get("llm_adjusted_score"),
        "quality_gate": item.get("quality_gate", ""),
        "reason": item.get("reason", ""),
    }
    return yaml.safe_dump(payload, allow_unicode=True, sort_keys=False).strip()


def parse_issue_body(body: str) -> dict[str, Any]:
    payload = yaml.safe_load(body or "") or {}
    if not isinstance(payload, dict):
        return {}
    return payload
