"""Final consistency arbiter for enterprise deep research."""

from __future__ import annotations

from typing import Any


def build_final_verdict(payload: dict[str, Any]) -> dict[str, Any]:
    context = payload.get("context", {}) if isinstance(payload.get("context"), dict) else {}
    metadata = context.get("metadata", {}) if isinstance(context.get("metadata"), dict) else {}
    architecture = payload.get("architecture", {}) if isinstance(payload.get("architecture"), dict) else {}
    negative = payload.get("negative_signals", {}) if isinstance(payload.get("negative_signals"), dict) else {}
    enterprise = payload.get("enterprise_fit", {}) if isinstance(payload.get("enterprise_fit"), dict) else {}
    final_llm = _llm_final(payload.get("llm_analysis", {}))

    risk_level = _risk_level(negative, enterprise)
    open_source_maturity = _engineering_maturity(context, architecture, negative)
    technical_potential = _technical_potential(metadata, payload)
    community_signal = _community_signal(metadata)
    enterprise_readiness = _enterprise_fit_level(enterprise, risk_level)
    implementation = _implementation_feasibility(open_source_maturity, risk_level, enterprise)
    recommendation = _recommendation(final_llm, risk_level, open_source_maturity, enterprise_readiness, implementation)
    rationale = _rationale(payload, risk_level, open_source_maturity, enterprise_readiness)
    blocking = _blocking_risks(negative, risk_level, open_source_maturity)

    return {
        "one_sentence": _one_sentence(final_llm, recommendation, risk_level, open_source_maturity),
        "recommendation": recommendation,
        "technical_potential": technical_potential,
        "community_signal": community_signal,
        "open_source_engineering_maturity": open_source_maturity,
        "enterprise_readiness": enterprise_readiness,
        "engineering_maturity": open_source_maturity,
        "enterprise_fit": enterprise_readiness,
        "implementation_feasibility": implementation,
        "risk_level": risk_level,
        "confidence": _confidence(payload),
        "rationale": rationale[:6],
        "blocking_risks": blocking[:8],
        "next_actions": _next_actions(recommendation, risk_level, open_source_maturity),
    }


def _llm_final(llm: Any) -> dict[str, Any]:
    if not isinstance(llm, dict):
        return {}
    stages = llm.get("stages", {}) if isinstance(llm.get("stages"), dict) else {}
    item = stages.get("final_report_synthesis", {}) if isinstance(stages.get("final_report_synthesis"), dict) else {}
    return item.get("data", {}) if isinstance(item.get("data"), dict) else {}


def _risk_level(negative: dict[str, Any], enterprise: dict[str, Any]) -> str:
    evidence = negative.get("negative_evidence", []) or []
    blockers = negative.get("enterprise_blockers", []) or []
    severe = [
        item
        for item in evidence
        if isinstance(item, dict)
        and (item.get("severity") == "high" or item.get("category") == "security")
    ]
    text = " ".join(str(item) for item in blockers + negative.get("maturity_risks", []) + negative.get("security_risks", []))
    if severe or any(keyword in text.lower() for keyword in ("secret", "api_key", "leak", "泄露", "凭据", "安全")):
        return "high"
    rating = enterprise.get("final_rating", {}) if isinstance(enterprise.get("final_rating"), dict) else {}
    level = str(rating.get("risk_level") or "medium").lower()
    if level in {"low", "medium", "high"}:
        return level
    return "medium"


def _engineering_maturity(context: dict[str, Any], architecture: dict[str, Any], negative: dict[str, Any]) -> str:
    core = architecture.get("core_modules", []) or []
    graph_pipeline = architecture.get("graph_pipeline", {}) or {}
    stages = graph_pipeline.get("stages", []) if isinstance(graph_pipeline, dict) else graph_pipeline
    readme_len = len(str(context.get("readme") or ""))
    core_paths = [item.get("path", "") if isinstance(item, dict) else str(item) for item in core]
    if not core_paths or all(path.startswith(("tests/", "test/", "fixtures/", "docs/", "examples/")) for path in core_paths):
        return "low"
    if negative.get("maturity_risks") and len(core) < 4:
        return "low"
    high_risk = any(isinstance(item, dict) and item.get("severity") == "high" for item in negative.get("negative_evidence", []) or [])
    if len(core) >= 5 and stages and readme_len >= 1200 and not high_risk:
        return "high"
    return "medium"


def _technical_potential(metadata: dict[str, Any], payload: dict[str, Any]) -> str:
    text = " ".join(
        [
            str(metadata.get("description") or ""),
            " ".join(metadata.get("topics", []) or []),
            str(payload.get("ecosystem_context", {}).get("primary_domain", "")),
        ]
    ).lower()
    stars = int(metadata.get("stargazers_count") or 0)
    if stars >= 1000 or any(keyword in text for keyword in ("graph", "rag", "agent", "mcp", "code", "knowledge")):
        return "high"
    return "medium" if stars >= 100 else "low"


