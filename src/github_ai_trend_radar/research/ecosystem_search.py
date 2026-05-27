"""Ecosystem search helpers for local deep research."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote, urlencode
from typing import Any

from github_ai_trend_radar.storage.files import load_json


DOMAIN_QUERIES = {
    "mcp": ['"model context protocol"', '"mcp server"', '"mcp client"'],
    "ai_agent": ['"ai agent"', '"agent framework"', '"multi-agent" llm'],
    "coding_agent": ['"coding agent"', '"software engineering agent"', '"ai coding assistant"'],
    "rag_knowledge": ['"retrieval augmented generation"', '"graph rag"', '"knowledge base" llm'],
    "llm_infra": ['"llm inference"', '"model serving" llm', '"openai compatible"'],
    "vector_database": ['"vector database"', '"vector search" embedding', '"semantic search" database'],
}


def search_ecosystem_context(
    context: dict[str, Any],
    company_profile: dict[str, Any],
    *,
    client: Any | None = None,
    max_projects: int = 10,
    snapshot_dir: str | Path = "data/snapshots",
) -> dict[str, Any]:
    metadata = context.get("metadata", {}) if isinstance(context.get("metadata"), dict) else {}
    topics = metadata.get("topics", []) or []
    primary = _primary_domain(topics, context.get("readme", ""))
    target_repo = str(context.get("repo") or metadata.get("full_name") or "").lower()
    github_projects, search_errors = _github_search_projects(
        primary,
        topics,
        client=client,
        target_repo=target_repo,
        limit=max_projects,
    )
    snapshot_projects = _snapshot_projects(
        primary,
        topics,
        snapshot_dir=Path(snapshot_dir),
        target_repo=target_repo,
        limit=max_projects,
    )
    notable = _merge_projects(github_projects + snapshot_projects, limit=max_projects)
    market_stage = _market_stage(notable, topics)
    active_topics = _active_topics(topics, notable)
    return {
        "primary_domain": primary,
        "market_stage": market_stage,
        "active_topics": active_topics,
        "notable_projects": notable,
        "recent_dynamics": _recent_dynamics(primary, notable, search_errors),
        "target_project_position": _target_position(context, notable),
        "confidence": "medium" if notable else "low",
        "search_errors": search_errors,
        "sources": {
            "github_search_count": len(github_projects),
            "snapshot_count": len(snapshot_projects),
        },
    }


def _primary_domain(topics: list[str], readme: str) -> str:
    text = " ".join(topics).lower() + " " + str(readme).lower()[:4000]
    if "mcp" in text or "model context protocol" in text:
        return "mcp"
    if any(keyword in text for keyword in ("code knowledge graph", "codebase graph", "repository knowledge graph", "repo map", "codebase rag")):
        return "code_knowledge_graph"
    if "agent" in text:
        return "ai_agent"
    if "rag" in text or "retrieval" in text:
        return "rag_knowledge"
    if "vector" in text or "embedding" in text:
        return "vector_database"
    if "llm" in text or "inference" in text:
        return "llm_infra"
    return "other"


def _github_search_projects(
    primary_domain: str,
    topics: list[str],
    *,
    client: Any | None,
    target_repo: str,
    limit: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    if client is None or not hasattr(client, "_get"):
        return [], []
    queries = _queries_for_domain(primary_domain, topics)
    projects: list[dict[str, Any]] = []
    errors: list[str] = []
    for query in queries:
        if len(projects) >= limit:
            break
        params = urlencode(
            {
                "q": f"{query} archived:false fork:false",
                "sort": "stars",
                "order": "desc",
                "per_page": min(10, max(limit, 1)),
            },
            quote_via=quote,
        )
        try:
            response = client._get(f"/search/repositories?{params}")
            payload = response.json()
        except Exception as exc:
            errors.append(f"github_search_failed:{query}:{exc}")
            continue
        for item in payload.get("items", []) if isinstance(payload, dict) else []:
            if not isinstance(item, dict):
                continue
            full_name = str(item.get("full_name") or "")
            if not full_name or full_name.lower() == target_repo:
                continue
            projects.append(_project_from_github_item(item, query=query, source="github_search"))
            if len(projects) >= limit:
                break
    return projects, errors


def _queries_for_domain(primary_domain: str, topics: list[str]) -> list[str]:
    queries = list(DOMAIN_QUERIES.get(primary_domain) or [])
    if primary_domain in {"code_knowledge_graph", "rag_knowledge", "coding_agent"}:
        queries = [
            '"code knowledge graph"',
            '"codebase graph"',
            '"repository knowledge graph"',
            '"codebase RAG"',
            '"repo map" "code"',
            '"coding agent memory"',
            '"Claude Code" context',
            '"Codex" context',
        ] + queries
    for topic in topics[:3]:
        normalized = str(topic).strip()
        if normalized:
            queries.append(f"topic:{normalized}")
    return queries[:4] or ["llm"]


def _project_from_github_item(item: dict[str, Any], *, query: str, source: str) -> dict[str, Any]:
    return {
        "repo": item.get("full_name") or "",
        "html_url": item.get("html_url") or "",
        "description": item.get("description") or "",
        "stars": item.get("stargazers_count") or item.get("stars") or 0,
        "forks": item.get("forks_count") or item.get("forks") or 0,
        "language": item.get("language") or "",
        "topics": item.get("topics") or [],
        "pushed_at": item.get("pushed_at") or "",
        "source": source,
        "search_query": query,
        "reason_selected": "GitHub Search 同主题高热项目",
    }


def _snapshot_projects(
    primary_domain: str,
    topics: list[str],
    *,
    snapshot_dir: Path,
    target_repo: str,
    limit: int,
) -> list[dict[str, Any]]:
    if not snapshot_dir.exists():
        return []
    wanted = {primary_domain, *[str(topic).lower().replace("-", "_") for topic in topics]}
    projects: list[dict[str, Any]] = []
    for path in sorted(snapshot_dir.glob("*-*-scored.json"), reverse=True) + sorted(snapshot_dir.glob("*-*-llm-scored.json"), reverse=True):
        if len(projects) >= limit:
            break
        try:
            payload = load_json(path)
        except Exception:
            continue
        for candidate in payload.get("candidates", []) if isinstance(payload, dict) else []:
            if not isinstance(candidate, dict):
                continue
            repo = str(candidate.get("repo_full_name") or "")
            if not repo or repo.lower() == target_repo:
                continue
            matched = {str(t).lower() for t in candidate.get("matched_focus_topics", []) or []}
            candidate_topics = {str(t).lower().replace("-", "_") for t in (candidate.get("metadata", {}) or {}).get("topics", []) or []}
            if wanted.isdisjoint(matched | candidate_topics):
                continue
            projects.append(_project_from_snapshot(candidate, path))
            if len(projects) >= limit:
                break
    return projects


def _project_from_snapshot(candidate: dict[str, Any], path: Path) -> dict[str, Any]:
    metrics = candidate.get("metrics", {}) if isinstance(candidate.get("metrics"), dict) else {}
    metadata = candidate.get("metadata", {}) if isinstance(candidate.get("metadata"), dict) else {}
    return {
        "repo": candidate.get("repo_full_name") or metadata.get("full_name") or "",
        "html_url": candidate.get("html_url") or metadata.get("html_url") or "",
        "description": candidate.get("description") or "",
        "stars": metrics.get("stars") or metadata.get("stargazers_count") or 0,
        "forks": metrics.get("forks") or metadata.get("forks_count") or 0,
        "language": metadata.get("language") or "",
        "topics": metadata.get("topics") or [],
        "pushed_at": metadata.get("pushed_at") or candidate.get("pushed_at") or "",
        "source": "trend_snapshot",
        "source_snapshot": str(path),
        "radar_score": candidate.get("radar_score") or candidate.get("final_score"),
        "reason_selected": "历史趋势雷达同主题候选",
    }


def _merge_projects(projects: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for project in projects:
        repo = str(project.get("repo") or "").lower()
        if not repo:
            continue
        existing = merged.get(repo)
        if existing:
            existing["source"] = ",".join(sorted(set(str(existing.get("source", "")).split(",") + [str(project.get("source", ""))])))
            existing["radar_score"] = existing.get("radar_score") or project.get("radar_score")
            continue
        merged[repo] = project
    return sorted(
        merged.values(),
        key=lambda item: (float(item.get("radar_score") or 0), int(item.get("stars") or 0), str(item.get("pushed_at") or "")),
        reverse=True,
    )[:limit]


def _active_topics(target_topics: list[str], projects: list[dict[str, Any]]) -> list[str]:
    counts: dict[str, int] = {}
    for topic in target_topics:
        counts[str(topic)] = counts.get(str(topic), 0) + 2
    for project in projects:
        for topic in project.get("topics", []) or []:
            key = str(topic)
            counts[key] = counts.get(key, 0) + 1
    return [item[0] for item in sorted(counts.items(), key=lambda item: item[1], reverse=True)[:10]]


def _market_stage(projects: list[dict[str, Any]], topics: list[str]) -> str:
    if not projects:
        return "unclear"
    high_star = sum(1 for project in projects if int(project.get("stars") or 0) >= 5000)
    recent_signal = sum(1 for project in projects if str(project.get("source", "")).find("trend_snapshot") >= 0)
    if high_star >= 3 and recent_signal >= 2:
        return "mature"
    if recent_signal >= 3:
        return "rising"
    if len(projects) >= 6 and high_star < 2:
        return "fragmented"
    return "early" if len(projects) < 4 else "rising"


def _recent_dynamics(primary_domain: str, projects: list[dict[str, Any]], errors: list[str]) -> str:
    if not projects:
        suffix = "；GitHub Search 调用失败或没有足够候选。" if errors else "；未发现足够同类候选。"
        return f"{primary_domain} 方向当前生态信号不足{suffix}"
    snapshot_count = sum(1 for project in projects if "trend_snapshot" in str(project.get("source", "")))
    github_count = sum(1 for project in projects if "github_search" in str(project.get("source", "")))
    return f"{primary_domain} 方向识别到 {len(projects)} 个同类项目，其中 GitHub Search {github_count} 个、历史趋势雷达 {snapshot_count} 个。"


def _target_position(context: dict[str, Any], projects: list[dict[str, Any]]) -> str:
    metadata = context.get("metadata", {}) if isinstance(context.get("metadata"), dict) else {}
    stars = int(metadata.get("stargazers_count") or 0)
    if not projects:
        return "缺少横向参照，当前只能基于仓库资料做单点评估。"
    comparable_stars = [int(project.get("stars") or 0) for project in projects]
    median = sorted(comparable_stars)[len(comparable_stars) // 2]
    if stars >= median:
        return "目标项目在同类候选中具备一定社区热度，建议重点验证工程成熟度和企业可控性。"
    return "目标项目社区热度低于同类中位数，更适合作为早期技术信号观察，需谨慎投入。"
