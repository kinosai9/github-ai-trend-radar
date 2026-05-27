"""Project archetype routing for deep research."""

from __future__ import annotations

from typing import Any


ARCHETYPES = {
    "code_knowledge_graph": (
        "code knowledge graph",
        "graph rag",
        "graphrag",
        "repo map",
        "codebase graph",
        "tree-sitter",
        "treesitter",
        "knowledge graph",
    ),
    "gui_agent": (
        "gui-agent",
        "gui agent",
        "computer-use",
        "computer use",
        "browser-use",
        "browser use",
        "desktop agent",
        "ui automation",
        "vision",
        "vlm",
        "screenshot",
        "operator",
        "electron",
    ),
    "mcp_tooling": (
        "mcp-server",
        "mcp server",
        "model context protocol",
        "tool server",
        "devtools mcp",
        "mcp-client",
    ),
    "agent_runtime": (
        "agent runtime",
        "multi-agent",
        "agent framework",
        "planner",
        "environment",
        "tools",
        "agent-tars",
        "tarko",
    ),
    "llm_infra": (
        "gateway",
        "inference",
        "model provider",
        "llm client",
        "prompt cache",
    ),
    "rag_knowledge": (
        "rag",
        "vector",
        "embedding",
        "retrieval",
        "knowledge base",
    ),
}


def detect_project_archetype(
    context: dict[str, Any],
    repo_structure: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Detect the project's analysis template from stable repo signals."""

    metadata = context.get("metadata", {}) if isinstance(context.get("metadata"), dict) else {}
    files = context.get("files", []) or []
    if repo_structure and repo_structure.get("all_files"):
        files = repo_structure.get("all_files", files)
    text_parts = [
        str(context.get("repo") or metadata.get("full_name") or ""),
        str(metadata.get("description") or ""),
        " ".join(str(topic) for topic in metadata.get("topics", []) or []),
        str(context.get("readme") or "")[:12000],
        " ".join(str(path) for path in files[:1200]),
        " ".join(str(path) for path in (repo_structure or {}).get("package_files", []) or []),
    ]
    text = " ".join(text_parts).lower()
    scores: dict[str, int] = {}
    evidence: dict[str, list[str]] = {}
    for archetype, keywords in ARCHETYPES.items():
        hits = [keyword for keyword in keywords if keyword in text]
        path_hits = [path for path in files if any(keyword.replace(" ", "-") in str(path).lower() or keyword in str(path).lower() for keyword in keywords)]
        score = len(hits) * 2 + min(len(path_hits), 6)
        if score:
            scores[archetype] = score
            evidence[archetype] = [*hits[:6], *[f"path:{path}" for path in path_hits[:4]]]

    if not scores:
        return {"primary": "unknown", "secondary": [], "confidence": "low", "evidence": []}

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    primary = ranked[0][0]
    secondary = [name for name, score in ranked[1:] if score >= max(2, ranked[0][1] // 3)][:3]
    confidence = "high" if ranked[0][1] >= 8 else "medium" if ranked[0][1] >= 4 else "low"
    return {
        "primary": primary,
        "secondary": secondary,
        "confidence": confidence,
        "evidence": evidence.get(primary, [])[:10],
        "scores": scores,
    }
