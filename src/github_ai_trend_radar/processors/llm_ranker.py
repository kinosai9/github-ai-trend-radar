"""LLM-based semantic calibration for scored candidates."""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from github_ai_trend_radar.llm.client import LLMClient
from github_ai_trend_radar.llm.config import DEFAULT_MODEL
from github_ai_trend_radar.llm.json_utils import parse_json_or_error


ACTION_ORDER = {
    "ignore": 0,
    "watch": 1,
    "read": 2,
    "deep_research": 3,
    "try_locally": 4,
}
VALID_ACTIONS = set(ACTION_ORDER)
LLM_SCORE_KEYS = (
    "llm_novelty_score",
    "llm_business_fit_score",
    "llm_technical_value_score",
    "llm_risk_score",
)


def clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def _num(value: Any, default: float = 0.0) -> float:
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return default
    return default


def load_project_score_prompt() -> str:
    return (Path(__file__).resolve().parents[1] / "prompts" / "project_score.md").read_text(encoding="utf-8")


def extract_json_object(text: str) -> dict[str, Any]:
    payload, error = parse_json_or_error(text)
    if error or payload is None:
        raise ValueError(error or "Failed to parse JSON")
    return payload


def select_llm_candidates(
    candidates: list[dict[str, Any]],
    *,
    llm_top_n: int = 30,
    breakout_n: int = 15,
    mature_n: int = 10,
    watchlist_n: int = 5,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    selected_names: set[str] = set()

    for bucket, limit in (
        ("breakout", breakout_n),
        ("valuable_mature", mature_n),
        ("watchlist", watchlist_n),
    ):
        for candidate in [item for item in candidates if item.get("radar_bucket") == bucket][:limit]:
            if len(selected) >= llm_top_n:
                return selected
            full_name = str(candidate.get("repo_full_name") or "")
            if full_name and full_name not in selected_names:
                selected.append(candidate)
                selected_names.add(full_name)

    for candidate in candidates:
        if len(selected) >= llm_top_n:
            break
        full_name = str(candidate.get("repo_full_name") or "")
        if full_name and full_name not in selected_names:
            selected.append(candidate)
            selected_names.add(full_name)
    return selected


def project_payload_for_llm(candidate: dict[str, Any], *, max_readme_chars: int = 8000) -> dict[str, Any]:
    metadata = candidate.get("metadata", {}) or {}
    metrics = candidate.get("metrics", {}) or {}
    return {
        "repo_full_name": candidate.get("repo_full_name") or "",
        "html_url": candidate.get("html_url") or "",
        "description": candidate.get("description") or "",
        "language": metadata.get("language"),
        "stars": metrics.get("stars"),
        "forks": metrics.get("forks"),
        "open_issues": metrics.get("open_issues"),
        "created_at": metadata.get("created_at"),
        "pushed_at": metadata.get("pushed_at"),
        "source_hits": candidate.get("source_hits") or [],
        "matched_focus_topics": candidate.get("matched_focus_topics") or [],
        "matched_keywords": candidate.get("matched_keywords") or [],
        "topic_match_confidence": candidate.get("topic_match_confidence"),
        "radar_bucket": candidate.get("radar_bucket"),
        "trend_score": candidate.get("trend_score"),
        "value_score": candidate.get("value_score"),
        "radar_score": candidate.get("radar_score"),
        "scores": candidate.get("scores") or {},
        "noise": candidate.get("noise") or {},
        "recommended_action_rule_based": candidate.get("recommended_action_rule_based"),
        "readme_excerpt": str(candidate.get("readme_excerpt") or "")[:max_readme_chars],
        "metadata": {
            "topics": metadata.get("topics") or [],
            "license": metadata.get("license"),
            "default_branch": metadata.get("default_branch"),
        },
    }


def default_llm_fields(candidate: dict[str, Any], *, status: str = "skipped") -> dict[str, Any]:
    radar = clamp(_num(candidate.get("radar_score") or candidate.get("final_score")))
    enriched = dict(candidate)
    enriched["llm_status"] = status
    enriched["llm_scores"] = {}
    enriched["llm_analysis"] = {}
    enriched["llm_adjusted_score"] = round(radar, 4)
    enriched["final_recommended_action"] = candidate.get("recommended_action_rule_based") or "ignore"
    return enriched


def normalize_llm_analysis(payload: dict[str, Any]) -> tuple[dict[str, float], dict[str, Any]]:
    scores = {key: clamp(_num(payload.get(key))) for key in LLM_SCORE_KEYS}
    analysis = dict(payload)
    for key in LLM_SCORE_KEYS:
        analysis[key] = scores[key]
    action = str(analysis.get("recommended_action_llm") or "watch")
    if action not in VALID_ACTIONS:
        analysis["recommended_action_llm"] = "watch"
    return scores, analysis


def adjusted_score(candidate: dict[str, Any], llm_analysis: dict[str, Any]) -> float:
    radar = clamp(_num(candidate.get("radar_score") or candidate.get("final_score")))
    score = (
        0.60 * radar
        + 0.15 * _num(llm_analysis.get("llm_novelty_score"))
        + 0.15 * _num(llm_analysis.get("llm_business_fit_score"))
        + 0.10 * _num(llm_analysis.get("llm_technical_value_score"))
        - 0.10 * _num(llm_analysis.get("llm_risk_score"))
    )
    if llm_analysis.get("llm_is_noise") is True:
        score -= 0.20
    if llm_analysis.get("llm_topic_match_confidence") == "weak":
        score -= 0.10
    return round(clamp(score), 4)


def final_action(rule_action: str, llm_analysis: dict[str, Any], *, score: float) -> str:
    llm_action = str(llm_analysis.get("recommended_action_llm") or rule_action or "ignore")
    if llm_action not in VALID_ACTIONS:
        llm_action = rule_action if rule_action in VALID_ACTIONS else "ignore"
    if llm_analysis.get("llm_is_noise") is True:
        return "ignore" if score < 0.55 else "watch"
    if ACTION_ORDER[llm_action] < ACTION_ORDER.get(rule_action, 0):
        return llm_action
    if (
        llm_analysis.get("llm_trend_judgement") in {"breakout", "rising"}
        and _num(llm_analysis.get("llm_technical_value_score")) >= 0.75
        and _num(llm_analysis.get("llm_business_fit_score")) >= 0.65
        and score >= 0.72
    ):
        return "try_locally" if llm_action == "try_locally" else "deep_research"
    return llm_action if ACTION_ORDER[llm_action] > ACTION_ORDER.get(rule_action, 0) else rule_action


def apply_llm_success(candidate: dict[str, Any], payload: dict[str, Any], *, raw_response: str) -> dict[str, Any]:
    scores, analysis = normalize_llm_analysis(payload)
    score = adjusted_score(candidate, analysis)
    enriched = dict(candidate)
    enriched["llm_status"] = "ok"
    enriched["llm_scores"] = scores
    enriched["llm_analysis"] = analysis
    enriched["llm_debug"] = {"raw_response": raw_response}
    enriched["llm_adjusted_score"] = score
    enriched["final_recommended_action"] = final_action(
        str(candidate.get("recommended_action_rule_based") or "ignore"),
        analysis,
        score=score,
    )
    return enriched


def apply_llm_parse_failed(candidate: dict[str, Any], *, raw_response: str, error: str) -> dict[str, Any]:
    enriched = default_llm_fields(candidate, status="parse_failed")
    enriched["llm_debug"] = {"raw_response": raw_response, "error": error}
    return enriched


def apply_llm_api_failed(candidate: dict[str, Any], *, error: str) -> dict[str, Any]:
    enriched = default_llm_fields(candidate, status="api_failed")
    enriched["llm_debug"] = {"error": error}
    return enriched


def enrich_with_llm(
    scored_payload: dict[str, Any],
    *,
    client: LLMClient,
    scoring_config: dict[str, Any],
    source_snapshot: str,
    llm_top_n: int = 30,
    breakout_n: int = 15,
    mature_n: int = 10,
    watchlist_n: int = 5,
    prompt: str | None = None,
) -> dict[str, Any]:
    candidates = [dict(candidate) for candidate in scored_payload.get("candidates") or []]
    selected = select_llm_candidates(
        candidates,
        llm_top_n=llm_top_n,
        breakout_n=breakout_n,
        mature_n=mature_n,
        watchlist_n=watchlist_n,
    )
    selected_names = {candidate.get("repo_full_name") for candidate in selected}
    system_prompt = prompt or load_project_score_prompt()
    max_readme_chars = int((scoring_config.get("llm") or {}).get("max_readme_chars", 8000))

    llm_candidates: list[dict[str, Any]] = []
    ok_count = 0
    api_failed_count = 0
    parse_failed_count = 0
    missing_key = not client.available

    for candidate in candidates:
        if candidate.get("repo_full_name") not in selected_names:
            llm_candidates.append(default_llm_fields(candidate, status="skipped"))
            continue
        if missing_key:
            llm_candidates.append(default_llm_fields(candidate, status="skipped"))
            continue
        try:
            response = client.chat_json(
                system_prompt=system_prompt,
                user_payload={"project": project_payload_for_llm(candidate, max_readme_chars=max_readme_chars)},
            )
        except Exception as exc:
            api_failed_count += 1
            llm_candidates.append(apply_llm_api_failed(candidate, error=str(exc)))
            continue
        if not response.ok:
            api_failed_count += 1
            llm_candidates.append(
                apply_llm_api_failed(
                    candidate,
                    error=f"{response.error_type}: {response.error_message}",
                )
            )
            continue
        try:
            parsed = extract_json_object(response.content)
        except (ValueError, json.JSONDecodeError) as exc:
            parse_failed_count += 1
            llm_candidates.append(apply_llm_parse_failed(candidate, raw_response=response.content, error=str(exc)))
            continue
        ok_count += 1
        llm_candidates.append(apply_llm_success(candidate, parsed, raw_response=response.content))

    stats = dict(scored_payload.get("stats") or {})
    stats["llm_analyzed_candidates"] = 0 if missing_key else len(selected)
    stats["llm_noise_candidates"] = sum(
        1 for candidate in llm_candidates if (candidate.get("llm_analysis") or {}).get("llm_is_noise") is True
    )

    return {
        "period": scored_payload.get("period"),
        "generated_at": datetime.now(UTC).isoformat(),
        "source_snapshot": source_snapshot,
        "llm": {
            "enabled": not missing_key,
            "requested": True,
            "model": client.model,
            "candidate_count": len(selected),
            "ok_count": ok_count,
            "failed_count": api_failed_count,
            "api_failed_count": api_failed_count,
            "parse_failed_count": parse_failed_count,
            "skipped_count": sum(1 for candidate in llm_candidates if candidate.get("llm_status") == "skipped"),
            "reason": "missing_api_key" if missing_key else None,
        },
        "stats": stats,
        "candidates": sorted(llm_candidates, key=lambda item: _num(item.get("llm_adjusted_score")), reverse=True),
    }


def action_distribution(candidates: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(str(candidate.get("final_recommended_action") or "ignore") for candidate in candidates))


def default_model_from_config(scoring_config: dict[str, Any]) -> str:
    return str((scoring_config.get("llm") or {}).get("default_model") or DEFAULT_MODEL)
