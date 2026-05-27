"""Mermaid diagram builders for deep research reports."""

from __future__ import annotations

from typing import Any


def build_diagrams(
    context: dict[str, Any],
    repo_structure: dict[str, Any],
    architecture: dict[str, Any],
    enterprise_fit: dict[str, Any],
    project_archetype: dict[str, Any] | None = None,
) -> dict[str, str]:
    return {
        "architecture": build_architecture_diagram(context, repo_structure, architecture, project_archetype=project_archetype),
        "mindmap": build_mindmap(context, enterprise_fit),
    }


def build_architecture_diagram(
    context: dict[str, Any],
    repo_structure: dict[str, Any],
    architecture: dict[str, Any],
    project_archetype: dict[str, Any] | None = None,
) -> str:
    if (project_archetype or {}).get("primary") == "gui_agent":
        return _gui_agent_diagram(context, architecture)
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


def _gui_agent_diagram(context: dict[str, Any], architecture: dict[str, Any]) -> str:
    repo = context.get("repo", "target repo")
    chain = architecture.get("gui_agent_chain", {}) if isinstance(architecture.get("gui_agent_chain"), dict) else {}
    labels = {stage.get("name"): stage.get("module") or "待验证" for stage in chain.get("stages", []) if isinstance(stage, dict)}
    app = labels.get("Desktop App / CLI / Web UI", _first_core(architecture, ("apps/ui-tars", "cli", "ui")))
    runtime = labels.get("Agent Runtime / Planner", _first_core(architecture, ("agent-tars", "tarko", "planner", "runtime")))
    provider = labels.get("Model Provider / VLM / LLM Client", _first_core(architecture, ("model-provider", "llm-client", "provider")))
    env = labels.get("Environment Adapters", _first_core(architecture, ("operator", "environment", "browser", "desktop")))
    parser = labels.get("Action Parser", _first_core(architecture, ("action-parser", "parser")))
    executor = labels.get("Operator / Executor", _first_core(architecture, ("operator", "executor", "nutjs", "adb")))
    tools = labels.get("MCP / Tools", _first_core(architecture, ("mcp", "tool")))
    store = labels.get("State / Logs / Store", _first_core(architecture, ("store", "log", "snapshot", "state")))
    security = labels.get("Security Boundary", "工具权限白名单 / 日志脱敏 / 人工确认断点 / 企业需补强")
    return f"""flowchart TD
  User["User Task / 人工目标"] --> UI["Desktop App / CLI / Web UI\\n{app}"]
  UI --> IPC["IPC / Preload / Renderer\\n企业需复核边界"]
  IPC --> Runtime["Agent Runtime / Planner\\n{runtime}"]
  Runtime --> Model["Model Provider / VLM / LLM Client\\n{provider}"]
  ModelGuard["Model Provider Isolation\\n企业需补强"] -. governs .-> Model
  Runtime --> Env["Environment Adapters\\n{env}"]
  Model --> Parser["Action Parser\\n{parser}"]
  Parser --> Executor["Operator / Executor\\n{executor}"]
  Executor --> Targets["Browser / Desktop / Terminal / Filesystem"]
  Runtime --> Tools["MCP / Tools\\n{tools}"]
  Executor --> Store["Feedback / Audit Logs / Redaction\\n{store}"]
  Approval["Human Approval / Interrupt Checkpoint\\n企业需补强"] -. interrupts .-> Executor
  Permission["Tool Permission Boundary\\n工具权限白名单 / 企业需补强"] -. governs .-> Tools
  Permission -. governs .-> Executor
  Security["Security Boundary\\n{security}"] -. governs .-> Env
  Security -. governs .-> Executor
  Store --> Runtime
  UI --> Repo["{repo}"]
"""


def _first_core(architecture: dict[str, Any], keywords: tuple[str, ...]) -> str:
    for item in architecture.get("core_modules", []) or []:
        if not isinstance(item, dict):
            continue
        text = " ".join([str(item.get("path", "")), str(item.get("role", "")), str(item.get("evidence", ""))]).lower()
        if any(keyword in text for keyword in keywords):
            return str(item.get("path") or item.get("role") or "待验证")[:120]
    return "待验证"


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
