"""Deterministic wording cleanup for deep research reports."""

from __future__ import annotations


REPLACEMENTS = {
    "私密化": "私有化",
    "短期不和投资": "短期不建议投入规模化工程资源",
    "回购可先作为": "可先作为",
    "回购可先": "可先",
    "依赖完全本地化部署": "需要受控或本地化部署",
    "本报告基于 LLM 分阶段分析做综合判断": "本报告基于仓库资料、源码结构、issue/PR 证据和企业落地约束综合判断",
    "基于 README、目录结构、入口模块和 LLM 分阶段分析做综合判断": "基于仓库资料、源码结构、issue/PR 证据和企业落地约束综合判断",
}


def polish_report_text(text: str) -> str:
    cleaned = str(text or "")
    for source, target in REPLACEMENTS.items():
        cleaned = cleaned.replace(source, target)
    return cleaned
