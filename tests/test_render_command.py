from github_ai_trend_radar.main import main
from github_ai_trend_radar.storage.files import save_json


def _snapshot():
    return {
        "period": "daily",
        "generated_at": "2026-05-21T00:00:00+00:00",
        "stats": {"total_candidates": 1, "bucket_counts": {"breakout": 1, "valuable_mature": 0, "watchlist": 0, "noise": 0}},
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


def test_render_command_writes_md_and_html(tmp_path):
    snapshot_dir = tmp_path / "snapshots"
    output_dir = tmp_path / "reports"
    save_json(_snapshot(), snapshot_dir / "2026-05-21-daily-scored.json")

    exit_code = main(
        [
            "render",
            "--period",
            "daily",
            "--date",
            "2026-05-21",
            "--snapshot-dir",
            str(snapshot_dir),
            "--output-dir",
            str(output_dir),
        ]
    )

    assert exit_code == 0
    assert (output_dir / "2026-05-21-daily-report.md").exists()
    assert (output_dir / "2026-05-21-daily-report.html").exists()


def test_render_command_format_md_only(tmp_path):
    snapshot_dir = tmp_path / "snapshots"
    output_dir = tmp_path / "reports"
    save_json(_snapshot(), snapshot_dir / "2026-05-21-daily-scored.json")

    exit_code = main(
        [
            "render",
            "--period",
            "daily",
            "--date",
            "2026-05-21",
            "--format",
            "md",
            "--snapshot-dir",
            str(snapshot_dir),
            "--output-dir",
            str(output_dir),
        ]
    )

    assert exit_code == 0
    assert (output_dir / "2026-05-21-daily-report.md").exists()
    assert not (output_dir / "2026-05-21-daily-report.html").exists()


def test_render_command_format_html_only(tmp_path):
    snapshot_dir = tmp_path / "snapshots"
    output_dir = tmp_path / "reports"
    save_json(_snapshot(), snapshot_dir / "2026-05-21-daily-scored.json")

    exit_code = main(
        [
            "render",
            "--period",
            "daily",
            "--date",
            "2026-05-21",
            "--format",
            "html",
            "--snapshot-dir",
            str(snapshot_dir),
            "--output-dir",
            str(output_dir),
        ]
    )

    assert exit_code == 0
    assert not (output_dir / "2026-05-21-daily-report.md").exists()
    assert (output_dir / "2026-05-21-daily-report.html").exists()


def test_render_command_open_is_mocked(tmp_path, monkeypatch):
    snapshot_dir = tmp_path / "snapshots"
    output_dir = tmp_path / "reports"
    opened = []
    save_json(_snapshot(), snapshot_dir / "2026-05-21-daily-scored.json")
    monkeypatch.setattr("github_ai_trend_radar.main.webbrowser.open", lambda url: opened.append(url))

    exit_code = main(
        [
            "render",
            "--period",
            "daily",
            "--date",
            "2026-05-21",
            "--format",
            "html",
            "--open",
            "--snapshot-dir",
            str(snapshot_dir),
            "--output-dir",
            str(output_dir),
        ]
    )

    assert exit_code == 0
    assert opened


def test_render_latest_uses_resolved_date_for_outputs(tmp_path):
    snapshot_dir = tmp_path / "snapshots"
    output_dir = tmp_path / "reports"
    save_json(_snapshot(), snapshot_dir / "2026-05-20-daily-scored.json")
    save_json({**_snapshot(), "period": "daily"}, snapshot_dir / "2026-05-21-daily-scored.json")

    exit_code = main(
        [
            "render",
            "--period",
            "daily",
            "--date",
            "latest",
            "--snapshot-dir",
            str(snapshot_dir),
            "--output-dir",
            str(output_dir),
        ]
    )

    assert exit_code == 0
    assert (output_dir / "2026-05-21-daily-report.md").exists()
    assert not (output_dir / "latest-daily-report.md").exists()


def test_render_uses_report_enriched_without_reenrichment(tmp_path, monkeypatch):
    snapshot_dir = tmp_path / "snapshots"
    output_dir = tmp_path / "reports"
    report_model = {
        "title": "GitHub AI 开源趋势雷达",
        "language": "zh-CN",
        "period": "daily",
        "period_label": "Daily",
        "generated_at": "2026-05-21T00:00:00+00:00",
        "snapshot_kind": "report-enriched",
        "uses_llm": False,
        "model": "",
        "llm_status_label": "规则评分",
        "stats": {"total_candidates": 1, "bucket_counts": {"breakout": 1, "valuable_mature": 0, "watchlist": 0, "noise": 0}},
        "summary": {
            "bucket_counts": {"breakout": 1, "valuable_mature": 0, "watchlist": 0, "noise": 0},
            "multi_source_candidates": 0,
            "top_observations": ["本期判断。"],
            "main_card_count": 1,
            "main_llm_coverage": {"analyzed": 0, "total": 1},
        },
        "sections": {
            "breakout": [
                {
                    "repo_full_name": "owner/repo",
                    "html_url": "https://github.com/owner/repo",
                    "summary": "摘要",
                    "reason_to_watch": "原因",
                    "engineering_takeaway": "启发",
                    "analysis_source": "LLM 报告补齐",
                }
            ],
            "deep_research": [],
            "long_term": [],
            "noise": [],
            "valuable_mature": [],
            "watchlist": [],
        },
        "noise_summary": {"total": 0, "reason_counts": [], "examples": []},
        "report_enrichment": {"requested": True, "enabled": True, "ok_count": 1, "fallback_count": 0, "failed_count": 0, "candidate_count": 1},
        "overview_enrichment": {"requested": False, "enabled": False},
        "data_sources": [],
        "config": {"show_noise_section": True, "include_data_source_section": True},
    }
    save_json(report_model, output_dir / "2026-05-21-daily-report-enriched.json")
    monkeypatch.setattr(
        "github_ai_trend_radar.main.enrich_report_model",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should not enrich")),
    )

    exit_code = main(
        [
            "render",
            "--period",
            "daily",
            "--date",
            "latest",
            "--enrich-report",
            "--snapshot-dir",
            str(snapshot_dir),
            "--output-dir",
            str(output_dir),
        ]
    )

    assert exit_code == 0
    assert (output_dir / "2026-05-21-daily-report.html").exists()
    payload = __import__("json").loads((output_dir / "2026-05-21-daily-report-enriched.json").read_text(encoding="utf-8"))
    assert payload["sections"]["breakout"][0]["report_enrichment_status"] == "ok"
