"""Rule-based candidate scoring."""

from __future__ import annotations

import math
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml


SCORE_KEYS = (
    "growth_score",
    "topic_relevance_score",
    "engineering_quality_score",
    "novelty_score",
    "community_activity_score",
    "business_fit_score",
    "source_confidence_score",
)

DEFAULT_RADAR_WEIGHTS = {
    "daily": {"trend_score": 0.60, "value_score": 0.25, "source_confidence_score": 0.15},
    "weekly": {"trend_score": 0.50, "value_score": 0.35, "source_confidence_score": 0.15},
    "monthly": {"trend_score": 0.40, "value_score": 0.45, "source_confidence_score": 0.15},
}

STRONG_TOPIC_TERMS = {
    "ai_agent": {
        "ai agent",
        "autonomous agent",
        "agent framework",
        "multi-agent",
        "tool use",
        "agent memory",
    },
    "mcp": {
        "model context protocol",
        "mcp server",
        "mcp client",
        "mcp tools",
    },
    "coding_agent": {
        "coding agent",
        "software engineering agent",
        "claude code",
        "codex",
        "cursor",
        "ai coding assistant",
    },
    "rag_knowledge": {
        "retrieval augmented generation",
        "graph rag",
        "vector search",
        "knowledge base",
        "embeddings",
        "hybrid search",
    },
}

SHORT_TOPIC_TERMS = {"ai", "llm", "mcp", "rag", "agent", "agents"}


def clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def load_scoring_config(config_dir: Path | str = "config") -> dict[str, Any]:
    path = Path(config_dir) / "scoring.default.yaml"
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"Scoring config must contain a mapping: {path}")
    return payload


def _num(value: Any, default: float = 0.0) -> float:
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.replace(",", "").strip())
        except ValueError:
            return default
    return default


def _metadata(candidate: dict[str, Any]) -> dict[str, Any]:
    return candidate.get("metadata", {}) or {}


def _metrics(candidate: dict[str, Any]) -> dict[str, Any]:
    return candidate.get("metrics", {}) or {}


def _topics(candidate: dict[str, Any]) -> set[str]:
    return {str(topic).lower() for topic in _metadata(candidate).get("topics", [])}


def _text(candidate: dict[str, Any]) -> str:
    parts = [
        candidate.get("repo_full_name") or "",
        candidate.get("description") or "",
        candidate.get("readme_excerpt") or "",
        " ".join(str(topic) for topic in _topics(candidate)),
    ]
    return " ".join(parts).lower()


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _days_since(value: Any, *, now: datetime | None = None) -> float | None:
    parsed = _parse_time(value)
    if parsed is None:
        return None
    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    return max((current - parsed).total_seconds() / 86400, 0.0)


def _recent_score(value: Any, *, horizon_days: float = 120, now: datetime | None = None) -> float:
    days = _days_since(value, now=now)
    if days is None:
        return 0.2
    return clamp(1.0 - days / horizon_days)


def _keyword_hits(text: str, keywords: Iterable[str]) -> list[str]:
    return [keyword for keyword in keywords if keyword.lower() in text]


def _rank_score(value: Any, *, max_rank: float = 100.0) -> float:
    rank = _num(value, 0)
    if rank <= 0:
        return 0.0
    return clamp(1.0 - (rank - 1) / max_rank)


def _period_horizons(period: str) -> tuple[int, int]:
    if period == "daily":
        return 30, 365
    if period == "weekly":
        return 60, 540
    return 120, 730


def _primary_pushed_at(candidate: dict[str, Any]) -> Any:
    return _metadata(candidate).get("pushed_at") or candidate.get("pushed_at")


def _primary_created_at(candidate: dict[str, Any]) -> Any:
    return _metadata(candidate).get("created_at") or candidate.get("created_at")


def source_confidence_score(candidate: dict[str, Any]) -> float:
    sources = set(candidate.get("source_hits") or [])
    if {"ossinsight", "github_search"}.issubset(sources):
        return 1.0
    if "ossinsight" in sources:
        return 0.7
    if "github_search" in sources:
        return 0.6
    if "signalforges" in sources:
        return 0.8
    return 0.2


