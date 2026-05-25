from urllib.parse import parse_qs, urlparse

from github_ai_trend_radar.renderers.html_ink import render_html
from github_ai_trend_radar.watchlist_queue import (
    attach_issue_links,
    build_issue_url,
    build_watchlist_queue,
    is_auto_queue_candidate,
    is_manual_watch_candidate,
    issue_body_yaml,
    parse_issue_body,
)


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
    assert "watch_add_command" in report["sections"]["breakout"][0]
    assert "deep_research_command" in report["sections"]["breakout"][0]
    assert "加入观察队列" not in render_html(report)
    assert "本地观察" in render_html(report)


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


def test_manual_eligible_non_auto_item_has_button_but_not_auto_queue():
    project = _project()
    project["recommended_action"] = "watch"
    project["recommended_action_label"] = "观察"
    project["radar_score"] = 0.3
    project["llm_adjusted_score"] = 0.3
    report = _report([project])

    attach_issue_links(report, repo_url="https://github.com/kinosai9/github-ai-trend-radar")

    assert is_manual_watch_candidate(project) is True
    assert is_auto_queue_candidate(project) is False
    assert build_watchlist_queue(report) == []
    assert report["watchlist_queue"]["count"] == 0
    assert report["sections"]["breakout"][0]["watchlist_queue_eligible"] is True
    assert "watchlist_issue_url" in report["sections"]["breakout"][0]


def test_report_enriched_fixture_render_contains_watchlist_button():
    report = _report([_project()])
    attach_issue_links(report, repo_url="https://github.com/kinosai9/github-ai-trend-radar")

    html = render_html(report)

    assert "加入观察队列" in html
    assert "本地深研" in html


def test_blocked_or_noise_item_is_not_manual_candidate():
    blocked = _project()
    blocked["quality_gate"] = {"level": "block"}
    noisy = _project()
    noisy["noise"] = {"is_noise": True}
    ignored = _project()
    ignored["recommended_action"] = "ignore"

    assert is_manual_watch_candidate(blocked) is False
    assert is_manual_watch_candidate(noisy) is False
    assert is_manual_watch_candidate(ignored) is False


def _report(projects):
    return {
        "language": "zh-CN",
        "title": "GitHub AI 开源趋势雷达",
        "period": "daily",
        "period_label": "Daily",
        "generated_at": "2026-05-22",
        "snapshot_kind": "report-enriched",
        "stats": {"total_candidates": len(projects)},
        "summary": {"top_observations": ["判断"], "bucket_counts": {"breakout": len(projects)}, "main_llm_coverage": {"analyzed": 0, "total": len(projects)}, "multi_source_candidates": 1},
        "report_enrichment": {"enabled": False},
        "sections": {"breakout": projects, "deep_research": [], "long_term": [], "noise": []},
        "noise_summary": {"total": 0, "reason_counts": [], "examples": []},
        "config": {"show_noise_section": True, "include_data_source_section": False},
        "data_sources": [],
        "uses_llm": False,
    }


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