def _community_signal(metadata: dict[str, Any]) -> str:
    stars = int(metadata.get("stargazers_count") or 0)
    forks = int(metadata.get("forks_count") or 0)
    issues = int(metadata.get("open_issues_count") or 0)
    if stars >= 5000 or forks >= 500:
        return "high"
    if stars >= 500 or issues >= 20:
        return "medium"
    return "low"


def _enterprise_fit_level(enterprise: dict[str, Any], risk_level: str) -> str:
    rating = enterprise.get("final_rating", {}) if isinstance(enterprise.get("final_rating"), dict) else {}
    score = int(rating.get("enterprise_fit") or 0)
    if risk_level == "high":
        return "low" if score < 5 else "medium"
    if score >= 4:
        return "high"
    return "medium" if score >= 3 else "low"


def _implementation_feasibility(engineering: str, risk: str, enterprise: dict[str, Any]) -> str:
    if risk == "high" or engineering == "low":
        return "low"
    rating = enterprise.get("final_rating", {}) if isinstance(enterprise.get("final_rating"), dict) else {}
    score = int(rating.get("implementation_feasibility") or 0)
    if score >= 4 and engineering == "high":
        return "high"
    return "medium"


def _recommendation(final_llm: dict[str, Any], risk: str, maturity: str, fit: str, implementation: str) -> str:
    llm_text = " ".join(str(final_llm.get(key, "")) for key in ("recommended_action", "investment_suggestion", "final_conclusion")).lower()
    if risk == "high" or maturity == "low":
        if any(keyword in llm_text for keyword in ("reject", "不建议", "禁止", "暂缓", "不直接")):
            return "hold"
        return "watch"
    if fit == "high" and implementation in {"medium", "high"}:
        return "try_locally" if "poc" in llm_text or "试" in llm_text else "deep_research"
    return "watch"


def _rationale(payload: dict[str, Any], risk: str, maturity: str, fit: str) -> list[str]:
    negative = payload.get("negative_signals", {}) if isinstance(payload.get("negative_signals"), dict) else {}
    architecture = payload.get("architecture", {}) if isinstance(payload.get("architecture"), dict) else {}
    ecosystem = payload.get("ecosystem_context", {}) if isinstance(payload.get("ecosystem_context"), dict) else {}
    reasons = [
        f"生态位置：{ecosystem.get('primary_domain', 'other')} / {ecosystem.get('market_stage', 'unclear')}",
        f"工程成熟度判定为 {maturity}，核心模块识别 {len(architecture.get('core_modules', []) or [])} 个。",
        f"企业适配判定为 {fit}。",
        f"最终风险等级为 {risk}。",
    ]
    for evidence in (negative.get("negative_evidence", []) or [])[:2]:
        if isinstance(evidence, dict):
            reasons.append(f"负面证据：{evidence.get('title')} -> {evidence.get('enterprise_impact')}")
    return [reason for reason in reasons if reason]


def _blocking_risks(negative: dict[str, Any], risk: str, maturity: str) -> list[str]:
    risks = list(negative.get("enterprise_blockers", []) or [])
    evidence = [item for item in negative.get("negative_evidence", []) or [] if isinstance(item, dict)]
    if any(item.get("category") == "security" for item in evidence):
        risks.append("未验证 secret/path 泄露风险是否已彻底修复。")
    if any(item.get("category") == "bug" for item in evidence):
        risks.append("未验证删除/移动文件一致性修复是否已覆盖。")
    if maturity == "low":
        risks.append("核心模块或主流程识别不足，工程成熟度不能判定为可落地。")
    if risk == "high" and not risks:
        risks.append("存在高风险信号，需要先完成安全与代码审计。")
    risks.extend(
        [
            "未验证本地部署是否完全离线。",
            "未验证是否支持 Neo4j 或本地知识库导出。",
            "未验证权限审计能力。",
        ]
    )
    return risks


def _next_actions(recommendation: str, risk: str, maturity: str) -> list[str]:
    if recommendation in {"hold", "reject"}:
        return ["不进入生产或客户交付", "保留 watchlist 月度复核", "等待核心代码、安全边界和维护信号补齐"]
    if recommendation == "watch":
        return ["加入 watchlist", "用非敏感仓库做只读 PoC", "复核 issue 中的安全和稳定性问题"]
    return ["安排本地 PoC", "验证私有化部署和权限审计", "评估二开成本和数据边界"]


def _one_sentence(final_llm: dict[str, Any], recommendation: str, risk: str, maturity: str) -> str:
    if final_llm.get("one_line_judgement"):
        base = str(final_llm["one_line_judgement"])
    else:
        base = f"当前推荐动作 {recommendation}，工程成熟度 {maturity}，风险 {risk}。"
    if risk == "high" and "low" in base.lower():
        base += " 最终风险裁决已上调为 high。"
    return base


def _confidence(payload: dict[str, Any]) -> str:
    source_quality = payload.get("source_quality", {}) if isinstance(payload.get("source_quality"), dict) else {}
    llm_ok = int(source_quality.get("llm_stage_success") or 0)
    if source_quality.get("code_analyzed") and source_quality.get("issues_analyzed") and llm_ok >= 4:
        return "high"
    if source_quality.get("code_analyzed") or source_quality.get("issues_analyzed"):
        return "medium"
    return "low"
