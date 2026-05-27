"""Comparable project selection for local deep research."""

from __future__ import annotations

from typing import Any


def find_comparable_projects(
    context: dict[str, Any],
    ecosystem_context: dict[str, Any],
    *,
    max_comparables: int = 5,
    project_archetype: dict[str, Any] | None = None,
) -> dict[str, Any]:
    target_repo = context.get("repo", "")
    target = _target_project(context, ecosystem_context)
    direct = []
    adjacent = []
    excluded = []
    for project in ecosystem_context.get("notable_projects", []) or []:
        if not isinstance(project, dict) or not project.get("repo") or project.get("repo") == target_repo:
            continue
        comparable_type, reason, overlaps, differences = _comparable_type(project, context, ecosystem_context, project_archetype=project_archetype)
        enriched = dict(project)
        enriched["comparable_type"] = comparable_type
        enriched["overlap_dimensions"] = overlaps
        enriched["difference_dimensions"] = differences
        if comparable_type == "excluded":
            enriched["reason_excluded"] = reason
            excluded.append(enriched)
            continue
        enriched["reason_selected"] = reason
        if comparable_type == "direct":
            direct.append(enriched)
        else:
            adjacent.append(enriched)
    direct_comparables = [_comparable_from_project(project, context, ecosystem_context) for project in direct[:max_comparables]]
    adjacent_comparables = [_comparable_from_project(project, context, ecosystem_context) for project in adjacent[:max_comparables]]
    rows = [_table_row(item) for item in [target] + direct_comparables]
    if len(direct_comparables) < 2 and adjacent_comparables:
        rows.extend(_table_row(item) for item in _prioritize_adjacent_for_table(adjacent_comparables)[: 2 - len(direct_comparables)])
    return {
        "comparables": direct_comparables + adjacent_comparables,
        "direct_comparables": direct_comparables,
        "adjacent_comparables": adjacent_comparables,
        "excluded_comparables": excluded[:20],
        "table": {
            "columns": ["项目", "定位", "核心能力", "成熟度/热度", "企业可控性", "主要风险", "适合我司的使用方式"],
            "rows": rows[: max_comparables + 1],
        },
        "note": _comparison_note(project_archetype, direct_comparables, adjacent_comparables),
        "filtered_weak_projects": [{"repo": item.get("repo"), "reason": item.get("reason_excluded")} for item in excluded[:20]],
    }


def _target_project(context: dict[str, Any], ecosystem_context: dict[str, Any]) -> dict[str, Any]:
    metadata = context.get("metadata", {}) if isinstance(context.get("metadata"), dict) else {}
    return {
        "repo": context.get("repo") or metadata.get("full_name") or "",
        "positioning": f"目标项目 / {ecosystem_context.get('primary_domain', 'other')}",
        "capabilities": metadata.get("description") or "待结合 README 与源码判断",
        "maturity": _maturity_label(metadata.get("stargazers_count") or 0, metadata.get("pushed_at")),
        "control": _control_label(metadata.get("license"), context.get("readme", "")),
        "risk": "需验证实际架构、权限边界、部署方式和维护活跃度",
        "usage": "作为专项 PoC 目标，优先验证企业数据隔离、可维护性和二开成本",
    }


def _comparable_from_project(project: dict[str, Any], context: dict[str, Any], ecosystem_context: dict[str, Any]) -> dict[str, Any]:
    topics = project.get("topics", []) or []
    return {
        "repo": project.get("repo", ""),
        "html_url": project.get("html_url", ""),
        "comparable_type": project.get("comparable_type", "adjacent"),
        "reason_selected": project.get("reason_selected") or "同主题/同生态候选",
        "reason_excluded": project.get("reason_excluded", ""),
        "overlap_dimensions": project.get("overlap_dimensions", []),
        "difference_dimensions": project.get("difference_dimensions", []),
        "positioning": _positioning(project, ecosystem_context),
        "capabilities": project.get("description") or _capability_from_topics(topics),
        "maturity": _maturity_label(project.get("stars") or 0, project.get("pushed_at")),
        "control": "需复核许可证与部署方式",
        "risk": _risk_label(project, context),
        "usage": _usage_label(project, ecosystem_context),
        "strengths": _strengths(project),
        "weaknesses": _weaknesses(project),
    }


