"""Rule-based architecture analysis for local research."""

from __future__ import annotations

import json
import re
import ast
from pathlib import Path
from typing import Any


EXCLUDED_CORE_PREFIXES = ("tests/", "test/", "fixtures/", "examples/", "example/", "docs/", "doc/", ".github/", "build/", "dist/")
SOURCE_PREFIXES = ("src/", "lib/", "packages/", "pkg/", "app/", "apps/")
GRAPH_KEYWORDS = ("graph", "node", "edge", "tree-sitter", "treesitter", "parser", "extractor", "index", "embedding", "rag", "neo4j", "networkx")


def analyze_code_architecture(
    context: dict[str, Any],
    repo_structure: dict[str, Any],
    *,
    clone_path: str | Path | None = None,
    project_archetype: dict[str, Any] | None = None,
) -> dict[str, Any]:
    files = context.get("files", [])
    readme = str(context.get("readme", "")).lower()
    root = Path(clone_path) if clone_path else None
    package_entrypoints = _package_entrypoints(root) if root else []
    core_paths = _core_modules(files)
    module_facts = [_module_fact(path, root=root) for path in core_paths]
    core_modules = [_core_module_from_fact(fact) for fact in module_facts]
    workspace_modules = _workspace_core_modules(repo_structure)
    core_modules = _dedupe_core_modules(workspace_modules + core_modules)
    archetype = (project_archetype or {}).get("primary", "unknown")
    graph_pipeline = _graph_pipeline(files, readme, core_modules, archetype=archetype)
    execution_chain = _gui_agent_chain(core_modules, files) if archetype == "gui_agent" else {}
    integrations = _integrations(files, core_modules)
    entrypoints = _entrypoints(package_entrypoints, repo_structure.get("entrypoints", []), module_facts)
    return {
        "entrypoints": entrypoints,
        "likely_entrypoints": [item["path"] for item in entrypoints],
        "core_modules": core_modules,
        "module_roles": {item["path"]: item["role"] for item in core_modules},
        "data_flow": _data_flow_hint(readme),
        "graph_pipeline": graph_pipeline,
        "gui_agent_chain": execution_chain,
        "integrations": integrations,
        "monorepo_structure": repo_structure.get("monorepo_structure", {}),
        "integration_points": [item["module"] for item in integrations],
        "storage_outputs": _keyword_paths(files, ("neo4j", "sqlite", "graphml", "json", "markdown", "wiki", "storage", "database", "db")),
        "extension_points": _keyword_paths(files, ("plugin", "extension", "adapter", "provider", "tool", "skill")),
        "external_dependencies": repo_structure.get("package_files", []),
        "llm_provider_integration": _keyword_paths(files, ("openai", "anthropic", "llm", "model", "provider")),
        "storage_integration": _keyword_paths(files, ("postgres", "sqlite", "redis", "vector", "database", "storage", "db")),
        "api_surface": _keyword_paths(files, ("api", "router", "routes", "server", "controller")),
        "cli_surface": _keyword_paths(files, ("cli", "command", "__main__")),
        "cli_commands": [item["path"] for item in entrypoints if "cli" in item.get("role", "").lower() or "entrypoint" in item.get("role", "").lower()],
        "config_surface": _keyword_paths(files, ("config", "settings", ".env", "yaml", "toml", "json")),
        "security_sensitive_paths": _keyword_paths(files, ("auth", "token", "secret", "key", "credential", "permission", "acl")),
        "excluded_paths": {
            "tests": [path for path in files if path.lower().startswith(("tests/", "test/"))][:50],
            "examples": [path for path in files if path.lower().startswith(("examples/", "example/", "worked/example/"))][:50],
            "fixtures": [path for path in files if "fixtures/" in path.lower() or "/raw/" in path.lower()][:50],
            "docs": [path for path in files if path.lower().startswith(("docs/", "doc/"))][:50],
        },
        "tests_and_fixtures": [path for path in files if _is_excluded_core(path)][:50],
        "security_boundary": _security_hint(readme, files),
    }