def growth_score(candidate: dict[str, Any]) -> float:
    metrics = _metrics(candidate)
    stars = _num(metrics.get("stars"))
    forks = _num(metrics.get("forks"))
    star_score = clamp(math.log1p(stars) / math.log1p(100000))
    fork_score = clamp(math.log1p(forks) / math.log1p(20000))
    oss_rank = _rank_score(metrics.get("ossinsight_rank") or candidate.get("source_rank"))
    search_rank = _rank_score(metrics.get("github_search_rank") or candidate.get("github_search_rank"), max_rank=300)
    source_bonus = 0.1 if len(candidate.get("source_hits") or []) > 1 else 0.0
    return clamp(0.42 * star_score + 0.18 * fork_score + 0.20 * oss_rank + 0.10 * search_rank + source_bonus)


def topic_match_confidence(candidate: dict[str, Any], topics_config: dict[str, dict[str, Any]]) -> str:
    text = _text(candidate)
    github_topics = _topics(candidate)
    matched_focus = set(candidate.get("matched_focus_topics") or [])
    matched_keywords = {str(keyword).lower() for keyword in (candidate.get("matched_keywords") or [])}

    for topic_name, config in topics_config.items():
        configured_topics = {str(topic).lower() for topic in config.get("github_topics", [])}
        if github_topics & configured_topics:
            return "strong"
        strong_terms = STRONG_TOPIC_TERMS.get(topic_name, set())
        if any(term in text for term in strong_terms):
            return "strong"
        if any(term in matched_keywords for term in strong_terms):
            return "strong"

    non_short_keywords = [keyword for keyword in matched_keywords if keyword not in SHORT_TOPIC_TERMS and len(keyword) > 3]
    if matched_focus and non_short_keywords:
        return "medium"
    if len(non_short_keywords) >= 2:
        return "medium"

    for topic_name, config in topics_config.items():
        keywords = {str(keyword).lower() for keyword in config.get("keywords", [])}
        longer_hits = [keyword for keyword in keywords if keyword not in SHORT_TOPIC_TERMS and keyword in text]
        if len(longer_hits) >= 2 or (topic_name in matched_focus and longer_hits):
            return "medium"

    if matched_focus or matched_keywords:
        return "weak"
    if any(term in text.split() for term in SHORT_TOPIC_TERMS):
        return "weak"
    return "weak"


def topic_relevance_score(candidate: dict[str, Any], topics_config: dict[str, dict[str, Any]]) -> float:
    text = _text(candidate)
    metadata_topics = _topics(candidate)
    matched_focus = candidate.get("matched_focus_topics") or []
    matched_keywords = candidate.get("matched_keywords") or []
    confidence = topic_match_confidence(candidate, topics_config)

    score = 0.0
    if matched_focus:
        weights = [float(topics_config.get(topic, {}).get("weight", 1.0)) for topic in matched_focus]
        score += min(sum(weights) / max(len(weights), 1), 1.5) * 0.18

    strong_keyword_count = 0
    medium_keyword_count = 0
    for keyword in matched_keywords:
        keyword_text = str(keyword).lower()
        if keyword_text in SHORT_TOPIC_TERMS:
            score += 0.015
        elif keyword_text in {term for terms in STRONG_TOPIC_TERMS.values() for term in terms}:
            strong_keyword_count += 1
        else:
            medium_keyword_count += 1
    score += min(strong_keyword_count, 4) * 0.10
    score += min(medium_keyword_count, 4) * 0.05

    for topic_name, config in topics_config.items():
        weight = float(config.get("weight", 1.0))
        configured_topics = {str(github_topic).lower() for github_topic in config.get("github_topics", [])}
        if metadata_topics & configured_topics:
            score += 0.20 * weight
        strong_hits = _keyword_hits(text, STRONG_TOPIC_TERMS.get(topic_name, set()))
        if strong_hits:
            score += min(len(strong_hits), 3) * 0.08 * weight
        keyword_hits = [
            keyword
            for keyword in _keyword_hits(text, config.get("keywords", []))
            if keyword.lower() not in SHORT_TOPIC_TERMS and keyword.lower() not in STRONG_TOPIC_TERMS.get(topic_name, set())
        ]
        if keyword_hits:
            score += min(len(keyword_hits), 3) * 0.035 * weight
        if topic_name in matched_focus:
            score += 0.05 * weight

    cap = {"strong": 1.0, "medium": 0.68, "weak": 0.34}[confidence]
    return clamp(min(score, cap))


