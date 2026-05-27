"""GitHub data collection for local deep research."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from github_ai_trend_radar.collectors.github_repo import GitHubRepoClient


PACKAGE_FILE_NAMES = {
    "pyproject.toml",
    "requirements.txt",
    "package.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "package-lock.json",
    "Cargo.toml",
    "go.mod",
    "pom.xml",
    "build.gradle",
    "Dockerfile",
    "docker-compose.yml",
}


class ResearchCollector:
    def __init__(self, client: GitHubRepoClient | None = None) -> None:
        self.client = client or GitHubRepoClient(timeout=20, retries=2)

    def collect_project_context(
        self,
        owner: str,
        repo: str,
        *,
        max_files: int = 80,
        max_issues: int = 50,
    ) -> dict[str, Any]:
        metadata = self._safe(lambda: self.client.get_repo(owner, repo), default={})
        readme = self._safe(lambda: self.client.get_readme(owner, repo), default="")
        default_branch = metadata.get("default_branch") or "main"
        tree = self._safe(lambda: self._get_json(f"/repos/{owner}/{repo}/git/trees/{default_branch}?recursive=1"), default={})
        files = _prioritize_files(_tree_files(tree), max_files=max_files)
        package_files = [path for path in files if Path(path).name in PACKAGE_FILE_NAMES]
        return {
            "repo": f"{owner}/{repo}",
            "metadata": metadata,
            "readme": readme,
            "files": files,
            "package_files": package_files,
            "releases": self._safe(lambda: self._get_json(f"/repos/{owner}/{repo}/releases?per_page=5"), default=[]),
            "open_issues": self._safe(lambda: self._get_json(f"/repos/{owner}/{repo}/issues?state=open&per_page={max_issues}"), default=[]),
            "closed_issues": self._safe(lambda: self._get_json(f"/repos/{owner}/{repo}/issues?state=closed&per_page={max_issues}"), default=[]),
            "pull_requests": self._safe(lambda: self._get_json(f"/repos/{owner}/{repo}/pulls?state=all&per_page={min(max_issues, 30)}"), default=[]),
            "errors": [],
        }

    def clone_repo(self, repo: str, target_dir: Path) -> tuple[bool, str]:
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        if target_dir.exists() and (target_dir / ".git").exists():
            return True, str(target_dir)
        if target_dir.exists():
            return False, f"clone target exists but is not a git repository: {target_dir}"
        cmd = ["gh", "repo", "clone", repo, str(target_dir)]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
        except FileNotFoundError:
            return False, "GitHub CLI not found. Install gh or use --no-clone."
        except subprocess.TimeoutExpired:
            return False, "gh repo clone timed out."
        if result.returncode != 0:
            git_ok, git_message = self._git_clone_fallback(repo, target_dir)
            if git_ok:
                return True, git_message
            return False, (result.stderr.strip() or result.stdout.strip()) + f"\ngit fallback: {git_message}"
        return True, str(target_dir)

    def _git_clone_fallback(self, repo: str, target_dir: Path) -> tuple[bool, str]:
        cmd = ["git", "clone", "--depth", "1", f"https://github.com/{repo}.git", str(target_dir)]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240)
        except FileNotFoundError:
            return False, "git not found."
        except subprocess.TimeoutExpired:
            return False, "git clone timed out."
        if result.returncode != 0:
            return False, result.stderr.strip() or result.stdout.strip()
        return True, str(target_dir)

    def _get_json(self, path: str) -> Any:
        return self.client._get(path).json()

    @staticmethod
    def _safe(fn, *, default):
        try:
            return fn()
        except Exception:
            return default


def _tree_files(tree_payload: dict[str, Any]) -> list[str]:
    items = tree_payload.get("tree", []) if isinstance(tree_payload, dict) else []
    paths = [item.get("path", "") for item in items if item.get("type") == "blob" and item.get("path")]
    return sorted(paths)


def _prioritize_files(paths: list[str], *, max_files: int) -> list[str]:
    key_paths = sorted([path for path in paths if _is_key_path(path)], key=_path_priority)
    others = sorted([path for path in paths if path not in set(key_paths)], key=_path_priority)
    selected: list[str] = []
    for path in key_paths + others:
        if path not in selected:
            selected.append(path)
        if len(selected) >= max_files:
            break
    return selected


def _is_key_path(path: str) -> bool:
    lower = path.lower()
    name = Path(path).name
    return (
        name in PACKAGE_FILE_NAMES
        or name.lower().startswith(("readme", "license", "copying", "notice"))
        or lower.startswith(("src/", "lib/", "packages/", "pkg/", "app/"))
        or (any(keyword in lower for keyword in ("graph", "parser", "extract", "mcp", "agent", "cli", "api")) and lower.endswith((".py", ".ts", ".js", ".go", ".rs")))
        or lower.startswith(("docs/", "doc/", "examples/", "example/", "tests/", "test/", ".github/workflows/"))
        or lower in {"dockerfile", "docker-compose.yml", "compose.yml"}
    )


def _path_priority(path: str) -> tuple[int, str]:
    lower = path.lower()
    name = Path(path).name.lower()
    if name in {"pyproject.toml", "package.json", "requirements.txt", "go.mod", "cargo.toml"}:
        return (0, lower)
    if lower.startswith(("src/", "lib/", "packages/", "pkg/", "app/")):
        return (1, lower)
    if any(keyword in lower for keyword in ("graph", "parser", "extract", "mcp", "agent", "cli", "api")) and lower.endswith((".py", ".ts", ".js", ".go", ".rs")):
        return (2, lower)
    if lower.startswith(("tests/", "test/")):
        return (3, lower)
    if lower.startswith(("docs/translations/",)):
        return (8, lower)
    if lower.startswith(("docs/", "examples/", ".github/workflows/")):
        return (5, lower)
    return (6, lower)
