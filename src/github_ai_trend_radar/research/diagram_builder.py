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
    diagrams = {
        "architecture": build_architecture_diagram(context, repo_structure, architecture, project_archetype=project_archetype),
        "mindmap": build_mindmap(context, enterprise_fit),
    }
    if (project_archetype or {}).get("primary") == "gui_agent":
        diagrams.update(
            {
                "gui_execution_flow": build_gui_execution_flow_diagram(context, architecture),
                "gui_security_boundary": build_gui_security_boundary_diagram(context, architecture),
                "gui_module_map": build_gui_module_map_diagram(context, repo_structure, architecture),
            }
        )
    if (project_archetype or {}).get("primary") == "code_knowledge_graph":
        diagrams.update(
            {
                "code_graph_build_flow": build_code_graph_build_flow_diagram(context, architecture),
                "code_graph_security_boundary": build_code_graph_security_boundary_diagram(context, architecture),
                "code_graph_module_map": build_code_graph_module_map_diagram(context, repo_structure, architecture),
            }
        )
    return diagrams


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
    return build_gui_execution_flow_diagram(context, architecture)


def build_gui_execution_flow_diagram(context: dict[str, Any], architecture: dict[str, Any]) -> str:
    repo = context.get("repo", "target repo")
    chain = architecture.get("gui_agent_chain", {}) if isinstance(architecture.get("gui_agent_chain"), dict) else {}
    labels = {stage.get("name"): stage.get("module") or "待验证" for stage in chain.get("stages", []) if isinstance(stage, dict)}
    app = labels.get("Desktop App / CLI / Web UI", _first_core(architecture, ("apps/ui-tars", "cli", "ui")))
    runtime = labels.get("Agent Runtime / Planner", _first_core(architecture, ("agent-tars", "tarko", "planner", "runtime")))
    provider = labels.get("Model Provider / VLM / LLM Client", _first_core(architecture, ("model-provider", "llm-client", "provider")))
    env = labels.get("Environment Adapters", _first_core(architecture, ("operator", "environment", "browser", "desktop")))
    parser = labels.get("Action Parser", _first_core(architecture, ("action-parser", "parser")))
    executor = labels.get("Operator / Executor", _first_core(architecture, ("operator", "executor", "nutjs", "adb")))
    store = labels.get("State / Logs / Store", _first_core(architecture, ("store", "log", "snapshot", "state")))
    return f"""flowchart LR
  User["用户任务"] --> App["Desktop App / CLI / Web UI\\n{app}"]

  subgraph Runtime["Agent Runtime"]
    Planner["Planner / Task Loop\\n{runtime}"]
    Env["Environment Adapters\\n{env}"]
  end

  subgraph Model["Model Layer"]
    VLM["VLM / LLM Provider\\n{provider}"]
    Guard["Provider Isolation\\n企业需验证"]
  end

  subgraph Action["Action Layer"]
    Parser["Action Parser\\n{parser}"]
    Operator["Operator / Executor\\n{executor}"]
  end

  subgraph Target["受控执行环境"]
    Browser["Browser"]
    Desktop["Desktop"]
    Terminal["Terminal"]
    FS["Filesystem"]
  end

  App --> Planner
  Planner --> VLM
  VLM --> Parser
  Parser --> Operator
  Operator --> Browser
  Operator --> Desktop
  Operator --> Terminal
  Operator --> FS
  Target --> Env
  Env --> Planner
  Operator --> Store["Feedback / Logs / Store\\n{store}"]
  Store --> Planner
  Repo["{repo}"] -. source .-> App
"""


