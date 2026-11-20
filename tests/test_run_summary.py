import json

from github_ai_trend_radar.run_summary import write_run_summary


def test_run_summary_contains_quality_gate_editorial_and_timing(tmp_path):
    report = {
        "stats": {"quality_gate": {"pass": 1, "warn": 2, "block": 3}},
        "overview_enrichment": {"enabled": True, "ok": True},
        "report_enrichment": {
            "enabled": True,
            "candidate_count": 1,
            "ok_count": 0,
            "failed_count": 1,
            "attempts": [{"repo_full_name": "owner/repo", "error_type": "empty_content"}],
        },
        "llm": {"candidate_count": 5},
        "data_sources": [{"name": "OSSInsight"}],
        "watchlist_queue": {"count": 2, "items": [{"repo": "owner/repo"}], "file": "data/watchlist_queue/x.json"},
    }

    path = write_run_summary(output_dir=tmp_path, period="daily", report_date="2026-05-22", report=report)
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["quality_gate"] == {"pass": 1, "warn": 2, "block": 3}
    assert payload["watchlist"]["queue_count"] == 2
    assert payload["watchlist"]["queue_file"] == "data/watchlist_queue/x.json"
    assert payload["llm"]["report_editorial"]["status"] == "ok"
    assert payload["llm"]["report_card_enrichment"]["failed_count"] == 1
    assert payload["llm"]["report_card_enrichment"]["attempts"][0]["error_type"] == "empty_content"
    assert "render" in payload["timing_seconds"]


def test_push_step_cannot_overwrite_prior_partial_success(tmp_path):
    report = {"stats": {}, "data_sources": []}
    write_run_summary(
        output_dir=tmp_path,
        period="weekly",
        report_date="2026-09-06",
        report=report,
        status="partial_success",
        warnings=["three project-level LLM calls failed"],
    )
    path = write_run_summary(
        output_dir=tmp_path,
        period="weekly",
        report_date="2026-09-06",
        report=report,
        status="success",
        pushplus_status="sent",
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["status"] == "partial_success"
    assert payload["pushplus"]["status"] == "sent"
    assert payload["warnings"] == ["three project-level LLM calls failed"]
