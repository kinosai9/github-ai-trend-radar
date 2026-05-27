"""Shared research data helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ResearchOptions:
    repo: str
    depth: str = "standard"
    profile: str = "enterprise_ai_service"
    compare: bool = False
    clone: bool = False
    max_files: int = 80
    max_issues: int = 50
    max_comparables: int = 5
    output_dir: Path = Path("data/research")
    private: bool = True


def repo_slug(repo: str) -> str:
    return repo.replace("/", "__")
