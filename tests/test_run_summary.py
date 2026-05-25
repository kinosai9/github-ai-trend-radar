import json

from github_ai_trend_radar.run_summary import write_run_summary


def test_run_summary_contains_quality_gate_editorial_and_timing(tmp_path):
    report = {
        "stats": {"quality_gate": {"pass": 1, "warn": 2, "block": 3}},
        "overview_enrichment": {"enabled": True, "ok": True},
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
    assert "render" in payload["timing_seconds"]
