"""Repository structure analysis."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Any

import yaml

DOC_HINTS = ("doc", "docs", "documentation")
EXAMPLE_HINTS = ("example", "examples", "demo", "sample", "samples")
TEST_HINTS = ("test", "tests", "spec", "specs")
DEPLOY_HINTS = ("dockerfile", "docker-compose", ".github/workflows", "helm", "k8s", "kubernetes")
CONFIG_SUFFIXES = (".toml", ".yaml", ".yml", ".json", ".ini", ".cfg", ".conf", ".env.example")


def analyze_repo_structure(context: dict[str, Any], *, clone_path: str | Path | None = None) -> dict[str, Any]:
    files = list(context.get("files") or [])
    if clone_path:
        local_files = _local_files(Path(clone_path))
        if local_files:
            files = local_files
    counts = Counter(Path(path).suffix.lower() or Path(path).name.lower() for path in files)
    monorepo = _monorepo_structure(files, Path(clone_path) if clone_path else None)
    return {
        "main_languages": _language_hints(files, context.get("metadata", {})),
        "file_type_counts": dict(counts.most_common(20)),
        "important_paths": _important_paths(files),
        "entrypoints": _entrypoints(files),
        "config_files": [path for path in files if path.lower().endswith(CONFIG_SUFFIXES)][:50],
        "docs_paths": _match(files, DOC_HINTS)[:50],
        "examples_paths": _match(files, EXAMPLE_HINTS)[:50],
        "tests_paths": _match(files, TEST_HINTS)[:50],
        "deployment_files": _match(files, DEPLOY_HINTS)[:50],
        "package_files": [path for path in files if Path(path).name in set(context.get("package_files", [])) or Path(path).name in _package_names()][:50],
        "monorepo_structure": monorepo,
        "workspace_packages": list(monorepo.keys()),
        "all_files": files[:5000],
        "total_files_analyzed": len(files),
    }


def _local_files(root: Path) -> list[str]:
    if not root.exists():
        return []
    paths: list[str] = []
    for path in root.rglob("*"):
        if path.is_file() and ".git" not in path.parts:
            paths.append(str(path.relative_to(root)).replace("\\", "/"))
    return sorted(paths)


def _language_hints(files: list[str], metadata: dict[str, Any]) -> list[str]:
    primary = metadata.get("language")
    ext_map = {".py": "Python", ".ts": "TypeScript", ".js": "JavaScript", ".go": "Go", ".rs": "Rust", ".java": "Java", ".cs": "C#"}
    hints = [primary] if primary else []
    for ext, language in ext_map.items():
        if any(path.endswith(ext) for path in files) and language not in hints:
            hints.append(language)
    return hints[:5]


def _important_paths(files: list[str]) -> list[str]:
    names = {"README.md", "pyproject.toml", "package.json", "Dockerfile", "docker-compose.yml", "Makefile", "LICENSE"}
    return [path for path in files if Path(path).name in names or path.startswith((".github/workflows/", "docs/", "examples/"))][:80]


def _entrypoints(files: list[str]) -> list[str]:
    suffixes = ("main.py", "__main__.py", "cli.py", "app.py", "server.py", "index.ts", "index.js", "main.ts", "main.go")
    return [path for path in files if path.lower().endswith(suffixes)][:30]


def _match(files: list[str], hints: tuple[str, ...]) -> list[str]:
    return [path for path in files if any(hint in path.lower() for hint in hints)]


def _package_names() -> set[str]:
    return {"pyproject.toml", "requirements.txt", "package.json", "pnpm-workspace.yaml", "turbo.json", "Cargo.toml", "go.mod", "pom.xml", "Dockerfile"}


def _monorepo_structure(files: list[str], root: Path | None) -> dict[str, dict[str, Any]]:
    candidates = set()
    for path in files:
        parts = Path(path).parts
        if len(parts) >= 2 and parts[0] in {"apps", "packages", "multimodal", "infra"}:
            if Path(path).name == "package.json":
                candidates.add("/".join(parts[:-1]).replace("\\", "/"))
            elif len(parts) >= 3 and parts[0] in {"apps", "packages", "infra"}:
                candidates.add("/".join(parts[:2]).replace("\\", "/"))
            elif len(parts) >= 3 and parts[0] == "multimodal":
                candidates.add("/".join(parts[:3]).replace("\\", "/"))
    for workspace in _workspace_globs(root):
        for path in files:
            if _matches_workspace(path, workspace):
                parts = Path(path).parts
                if Path(path).name == "package.json":
                    candidates.add("/".join(parts[:-1]).replace("\\", "/"))
    result: dict[str, dict[str, Any]] = {}
    for candidate in sorted(candidates):
        related = [path for path in files if path == candidate or path.startswith(candidate + "/")]
        package_json = f"{candidate}/package.json"
        role, evidence = _workspace_role(candidate, related, root)
        result[candidate] = {
            "role": role,
            "evidence": evidence,
            "package_json": package_json if package_json in files else "",
            "key_files": _workspace_key_files(related)[:12],
            "file_count": len(related),
        }
    return result


def _workspace_globs(root: Path | None) -> list[str]:
    if not root:
        return []
    globs: list[str] = []
    package_json = root / "package.json"
    if package_json.exists():
        try:
            data = json.loads(package_json.read_text(encoding="utf-8", errors="replace"))
            workspaces = data.get("workspaces", []) if isinstance(data, dict) else []
            if isinstance(workspaces, dict):
                workspaces = workspaces.get("packages", [])
            globs.extend(str(item) for item in workspaces if isinstance(item, str))
        except Exception:
            pass
    workspace_yaml = root / "pnpm-workspace.yaml"
    if workspace_yaml.exists():
        try:
            data = yaml.safe_load(workspace_yaml.read_text(encoding="utf-8", errors="replace")) or {}
            globs.extend(str(item) for item in data.get("packages", []) if isinstance(item, str))
        except Exception:
            pass
    return globs


def _matches_workspace(path: str, pattern: str) -> bool:
    prefix = pattern.replace("\\", "/").rstrip("/")
    if prefix.endswith("/*"):
        base = prefix[:-2]
        return path.startswith(base + "/")
    return path.startswith(prefix + "/") or path == prefix


def _workspace_key_files(paths: list[str]) -> list[str]:
    names = ("package.json", "src/index.ts", "src/main.ts", "src/index.tsx", "src/main.tsx", "src/cli.ts", "README.md")
    key = [path for path in paths if any(path.endswith(name) for name in names)]
    key.extend(path for path in paths if any(term in path.lower() for term in ("action-parser", "operator", "provider", "mcp", "ipc", "preload", "main.ts", "window", "store")))
    return sorted(dict.fromkeys(key))


def _workspace_role(path: str, files: list[str], root: Path | None) -> tuple[str, list[str]]:
    text = path.lower() + " " + " ".join(files[:200]).lower()
    package_name = ""
    package_json = root / path / "package.json" if root else None
    if package_json and package_json.exists():
        try:
            data = json.loads(package_json.read_text(encoding="utf-8", errors="replace"))
            package_name = str(data.get("name") or "")
            text += " " + package_name.lower() + " " + " ".join(str(k) for k in (data.get("scripts") or {}).keys()).lower()
        except Exception:
            pass
    rules = (
        ("Electron desktop application shell", ("apps/ui-tars", "electron", "preload", "ipc", "renderer", "desktop")),
        ("Agent runtime / CLI / environments", ("agent-tars", "agent runtime", "environment", "agent-cli", "agent-server", "tarko")),
        ("GUI agent SDK / action parser", ("gui-agent", "action-parser", "operator", "browser", "nutjs", "adb")),
        ("Model provider integration", ("model-provider", "llm-client", "provider", "openai", "anthropic")),
        ("MCP / tool integration", ("mcp", "tool", "server")),
        ("Plugin/development toolkit", ("infra/pdk", "pdk", "plugin", "commands")),
        ("Benchmark / evaluation", ("benchmark", "eval")),
    )
    for role, keywords in rules:
        hits = [keyword for keyword in keywords if keyword in text]
        if hits:
            return role, [f"workspace:{path}", f"package:{package_name}" if package_name else "", f"matched:{', '.join(hits[:4])}"]
    return "Workspace package / role pending validation", [f"workspace:{path}", f"package:{package_name}" if package_name else ""]
