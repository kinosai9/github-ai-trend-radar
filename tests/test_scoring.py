from datetime import UTC, datetime

from github_ai_trend_radar.processors.scoring import (
    community_activity_score,
    engineering_quality_score,
    final_score_from_subscores,
    radar_score_from_layers,
    recommended_action,
    score_candidate,
    source_confidence_score,
    topic_match_confidence,
    topic_relevance_score,
    trend_score,
)


CONFIG = {
    "weights": {
        "growth_score": 0.25,
        "topic_relevance_score": 0.20,
        "engineering_quality_score": 0.15,
        "novelty_score": 0.15,
        "community_activity_score": 0.10,
        "business_fit_score": 0.10,
        "source_confidence_score": 0.05,
    },
    "radar_weights": {
        "daily": {"trend_score": 0.60, "value_score": 0.25, "source_confidence_score": 0.15},
        "weekly": {"trend_score": 0.50, "value_score": 0.35, "source_confidence_score": 0.15},
        "monthly": {"trend_score": 0.40, "value_score": 0.45, "source_confidence_score": 0.15},
    },
    "noise_keywords": ["awesome", "tutorial", "prompt collection", "wrapper"],
    "business_fit_keywords": ["mcp", "rag", "coding agent", "agent memory", "workflow"],
    "engineering_positive_keywords": ["quickstart", "installation", "examples", "docker", "api", "tests"],
}

TOPICS = {
    "ai_agent": {
        "weight": 1.0,
        "keywords": ["ai agent", "agent memory"],
        "github_topics": ["ai-agents"],
    },
    "mcp": {
        "weight": 1.0,
        "keywords": ["mcp", "model context protocol"],
        "github_topics": ["mcp"],
    },
}


def candidate(**overrides):
    base = {
        "repo_full_name": "owner/repo",
        "description": "AI agent memory framework for MCP workflow",
        "source_hits": ["ossinsight", "github_search"],
        "matched_focus_topics": ["ai_agent"],
        "matched_keywords": ["ai agent", "agent memory"],
        "metrics": {"stars": 1000, "forks": 80, "open_issues": 10},
        "metadata": {
            "topics": ["ai-agents", "mcp"],
            "license": "MIT",
            "pushed_at": "2026-05-20T00:00:00Z",
            "created_at": "2026-04-20T00:00:00Z",
            "default_branch": "main",
            "archived": False,
            "fork": False,
        },
        "readme_excerpt": "Quickstart installation examples docker api tests " * 30,
    }
    base.update(overrides)
    return base


def test_final_score_weighted_sum():
    scores = {key: 1.0 for key in CONFIG["weights"]}

    assert final_score_from_subscores(scores, CONFIG["weights"]) == 1.0


def test_score_range_is_clamped():
    scored = score_candidate(candidate(), scoring_config=CONFIG, topics_config=TOPICS)

    assert 0.0 <= scored["final_score"] <= 1.0
    assert scored["final_score"] == scored["radar_score"]
    assert 0.0 <= scored["trend_score"] <= 1.0
    assert 0.0 <= scored["value_score"] <= 1.0
    assert all(0.0 <= value <= 1.0 for value in scored["scores"].values())


def test_multi_source_confidence_higher_than_single_source():
    assert source_confidence_score({"source_hits": ["ossinsight", "github_search"]}) > source_confidence_score(
        {"source_hits": ["github_search"]}
    )


def test_noise_keyword_triggers_penalty():
    scored = score_candidate(
        candidate(description="awesome tutorial prompt collection"),
        scoring_config=CONFIG,
        topics_config=TOPICS,
    )

    assert scored["noise"]["is_noise"] is True
    assert scored["noise"]["penalty"] > 0


def test_awesome_list_is_discounted():
    clean = score_candidate(candidate(), scoring_config=CONFIG, topics_config=TOPICS)
    noisy = score_candidate(candidate(repo_full_name="owner/awesome-agents"), scoring_config=CONFIG, topics_config=TOPICS)

    assert noisy["final_score"] < clean["final_score"]


def test_readme_non_empty_improves_engineering_quality():
    with_readme = engineering_quality_score(candidate(), CONFIG)
    without_readme = engineering_quality_score(candidate(readme_excerpt=""), CONFIG)

    assert with_readme > without_readme


def test_matched_focus_topics_improve_topic_relevance():
    matched = topic_relevance_score(candidate(), TOPICS)
    unmatched = topic_relevance_score(candidate(matched_focus_topics=[], matched_keywords=[]), TOPICS)

    assert matched > unmatched


def test_recent_pushed_at_improves_activity_scores():
    now = datetime(2026, 5, 20, tzinfo=UTC)
    recent = candidate(metadata={**candidate()["metadata"], "pushed_at": "2026-05-20T00:00:00Z"})
    old = candidate(metadata={**candidate()["metadata"], "pushed_at": "2024-01-01T00:00:00Z"})

    assert engineering_quality_score(recent, CONFIG, now=now) > engineering_quality_score(old, CONFIG, now=now)
    assert community_activity_score(recent, now=now) > community_activity_score(old, now=now)