def _table_row(item: dict[str, Any]) -> list[str]:
    name = item.get("repo", "")
    if item.get("html_url"):
        name = f"[{name}]({item.get('html_url')})"
    return [
        name,
        f"{item.get('positioning', '')} / {item.get('comparable_type', 'target')}",
        item.get("capabilities", ""),
        item.get("maturity", ""),
        item.get("control", ""),
        item.get("risk", ""),
        item.get("usage", ""),
    ]


def _comparison_note(project_archetype: dict[str, Any] | None, direct: list[dict[str, Any]], adjacent: list[dict[str, Any]]) -> str:
    if (project_archetype or {}).get("primary") == "gui_agent" and len(direct) < 2:
        return "直接开源竞品样本不足，本报告采用 direct + adjacent 两层对比；adjacent 仅作生态参考，不作为功能替代品。browser-use 更偏 Web automation；UI-TARS 更偏 desktop / GUI / multimodal / operator；ChromeDevTools MCP 更偏 browser debugging / coding-agent tool surface。"
    return "P2.3 基于 GitHub Search 与历史趋势雷达快照生成同类项目对比；结论仍需结合源码和许可证复核。"


def _prioritize_adjacent_for_table(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        items,
        key=lambda item: (
            0 if "chromedevtools" in str(item.get("repo", "")).lower() or "devtools" in str(item.get("description", "")).lower() else 1,
            -int(item.get("stars") or 0),
        ),
    )


def _positioning(project: dict[str, Any], ecosystem_context: dict[str, Any]) -> str:
    source = project.get("source", "")
    domain = ecosystem_context.get("primary_domain", "other")
    if "trend_snapshot" in str(source):
        return f"{domain} 趋势候选"
    return f"{domain} 同类开源项目"


def _capability_from_topics(topics: list[str]) -> str:
    if not topics:
        return "需阅读 README 进一步判断"
    return "围绕 " + "、".join(str(topic) for topic in topics[:4]) + " 的开源能力"


def _maturity_label(stars: Any, pushed_at: Any) -> str:
    try:
        star_count = int(stars or 0)
    except (TypeError, ValueError):
        star_count = 0
    if star_count >= 10000:
        level = "成熟高热"
    elif star_count >= 1000:
        level = "较成熟"
    elif star_count >= 100:
        level = "早期可观察"
    else:
        level = "早期信号"
    return f"{level} / Star {star_count} / 最近更新 {pushed_at or '未知'}"


def _control_label(license_data: Any, readme: str) -> str:
    text = str(readme).lower()
    license_name = ""
    if isinstance(license_data, dict):
        license_name = str(license_data.get("spdx_id") or license_data.get("name") or "")
    elif license_data:
        license_name = str(license_data)
    deployment = "具备私有化线索" if any(word in text for word in ("self-hosted", "docker", "local deploy", "on-prem")) else "部署可控性待验证"
    return f"{license_name or '许可证待确认'} / {deployment}"


def _risk_label(project: dict[str, Any], context: dict[str, Any]) -> str:
    target_language = (context.get("metadata", {}) or {}).get("language")
    language = project.get("language")
    if target_language and language and language != target_language:
        return "技术栈不同，迁移/集成成本需单独评估"
    if int(project.get("stars") or 0) < 100:
        return "社区信号偏早期，需验证维护连续性"
    return "需复核许可证、部署边界和企业权限审计能力"


def _usage_label(project: dict[str, Any], ecosystem_context: dict[str, Any]) -> str:
    domain = ecosystem_context.get("primary_domain", "other")
    if domain == "mcp":
        return "作为 MCP 能力、协议实现或工具生态参照"
    if domain == "coding_agent":
        return "作为 Coding Agent 工作流或插件生态参照"
    if domain == "rag_knowledge":
        return "作为知识库/RAG 技术路线对照"
    return "作为同类方案的能力边界和工程成熟度参照"


