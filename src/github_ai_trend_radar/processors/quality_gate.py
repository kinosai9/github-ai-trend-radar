"""Rule-based quality gate for report promotion decisions."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import Any


def apply_quality_gate_to_payload(payload: dict[str, Any]) -> dict[str, Any]:
    updated = deepcopy(payload)
    counts = {"pass": 0, "warn": 0, "block": 0}
    for candidate in updated.get("candidates", []):
        if not isinstance(candidate, dict):
            continue
        gate = evaluate_quality_gate(candidate)
        candidate["quality_gate"] = gate
        counts[gate["level"]] += 1
        if gate["level"] == "block":
            action = candidate.get("final_recommended_action") or candidate.get("recommended_action_rule_based")
            if action in {"deep_research", "try_locally", "read"}:
                candidate["final_recommended_action"] = "watch"
                candidate["recommended_action_rule_based"] = "watch"
        elif gate["level"] == "warn":
            if candidate.get("final_recommended_action") == "try_locally":
                candidate["final_recommended_action"] = "read"
    updated.setdefault("stats", {})["quality_gate"] = counts
    return updated


def evaluate_quality_gate(candidate: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    metrics = candidate.get("metrics", {}) if isinstance(candidate.get("metrics"), dict) else {}
    metadata = candidate.get("metadata", {}) if isinstance(candidate.get("metadata"), dict) else {}
    noise = candidate.get("noise", {}) if isinstance(candidate.get("noise"), dict) else {}
    llm_analysis = candidate.get("llm_analysis", {}) if isinstance(candidate.get("llm_analysis"), dict) else {}
    readme = str(candidate.get("readme_excerpt") or "")
    readme_lower = readme.lower()
    stars = _number(metrics.get("stars"), candidate.get("stars"))
    pushed_at = str(metadata.get("pushed_at") or candidate.get("pushed_at") or "")
    recent_push = _is_recent(pushed_at, now=now)
    source_hits = candidate.get("source_hits") if isinstance(candidate.get("source_hits"), list) else []
    topic_confidence = str(candidate.get("topic_match_confidence") or "")

    signals = {
        "has_readme": bool(readme.strip()),
        "readme_length": len(readme),
        "has_license": bool(metadata.get("license")),
        "has_installation": _contains_any(readme_lower, ("install", "installation", "quickstart", "getting started")),
        "has_examples": _contains_any(readme_lower, ("example", "examples", "demo")),
        "has_tests": _contains_any(readme_lower, ("test", "pytest", "unittest", "ci")),
        "has_docs": _contains_any(readme_lower, ("docs", "documentation", "api reference")),
        "has_release": None,
        "recent_push": recent_push,
        "contributors_known": None,
    }
    reasons: list[str] = []
    level = "pass"

    if metadata.get("archived") is True or candidate.get("archived") is True:
        reasons.append("项目已归档")
        level = "block"
    if metadata.get("fork") is True or candidate.get("fork") is True:
        reasons.append("项目是 fork")
        level = "block"
    if (not signals["has_readme"] or signals["readme_length"] < 300) and stars < 30:
        reasons.append("README 信息不足且 Star 较低")
        level = "block"
    if noise.get("is_noise") is True and llm_analysis.get("llm_is_noise") is True:
        reasons.append("规则与 LLM 均判定为噪声")
        level = "block"
    if topic_confidence == "weak" and "ossinsight" not in source_hits:
        reasons.append("主题弱匹配且缺少趋势源佐证")
        level = "block"

    warn_reasons = []
    if stars < 50:
        warn_reasons.append("Star 规模较小")
    if signals["readme_length"] < 1000:
        warn_reasons.append("README 信息偏少")
    if not signals["has_license"]:
        warn_reasons.append("未识别到 license")
    if not (signals["has_installation"] or signals["has_examples"] or signals["has_docs"]):
        warn_reasons.append("安装、示例或文档信号不足")
    if not recent_push:
        warn_reasons.append("近期更新信号不足")
    if source_hits == ["github_search"]:
        warn_reasons.append("仅 GitHub Search 单源命中")

    positive = sum(
        bool(signals[key])
        for key in ("has_readme", "has_license", "has_installation", "has_examples", "has_docs", "recent_push")
    )
    if level != "block":
        if warn_reasons and positive < 4:
            level = "warn"
            reasons.extend(warn_reasons[:4])
        else:
            level = "pass"
            if not reasons:
                reasons.append("工程信号较完整")

    return {
        "passed": level == "pass",
        "level": level,
        "reasons": reasons,
        "maturity_signals": signals,
    }


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _number(*values: Any) -> float:
    for value in values:
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return 0.0


def _is_recent(value: str, *, now: datetime) -> bool:
    if not value:
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed >= now - timedelta(days=120)
