"""Local deep research report generation."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from github_ai_trend_radar.collectors.github_repo import GitHubRepoClient


def write_deep_research_report(repo: str, *, output_dir: str | Path = "data/research", client: GitHubRepoClient | None = None) -> tuple[Path, Path]:
    owner, name = repo.split("/", 1)
    client = client or GitHubRepoClient()
    details: dict[str, Any] = {}
    readme = ""
    try:
        details = client.get_repo(owner, name)
    except Exception as exc:
        details = {"full_name": repo, "error": str(exc)}
    try:
        readme = client.get_readme(owner, name)[:16000]
    except Exception:
        readme = ""
    root = Path(output_dir) / repo.replace("/", "__")
    root.mkdir(parents=True, exist_ok=True)
    day = date.today().isoformat()
    md = root / f"{day}-research.md"
    html = root / f"{day}-research.html"
    markdown = _markdown(repo, details, readme)
    md.write_text(markdown, encoding="utf-8")
    html.write_text(_html(repo, markdown), encoding="utf-8")
    return md, html


def _markdown(repo: str, details: dict[str, Any], readme: str) -> str:
    return f"""# {repo} 本地深研

## 基础信息

- GitHub: {details.get('html_url', f'https://github.com/{repo}')}
- 描述: {details.get('description', '')}
- 语言: {details.get('language', '')}
- Star: {details.get('stargazers_count', '')}
- Fork: {details.get('forks_count', '')}
- Open Issues: {details.get('open_issues_count', '')}
- License: {(details.get('license') or {}).get('spdx_id', '') if isinstance(details.get('license'), dict) else details.get('license', '')}
- 最近更新: {details.get('pushed_at', '')}

## README 摘要材料

```text
{readme[:12000] or 'README 获取失败或为空。'}
```

## 初步判断

- 该报告为本地资料汇总版。
- 如果配置了 LLM，可在后续版本生成更完整的技术价值、风险和落地建议。
"""


def _html(repo: str, markdown: str) -> str:
    import html

    return f"<!doctype html><html lang='zh-CN'><meta charset='utf-8'><title>{html.escape(repo)} 本地深研</title><body><pre>{html.escape(markdown)}</pre></body></html>"
