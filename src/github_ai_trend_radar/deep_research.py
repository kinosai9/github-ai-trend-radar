"""Local enterprise deep research report generation."""

from __future__ import annotations

from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from github_ai_trend_radar.collectors.github_repo import GitHubRepoClient
from github_ai_trend_radar.llm.client import LLMClient
from github_ai_trend_radar.llm.config import LLMConfig
from github_ai_trend_radar.research.code_analyzer import analyze_code_architecture
from github_ai_trend_radar.research.collector import ResearchCollector
from github_ai_trend_radar.research.comparable_finder import find_comparable_projects
from github_ai_trend_radar.research.diagram_builder import build_diagrams
from github_ai_trend_radar.research.ecosystem_search import search_ecosystem_context
from github_ai_trend_radar.research.enterprise_fit import evaluate_enterprise_fit
from github_ai_trend_radar.research.issue_analyzer import analyze_issues_and_limitations
from github_ai_trend_radar.research.llm_analyzer import run_staged_llm_analysis
from github_ai_trend_radar.research.models import ResearchOptions, repo_slug
from github_ai_trend_radar.research.profile import load_company_profile
from github_ai_trend_radar.research.repo_analyzer import analyze_repo_structure
from github_ai_trend_radar.research.report_writer import write_research_outputs
from github_ai_trend_radar.research.verdict import build_final_verdict
from github_ai_trend_radar.research.archetype import detect_project_archetype


def run_deep_research(
    repo: str,
    *,
    depth: str = "standard",
    profile: str = "enterprise_ai_service",
    compare: bool = False,
    clone: bool = False,
    max_files: int = 80,
    max_issues: int = 50,
    max_comparables: int = 5,
    output_dir: str | Path = "data/research",
    private: bool = True,
    config_dir: str | Path = "config",
    client: GitHubRepoClient | None = None,
    use_llm: bool = True,
    llm_client: Any | None = None,
    llm_timeout: float | None = None,
    llm_stages: list[str] | None = None,
) -> dict[str, Any]:
    owner, name = _split_repo(repo)
    options = ResearchOptions(
        repo=repo,
        depth=depth,
        profile=profile,
        compare=compare,
        clone=clone,
        max_files=max_files,
        max_issues=max_issues,
        max_comparables=max_comparables,
        output_dir=Path(output_dir),
        private=private,
    )
    errors: list[str] = []
    company_profile = load_company_profile(config_dir, profile=profile)
    collector = ResearchCollector(client=client)

    context = collector.collect_project_context(owner, name, max_files=max_files, max_issues=max_issues)
    clone_path = None
    if clone:
        target = Path(output_dir) / "_cache" / repo_slug(repo) / "repo"
        ok, message = collector.clone_repo(repo, target)
        if ok:
            clone_path = message
        else:
            errors.append(f"clone_failed: {message}")

    repo_structure = analyze_repo_structure(context, clone_path=clone_path)
    project_archetype = detect_project_archetype(context, repo_structure)
    architecture = analyze_code_architecture(context, repo_structure, clone_path=clone_path, project_archetype=project_archetype)
    ecosystem_context = search_ecosystem_context(
        context,
        company_profile,
        project_archetype=project_archetype,
        client=collector.client,
        max_projects=max(max_comparables * 2, 10),
    )
    comparison = find_comparable_projects(context, ecosystem_context, max_comparables=max_comparables, project_archetype=project_archetype) if compare else {
        "comparables": [],
        "table": {"columns": ["项目", "定位", "核心能力", "企业可控性", "风险", "适合我司的使用方式"], "rows": []},
        "note": "未启用 --compare。",
    }
    negative_signals = analyze_issues_and_limitations(context)
    enterprise_fit = evaluate_enterprise_fit(context, repo_structure, architecture, negative_signals, company_profile, project_archetype=project_archetype)
    diagrams = build_diagrams(context, repo_structure, architecture, enterprise_fit, project_archetype=project_archetype)
    options_payload = asdict(options)
    options_payload["output_dir"] = str(options.output_dir)
    payload = {
        "repo": repo,
        "generated_at": datetime.now(UTC).isoformat(),
        "options": options_payload,
        "company_profile": company_profile,
        "context": context,
        "repo_structure": repo_structure,
        "project_archetype": project_archetype,
        "architecture": architecture,
        "ecosystem_context": ecosystem_context,
        "comparison": comparison,
        "negative_signals": negative_signals,
        "enterprise_fit": enterprise_fit,
        "diagrams": diagrams,
        "llm_analysis": {"enabled": False, "reason": "not_requested"},
        "errors": errors,
    }
    if use_llm:
        if llm_client is None:
            llm_config = LLMConfig.from_research_env()
            if llm_timeout is not None:
                llm_config = replace(llm_config, timeout=llm_timeout)
            llm_client = LLMClient(llm_config)
        llm_analysis = run_staged_llm_analysis(payload, client=llm_client, stages=llm_stages)
        payload["llm_analysis"] = llm_analysis
        if llm_analysis.get("failed_count"):
            payload["errors"].append(f"llm_stage_failures: {llm_analysis.get('failed_count')}")
    payload["evidence"] = _build_evidence(payload)
    payload["source_quality"] = _build_source_quality(payload, clone_path=clone_path)
    payload["analysis_confidence"] = _build_analysis_confidence(payload)
    payload["final_verdict"] = build_final_verdict(payload)
    _align_enterprise_fit_with_verdict(payload)
    md, html, json_path, summary = write_research_outputs(payload, options)
    payload["outputs"] = {"markdown": str(md), "html": str(html), "json": str(json_path), "summary": str(summary)}
    return payload