def engineering_quality_score(candidate: dict[str, Any], scoring_config: dict[str, Any], *, now: datetime | None = None) -> float:
    metadata = _metadata(candidate)
    readme = candidate.get("readme_excerpt") or ""
    text = readme.lower()
    score = 0.0
    score += 0.18 if len(readme) >= 800 else 0.1 if readme else 0.0
    score += 0.1 if metadata.get("license") else 0.0
    score += 0.12 * _recent_score(_primary_pushed_at(candidate), horizon_days=180, now=now)
    score += 0.1 if metadata.get("topics") else 0.0
    score += 0.08 if metadata.get("default_branch") else 0.0
    score += 0.1 if candidate.get("description") else 0.0
    score += min(len(_keyword_hits(text, scoring_config.get("engineering_positive_keywords", []))), 6) * 0.06
    if metadata.get("archived"):
        score -= 0.4
    if metadata.get("fork"):
        score -= 0.25
    if not readme:
        score -= 0.15
    if not candidate.get("description"):
        score -= 0.1
    if _recent_score(_primary_pushed_at(candidate), horizon_days=365, now=now) < 0.1:
        score -= 0.1
    return clamp(score)


def community_activity_score(candidate: dict[str, Any], *, now: datetime | None = None) -> float:
    metrics = _metrics(candidate)
    stars = _num(metrics.get("stars"))
    forks = _num(metrics.get("forks"))
    issues = _num(metrics.get("open_issues"))
    score = 0.35 * clamp(math.log1p(stars) / math.log1p(100000))
    score += 0.2 * clamp(math.log1p(forks) / math.log1p(20000))
    score += 0.15 * clamp(math.log1p(issues + 1) / math.log1p(2000))
    score += 0.2 * _recent_score(_primary_pushed_at(candidate), now=now)
    score += 0.1 if len(candidate.get("source_hits") or []) > 1 else 0.0
    return clamp(score)


def business_fit_score(candidate: dict[str, Any], scoring_config: dict[str, Any]) -> float:
    text = _text(candidate)
    hits = _keyword_hits(text, scoring_config.get("business_fit_keywords", []))
    focus_bonus = min(len(candidate.get("matched_focus_topics") or []), 3) * 0.10
    confidence = topic_match_confidence(candidate, {})
    confidence_bonus = 0.08 if confidence == "strong" else 0.03 if confidence == "medium" else 0.0
    return clamp(min(len(hits), 8) * 0.09 + focus_bonus + confidence_bonus)


def novelty_score(candidate: dict[str, Any], scoring_config: dict[str, Any], *, now: datetime | None = None) -> float:
    text = _text(candidate)
    novelty_terms = ["framework", "protocol", "runtime", "engine", "server", "gateway", "memory", "agent", "mcp", "rag"]
    score = 0.15
    score += 0.2 * _recent_score(_primary_created_at(candidate), horizon_days=365, now=now)
    score += 0.15 if len(candidate.get("source_hits") or []) > 1 else 0.0
    score += min(len(_keyword_hits(text, novelty_terms)), 5) * 0.08
    if set(candidate.get("matched_focus_topics") or []) & {"coding_agent", "mcp", "ai_agent"}:
        score += 0.15
    noise_hits = _keyword_hits(text, scoring_config.get("noise_keywords", []))
    score -= min(len(noise_hits), 4) * 0.12
    return clamp(score)


def trend_score(
    candidate: dict[str, Any],
    scores: dict[str, float],
    *,
    period: str = "daily",
    now: datetime | None = None,
) -> float:
    metrics = _metrics(candidate)
    sources = set(candidate.get("source_hits") or [])
    pushed_horizon, created_horizon = _period_horizons(period)
    pushed_recent = _recent_score(_primary_pushed_at(candidate), horizon_days=pushed_horizon, now=now)
    created_recent = _recent_score(_primary_created_at(candidate), horizon_days=created_horizon, now=now)
    oss_rank = _rank_score(metrics.get("ossinsight_rank") or candidate.get("source_rank"), max_rank=100)
    search_rank = _rank_score(metrics.get("github_search_rank") or candidate.get("github_search_rank"), max_rank=300)
    oss_bonus = 0.22 if "ossinsight" in sources else 0.0
    multi_bonus = 0.07 if {"ossinsight", "github_search"}.issubset(sources) else 0.0

    if period == "daily":
        base = 0.22 * scores["growth_score"] + 0.24 * oss_rank + 0.11 * search_rank + 0.26 * pushed_recent + 0.10 * created_recent
    elif period == "weekly":
        base = 0.25 * scores["growth_score"] + 0.21 * oss_rank + 0.12 * search_rank + 0.22 * pushed_recent + 0.12 * created_recent
    else:
        base = 0.28 * scores["growth_score"] + 0.16 * oss_rank + 0.12 * search_rank + 0.18 * pushed_recent + 0.18 * created_recent

    score = base + oss_bonus + multi_bonus
    stars = _num(metrics.get("stars"))
    created_days = _days_since(_primary_created_at(candidate), now=now)
    github_search_only = sources == {"github_search"}
    if github_search_only and stars >= 20000 and created_days is not None and created_days > 730:
        score -= 0.22 if period == "daily" else 0.14
    if github_search_only and oss_rank == 0 and pushed_recent < 0.9:
        score -= 0.08
    return clamp(score)


