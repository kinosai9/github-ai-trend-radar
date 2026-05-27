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

SECURITY_TERMS = ("security", "vulnerability", "injection", "leak", "cve", "ghsa", "unsafe", "auth", "token", "secret", "credential", "shell", "yaml.load")
DOCS_PREFIXES = ("docs", "doc", "chore", "style", "refactor", "test", "ci")
FEATURE_PREFIXES = ("feat", "feature")


def analyze_issues_and_limitations(context: dict[str, Any], *, max_examples: int = 12) -> dict[str, Any]:
    issues = list(context.get("open_issues") or []) + list(context.get("closed_issues") or [])
    prs = [dict(item, _source_type="pull_request") for item in list(context.get("pull_requests") or []) if isinstance(item, dict)]
    readme = str(context.get("readme") or "")
    hits = []
    evidence = []
    counter: Counter[str] = Counter()
    seen_urls: set[str] = set()
    for item in prs + issues:
        url = str(item.get("html_url") or "")
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)
        title = str(item.get("title", ""))
        text = f"{title}\n{item.get('body', '')}".lower()
        if _is_non_risk_pr(item, text):
            continue
        if _is_positive_maintenance_pr(item, text):
            evidence.append(_build_evidence_item(item, "maintenance", ["test"], "maintenance_signal", "not_a_risk", "low"))
            continue
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
            evidence.append(_build_evidence_item(item, category, matched, evidence_kind, risk_status, severity))
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


def _build_evidence_item(
    item: dict[str, Any],
    category: str,
    matched: list[str],
    evidence_kind: str,
    risk_status: str,
    severity: str,
) -> dict[str, Any]:
    return {
        "title": item.get("title", ""),
        "url": item.get("html_url", ""),
        "issue_number": item.get("number"),
        "state": item.get("state", "unknown"),
        "labels": _labels(item),
        "merged": _is_merged_pr(item),
        "merged_at": item.get("merged_at"),
        "closed_at": item.get("closed_at"),
        "created_at": item.get("created_at"),
        "github_state": item.get("state", "unknown"),
        "state_source": _state_source(item),
        "author": _author(item),
        "body_excerpt": str(item.get("body") or "")[:500],
        "item_type": _item_type(item, category, evidence_kind),
        "category": category,
        "severity": severity,
        "evidence_kind": evidence_kind,
        "risk_status": risk_status,
        "summary": _summary(item, matched),
        "enterprise_impact": _enterprise_impact(category, severity),
        "confidence": "high" if item.get("html_url") else "medium",
    }


def _category(matched: list[str], text: str) -> str:
    if any(keyword in matched for keyword in ("security", "leak")) or any(word in text for word in SECURITY_TERMS):
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
    is_pr = _is_pr(item)
    if is_pr and category == "security":
        if _is_merged_pr(item):
            return "merged_security_fix"
        if state == "open":
            return "pending_fix_pr"
        return "security_signal_fixed"
    if is_pr and _starts_with(title, FEATURE_PREFIXES):
        return "feature_enhancement"
    if is_pr and _starts_with(title, DOCS_PREFIXES):
        return "maintenance_signal"
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
    if evidence_kind in {"merged_security_fix", "security_signal_fixed"}:
        return "fixed_but_requires_verification"
    if evidence_kind == "pending_fix_pr":
        return "pending_fix"
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
    if risk_status in {"fixed", "not_a_risk", "fixed_but_requires_verification"}:
        return "low"
    if risk_status == "pending_fix":
        return "medium" if category == "security" else "low"
    if category == "security":
        return "high"
    if "breaking" in matched or "not working" in matched or "data" in text:
        return "medium"
    if category in {"bug", "performance"}:
        return "medium"
    return "low"


def _is_non_risk_pr(item: dict[str, Any], text: str) -> bool:
    if not _is_pr(item):
        return False
    title = str(item.get("title") or "").lower().strip()
    title_has_security = any(term in title for term in SECURITY_TERMS)
    if _starts_with(title, DOCS_PREFIXES):
        return not title_has_security
    if _starts_with(title, FEATURE_PREFIXES):
        return not title_has_security
    if any(term in text for term in SECURITY_TERMS):
        return False
    return False


def _is_positive_maintenance_pr(item: dict[str, Any], text: str) -> bool:
    if not _is_pr(item):
        return False
    title = str(item.get("title") or "").lower()
    if "security" in text or any(term in text for term in ("cve", "ghsa", "injection", "leak", "token", "shell", "unsafe", "yaml.load")):
        return False
    return ("unit test coverage" in title) or ("coverage" in title and "test" in title)


def _is_pr(item: dict[str, Any]) -> bool:
    return item.get("_source_type") == "pull_request" or bool(item.get("pull_request")) or "/pull/" in str(item.get("html_url", ""))


def _is_merged_pr(item: dict[str, Any]) -> bool:
    value = item.get("merged")
    if isinstance(value, bool):
        return value
    return bool(item.get("merged_at")) or str(item.get("state") or "").lower() == "merged"


def _labels(item: dict[str, Any]) -> list[str]:
    labels = item.get("labels") or []
    result = []
    for label in labels:
        if isinstance(label, dict):
            result.append(str(label.get("name") or ""))
        else:
            result.append(str(label))
    return [label for label in result if label]


def _author(item: dict[str, Any]) -> str:
    user = item.get("user")
    if isinstance(user, dict):
        return str(user.get("login") or "")
    return str(user or "")


def _item_type(item: dict[str, Any], category: str, evidence_kind: str) -> str:
    if _is_pr(item):
        if category == "security" or evidence_kind in {"merged_security_fix", "pending_fix_pr", "security_signal_fixed"}:
            return "Security PR"
        if evidence_kind == "feature_enhancement":
            return "Feature Request"
        if evidence_kind == "maintenance_signal":
            return "Maintenance PR"
        return "PR"
    return "Issue"


def _state_source(item: dict[str, Any]) -> str:
    if _is_pr(item) and item.get("state") and ("merged_at" in item or "merged" in item):
        return "github_api"
    if not _is_pr(item) and item.get("state"):
        return "github_api"
    return "title_heuristic"


def _starts_with(title: str, prefixes: tuple[str, ...]) -> bool:
    return any(title.startswith(prefix + ":") or title.startswith(prefix + "(") or title.startswith(prefix + " ") for prefix in prefixes)


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
