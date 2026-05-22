from github_ai_trend_radar.main import main
from github_ai_trend_radar.storage.files import save_json


def _report_model():
    return {
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
            "top_observations": ["本期判断"],
            "main_card_count": 1,
            "main_llm_coverage": {"analyzed": 0, "total": 1},
        },
        "sections": {
            "breakout": [{"repo_full_name": "owner/repo", "html_url": "https://github.com/owner/repo", "summary": "摘要", "recommended_action_label": "深研"}],
            "deep_research": [],
            "long_term": [],
            "noise": [],
            "valuable_mature": [],
            "watchlist": [],
        },
        "noise_summary": {"total": 0, "reason_counts": [], "examples": []},
        "report_enrichment": {"requested": True, "enabled": False, "ok_count": 0, "fallback_count": 0, "failed_count": 0, "candidate_count": 1},
        "data_sources": [],
        "config": {"show_noise_section": True, "include_data_source_section": True},
    }


def test_push_dry_run_writes_summary_and_does_not_call_api(tmp_path, monkeypatch):
    output_dir = tmp_path / "reports"
    save_json(_report_model(), output_dir / "2026-05-21-daily-report-enriched.json")
    monkeypatch.setattr("github_ai_trend_radar.main.send_pushplus", lambda **kwargs: (_ for _ in ()).throw(AssertionError("API called")))

    exit_code = main(["push", "--period", "daily", "--date", "latest", "--channel", "pushplus", "--dry-run", "--output-dir", str(output_dir), "--snapshot-dir", str(tmp_path / "snapshots")])

    assert exit_code == 0
    assert (output_dir / "2026-05-21-daily-pushplus-summary.html").exists()


def test_push_without_token_skips_and_returns_zero(tmp_path, monkeypatch):
    output_dir = tmp_path / "reports"
    save_json(_report_model(), output_dir / "2026-05-21-daily-report-enriched.json")
    monkeypatch.setenv("PUSHPLUS_TOKEN", "")

    exit_code = main(["push", "--period", "daily", "--date", "latest", "--channel", "pushplus", "--output-dir", str(output_dir), "--snapshot-dir", str(tmp_path / "snapshots")])

    assert exit_code == 0


def test_push_without_token_fail_on_error_returns_nonzero(tmp_path, monkeypatch):
    output_dir = tmp_path / "reports"
    save_json(_report_model(), output_dir / "2026-05-21-daily-report-enriched.json")
    monkeypatch.setenv("PUSHPLUS_TOKEN", "")

    exit_code = main(["push", "--period", "daily", "--date", "latest", "--channel", "pushplus", "--fail-on-push-error", "--output-dir", str(output_dir), "--snapshot-dir", str(tmp_path / "snapshots")])

    assert exit_code == 1


def test_push_api_failure_default_does_not_crash(tmp_path, monkeypatch):
    output_dir = tmp_path / "reports"
    save_json(_report_model(), output_dir / "2026-05-21-daily-report-enriched.json")
    monkeypatch.setenv("PUSHPLUS_TOKEN", "token")
    monkeypatch.setattr("github_ai_trend_radar.main.send_pushplus", lambda **kwargs: type("R", (), {"skipped": False, "ok": False, "status_code": 500, "error": "bad", "response_text": "bad"})())

    exit_code = main(["push", "--period", "daily", "--date", "latest", "--channel", "pushplus", "--output-dir", str(output_dir), "--snapshot-dir", str(tmp_path / "snapshots")])

    assert exit_code == 0


def test_push_api_failure_fail_on_error_returns_nonzero(tmp_path, monkeypatch):
    output_dir = tmp_path / "reports"
    save_json(_report_model(), output_dir / "2026-05-21-daily-report-enriched.json")
    monkeypatch.setenv("PUSHPLUS_TOKEN", "token")
    monkeypatch.setattr("github_ai_trend_radar.main.send_pushplus", lambda **kwargs: type("R", (), {"skipped": False, "ok": False, "status_code": 500, "error": "bad", "response_text": "bad"})())

    exit_code = main(["push", "--period", "daily", "--date", "latest", "--channel", "pushplus", "--fail-on-push-error", "--output-dir", str(output_dir), "--snapshot-dir", str(tmp_path / "snapshots")])

    assert exit_code == 1


def test_push_uses_site_base_url(tmp_path, monkeypatch):
    output_dir = tmp_path / "reports"
    save_json(_report_model(), output_dir / "2026-05-21-daily-report-enriched.json")
    monkeypatch.setenv("SITE_BASE_URL", "https://example.com/repo")

    exit_code = main(["push", "--period", "daily", "--date", "latest", "--channel", "pushplus", "--dry-run", "--output-dir", str(output_dir), "--snapshot-dir", str(tmp_path / "snapshots")])

    assert exit_code == 0
    content = (output_dir / "2026-05-21-daily-pushplus-summary.html").read_text(encoding="utf-8")
    assert "https://example.com/repo/reports/2026-05-21-daily-report.html" in content
