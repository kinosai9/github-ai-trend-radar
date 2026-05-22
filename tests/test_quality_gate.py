from datetime import UTC, datetime

from github_ai_trend_radar.processors.quality_gate import apply_quality_gate_to_payload, evaluate_quality_gate
from github_ai_trend_radar.renderers.report_model import build_report_model


def _candidate(**overrides):
    candidate = {
        "repo_full_name": "owner/repo",
        "html_url": "https://github.com/owner/repo",
        "description": "AI agent framework",
        "radar_bucket": "breakout",
        "final_recommended_action": "deep_research",
        "recommended_action_rule_based": "deep_research",
        "topic_match_confidence": "strong",
        "source_hits": ["ossinsight", "github_search"],
        "metrics": {"stars": 200},
        "metadata": {"license": "MIT", "pushed_at": "2026-05-01T00:00:00Z"},
        "readme_excerpt": "Installation quickstart examples documentation api tests " * 40,
        "noise": {"is_noise": False},
    }
    candidate.update(overrides)
    return candidate


def test_short_readme_low_stars_blocks():
    gate = evaluate_quality_gate(
        _candidate(metrics={"stars": 5}, readme_excerpt="tiny"),
        now=datetime(2026, 5, 22, tzinfo=UTC),
    )
    assert gate["level"] == "block"


def test_multi_source_complete_readme_passes():
    gate = evaluate_quality_gate(_candidate(), now=datetime(2026, 5, 22, tzinfo=UTC))
    assert gate["level"] == "pass"


def test_quality_gate_block_not_in_main_sections():
    payload = {
        "period": "daily",
        "generated_at": "2026-05-22T00:00:00+00:00",
        "stats": {"total_candidates": 1},
        "candidates": [_candidate(metrics={"stars": 2}, readme_excerpt="tiny")],
    }
    gated = apply_quality_gate_to_payload(payload)
    report = build_report_model(gated, {"top_n": {"breakout": 5, "deep_research": 5, "valuable_mature": 3, "watchlist": 3, "noise": 5}, "show_noise_section": True})
    assert report["sections"]["breakout"] == []
    assert report["sections"]["deep_research"] == []


def test_quality_gate_warn_shows_quality_tip():
    payload = {
        "period": "daily",
        "generated_at": "2026-05-22T00:00:00+00:00",
        "stats": {"total_candidates": 1},
        "candidates": [_candidate(metrics={"stars": 40}, readme_excerpt="Installation " * 80, metadata={"pushed_at": "2026-05-01T00:00:00Z"})],
    }
    gated = apply_quality_gate_to_payload(payload)
    report = build_report_model(gated, {"top_n": {"breakout": 5, "deep_research": 5, "valuable_mature": 3, "watchlist": 3, "noise": 5}, "show_noise_section": True})
    item = report["sections"]["breakout"][0]
    assert item["maturity_label"] in {"早期", "可试用", "信息不足"}
    assert "建议先观察" in item["quality_tip"]
