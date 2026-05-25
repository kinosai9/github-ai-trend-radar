"""Local inbox backed by GitHub watchlist issues."""

from __future__ import annotations

import json
import shutil
import subprocess
import webbrowser
from pathlib import Path
from typing import Any

from rich.console import Console

from github_ai_trend_radar.storage.files import save_json, load_json
from github_ai_trend_radar.watchlist import add_watch_item
from github_ai_trend_radar.watchlist_queue import parse_issue_body


def _run_gh(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def sync_inbox(repo: str, *, output_path: str | Path = "data/inbox/watchlist_issues.json") -> tuple[bool, str, list[dict[str, Any]]]:
    gh = shutil.which("gh")
    if not gh:
        return False, "GitHub CLI not found. Please install GitHub CLI and run: gh auth login.", []
    auth = _run_gh([gh, "auth", "status"])
    if auth.returncode != 0:
        return False, "GitHub CLI is not logged in. Please run: gh auth login.", []
    cmd = [
        gh,
        "issue",
        "list",
        "--repo",
        repo,
        "--label",
        "watchlist",
        "--state",
        "open",
        "--json",
        "number,title,body,labels,url,createdAt",
    ]
    result = _run_gh(cmd)
    if result.returncode != 0:
        return False, result.stderr.strip() or result.stdout.strip(), []
    try:
        issues = json.loads(result.stdout or "[]")
    except json.JSONDecodeError as exc:
        preview = (result.stdout or result.stderr or "").strip()[:300]
        return False, f"Failed to parse GitHub CLI JSON output: {exc}. Output preview: {preview}", []
    parsed = [parse_issue(issue) for issue in issues]
    save_json({"repo": repo, "items": parsed}, output_path)
    return True, str(output_path), parsed


def parse_issue(issue: dict[str, Any]) -> dict[str, Any]:
    body = parse_issue_body(issue.get("body") or "")
    return {
        "number": issue.get("number"),
        "title": issue.get("title", ""),
        "url": issue.get("url", ""),
        "created_at": issue.get("createdAt", ""),
        "repo": body.get("repo", ""),
        "html_url": body.get("html_url", ""),
        "reason": body.get("reason", ""),
        "topics": body.get("topics", []) or [],
        "source_report": body.get("source_report", ""),
        "source_section": body.get("source_section", ""),
        "recommended_action": body.get("recommended_action", ""),
        "status": "pending",
    }


def load_inbox(path: str | Path = "data/inbox/watchlist_issues.json") -> list[dict[str, Any]]:
    target = Path(path)
    if not target.exists():
        return []
    payload = load_json(target)
    return payload.get("items", []) if isinstance(payload, dict) else []


def save_inbox_items(items: list[dict[str, Any]], path: str | Path = "data/inbox/watchlist_issues.json") -> Path:
    return save_json({"items": items}, path)


def interactive_inbox(
    *,
    inbox_path: str | Path = "data/inbox/watchlist_issues.json",
    watchlist_path: str | Path = "data/watchlist.yaml",
    console: Console | None = None,
    deep_research_callback=None,
) -> int:
    console = console or Console()
    items = load_inbox(inbox_path)
    pending = [item for item in items if item.get("status", "pending") == "pending"]
    if not pending:
        console.print("[yellow]No pending inbox items. Run inbox sync first.[/yellow]")
        return 0
    for item in pending:
        console.print(f"[bold]{item.get('repo')}[/bold] #{item.get('number')} {item.get('source_report')}")
        console.print(f"topics={item.get('topics', [])} action={item.get('recommended_action')} reason={item.get('reason')}")
        action = input("A/add, D/deep, S/skip, O/open, I/issue, Q/quit: ").strip().lower()
        if action in {"q", "quit"}:
            break
        if action in {"o", "open"} and item.get("html_url"):
            webbrowser.open(item["html_url"])
            continue
        if action in {"i", "issue"} and item.get("url"):
            webbrowser.open(item["url"])
            continue
        if action in {"s", "skip"}:
            item["status"] = "skipped"
            continue
        if action in {"a", "add", "d", "deep"}:
            add_watch_item(
                item.get("repo", ""),
                reason=item.get("reason", ""),
                priority="high" if item.get("recommended_action") in {"deep_research", "try_locally"} else "medium",
                topics=[str(topic) for topic in item.get("topics", [])],
                source_issue=item.get("number"),
                path=watchlist_path,
            )
            item["status"] = "added"
            if action in {"d", "deep"} and deep_research_callback:
                deep_research_callback(item.get("repo", ""))
                item["status"] = "researched"
    save_inbox_items(items, inbox_path)
    return 0
