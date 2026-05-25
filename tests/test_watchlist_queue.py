from urllib.parse import parse_qs, urlparse

from github_ai_trend_radar.renderers.html_ink import render_html
from github_ai_trend_radar.watchlist_queue import attach_issue_links, build_issue_url, issue_body_yaml, parse_issue_body


def _item():
    return {
        "repo": "anthropics/claude-plugins-official",
        "html_url": "https://github.com/anthropics/claude-plugins-official",
        "source_report": "2026-05-22-daily",
        "source_section": "breakout",
        "recommended_action": "deep_research",
        "topics": ["coding_agent", "mcp"],
        "radar_score": 0.86,
        "llm_adjusted_score": 0.88,
        "quality_gate": "pass",
        "reason": "Claude Code 官方插件目录",
    }


def test_issue_url_is_encoded_and_parseable():
    url = build_issue_url("https://github.com/kinosai9/github-ai-trend-radar", _item())
    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    assert parsed.path.endswith("/issues/new")
    assert query["title"][0] == "Watchlist: anthropics/claude-plugins-official"
    assert query["labels"][0] == "watchlist,pending-review"
    body = parse_issue_body(query["body"][0])
    assert body["repo"] == "anthropics/claude-plugins-official"
    assert body["topics"] == ["coding_agent", "mcp"]


def test_issue_body_yaml_parse_roundtrip():
    body = issue_body_yaml(_item())
    parsed = parse_issue_body(body)
    assert parsed["quality_gate"] == "pass"
    assert parsed["reason"] == "Claude Code 官方插件目录"


def test_no_repo_url_hides_button():
    report = {
        "language": "zh-CN",
        "title": "GitHub AI 开源趋势雷达",
        "period": "daily",
        "period_label": "Daily",
        "generated_at": "2026-05-22",
        "snapshot_kind": "scored",
        "stats": {"total_candidates": 1},
        "summary": {"top_observations": ["判断"], "bucket_counts": {"breakout": 1}, "main_llm_coverage": {"analyzed": 0, "total": 1}, "multi_source_candidates": 1},
        "report_enrichment": {"enabled": False},
        "sections": {"breakout": [_project()], "deep_research": [], "long_term": [], "noise": []},
        "noise_summary": {"total": 0, "reason_counts": [], "examples": []},
        "config": {"show_noise_section": True, "include_data_source_section": False},
        "data_sources": [],
    }
    attach_issue_links(report, repo_url="")
    assert "watchlist_issue_url" not in report["sections"]["breakout"][0]
    assert "加入观察队列" not in render_html(report)


def test_repo_url_shows_button():
    report = {
        "language": "zh-CN",
        "title": "GitHub AI 开源趋势雷达",
        "period": "daily",
        "period_label": "Daily",
        "generated_at": "2026-05-22",
        "snapshot_kind": "scored",
        "stats": {"total_candidates": 1},
        "summary": {"top_observations": ["判断"], "bucket_counts": {"breakout": 1}, "main_llm_coverage": {"analyzed": 0, "total": 1}, "multi_source_candidates": 1},
        "report_enrichment": {"enabled": False},
        "sections": {"breakout": [_project()], "deep_research": [], "long_term": [], "noise": []},
        "noise_summary": {"total": 0, "reason_counts": [], "examples": []},
        "config": {"show_noise_section": True, "include_data_source_section": False},
        "data_sources": [],
    }
    attach_issue_links(report, repo_url="https://github.com/kinosai9/github-ai-trend-radar")
    html = render_html(report)
    assert "加入观察队列" in html
    assert "issues/new" in html


def _project():
    return {
        "repo_full_name": "anthropics/claude-plugins-official",
        "html_url": "https://github.com/anthropics/claude-plugins-official",
        "summary": "摘要",
        "reason_to_watch": "原因",
        "engineering_takeaway": "启发",
        "recommended_action": "deep_research",
        "recommended_action_label": "深研",
        "radar_score": 0.86,
        "llm_adjusted_score": 0.88,
        "topic_match_confidence": "strong",
        "matched_focus_topics": ["coding_agent", "mcp"],
        "quality_gate": {"level": "pass"},
        "noise": {"is_noise": False},
    }