def value_score(candidate: dict[str, Any], scores: dict[str, float]) -> float:
    readme = candidate.get("readme_excerpt") or ""
    metadata = _metadata(candidate)
    readme_bonus = 0.05 if len(readme) >= 2000 else 0.025 if readme else 0.0
    license_bonus = 0.03 if metadata.get("license") else 0.0
    return clamp(
        0.34 * scores["engineering_quality_score"]
        + 0.28 * scores["topic_relevance_score"]
        + 0.18 * scores["business_fit_score"]
        + 0.15 * scores["community_activity_score"]
        + readme_bonus
        + license_bonus
    )


def radar_score_from_layers(
    trend: float,
    value: float,
    source_confidence: float,
    scoring_config: dict[str, Any],
    *,
    period: str = "daily",
    penalty: float = 0.0,
) -> float:
    weights = (scoring_config.get("radar_weights") or DEFAULT_RADAR_WEIGHTS).get(period, DEFAULT_RADAR_WEIGHTS["daily"])
    base = (
        clamp(trend) * float(weights.get("trend_score", 0.5))
        + clamp(value) * float(weights.get("value_score", 0.35))
        + clamp(source_confidence) * float(weights.get("source_confidence_score", 0.15))
    )
    return round(clamp(base * (1.0 - clamp(penalty))), 4)


def detect_noise(candidate: dict[str, Any], scoring_config: dict[str, Any]) -> dict[str, Any]:
    text = _text(candidate)
    metadata = _metadata(candidate)
    reasons: list[str] = []
    for keyword in scoring_config.get("noise_keywords", []):
        if keyword.lower() in text:
            reasons.append(f"keyword:{keyword}")
    if metadata.get("archived"):
        reasons.append("archived")
    if metadata.get("fork"):
        reasons.append("fork")

    penalty = 0.0
    for reason in reasons:
        if any(term in reason for term in ("awesome", "prompt", "course", "tutorial")):
            penalty += 0.25
        elif reason in {"archived", "fork"}:
            penalty += 0.3
        else:
            penalty += 0.12
    penalty = clamp(penalty, 0.0, 0.75)
    return {"is_noise": bool(reasons), "noise_reasons": reasons, "penalty": penalty}


def final_score_from_subscores(scores: dict[str, float], weights: dict[str, float], *, penalty: float = 0.0) -> float:
    base = sum(clamp(scores.get(key, 0.0)) * float(weights.get(key, 0.0)) for key in SCORE_KEYS)
    return round(clamp(base * (1.0 - clamp(penalty))), 4)


def recommended_action(final_score: float, noise: dict[str, Any]) -> str:
    if final_score >= 0.8:
        action = "deep_research"
    elif final_score >= 0.65:
        action = "read"
    elif final_score >= 0.5:
        action = "watch"
    else:
        action = "ignore"
    if noise.get("is_noise") and _num(noise.get("penalty")) >= 0.35 and action in {"deep_research", "read"}:
        return "watch"
    return action


def radar_bucket(candidate: dict[str, Any]) -> str:
    noise = candidate.get("noise", {}) or {}
    scores = candidate.get("scores", {}) or {}
    sources = set(candidate.get("source_hits") or [])
    topic_score = _num(scores.get("topic_relevance_score"))
    trend = _num(candidate.get("trend_score"))
    value = _num(candidate.get("value_score"))
    radar = _num(candidate.get("radar_score") or candidate.get("final_score"))
    pushed_recent = _recent_score(_primary_pushed_at(candidate), horizon_days=30)

    if (noise.get("is_noise") and _num(noise.get("penalty")) >= 0.35) or topic_score < 0.12:
        return "noise"
    if trend >= 0.65 and topic_score >= 0.45 and not noise.get("is_noise") and ("ossinsight" in sources or pushed_recent >= 0.75):
        return "breakout"
    if value >= 0.70 and trend < 0.65 and not noise.get("is_noise"):
        return "valuable_mature"
    if radar >= 0.45:
        return "watchlist"
    return "watchlist"