def build_gui_security_boundary_diagram(context: dict[str, Any], architecture: dict[str, Any]) -> str:
    tools = _first_core(architecture, ("mcp", "tool", "pdk"))
    executor = _first_core(architecture, ("operator", "executor", "nutjs", "adb"))
    provider = _first_core(architecture, ("model-provider", "llm-client", "provider"))
    store = _first_core(architecture, ("store", "log", "snapshot", "state"))
    return f"""flowchart LR
  subgraph Inputs["输入与上下文"]
    Screenshot["Screenshot / OCR / UI State"]
    Prompt["User Prompt / Task Context"]
  end

  subgraph ModelBoundary["模型与数据边界"]
    Provider["Model Provider\\n{provider}"]
    ProviderGuard["Provider Isolation\\n私有模型 / 企业批准模型"]
  end

  subgraph ToolBoundary["工具权限边界"]
    Tools["MCP / Tools\\n{tools}"]
    Permission["Tool Permission Boundary\\n白名单 / 参数审计"]
    Approval["Human Approval Checkpoint\\n高危操作人工确认"]
  end

  subgraph Execution["高危执行面"]
    Executor["Operator / Executor\\n{executor}"]
    Shell["Shell"]
    Browser["Browser"]
    FS["Filesystem"]
    Desktop["Desktop"]
  end

  subgraph Audit["审计与脱敏"]
    Logs["Audit Logs / Redaction\\n{store}"]
    Secrets["Secret / Path / Screenshot Redaction\\n企业需补强"]
  end

  Screenshot --> Provider
  Prompt --> Provider
  ProviderGuard -. governs .-> Provider
  Provider --> Tools
  Permission -. governs .-> Tools
  Tools --> Executor
  Approval -. interrupts .-> Executor
  Executor --> Shell
  Executor --> Browser
  Executor --> FS
  Executor --> Desktop
  Executor --> Logs
  Secrets -. governs .-> Logs
"""


def build_gui_module_map_diagram(context: dict[str, Any], repo_structure: dict[str, Any], architecture: dict[str, Any]) -> str:
    modules = architecture.get("core_modules", []) if isinstance(architecture.get("core_modules"), list) else []
    lookup = {str(item.get("path", "")): str(item.get("role", "")) for item in modules if isinstance(item, dict)}

    def role(path: str, fallback: str) -> str:
        for key, value in lookup.items():
            if key.startswith(path) or path in key:
                return value or fallback
        monorepo = repo_structure.get("monorepo_structure", {}) if isinstance(repo_structure.get("monorepo_structure"), dict) else {}
        info = monorepo.get(path, {}) if isinstance(monorepo.get(path), dict) else {}
        return str(info.get("role") or fallback)

    return f"""flowchart TB
  Repo["bytedance/UI-TARS-desktop\\nTypeScript Monorepo"]

  subgraph Apps["应用层"]
    UITars["apps/ui-tars\\n{role('apps/ui-tars', 'Electron desktop application shell')}"]
  end

  subgraph Runtime["Agent Runtime 层"]
    AgentTars["multimodal/agent-tars\\n{role('multimodal/agent-tars', 'Agent runtime / CLI / environments')}"]
    Tarko["multimodal/tarko\\n{role('multimodal/tarko', 'Model provider / agent server / snapshot')}"]
  end

  subgraph GuiSdk["GUI Agent SDK 层"]
    GuiAgent["multimodal/gui-agent\\n{role('multimodal/gui-agent', 'Action parser / operators / SDK')}"]
    Parser["action-parser"]
    Operators["operator-adb / browser / nutjs / aio"]
  end

  subgraph Extension["扩展与工具层"]
    PDK["infra/pdk\\n{role('infra/pdk', 'Plugin/development toolkit')}"]
    MCP["MCP / Tools\\n权限与审计需复核"]
  end

  Repo --> UITars
  Repo --> AgentTars
  Repo --> GuiAgent
  Repo --> Tarko
  Repo --> PDK
  UITars --> AgentTars
  AgentTars --> Tarko
  AgentTars --> GuiAgent
  GuiAgent --> Parser
  GuiAgent --> Operators
  AgentTars --> MCP
  PDK -. supports .-> MCP
"""


