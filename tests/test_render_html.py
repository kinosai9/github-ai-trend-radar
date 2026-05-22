from github_ai_trend_radar.renderers.html_ink import render_html
from github_ai_trend_radar.renderers.report_model import build_report_model, load_report_config


def test_html_render_contains_basic_structure_css_and_link():
    snapshot = {
        "period": "daily",
        "generated_at": "2026-05-21T00:00:00+00:00",
        "stats": {"total_candidates": 1},
        "candidates": [
            {
                "repo_full_name": "owner/repo",
                "html_url": "https://github.com/owner/repo",
                "description": "AI agent framework",
                "radar_bucket": "breakout",
                "radar_score": 0.8,
                "trend_score": 0.7,
                "value_score": 0.6,
                "source_hits": ["ossinsight"],
            }
        ],
    }
    report = build_report_model(snapshot, load_report_config("missing-config-dir"))

    output = render_html(report)

    assert "<!DOCTYPE html>" in output
    assert "<style>" in output
    assert "GitHub AI 开源趋势雷达" in output
    assert 'href="https://github.com/owner/repo"' in output
