"""GitHub Search API collector for topic recall."""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import requests

from github_ai_trend_radar.storage.files import save_json, snapshot_path


LOGGER = logging.getLogger(__name__)

GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"
DEFAULT_USER_AGENT = "github-ai-trend-radar/0.1"
PUSHED_WINDOW_DAYS = {
    "daily": 30,
    "weekly": 60,
    "monthly": 120,
}


@dataclass(frozen=True)
class SearchSourceStatus:
    ok: bool
    error: str | None = None
    status_code: int | None = None
    raw_snapshot: str | None = None


def pushed_after_for_period(period: str, *, now: datetime | None = None) -> str:
    try:
        days = PUSHED_WINDOW_DAYS[period]
    except KeyError as exc:
        raise ValueError(f"Unsupported period: {period!r}") from exc
    current = now or datetime.now(UTC)
    return (current - timedelta(days=days)).date().isoformat()


def build_search_queries(
    topic_name: str,
    topic_config: dict[str, Any],
    period: str,
    *,
    max_queries_per_topic: int = 3,
    now: datetime | None = None,
) -> list[str]:
    pushed_after = pushed_after_for_period(period, now=now)
    qualifiers = f"archived:false fork:false pushed:>{pushed_after}"

    queries: list[str] = []
    for query in topic_config.get("include_queries", [])[: max(max_queries_per_topic - 1, 0)]:
        queries.append(f"{query} {qualifiers}")

    github_topics = topic_config.get("github_topics", [])
    if github_topics and len(queries) < max_queries_per_topic:
        queries.append(f"topic:{github_topics[0]} {qualifiers}")

    if not queries:
        queries.append(f"{topic_name.replace('_', '-')} {qualifiers}")

    return queries[:max_queries_per_topic]


def _headers() -> dict[str, str]:
    token = os.getenv("GH_PAT") or os.getenv("GITHUB_TOKEN")
    if not token:
        LOGGER.warning("GH_PAT/GITHUB_TOKEN is missing; GitHub Search will use the low anonymous rate limit")
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": DEFAULT_USER_AGENT,
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _matched_keywords(item: dict[str, Any], topic_config: dict[str, Any]) -> list[str]:
    haystack = " ".join(
        [
            str(item.get("name") or ""),
            str(item.get("full_name") or ""),
            str(item.get("description") or ""),
            " ".join(item.get("topics") or []),
        ]
    ).lower()
    return [keyword for keyword in topic_config.get("keywords", []) if keyword.lower() in haystack]


def _is_excluded(item: dict[str, Any], topic_config: dict[str, Any]) -> bool:
    haystack = f"{item.get('full_name') or ''} {item.get('description') or ''}".lower()
    return any(keyword.lower() in haystack for keyword in topic_config.get("exclude_keywords", []))


def _candidate_from_item(
    item: dict[str, Any],
    *,
    topic_name: str,
    matched_keywords: list[str],
    search_query: str,
    rank: int,
) -> dict[str, Any]:
    return {
        "repo_full_name": item.get("full_name") or "",
        "html_url": item.get("html_url") or "",
        "description": item.get("description") or "",
        "source_hits": ["github_search"],
        "matched_focus_topics": [topic_name],
        "matched_keywords": matched_keywords,
        "search_query": search_query,
        "github_search_rank": rank,
        "metrics": {
            key: value
            for key, value in {
                "stars": item.get("stargazers_count"),
                "forks": item.get("forks_count"),
                "open_issues": item.get("open_issues_count"),
                "github_search_rank": rank,
            }.items()
            if value is not None
        },
        "metadata": {
            key: value
            for key, value in {
                "owner": (item.get("owner") or {}).get("login") if isinstance(item.get("owner"), dict) else None,
                "repo": item.get("name"),
                "full_name": item.get("full_name"),
                "language": item.get("language"),
                "topics": item.get("topics") or [],
                "archived": item.get("archived"),
                "fork": item.get("fork"),
                "created_at": item.get("created_at"),
                "pushed_at": item.get("pushed_at"),
                "default_branch": item.get("default_branch"),
            }.items()
            if value is not None
        },
        "readme_excerpt": "",
    }


def collect_github_search(
    topics: dict[str, dict[str, Any]],
    period: str,
    *,
    snapshot_dir: Path | str = "data/snapshots",
    timeout: float = 20,
    pages_per_query: int = 2,
    per_page: int = 50,
    max_queries_per_topic: int = 3,
    sort: str = "stars",
    session: requests.Session | None = None,
) -> tuple[list[dict[str, Any]], Path, SearchSourceStatus]:
    http = session or requests.Session()
    headers = _headers()
    raw_entries: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    rank = 0

    for topic_name, topic_config in topics.items():
        queries = build_search_queries(
            topic_name,
            topic_config,
            period,
            max_queries_per_topic=max_queries_per_topic,
        )
        for query in queries:
            for page in range(1, pages_per_query + 1):
                params = {
                    "q": query,
                    "sort": sort,
                    "order": "desc",
                    "per_page": min(per_page, 100),
                    "page": page,
                }
                try:
                    response = http.get(GITHUB_SEARCH_URL, headers=headers, params=params, timeout=timeout)
                    status_code = response.status_code
                    try:
                        payload: dict[str, Any] = response.json()
                    except ValueError:
                        payload = {"text": response.text}
                    raw_entries.append(
                        {
                            "topic": topic_name,
                            "query": query,
                            "page": page,
                            "status_code": status_code,
                            "url": response.url,
                            "payload": payload,
                        }
                    )
                    if status_code in (403, 429):
                        message = str(payload.get("message") or "")
                        if response.headers.get("X-RateLimit-Remaining") == "0" or "rate limit" in message.lower():
                            raw_path = snapshot_path(snapshot_dir, period, "github-search-raw")
                            save_json(raw_entries, raw_path)
                            return (
                                candidates,
                                raw_path,
                                SearchSourceStatus(False, "rate_limit_exhausted", status_code, str(raw_path)),
                            )
                    response.raise_for_status()
                except requests.RequestException as exc:
                    raw_entries.append(
                        {
                            "topic": topic_name,
                            "query": query,
                            "page": page,
                            "status_code": getattr(getattr(exc, "response", None), "status_code", None),
                            "error": str(exc),
                        }
                    )
                    LOGGER.warning("GitHub Search request failed for %s page %s: %s", query, page, exc)
                    continue

                for item in payload.get("items", []):
                    if not isinstance(item, dict) or _is_excluded(item, topic_config):
                        continue
                    rank += 1
                    candidates.append(
                        _candidate_from_item(
                            item,
                            topic_name=topic_name,
                            matched_keywords=_matched_keywords(item, topic_config),
                            search_query=query,
                            rank=rank,
                        )
                    )
                time.sleep(0.1)

    raw_path = snapshot_path(snapshot_dir, period, "github-search-raw")
    save_json(raw_entries, raw_path)
    return candidates, raw_path, SearchSourceStatus(True, None, 200, str(raw_path))