def _core_modules(files: list[str]) -> list[str]:
    code_files = [
        path
        for path in files
        if path.endswith((".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java"))
        and not _is_excluded_core(path)
    ]
    preferred = [
        path
        for path in code_files
        if path.startswith(SOURCE_PREFIXES)
        or any(keyword in path.lower() for keyword in ("graph", "parser", "extractor", "index", "pipeline", "storage", "mcp", "agent", "query"))
    ]
    fallback = [path for path in code_files if path.count("/") <= 3]
    return _dedupe(preferred + fallback)[:40]


def _workspace_core_modules(repo_structure: dict[str, Any]) -> list[dict[str, Any]]:
    modules = []
    monorepo = repo_structure.get("monorepo_structure", {})
    if not isinstance(monorepo, dict):
        return modules
    priority_terms = ("apps/ui-tars", "agent-tars", "gui-agent", "model-provider", "llm-client", "mcp", "infra/pdk", "tarko")
    for path, info in monorepo.items():
        if not isinstance(info, dict):
            continue
        role = info.get("role") or "Workspace package / role pending validation"
        if any(term in path.lower() or term in str(role).lower() for term in priority_terms):
            modules.append(
                {
                    "path": path,
                    "role": role,
                    "key_functions": [],
                    "dependencies": [],
                    "evidence": "; ".join(str(item) for item in info.get("evidence", []) if item),
                    "key_files": info.get("key_files", [])[:12],
                    "docstring": "",
                    "cli_command_registration": "",
                    "config_keys": [],
                }
            )
    return modules[:30]