def write_deep_research_report(
    repo: str,
    *,
    output_dir: str | Path = "data/research",
    client: GitHubRepoClient | None = None,
    **kwargs: Any,
) -> tuple[Path, Path]:
    payload = run_deep_research(repo, output_dir=output_dir, client=client, **kwargs)
    return Path(payload["outputs"]["markdown"]), Path(payload["outputs"]["html"])


def _split_repo(repo: str) -> tuple[str, str]:
    if "/" not in repo:
        raise ValueError("repo must use owner/repo format")
    owner, name = repo.split("/", 1)
    return owner, name


def _build_evidence(payload: dict[str, Any]) -> dict[str, Any]:
    context = payload.get("context", {}) if isinstance(payload.get("context"), dict) else {}
    architecture = payload.get("architecture", {}) if isinstance(payload.get("architecture"), dict) else {}
    negative = payload.get("negative_signals", {}) if isinstance(payload.get("negative_signals"), dict) else {}
    positive = []
    if context.get("readme"):
        positive.append("README 可用，可进行项目定位和能力宣称复核。")
    if architecture.get("core_modules"):
        positive.append(f"识别到 {len(architecture.get('core_modules') or [])} 个核心代码模块候选。")
    if payload.get("comparison", {}).get("comparables"):
        positive.append("已生成横向同类项目对比样本。")
    uncertainty = []
    archetype = payload.get("project_archetype", {}) if isinstance(payload.get("project_archetype"), dict) else {}
    if archetype.get("primary") == "gui_agent":
        chain = architecture.get("gui_agent_chain", {}) if isinstance(architecture.get("gui_agent_chain"), dict) else {}
        if not chain.get("stages") or "待验证" in str(chain):
            uncertainty.append("GUI Agent 执行链路未完全从源码结构中确认。")
    elif not architecture.get("graph_pipeline") or "待验证" in str(architecture.get("graph_pipeline")):
        uncertainty.append("graph pipeline 未完全从源码结构中确认。")
    if not context.get("releases"):
        uncertainty.append("未发现正式 release 样本。")
    return {
        "positive": positive,
        "negative": negative.get("negative_evidence", []) or negative.get("recurring_complaints", []),
        "uncertainty": uncertainty,
    }


def _build_source_quality(payload: dict[str, Any], *, clone_path: str | None) -> dict[str, Any]:
    context = payload.get("context", {}) if isinstance(payload.get("context"), dict) else {}
    llm = payload.get("llm_analysis", {}) if isinstance(payload.get("llm_analysis"), dict) else {}
    comparison = payload.get("comparison", {}) if isinstance(payload.get("comparison"), dict) else {}
    return {
        "readme_available": bool(context.get("readme")),
        "code_analyzed": bool(payload.get("repo_structure", {}).get("total_files_analyzed")),
        "clone_used": bool(clone_path),
        "issues_analyzed": bool(context.get("open_issues") or context.get("closed_issues")),
        "releases_analyzed": bool(context.get("releases")),
        "comparable_count": len(comparison.get("comparables", []) or []),
        "llm_stage_success": llm.get("ok_count", 0),
    }


def _build_analysis_confidence(payload: dict[str, Any]) -> dict[str, str]:
    source = _build_source_quality(payload, clone_path=None)
    return {
        "repo_structure": "high" if source["code_analyzed"] else "low",
        "architecture": "medium" if payload.get("architecture", {}).get("core_modules") else "low",
        "ecosystem": "medium" if payload.get("ecosystem_context", {}).get("notable_projects") else "low",
        "comparison": "medium" if source["comparable_count"] else "low",
        "enterprise_fit": "medium" if source["readme_available"] else "low",
        "final_verdict": "high" if source["llm_stage_success"] >= 4 and source["code_analyzed"] else "medium",
    }


def _align_enterprise_fit_with_verdict(payload: dict[str, Any]) -> None:
    verdict = payload.get("final_verdict", {}) if isinstance(payload.get("final_verdict"), dict) else {}
    enterprise = payload.get("enterprise_fit", {}) if isinstance(payload.get("enterprise_fit"), dict) else {}
    if not verdict or not enterprise:
        return
    rating = enterprise.setdefault("final_rating", {})
    if not isinstance(rating, dict):
        rating = {}
        enterprise["final_rating"] = rating
    if verdict.get("risk_level") == "high":
        rating["risk_level"] = "high"
    if verdict.get("enterprise_readiness") == "low":
        rating["enterprise_fit"] = min(int(rating.get("enterprise_fit") or 5), 2)
        enterprise["deployment_feasibility"] = "暂不具备直接落地条件"
    if verdict.get("implementation_feasibility") == "low":
        rating["implementation_feasibility"] = min(int(rating.get("implementation_feasibility") or 5), 2)
    if verdict.get("recommendation") in {"hold", "reject"}:
        enterprise["short_term_action"] = "暂缓规模化投入，仅限隔离环境安全验证型 PoC。"
        enterprise["medium_term_action"] = "仅在安全、权限、审计、模型边界和操作可控性完成复核后，再考虑非关键场景试点。"
        enterprise["deployment_feasibility"] = "暂不具备直接落地条件"
    if payload.get("project_archetype", {}).get("primary") == "gui_agent":
        rating["technical_value"] = max(int(rating.get("technical_value") or 0), 4)
        rating["strategic_relevance"] = max(int(rating.get("strategic_relevance") or 0), 4)
        enterprise["private_deployment_feasibility"] = "概念上可行，但需安全、权限、审计和模型边界加固"
        enterprise["fit_with_existing_stack"] = (
            "与 AI Agent、MCP 工具生态、工作流自动化方向存在明确相关性；与 Coding Agent 上下文增强"
            "和业务理解编译层为间接相关；不适合作为知识库/RAG 底座优先评估，更适合作为 GUI Agent / Computer Use 自动化能力储备。"
        )