def test_recommended_action_thresholds():
    clean_noise = {"is_noise": False, "penalty": 0.0}

    assert recommended_action(0.81, clean_noise) == "deep_research"
    assert recommended_action(0.7, clean_noise) == "read"
    assert recommended_action(0.55, clean_noise) == "watch"
    assert recommended_action(0.4, clean_noise) == "ignore"
    assert recommended_action(0.2, clean_noise) == "ignore"
    assert recommended_action(0.9, {"is_noise": True, "penalty": 0.5}) == "watch"


def test_mature_github_search_only_has_value_but_limited_daily_trend():
    mature = score_candidate(
        candidate(
            source_hits=["github_search"],
            metrics={"stars": 50000, "forks": 3000, "open_issues": 100, "github_search_rank": 1},
            metadata={
                **candidate()["metadata"],
                "created_at": "2018-01-01T00:00:00Z",
                "pushed_at": "2026-05-18T00:00:00Z",
            },
        ),
        scoring_config=CONFIG,
        topics_config=TOPICS,
        period="daily",
        now=datetime(2026, 5, 20, tzinfo=UTC),
    )

    assert mature["value_score"] >= 0.45
    assert mature["trend_score"] < 0.65
    assert mature["radar_bucket"] != "breakout"


def test_ossinsight_project_gets_higher_trend_than_search_only():
    now = datetime(2026, 5, 20, tzinfo=UTC)
    base = candidate(
        metrics={"stars": 500, "forks": 30, "open_issues": 4, "github_search_rank": 4},
        metadata={**candidate()["metadata"], "created_at": "2026-05-01T00:00:00Z"},
    )
    oss = score_candidate(
        {**base, "source_hits": ["ossinsight"], "metrics": {**base["metrics"], "ossinsight_rank": 3}},
        scoring_config=CONFIG,
        topics_config=TOPICS,
        period="daily",
        now=now,
    )
    search = score_candidate(
        {**base, "source_hits": ["github_search"]},
        scoring_config=CONFIG,
        topics_config=TOPICS,
        period="daily",
        now=now,
    )

    assert oss["trend_score"] > search["trend_score"]


def test_weak_topic_match_does_not_score_high_relevance():
    weak = candidate(
        description="enterprise dashboard mcp workflow",
        matched_focus_topics=[],
        matched_keywords=["mcp"],
        metadata={**candidate()["metadata"], "topics": []},
        readme_excerpt="generic platform " * 20,
    )

    assert topic_match_confidence(weak, TOPICS) == "weak"
    assert topic_relevance_score(weak, TOPICS) <= 0.34


def test_short_mcp_word_is_not_strong_topic_signal():
    weak = candidate(
        description="MCP integration",
        matched_focus_topics=["mcp"],
        matched_keywords=["mcp"],
        metadata={**candidate()["metadata"], "topics": []},
        readme_excerpt="mcp " * 10,
    )

    assert topic_match_confidence(weak, TOPICS) == "weak"
    assert topic_relevance_score(weak, TOPICS) <= 0.34


def test_breakout_bucket():
    scored = score_candidate(
        candidate(metrics={"stars": 800, "forks": 50, "open_issues": 10, "ossinsight_rank": 1}),
        scoring_config=CONFIG,
        topics_config=TOPICS,
        period="daily",
        now=datetime(2026, 5, 20, tzinfo=UTC),
    )

    assert scored["radar_bucket"] == "breakout"


def test_valuable_mature_bucket():
    scored = score_candidate(
        candidate(
            source_hits=["github_search"],
            metrics={"stars": 90000, "forks": 9000, "open_issues": 100, "github_search_rank": 1},
            matched_focus_topics=["ai_agent", "mcp"],
            matched_keywords=["ai agent", "model context protocol", "agent memory"],
            metadata={
                **candidate()["metadata"],
                "created_at": "2016-01-01T00:00:00Z",
                "pushed_at": "2026-05-18T00:00:00Z",
            },
            readme_excerpt=("quickstart installation examples docker api tests model context protocol ai agent " * 80),
        ),
        scoring_config=CONFIG,
        topics_config=TOPICS,
        period="daily",
        now=datetime(2026, 5, 20, tzinfo=UTC),
    )

    assert scored["value_score"] >= 0.70
    assert scored["trend_score"] < 0.65
    assert scored["radar_bucket"] == "valuable_mature"


def test_noise_bucket():
    scored = score_candidate(
        candidate(repo_full_name="owner/awesome-agents", description="awesome tutorial prompt collection"),
        scoring_config=CONFIG,
        topics_config=TOPICS,
    )

    assert scored["radar_bucket"] == "noise"


def test_period_radar_weights_are_different():
    daily = radar_score_from_layers(0.8, 0.2, 1.0, CONFIG, period="daily")
    monthly = radar_score_from_layers(0.8, 0.2, 1.0, CONFIG, period="monthly")

    assert daily != monthly
    assert daily > monthly