def _dedupe_core_modules(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    result = []
    for item in items:
        path = item.get("path")
        if not path or path in seen:
            continue
        seen.add(path)
        result.append(item)
    return result[:50]


def _keyword_paths(files: list[str], keywords: tuple[str, ...]) -> list[str]:
    return [path for path in files if any(keyword in path.lower() for keyword in keywords)][:30]


def _data_flow_hint(readme: str) -> list[str]:
    hints = []
    for keyword in ("ingest", "retrieve", "search", "index", "query", "agent", "tool", "workflow"):
        if keyword in readme:
            hints.append(keyword)
    return hints


def _security_hint(readme: str, files: list[str]) -> list[str]:
    hints = []
    for keyword in ("auth", "permission", "token", "secret", "sandbox", "private", "self-hosted"):
        if keyword in readme or any(keyword in path.lower() for path in files):
            hints.append(keyword)
    return hints or ["未在轻量扫描中发现明确安全边界说明"]


def _is_excluded_core(path: str) -> bool:
    lower = path.lower().replace("\\", "/")
    return lower.startswith(EXCLUDED_CORE_PREFIXES) or "/fixtures/" in lower or "/tests/" in lower


def _module_roles(paths: list[str]) -> dict[str, str]:
    roles = {}
    role_keywords = {
        "parser/extractor": ("parser", "extract", "tree-sitter", "treesitter"),
        "graph pipeline": ("graph", "node", "edge", "pipeline"),
        "storage/output": ("storage", "db", "database", "neo4j", "sqlite", "export", "render"),
        "integration": ("mcp", "agent", "provider", "openai", "anthropic", "claude", "codex"),
        "cli/api": ("cli", "api", "server", "router", "command"),
    }
    for path in paths:
        lower = path.lower()
        roles[path] = next((role for role, keywords in role_keywords.items() if any(keyword in lower for keyword in keywords)), "core logic")
    return roles


def _graph_pipeline(files: list[str], readme: str, core_modules: list[dict[str, Any]], *, archetype: str = "unknown") -> dict[str, Any]:
    if archetype != "code_knowledge_graph":
        return {"stages": [], "confidence": "not_applicable", "reason": f"archetype={archetype}; graph pipeline template not applied"}
    stages = []
    text = readme + " " + " ".join(files).lower()
    steps = (
        ("输入资产", ("code", "docs", "schema", "asset"), "源码、文档、schema、静态资产"),
        ("资产检测 / language detection", ("detect", "language", "tree-sitter", "treesitter"), "识别语言和可解析资产"),
        ("parser / extractor", ("parser", "extract", "tree-sitter", "treesitter"), "解析符号、依赖和结构"),
        ("graph builder", ("graph", "node", "edge", "networkx", "build"), "构建代码知识图谱"),
        ("cache / incremental update", ("cache", "increment", "affected"), "缓存、增量更新和影响分析"),
        ("query / affected analysis", ("query", "search", "lookup", "affected"), "查询、检索或影响面分析"),
        ("wiki / html / json 输出", ("wiki", "html", "json", "render", "export"), "报告、wiki、HTML 或 JSON 输出"),
        ("AI assistant integration", ("mcp", "claude", "codex", "agent", "assistant"), "Claude Code / Codex / MCP 集成"),
    )
    for name, keywords, output in steps:
        module = _first_module_for_keywords(core_modules, keywords)
        if module or any(keyword in text for keyword in keywords):
            stages.append(
                {
                    "name": name,
                    "module": module.get("path", "待验证") if module else "待验证",
                    "input": "上游源码/结构化中间结果" if name != "输入资产" else "repository files",
                    "output": output,
                    "evidence": module.get("evidence", "README/path keyword") if module else "README/path keyword",
                }
            )
    return {"stages": stages, "confidence": "medium" if stages else "low"}


def _gui_agent_chain(core_modules: list[dict[str, Any]], files: list[str]) -> dict[str, Any]:
    steps = (
        ("User Task", ("apps/ui-tars", "agent-cli", "tarko")),
        ("Desktop App / CLI / Web UI", ("apps/ui-tars", "electron", "renderer", "agent-ui", "cli")),
        ("Agent Runtime / Planner", ("agent-tars", "tarko", "omni-agent", "planner")),
        ("Model Provider / VLM / LLM Client", ("model-provider", "llm-client", "provider", "vlm")),
        ("Environment Adapters", ("environment", "operator", "browser", "desktop", "terminal", "filesystem")),
        ("Action Parser", ("action-parser", "parser")),
        ("Operator / Executor", ("operator", "executor", "nutjs", "adb", "browser")),
        ("MCP / Tools", ("mcp", "tool")),
        ("State / Logs / Store", ("store", "state", "log", "snapshot")),
        ("Security Boundary", ("security", "permission", "secret", "auth", "safe")),
    )
    stages = []
    file_text = " ".join(files).lower()
    for name, keywords in steps:
        module = _first_module_for_keywords(core_modules, keywords)
        if module or any(keyword in file_text for keyword in keywords):
            stages.append(
                {
                    "name": name,
                    "module": module.get("path", "待验证") if module else "待验证",
                    "evidence": module.get("evidence", "path/package keyword") if module else "path/package keyword",
                }
            )
    return {"stages": stages, "confidence": "medium" if len(stages) >= 5 else "low"}


def _entrypoints(package_entrypoints: list[str], structure_entrypoints: list[str], module_facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for item in package_entrypoints:
        entries.append({"path": item, "evidence": "pyproject.toml/package.json script", "role": "CLI entrypoint"})
    for path in structure_entrypoints:
        if _is_excluded_core(path):
            continue
        entries.append({"path": path, "evidence": "filename convention", "role": "entrypoint candidate"})
    for fact in module_facts:
        if fact.get("has_main_guard") or "main" in fact.get("functions", []) or "cli" in fact["path"].lower():
            entries.append({"path": fact["path"], "evidence": "main guard/function or cli filename", "role": "CLI entrypoint"})
    return _dedupe_dicts(entries, "path")[:20]


def _module_fact(path: str, *, root: Path | None) -> dict[str, Any]:
    text = _read_text(root / path) if root else ""
    facts = {
        "path": path,
        "imports": [],
        "classes": [],
        "functions": [],
        "docstring": "",
        "has_main_guard": "__name__" in text and "__main__" in text,
        "constants": [],
        "source_excerpt": "\n".join(text.splitlines()[:120]) if text else "",
    }
    if path.endswith(".py") and text:
        try:
            tree = ast.parse(text)
            facts["docstring"] = ast.get_docstring(tree) or ""
            for node in tree.body:
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    module = getattr(node, "module", None)
                    facts["imports"].append(module or ",".join(alias.name for alias in node.names))
                elif isinstance(node, ast.ClassDef):
                    facts["classes"].append(node.name)
                elif isinstance(node, ast.FunctionDef):
                    facts["functions"].append(node.name)
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id.isupper():
                            facts["constants"].append(target.id)
        except SyntaxError:
            pass
    return facts


def _core_module_from_fact(fact: dict[str, Any]) -> dict[str, Any]:
    role, evidence = _role_from_fact(fact)
    return {
        "path": fact["path"],
        "role": role,
        "key_functions": fact.get("functions", [])[:8],
        "dependencies": fact.get("imports", [])[:10],
        "evidence": evidence,
        "docstring": str(fact.get("docstring", ""))[:240],
        "cli_command_registration": "main guard" if fact.get("has_main_guard") else "",
        "config_keys": fact.get("constants", [])[:10],
    }


def _role_from_fact(fact: dict[str, Any]) -> tuple[str, str]:
    path = fact["path"].lower()
    path_signal = Path(path).name.lower() + " " + " ".join(Path(path).parts[1:]).lower()
    words = " ".join([path_signal, " ".join(fact.get("functions", [])), " ".join(fact.get("classes", [])), str(fact.get("docstring", ""))]).lower()
    role_map = (
        ("Electron desktop application shell", ("electron", "renderer", "preload", "ipc", "window")),
        ("Agent runtime / planner", ("agent", "runtime", "planner", "environment")),
        ("GUI action parser / operator", ("action", "operator", "browser", "desktop", "nutjs", "adb")),
        ("Model provider / LLM client", ("model", "provider", "llm", "openai", "anthropic")),
        ("MCP / tool integration", ("mcp", "tool", "server")),
        ("parser/extractor", ("parser", "extract", "parse", "tree_sitter", "tree-sitter")),
        ("graph builder", ("graph", "node", "edge", "build", "networkx")),
        ("cache / incremental update", ("cache", "affected", "increment", "dedup")),
        ("query / affected analysis", ("query", "search", "lookup", "affected")),
        ("wiki / html / json output", ("wiki", "html", "json", "render", "export", "callflow")),
        ("integration", ("mcp", "claude", "codex", "agent", "assistant")),
        ("cli/api surface", ("__main__", "cli", "main", "api", "server")),
        ("configuration/security", ("config", "auth", "token", "secret", "credential")),
    )
    for role, keywords in role_map:
        if any(keyword in words for keyword in keywords):
            return role, f"matched keywords: {', '.join(keyword for keyword in keywords if keyword in words)[:120]}"
    return "unknown", "no strong role signal from path/functions/docstring"


def _integrations(files: list[str], core_modules: list[dict[str, Any]]) -> list[dict[str, str]]:
    items = []
    integration_terms = {
        "claude_code": ("claude",),
        "codex": ("codex",),
        "mcp": ("mcp",),
        "neo4j": ("neo4j",),
        "html": ("html",),
        "wiki": ("wiki",),
        "json": ("json",),
        "cache": ("cache",),
    }
    haystack_modules = [(item["path"], " ".join([item["path"], item.get("role", ""), item.get("evidence", "")]).lower()) for item in core_modules]
    for kind, terms in integration_terms.items():
        for module, text in haystack_modules:
            if any(term in text for term in terms):
                items.append({"type": kind, "module": module, "evidence": f"matched {kind} in module role/path"})
                break
    return items


def _first_module_for_keywords(core_modules: list[dict[str, Any]], keywords: tuple[str, ...]) -> dict[str, Any] | None:
    for module in core_modules:
        text = " ".join([module.get("path", ""), module.get("role", ""), " ".join(module.get("key_functions", [])), module.get("evidence", "")]).lower()
        if any(keyword in text for keyword in keywords):
            return module
    return None


def _package_entrypoints(root: Path) -> list[str]:
    entrypoints: list[str] = []
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        text = _read_text(pyproject)
        in_scripts = False
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("["):
                in_scripts = stripped in {"[project.scripts]", "[tool.poetry.scripts]"}
                continue
            if in_scripts and "=" in stripped:
                entrypoints.append(f"pyproject:{stripped}")
    package_json = root / "package.json"
    if package_json.exists():
        try:
            data = json.loads(_read_text(package_json))
            scripts = data.get("scripts", {}) if isinstance(data, dict) else {}
            for name, command in list(scripts.items())[:10]:
                entrypoints.append(f"package.json:{name}={command}")
            if data.get("bin"):
                entrypoints.append(f"package.json:bin={data.get('bin')}")
        except Exception:
            pass
    return entrypoints[:20]


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:20000]
    except Exception:
        return ""


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _dedupe_dicts(items: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    seen = set()
    result = []
    for item in items:
        value = item.get(key)
        if value and value not in seen:
            seen.add(value)
            result.append(item)
    return result
