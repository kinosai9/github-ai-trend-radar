"""Deduplicate and merge repository candidates from multiple sources."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from github_ai_trend_radar.processors.normalize import normalize_repo_full_name


def canonical_repo_key(candidate: dict[str, Any]) -> str:
    return normalize_repo_full_name(candidate.get("repo_full_name") or candidate.get("html_url") or "").lower()


def _merge_unique(left: list[Any], right: list[Any]) -> list[Any]:
    merged: list[Any] = []
    for value in [*left, *right]:
        if value not in merged:
            merged.append(value)
    return merged


def _merge_dict_fill(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    merged = dict(left)
    for key, value in right.items():
        if merged.get(key) in (None, "", [], {}):
            merged[key] = value
    return merged


def merge_candidates(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    merged = dict(left)
    merged["source_hits"] = _merge_unique(left.get("source_hits", []), right.get("source_hits", []))
    merged["matched_focus_topics"] = _merge_unique(
        left.get("matched_focus_topics", []),
        right.get("matched_focus_topics", []),
    )
    merged["matched_keywords"] = _merge_unique(left.get("matched_keywords", []), right.get("matched_keywords", []))

    if not merged.get("search_query") and right.get("search_query"):
        merged["search_query"] = right["search_query"]

    merged["metrics"] = _merge_dict_fill(left.get("metrics", {}), right.get("metrics", {}))
    merged["metadata"] = _merge_dict_fill(left.get("metadata", {}), right.get("metadata", {}))

    for key in ("repo_full_name", "html_url", "description"):
        if not merged.get(key) and right.get(key):
            merged[key] = right[key]

    if not merged.get("readme_excerpt") and right.get("readme_excerpt"):
        merged["readme_excerpt"] = right["readme_excerpt"]
    return merged


def _pushed_at(candidate: dict[str, Any]) -> datetime:
    value = candidate.get("metadata", {}).get("pushed_at")
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.min.replace(tzinfo=UTC)


def sort_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        candidates,
        key=lambda item: (
            len(item.get("source_hits", [])),
            item.get("metrics", {}).get("stars") or 0,
            _pushed_at(item),
        ),
        reverse=True,
    )


def dedupe_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_repo: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        key = canonical_repo_key(candidate)
        if not key:
            continue
        if key in by_repo:
            by_repo[key] = merge_candidates(by_repo[key], candidate)
        else:
            by_repo[key] = dict(candidate)
    return sort_candidates(list(by_repo.values()))