def score_candidate(
    candidate: dict[str, Any],
    *,
    scoring_config: dict[str, Any],
    topics_config: dict[str, dict[str, Any]],
    period: str = "daily",
    now: datetime | None = None,
) -> dict[str, Any]:
    confidence = topic_match_confidence(candidate, topics_config)
    scores = {
        "growth_score": growth_score(candidate),
        "topic_relevance_score": topic_relevance_score(candidate, topics_config),
        "engineering_quality_score": engineering_quality_score(candidate, scoring_config, now=now),
        "novelty_score": novelty_score(candidate, scoring_config, now=now),
        "community_activity_score": community_activity_score(candidate, now=now),
        "business_fit_score": business_fit_score(candidate, scoring_config),
        "source_confidence_score": source_confidence_score(candidate),
    }
    scores = {key: round(clamp(value), 4) for key, value in scores.items()}
    noise = detect_noise(candidate, scoring_config)
    trend = round(trend_score(candidate, scores, period=period, now=now), 4)
    value = round(value_score(candidate, scores), 4)
    radar = radar_score_from_layers(
        trend,
        value,
        scores["source_confidence_score"],
        scoring_config,
        period=period,
        penalty=noise["penalty"],
    )

    scored = dict(candidate)
    scored["scores"] = scores
    scored["trend_score"] = trend
    scored["value_score"] = value
    scored["radar_score"] = radar
    scored["final_score"] = radar
    scored["topic_match_confidence"] = confidence
    scored["noise"] = noise
    scored["radar_bucket"] = radar_bucket(scored)
    scored["recommended_action_rule_based"] = recommended_action(radar, noise)
    return scored


def _sort_key(candidate: dict[str, Any]) -> tuple[float, float, float, float, float, float]:
    pushed = _parse_time(_primary_pushed_at(candidate))
    timestamp = pushed.timestamp() if pushed else 0.0
    scores = candidate.get("scores", {}) or {}
    return (
        _num(candidate.get("radar_score") or candidate.get("final_score")),
        _num(scores.get("source_confidence_score")),
        _num(candidate.get("trend_score")),
        _num(scores.get("topic_relevance_score")),
        timestamp,
        _num(_metrics(candidate).get("stars")),
    )


def score_candidates(
    candidates: list[dict[str, Any]],
    *,
    scoring_config: dict[str, Any],
    topics_config: dict[str, dict[str, Any]],
    period: str = "daily",
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    scored = [
        score_candidate(
            candidate,
            scoring_config=scoring_config,
            topics_config=topics_config,
            period=period,
            now=now,
        )
        for candidate in candidates
    ]
    return sorted(scored, key=_sort_key, reverse=True)


def _source_hit_counts(scored: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "ossinsight_only": sum(1 for candidate in scored if set(candidate.get("source_hits") or []) == {"ossinsight"}),
        "github_search_only": sum(1 for candidate in scored if set(candidate.get("source_hits") or []) == {"github_search"}),
        "multi_source": sum(1 for candidate in scored if {"ossinsight", "github_search"}.issubset(set(candidate.get("source_hits") or []))),
    }


def _bucket_counts(scored: list[dict[str, Any]]) -> dict[str, int]:
    buckets = {"breakout": 0, "valuable_mature": 0, "watchlist": 0, "noise": 0}
    for candidate in scored:
        bucket = candidate.get("radar_bucket") or "watchlist"
        buckets[str(bucket)] = buckets.get(str(bucket), 0) + 1
    return buckets


def score_snapshot_payload(
    candidates_payload: dict[str, Any],
    *,
    scoring_config: dict[str, Any],
    topics_config: dict[str, dict[str, Any]],
    source_snapshot: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    period = candidates_payload.get("period") or "daily"
    candidates = candidates_payload.get("candidates") or []
    scored = score_candidates(
        candidates,
        scoring_config=scoring_config,
        topics_config=topics_config,
        period=str(period),
        now=now,
    )
    return {
        "period": period,
        "generated_at": datetime.now(UTC).isoformat(),
        "source_snapshot": source_snapshot,
        "scoring_config": scoring_config,
        "stats": {
            "total_candidates": len(candidates),
            "scored_candidates": len(scored),
            "noise_candidates": sum(1 for candidate in scored if candidate.get("noise", {}).get("is_noise")),
            "multi_source_candidates": sum(1 for candidate in scored if len(candidate.get("source_hits") or []) > 1),
            "bucket_counts": _bucket_counts(scored),
            "top_source_hits": _source_hit_counts(scored),
        },
        "candidates": scored,
    }
