"""Normalize collector responses into the public candidate schema."""

from __future__ import annotations

import re
from typing import Any


GITHUB_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def normalize_repo_full_name(value: str | None = None, *, owner: str | None = None, repo: str | None = None) -> str:
    if owner and repo:
        return f"{owner.strip()}/{repo.strip()}".strip("/")

    if not value:
        return ""

    full_name = value.strip()
    full_name = re.sub(r"^https?://github\.com/", "", full_name, flags=re.IGNORECASE)
    full_name = re.sub(r"^git@github\.com:", "", full_name, flags=re.IGNORECASE)
    full_name = full_name.removesuffix(".git")
    full_name = full_name.strip("/")

    parts = [part for part in full_name.split("/") if part]
    if len(parts) >= 2:
        return f"{parts[0]}/{parts[1]}"

    return full_name


def split_repo_full_name(full_name: str) -> tuple[str, str]:
    normalized = normalize_repo_full_name(full_name)
    if not GITHUB_REPO_RE.match(normalized):
        raise ValueError(f"Invalid GitHub repo full name: {full_name!r}")
    owner, repo = normalized.split("/", 1)
    return owner, repo


def full_name_from_ossinsight_item(item: dict[str, Any]) -> str:
    for key in (
        "repo_full_name",
        "full_name",
        "repo_name",
        "repository",
        "name",
        "html_url",
        "url",
    ):
        value = item.get(key)
        if isinstance(value, str):
            normalized = normalize_repo_full_name(value)
            if "/" in normalized:
                return normalized

    owner = item.get("owner") or item.get("owner_login") or item.get("org") or item.get("org_login")
    repo = item.get("repo") or item.get("repository_name") or item.get("repo_name")
    if isinstance(owner, str) and isinstance(repo, str):
        return normalize_repo_full_name(owner=owner, repo=repo)

    return ""


def _license_name(license_payload: Any) -> str | None:
    if isinstance(license_payload, dict):
        return license_payload.get("spdx_id") or license_payload.get("key") or license_payload.get("name")
    if isinstance(license_payload, str):
        return license_payload
    return None


def _number(value: Any) -> int | float | None:
    if isinstance(value, int | float):
        return value
    if isinstance(value, str):
        text = value.strip().replace(",", "")
        if not text:
            return None
        try:
            if "." in text:
                return float(text)
            return int(text)
        except ValueError:
            return None
    return None


def normalize_candidate(
    full_name: str,
    *,
    source_item: dict[str, Any] | None = None,
    repo_metadata: dict[str, Any] | None = None,
    readme_text: str = "",
) -> dict[str, Any]:
    source_item = source_item or {}
    repo_metadata = repo_metadata or {}

    repo_full_name = normalize_repo_full_name(repo_metadata.get("full_name") or full_name)
    html_url = repo_metadata.get("html_url") or source_item.get("html_url") or f"https://github.com/{repo_full_name}"

    metrics = {
        "stars": repo_metadata.get("stargazers_count") or _number(source_item.get("stars")),
        "forks": repo_metadata.get("forks_count") or _number(source_item.get("forks")),
        "open_issues": repo_metadata.get("open_issues_count"),
    }
    metrics.update(
        {
            key: number
            for key, value in source_item.items()
            if (number := _number(value)) is not None and key not in metrics
        }
    )
    fallback_owner, fallback_repo = ("", "")
    if "/" in repo_full_name:
        fallback_owner, fallback_repo = repo_full_name.split("/", 1)

    metadata = {
        "owner": (
            repo_metadata.get("owner", {}).get("login")
            if isinstance(repo_metadata.get("owner"), dict)
            else fallback_owner
        ),
        "repo": repo_metadata.get("name") or fallback_repo,
        "full_name": repo_metadata.get("full_name") or repo_full_name,
        "language": repo_metadata.get("language") or source_item.get("primary_language") or source_item.get("language"),
        "topics": repo_metadata.get("topics") or [],
        "license": _license_name(repo_metadata.get("license")),
        "archived": repo_metadata.get("archived"),
        "fork": repo_metadata.get("fork"),
        "created_at": repo_metadata.get("created_at"),
        "pushed_at": repo_metadata.get("pushed_at"),
        "default_branch": repo_metadata.get("default_branch"),
    }

    return {
        "repo_full_name": repo_full_name,
        "html_url": html_url,
        "description": repo_metadata.get("description") or source_item.get("description") or "",
        "source_hits": ["ossinsight"],
        "metrics": {key: value for key, value in metrics.items() if value is not None},
        "metadata": {key: value for key, value in metadata.items() if value is not None},
        "readme_excerpt": readme_text[:12000],
    }