def _comparable_type(
    project: dict[str, Any],
    context: dict[str, Any],
    ecosystem_context: dict[str, Any],
    *,
    project_archetype: dict[str, Any] | None = None,
) -> tuple[str, str, list[str], list[str]]:
    text = " ".join(
        [
            str(project.get("repo", "")),
            str(project.get("description", "")),
            " ".join(str(topic) for topic in project.get("topics", []) or []),
        ]
    ).lower()
    if any(noise in text for noise in ("awesome", "prompt", "plugin directory", "skill bundle", "game agent", "api router", "notebooklm", "cybersecurity skill", "wallpaper", "generic router")):
        return "excluded", "过滤：更像列表/插件目录/泛工具，非目标项目直接竞品。", [], ["项目定位不重合"]
    archetype = (project_archetype or {}).get("primary") or ecosystem_context.get("primary_domain")
    if archetype == "gui_agent":
        direct_terms = ("browser-use", "browser use", "computer use", "computer-use", "gui agent", "desktop agent", "ui automation", "browser agent", "operator", "vision agent")
        adjacent_terms = ("mcp", "devtools", "agent runtime", "agent framework", "tool server", "browser automation", "desktop automation")
        overlaps = [term for term in direct_terms + adjacent_terms if term in text]
        if sum(1 for term in direct_terms if term in text) >= 1 and any(term in text for term in ("agent", "automation", "operator", "browser", "desktop", "computer")):
            return "direct", "同为 GUI Agent / Computer Use / browser-desktop automation 方向。", overlaps or ["GUI Agent"], ["需复核权限边界、模型 provider 和执行稳定性"]
        if any(term in text for term in adjacent_terms):
            return "adjacent", "相邻方向：MCP/browser tooling 或 Agent runtime 生态参照。", overlaps, ["不是完整 GUI Agent 桌面执行栈"]
        return "excluded", "过滤：缺少 GUI Agent / Computer Use / browser automation 重合点。", [], ["与桌面自动化执行链路不重合"]
    direct_terms = ("code knowledge graph", "codebase graph", "repository knowledge graph", "code graph", "repo map", "codebase rag", "graphrag code")
    adjacent_terms = ("coding agent memory", "code intelligence", "claude code context", "codex context", "agent memory", "graph rag", "knowledge graph")
    overlaps = [term for term in direct_terms + adjacent_terms if term in text]
    if sum(1 for term in direct_terms if term in text) >= 2 or ("code" in text and "graph" in text and ("repo" in text or "codebase" in text)):
        return "direct", "同为代码库知识图谱 / repo context / GraphRAG code 方向。", overlaps or ["代码知识图谱"], ["需复核实现深度与企业部署方式"]
    if any(term in text for term in adjacent_terms):
        return "adjacent", "相邻方向：Coding Agent 上下文增强或知识图谱能力。", overlaps, ["不是直接代码图谱竞品"]
    primary = ecosystem_context.get("primary_domain")
    if primary in {"rag_knowledge", "coding_agent"} and any(term in text for term in ("rag", "graph", "code", "agent", "context")):
        return "adjacent", "相邻方向，不是直接竞品。", ["RAG/Graph/Agent"], ["方向相邻但定位不完全重合"]
    if primary == "mcp" and any(term in text for term in ("mcp", "model context protocol", "server", "client")):
        return "adjacent", "相邻方向：MCP 工具或协议生态参照。", ["MCP"], ["不是代码知识图谱竞品"]
    return "excluded", "过滤：与目标项目的代码知识图谱 / repo context 方向相关性不足。", [], ["缺少 code graph / repo context / coding agent context 重合点"]


def _strengths(project: dict[str, Any]) -> list[str]:
    strengths = []
    if int(project.get("stars") or 0) >= 1000:
        strengths.append("社区关注度较高")
    if project.get("description"):
        strengths.append("定位描述清晰")
    if project.get("topics"):
        strengths.append("GitHub topics 较完整")
    return strengths or ["具备同主题参照价值"]


def _weaknesses(project: dict[str, Any]) -> list[str]:
    weaknesses = ["未做源码级验证"]
    if int(project.get("stars") or 0) < 100:
        weaknesses.append("Star 较低")
    if not project.get("pushed_at"):
        weaknesses.append("缺少最近更新信息")
    return weaknesses