def build_code_graph_build_flow_diagram(context: dict[str, Any], architecture: dict[str, Any]) -> str:
    repo = context.get("repo", "target repo")
    stages = _pipeline_stages(architecture)
    labels = {stage.get("name"): stage.get("module") or "待验证" for stage in stages if isinstance(stage, dict)}
    parser = labels.get("parser / extractor", _first_core(architecture, ("parser", "tree-sitter", "extract")))
    graph = labels.get("graph builder", _first_core(architecture, ("graph", "node", "edge", "builder")))
    storage = labels.get("cache / incremental update", _first_core(architecture, ("store", "cache", "index", "sqlite", "neo4j")))
    query = labels.get("query / affected analysis", _first_core(architecture, ("query", "search", "rag", "context")))
    output = labels.get("wiki / html / json 输出", _first_core(architecture, ("wiki", "html", "json", "export", "mcp")))
    return f"""flowchart LR
  subgraph BuildFlow["Code Knowledge Graph 构建链路"]
    Repo["Repo / Source Files\\n{repo}"]
    Parser["Parser / Tree-sitter\\n{parser}"]
    Symbols["Symbol / Dependency Extraction"]
    Graph["Graph Builder\\n{graph}"]
    Store["Graph Store / Cache\\n{storage}"]
    Query["Query / RAG / Agent Context\\n{query}"]
    Output["Coding Agent / Wiki / JSON / MCP\\n{output}"]
  end
  Repo --> Parser --> Symbols --> Graph --> Store --> Query --> Output
"""


def build_code_graph_security_boundary_diagram(context: dict[str, Any], architecture: dict[str, Any]) -> str:
    storage = _first_core(architecture, ("store", "cache", "index", "sqlite", "neo4j"))
    query = _first_core(architecture, ("query", "search", "rag", "context", "mcp"))
    return f"""flowchart TB
  subgraph CodeInput["代码输入边界"]
    Repo["Repository Files"]
    Secrets["Secret / Path / Comment Redaction\\n企业需验证"]
  end
  subgraph IndexBoundary["索引与存储边界"]
    LocalIndex["Local Graph Index / Cache\\n{storage}"]
    Retention["Retention / Deletion Consistency\\n企业需验证"]
  end
  subgraph QueryBoundary["查询与权限边界"]
    Query["Graph Query / Repo Context\\n{query}"]
    ACL["Repo / Team / Branch ACL\\n企业需补强"]
  end
  subgraph AgentBoundary["Agent 调用边界"]
    Agent["Claude Code / Codex / RAG / MCP"]
    Guard["Prompt Injection / Data Exfiltration Guard\\n企业需补强"]
  end
  Repo --> LocalIndex
  LocalIndex --> Query
  Query --> Agent
"""


def build_code_graph_module_map_diagram(context: dict[str, Any], repo_structure: dict[str, Any], architecture: dict[str, Any]) -> str:
    parser = _first_core(architecture, ("parser", "tree-sitter", "extract"))
    graph = _first_core(architecture, ("graph", "node", "edge", "builder"))
    storage = _first_core(architecture, ("store", "cache", "index", "sqlite", "neo4j"))
    query = _first_core(architecture, ("query", "search", "rag", "context"))
    output = _first_core(architecture, ("wiki", "html", "json", "mcp", "export"))
    return f"""flowchart TB
  subgraph ParseLayer["源码解析层"]
    Parser["{parser}"]
    TreeSitter["tree-sitter / language parser\\n如存在"]
  end
  subgraph GraphLayer["图谱构建层"]
    Graph["{graph}"]
    Relations["symbols / dependencies / call graph"]
  end
  subgraph StoreLayer["存储与查询层"]
    Store["{storage}"]
    Query["{query}"]
  end
  subgraph IntegrationLayer["Agent / RAG 接入层"]
    Output["{output}"]
    Agent["Coding Agent / GraphRAG / Repo Context"]
  end
  Parser --> Graph
  Graph --> Store
  Store --> Output
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
