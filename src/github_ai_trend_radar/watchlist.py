"""Local watchlist store."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


def load_watchlist(path: str | Path = "data/watchlist.yaml") -> dict[str, Any]:
    target = Path(path)
    if not target.exists():
        return {"items": []}
    payload = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        return {"items": []}
    payload.setdefault("items", [])
    return payload


def save_watchlist(payload: dict[str, Any], path: str | Path = "data/watchlist.yaml") -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return target


def add_watch_item(
    repo: str,
    *,
    reason: str = "",
    priority: str = "medium",
    topics: list[str] | None = None,
    source_issue: int | None = None,
    path: str | Path = "data/watchlist.yaml",
) -> dict[str, Any]:
    payload = load_watchlist(path)
    now = datetime.now().isoformat(timespec="seconds")
    topics = topics or []
    for item in payload["items"]:
        if item.get("repo", "").lower() == repo.lower():
            item.update({"last_seen": now, "status": "active"})
            if reason:
                item["reason"] = reason
            if priority:
                item["priority"] = priority
            if topics:
                item["topics"] = sorted(set(item.get("topics", []) + topics))
            if source_issue:
                item["source_issue"] = source_issue
            save_watchlist(payload, path)
            return item
    item = {
        "repo": repo,
        "status": "active",
        "priority": priority,
        "topics": topics,
        "reason": reason,
        "created_at": now,
        "last_seen": now,
    }
    if source_issue:
        item["source_issue"] = source_issue
    payload["items"].append(item)
    save_watchlist(payload, path)
    return item


def archive_watch_item(repo: str, *, path: str | Path = "data/watchlist.yaml") -> bool:
    payload = load_watchlist(path)
    found = False
    for item in payload["items"]:
        if item.get("repo", "").lower() == repo.lower():
            item["status"] = "archived"
            item["archived_at"] = datetime.now().isoformat(timespec="seconds")
            found = True
    save_watchlist(payload, path)
    return found
