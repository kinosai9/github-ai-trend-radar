"""Repository structure analysis."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any


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
    return {"pyproject.toml", "requirements.txt", "package.json", "Cargo.toml", "go.mod", "pom.xml", "Dockerfile"}
