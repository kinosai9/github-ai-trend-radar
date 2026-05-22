from pathlib import Path

from github_ai_trend_radar.renderers.pushplus_summary import build_full_report_url, render_pushplus_summary


def _report():
    return {
        "title": "GitHub AI 开源趋势雷达",
        "period_label": "Daily",
        "generated_at": "2026-05-21T00:00:00+00:00",
        "stats": {"total_candidates": 3},
        "summary": {
            "top_observations": ["判断一", "判断二"],
            "multi_source_candidates": 2,
            "main_llm_coverage": {"analyzed": 2, "total": 3},
        },
        "sections": {
            "breakout": [
                {"repo_full_name": f"owner/b{i}", "html_url": f"https://github.com/owner/b{i}", "summary": "摘要", "recommended_action_label": "深研"}
                for i in range(4)
            ],
            "deep_research": [
                {"repo_full_name": f"owner/d{i}", "html_url": f"https://github.com/owner/d{i}", "summary": "摘要"}
                for i in range(3)
            ],
        },
        "run_summary": {"status": "partial_success"},
    }


def test_pushplus_summary_contains_observations_top3_and_full_report_link():
    html = render_pushplus_summary(_report(), full_report_url="https://example.com/report.html", full_report_is_url=True)

    assert "判断一" in html
    assert "owner/b0" in html
    assert "owner/b2" in html
    assert "owner/b3" not in html
    assert "owner/d1" in html
    assert "owner/d2" not in html
    assert "https://example.com/report.html" in html


def test_site_base_url_derives_full_report_url():
    url, is_url = build_full_report_url(
        explicit_url=None,
        site_base_url="https://username.github.io/github-ai-trend-radar/",
        report_path=Path("data/reports/x.html"),
        resolved_date="2026-05-21",
        period="daily",
    )

    assert is_url is True
    assert url == "https://username.github.io/github-ai-trend-radar/reports/2026-05-21-daily-report.html"


def test_summary_html_is_compact_without_full_report_css():
    html = render_pushplus_summary(_report(), full_report_url="local.html", full_report_is_url=False)

    assert "<script" not in html
    assert "<style" not in html
    assert "--ink" not in html


def test_pushplus_summary_contains_run_status():
    html = render_pushplus_summary(_report(), full_report_url="local.html", full_report_is_url=False)
    assert "运行状态：部分成功" in html
