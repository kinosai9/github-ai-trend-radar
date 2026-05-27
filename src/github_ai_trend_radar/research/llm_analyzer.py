"""Staged LLM analysis for local enterprise deep research."""

from __future__ import annotations

import re
from typing import Any

from github_ai_trend_radar.llm.client import LLMClient
from github_ai_trend_radar.llm.json_utils import parse_json_or_error


STAGES = (
    "repo_overview_summary",
    "code_architecture_summary",
    "negative_signal_summary",
    "comparison_summary",
    "enterprise_fit_summary",
    "final_report_synthesis",
)

STAGE_MAX_TOKENS = {
    "repo_overview_summary": 1200,
    "code_architecture_summary": 3200,
    "negative_signal_summary": 1200,
    "comparison_summary": 2200,
    "enterprise_fit_summary": 1800,
    "final_report_synthesis": 2200,
}


PROMPTS = {
    "repo_overview_summary": "你是企业 AI 工程尽调分析师。只输出紧凑 JSON，不要 Markdown fence。每个数组最多 5 条，每条不超过 60 字。字段：summary, project_type, maturity, core_value, reasons_to_continue, concerns。",
    "code_architecture_summary": "你是资深软件架构师。只输出紧凑 JSON，不要 Markdown fence，不要解释。数组最多 8 条，每条不超过 80 字。必须遵循 project_archetype：gui_agent 关注 Electron/Agent Runtime/Model Provider/Environment Adapters/Action Parser/Operator/MCP/Logs/Security；code_knowledge_graph 才分析 graph pipeline。字段：summary, entrypoints, core_modules, data_flow, extension_points, api_cli_surface, security_boundary, architecture_risks。不编造未提供的信息。",
    "negative_signal_summary": "你是企业技术风险审查员。只输出 JSON，不要 Markdown fence。字段：summary, maturity_risks, security_risks, maintenance_risks, enterprise_blockers, risk_note。",
    "comparison_summary": "你是企业技术选型分析师。只输出紧凑 JSON，不要 Markdown fence。每个数组最多 5 条，每条不超过 80 字。基于 comparison 中 direct/adjacent comparable，输出字段：summary, direct_comparables, adjacent_comparables, target_position, differentiators, replacement_options, comparison_risks。不使用 weak 项目做主要结论。",
    "enterprise_fit_summary": "你是面向 toB 业务的企业 AI 落地顾问。只输出 JSON，不要 Markdown fence。必须基于 company_profile 逐项回答私有化部署、Claude Code/Codex 工作流、Coding Agent 上下文增强、Neo4j/pgvector/Obsidian/llm_wiki/企业知识库结合、skill/agent 能力沉淀、行业项目交付可维护性、权限审计隔离数据安全、最小 PoC 路径、不建议投入条件。字段：summary, relevance, applicable_scenarios, integration_paths, required_adaptations, deployment_feasibility, risk_note, recommended_action, investment_suggestion, enterprise_action_plan。",
    "final_report_synthesis": "你是中文技术情报编辑。只输出 JSON，不要 Markdown fence。最终阶段只引用前面结构化产物，不再根据 README 宣传重新判断。字段：one_line_judgement, final_conclusion, recommended_action, investment_suggestion, risk_note, key_findings。key_findings 为 3-6 条字符串。必须区分技术潜力、当前成熟度、企业落地可行性、战略相关性、安全与合规风险；不允许同时给出互相冲突的结论；对信息不足写待验证；高 Star 不等于成熟；README 宣称和代码实现不一致要指出。",
}


