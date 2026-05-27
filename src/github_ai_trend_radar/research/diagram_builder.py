"""Mermaid diagram builders for deep research reports."""

from __future__ import annotations

from typing import Any


def build_diagrams(context: dict[str, Any], repo_structure: dict[str, Any], architecture: dict[str, Any], enterprise_fit: dict[str, Any]) -> dict[str, str]:
    return {
        "architecture": build_architecture_diagram(context, repo_structure, architecture),
        "mindmap": build_mindmap(context, enterprise_fit),
    }


def build_architecture_diagram(context: dict[str, Any], repo_structure: dict[str, Any], architecture: dict[str, Any]) -> str:
    repo = context.get("repo", "target repo")
    stages = _pipeline_stages(architecture)
    labels = {stage["name"]: stage.get("module") or "待验证" for stage in stages}
    entry = _label(architecture.get("entrypoints", []) or architecture.get("likely_entrypoints", []), "入口待验证")
    asset = labels.get("输入资产", "repository files")
    detection = labels.get("资产检测 / language detection", "language detection 待验证")
    parser = labels.get("parser / extractor", "parser/extractor 待验证")
    graph = labels.get("graph builder", "graph builder 待验证")
    cache = labels.get("cache / incremental update", "cache/incremental update 待验证")
    query = labels.get("query / affected analysis", "query/affected analysis 待验证")
    output = labels.get("wiki / html / json 输出", "wiki/html/json 输出待验证")
    integration = _integration_label(architecture)
    return f"""flowchart TD
  Input["输入资产\\n{asset}"] --> Entry["{repo}\\n{entry}"]
  Entry --> Detect["资产检测 / language detection\\n{detection}"]
  Detect --> Parser["parser / extractor\\n{parser}"]
  Parser --> Graph["graph builder\\n{graph}"]
  Graph --> Cache["cache / incremental update\\n{cache}"]
  Cache --> Query["query / affected analysis\\n{query}"]
  Query --> Output["wiki / html / json 输出\\n{output}"]
  Output --> Assistant["Claude Code / Codex / MCP 集成\\n{integration}"]
  Assistant --> Existing["企业工作流 / Claude Code / Codex / MCP / RAG"]
"""


def build_mindmap(context: dict[str, Any], enterprise_fit: dict[str, Any]) -> str:
    repo = context.get("repo", "repo")
    risk = enterprise_fit.get("final_rating", {}).get("risk_level", "unknown")
    return f"""mindmap
  root(({repo}))
    技术能力
      核心模块
      API/CLI
      扩展点
    企业落地
      私有化部署
      数据安全
      权限审计
    风险
      成熟度
      维护状态
      风险等级: {risk}
"""


def _paths_for_role(architecture: dict[str, Any], keyword: str) -> list[str]:
    roles = architecture.get("module_roles", {}) if isinstance(architecture.get("module_roles"), dict) else {}
    return [path for path, role in roles.items() if keyword in str(role).lower()]


def _pipeline_stages(architecture: dict[str, Any]) -> list[dict[str, Any]]:
    graph_pipeline = architecture.get("graph_pipeline", {})
    if isinstance(graph_pipeline, dict):
        stages = graph_pipeline.get("stages", [])
        return [stage for stage in stages if isinstance(stage, dict)]
    return []


def _integration_label(architecture: dict[str, Any]) -> str:
    integrations = architecture.get("integrations", [])
    if isinstance(integrations, list) and integrations:
        return "\\n".join(f"{item.get('type')}: {item.get('module')}" for item in integrations[:3] if isinstance(item, dict))[:180]
    return "企业系统集成边界待验证"


def _label(items: Any, fallback: str) -> str:
    if not items:
        return fallback
    if isinstance(items, dict):
        items = [str(item.get("path") or item.get("module") or item) if isinstance(item, dict) else str(item) for item in items.keys()]
    if not isinstance(items, list):
        return str(items)[:80]
    normalized = [str(item.get("path") or item.get("module") or item) if isinstance(item, dict) else str(item) for item in items]
    return "\\n".join(normalized[:3])[:180]
