"""Negative signal analysis from issues, PRs, releases, and text."""

from __future__ import annotations

from collections import Counter
from typing import Any


NEGATIVE_KEYWORDS = (
    "bug",
    "error",
    "fail",
    "failed",
    "broken",
    "performance",
    "slow",
    "security",
    "leak",
    "not working",
    "limitation",
    "unsupported",
    "roadmap",
    "breaking",
    "feature",
    "enhancement",
)


def analyze_issues_and_limitations(context: dict[str, Any], *, max_examples: int = 12) -> dict[str, Any]:
    issues = list(context.get("open_issues") or []) + list(context.get("closed_issues") or [])
    prs = list(context.get("pull_requests") or [])
    readme = str(context.get("readme") or "")
    hits = []
    evidence = []
    counter: Counter[str] = Counter()
    for item in issues + prs:
        text = f"{item.get('title', '')}\n{item.get('body', '')}".lower()
        matched = [keyword for keyword in NEGATIVE_KEYWORDS if keyword in text]
        if matched:
            for keyword in matched:
                counter[keyword] += 1
            category = _category(matched, text)
            evidence_kind = _evidence_kind(item, category, matched, text)
            risk_status = _risk_status(item, evidence_kind)
            severity = _severity(category, matched, text, risk_status)
            hit = {"title": item.get("title", ""), "url": item.get("html_url", ""), "keywords": matched[:5]}
            hits.append(hit)
            evidence.append(
                {
                    "title": item.get("title", ""),
                    "url": item.get("html_url", ""),
                    "issue_number": item.get("number"),
                    "state": item.get("state", "unknown"),
                    "category": category,
                    "severity": severity,
                    "evidence_kind": evidence_kind,
                    "risk_status": risk_status,
                    "summary": _summary(item, matched),
                    "enterprise_impact": _enterprise_impact(category, severity),
                    "confidence": "high" if item.get("html_url") else "medium",
                }
            )
    readme_lower = readme.lower()
    readme_limitations = [keyword for keyword in ("limitation", "unsupported", "experimental", "beta", "security") if keyword in readme_lower]
    return {
        "issue_hotspots": counter.most_common(10),
        "recurring_complaints": hits[:max_examples],
        "negative_evidence": evidence[:max_examples],
        "keyword_counts": [{"keyword": keyword, "count": count} for keyword, count in counter.most_common(10)],
        "missing_capabilities": readme_limitations,
        "maturity_risks": _maturity_risks(context),
        "security_risks": [hit for hit in hits if "security" in hit.get("keywords", []) or "leak" in hit.get("keywords", [])][:5],
        "maintenance_risks": _maintenance_risks(context),
        "enterprise_blockers": _enterprise_blockers(context, readme_limitations),
        "confidence": "medium" if issues else "low",
    }


def _category(matched: list[str], text: str) -> str:
    if any(keyword in matched for keyword in ("security", "leak")) or any(word in text for word in ("token", "secret", "api_key", "credential")):
        return "security"
    if any(keyword in matched for keyword in ("performance", "slow")):
        return "performance"
    if any(keyword in matched for keyword in ("unsupported", "limitation", "roadmap")):
        return "maintenance"
    if any(keyword in matched for keyword in ("not working", "error", "fail", "failed", "broken", "bug")):
        return "bug"
    if "doc" in text:
        return "docs"
    return "usability"


def _evidence_kind(item: dict[str, Any], category: str, matched: list[str], text: str) -> str:
    title = str(item.get("title") or "").lower()
    state = str(item.get("state") or "").lower()
    if category == "security":
        return "security_signal"
    if any(word in title for word in ("fix", "fixed", "resolve", "resolved")) and state in {"closed", "merged"}:
        return "merged_fix_pr"
    if any(word in title or word in text for word in ("feature", "enhancement", "support", "add ", "roadmap")):
        return "feature_enhancement"
    if category == "performance":
        return "performance_claim_challenge"
    if category in {"maintenance", "docs"}:
        return "maintenance_signal"
    if state == "closed":
        return "closed_issue"
    if any(word in text for word in ("not working", "broken", "fail", "crash")):
        return "user_complaint"
    return "unresolved_issue"


def _risk_status(item: dict[str, Any], evidence_kind: str) -> str:
    state = str(item.get("state") or "").lower()
    if evidence_kind == "feature_enhancement":
        return "not_a_risk"
    if evidence_kind == "merged_fix_pr" or state in {"merged"}:
        return "fixed"
    if state == "closed":
        return "mitigated"
    if evidence_kind in {"security_signal", "unresolved_issue", "user_complaint", "performance_claim_challenge"}:
        return "unresolved"
    return "unclear"


def _severity(category: str, matched: list[str], text: str, risk_status: str) -> str:
    if risk_status in {"fixed", "not_a_risk"}:
        return "low"
    if category == "security":
        return "high"
    if "breaking" in matched or "not working" in matched or "data" in text:
        return "medium"
    if category in {"bug", "performance"}:
        return "medium"
    return "low"


def _summary(item: dict[str, Any], matched: list[str]) -> str:
    title = str(item.get("title") or "")
    return f"{title}；命中关键词：{', '.join(matched[:5])}"


def _enterprise_impact(category: str, severity: str) -> str:
    if category == "security":
        return "可能影响企业代码、凭据或客户数据安全，必须在 PoC 前完成复核。"
    if category == "bug":
        return "可能影响稳定性和交付可维护性，需要通过本地 PoC 验证。"
    if category == "performance":
        return "可能影响大规模仓库或多人协作场景下的可用性。"
    if category == "maintenance":
        return "可能意味着能力边界或路线图尚不稳定，需降低投入预期。"
    return "对企业落地影响待验证。"


def _maturity_risks(context: dict[str, Any]) -> list[str]:
    metadata = context.get("metadata", {}) if isinstance(context.get("metadata"), dict) else {}
    risks = []
    if not context.get("readme"):
        risks.append("README 缺失或为空")
    if not metadata.get("license"):
        risks.append("许可证信息不明确")
    if not context.get("releases"):
        risks.append("未发现正式 release")
    return risks


def _maintenance_risks(context: dict[str, Any]) -> list[str]:
    metadata = context.get("metadata", {}) if isinstance(context.get("metadata"), dict) else {}
    if metadata.get("archived"):
        return ["仓库已归档"]
    return []


def _enterprise_blockers(context: dict[str, Any], readme_limitations: list[str]) -> list[str]:
    blockers = []
    if "security" in readme_limitations:
        blockers.append("README 中出现安全相关限制，需要人工复核")
    if not context.get("readme"):
        blockers.append("缺少 README，难以判断企业落地边界")
    return blockers