def run_staged_llm_analysis(
    payload: dict[str, Any],
    client: LLMClient | None = None,
    *,
    stages: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    client = client or LLMClient()
    selected_stages = _normalize_stages(stages)
    results: dict[str, Any] = {
        "enabled": bool(client.available),
        "model": client.model,
        "ok_count": 0,
        "failed_count": 0,
        "selected_stages": selected_stages,
        "stages": {},
    }
    if not client.available:
        results["reason"] = "missing_api_key"
        return results

    prior: dict[str, Any] = {}
    for stage in selected_stages:
        stage_payload = _stage_payload(stage, payload, prior)
        result = client.chat_json(
            system_prompt=PROMPTS[stage],
            user_payload=stage_payload,
            max_tokens=STAGE_MAX_TOKENS.get(stage, 800),
        )
        if not result.ok:
            results["failed_count"] += 1
            results["stages"][stage] = {
                "status": "api_failed",
                "error_type": result.error_type,
                "error_message": result.error_message,
                "raw": result.raw,
            }
            continue
        parsed, error = parse_json_or_error(result.content)
        if error:
            results["failed_count"] += 1
            results["stages"][stage] = {
                "status": "parse_failed",
                "error_type": "parse_failed",
                "error_message": error,
                "raw": result.content,
            }
            continue
        results["ok_count"] += 1
        results["stages"][stage] = {
            "status": "ok",
            "data": parsed,
            "usage": result.usage,
            "finish_reason": result.finish_reason,
        }
        prior[stage] = parsed
    return results


def _stage_payload(stage: str, payload: dict[str, Any], prior: dict[str, Any]) -> dict[str, Any]:
    context = payload.get("context", {})
    metadata = context.get("metadata", {}) if isinstance(context.get("metadata"), dict) else {}
    base = {
        "repo": payload.get("repo"),
        "metadata": {
            "description": metadata.get("description"),
            "stars": metadata.get("stargazers_count"),
            "forks": metadata.get("forks_count"),
            "open_issues": metadata.get("open_issues_count"),
            "license": _license_text(metadata.get("license")),
            "topics": (metadata.get("topics", []) or [])[:12],
            "pushed_at": metadata.get("pushed_at"),
        },
        "company_profile": _compact_company_profile(payload.get("company_profile", {})),
        "project_archetype": payload.get("project_archetype", {}),
        "prior_stage_results": _compact_prior(prior),
    }
    if stage == "repo_overview_summary":
        base.update({"readme_excerpt": _safe_excerpt(str(context.get("readme", "")), 1200), "repo_structure": _compact_repo_structure(payload.get("repo_structure", {}))})
    elif stage == "code_architecture_summary":
        base.update({"repo_structure": _compact_repo_structure(payload.get("repo_structure", {})), "architecture": _compact_architecture(payload.get("architecture", {}))})
    elif stage == "negative_signal_summary":
        base.update({"negative_signals": _compact_negative(payload.get("negative_signals", {}))})
    elif stage == "comparison_summary":
        base.update({"ecosystem_context": payload.get("ecosystem_context", {}), "comparison": payload.get("comparison", {})})
    elif stage == "enterprise_fit_summary":
        base.update({"enterprise_fit": payload.get("enterprise_fit", {}), "negative_signals": _compact_negative(payload.get("negative_signals", {})), "company_profile_full": payload.get("company_profile", {})})
    else:
        base.update(
            {
                "repo_structure": _compact_repo_structure(payload.get("repo_structure", {})),
                "architecture": _compact_architecture(payload.get("architecture", {})),
                "ecosystem_context": payload.get("ecosystem_context", {}),
                "comparison": payload.get("comparison", {}),
                "negative_signals": _compact_negative(payload.get("negative_signals", {})),
                "enterprise_fit": payload.get("enterprise_fit", {}),
            }
        )
    return base


def _normalize_stages(stages: list[str] | tuple[str, ...] | None) -> list[str]:
    if not stages:
        return list(STAGES)
    selected = [stage for stage in stages if stage in STAGES]
    return selected or list(STAGES)


def _license_text(license_data: Any) -> str:
    if isinstance(license_data, dict):
        return str(license_data.get("spdx_id") or license_data.get("name") or "")
    return str(license_data or "")


def _compact_company_profile(profile: Any) -> dict[str, Any]:
    if not isinstance(profile, dict):
        return {}
    company = profile.get("company", {}) if isinstance(profile.get("company"), dict) else {}
    return {
        "role": company.get("role", ""),
        "delivery_mode": company.get("delivery_mode", ""),
        "focus_domains": (company.get("focus_domains", []) or [])[:8],
        "current_stack": (company.get("current_stack", []) or [])[:10],
        "evaluation_priorities": (company.get("evaluation_priorities", []) or [])[:8],
        "risk_concerns": (company.get("risk_concerns", []) or [])[:8],
        "integration_targets": (company.get("integration_targets", []) or [])[:8],
        "unacceptable_risks": (company.get("unacceptable_risks", []) or [])[:8],
    }


def _compact_repo_structure(structure: Any) -> dict[str, Any]:
    if not isinstance(structure, dict):
        return {}
    return {
        "main_languages": structure.get("main_languages", []),
        "file_type_counts": structure.get("file_type_counts", {}),
        "entrypoints": (structure.get("entrypoints", []) or [])[:12],
        "important_paths": (structure.get("important_paths", []) or [])[:20],
        "docs_paths": (structure.get("docs_paths", []) or [])[:12],
        "examples_paths": (structure.get("examples_paths", []) or [])[:12],
        "tests_paths": (structure.get("tests_paths", []) or [])[:12],
        "deployment_files": (structure.get("deployment_files", []) or [])[:12],
        "package_files": (structure.get("package_files", []) or [])[:12],
        "monorepo_structure": {
            key: {
                "role": value.get("role", ""),
                "key_files": (value.get("key_files", []) or [])[:5],
            }
            for key, value in list((structure.get("monorepo_structure", {}) or {}).items())[:12]
            if isinstance(value, dict)
        },
    }


def _compact_architecture(architecture: Any) -> dict[str, Any]:
    if not isinstance(architecture, dict):
        return {}
    return {key: value[:12] if isinstance(value, list) else value for key, value in architecture.items()}


def _compact_negative(signals: Any) -> dict[str, Any]:
    if not isinstance(signals, dict):
        return {}
    return {
        "issue_hotspots": signals.get("issue_hotspots", [])[:10],
        "recurring_complaints": [
            {"title": item.get("title", ""), "keywords": item.get("keywords", [])}
            for item in (signals.get("recurring_complaints", []) or [])[:8]
            if isinstance(item, dict)
        ],
        "missing_capabilities": signals.get("missing_capabilities", [])[:8],
        "maturity_risks": signals.get("maturity_risks", [])[:8],
        "security_risks": [
            {"title": item.get("title", ""), "keywords": item.get("keywords", [])}
            for item in (signals.get("security_risks", []) or [])[:5]
            if isinstance(item, dict)
        ],
        "maintenance_risks": signals.get("maintenance_risks", [])[:8],
        "enterprise_blockers": signals.get("enterprise_blockers", [])[:8],
        "confidence": signals.get("confidence", ""),
    }


def _compact_prior(prior: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for stage, data in prior.items():
        if isinstance(data, dict):
            compact[stage] = {key: value for key, value in data.items() if key in {"summary", "final_conclusion", "recommended_action", "risk_note", "key_findings"}}
    return compact


def _safe_excerpt(text: str, limit: int) -> str:
    cleaned = re.sub(r"```.*?```", " ", text or "", flags=re.DOTALL)
    cleaned = re.sub(r"https?://\S+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:limit]
