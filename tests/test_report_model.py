import pytest

from github_ai_trend_radar.renderers.report_model import (
    SnapshotNotFoundError,
    build_report_model,
    find_latest_snapshot,
    load_best_snapshot,
    load_report_config,
    resolve_render_input,
    select_bucket_items,
)
from github_ai_trend_radar.storage.files import save_json


def _candidate(name, bucket="breakout", radar=0.5, llm=None):
    payload = {
        "repo_full_name": name,
        "html_url": f"https://github.com/{name}",
        "description": "AI agent framework",
        "radar_bucket": bucket,
        "radar_score": radar,
        "trend_score": radar - 0.1,
        "value_score": radar - 0.2,
        "source_hits": ["ossinsight"],
        "matched_focus_topics": ["ai_agent"],
        "metrics": {"stars": 100, "forks": 5},
        "metadata": {"pushed_at": "2026-05-21T00:00:00Z"},
        "noise": {"is_noise": bucket == "noise", "noise_reasons": []},
    }
    if llm is not None:
        payload["llm_adjusted_score"] = llm
        payload["final_recommended_action"] = "read"
        payload["llm_analysis"] = {"summary_for_report": "LLM summary"}
    return payload


def _snapshot(candidates):
    return {
        "period": "daily",
        "generated_at": "2026-05-21T00:00:00+00:00",
        "stats": {"total_candidates": len(candidates), "multi_source_candidates": 0},
        "candidates": candidates,
    }


def test_load_best_snapshot_prefers_llm_scored(tmp_path):
    save_json(_snapshot([_candidate("owner/scored")]), tmp_path / "2026-05-21-daily-scored.json")
    save_json(
        {**_snapshot([_candidate("owner/llm")]), "llm": {"model": "test"}},
        tmp_path / "2026-05-21-daily-llm-scored.json",
    )

    payload, path, kind = load_best_snapshot("daily", "2026-05-21", snapshot_dir=tmp_path)

    assert kind == "llm-scored"
    assert path.name.endswith("llm-scored.json")
    assert payload["candidates"][0]["repo_full_name"] == "owner/llm"


def test_load_best_snapshot_fallbacks_to_scored(tmp_path):
    save_json(_snapshot([_candidate("owner/scored")]), tmp_path / "2026-05-21-daily-scored.json")

    _, path, kind = load_best_snapshot("daily", "2026-05-21", snapshot_dir=tmp_path)

    assert kind == "scored"
    assert path.name.endswith("scored.json")


def test_load_best_snapshot_missing_raises_clear_error(tmp_path):
    with pytest.raises(SnapshotNotFoundError) as exc:
        load_best_snapshot("daily", "2026-05-21", snapshot_dir=tmp_path)

    assert "run --period daily" in str(exc.value)


def test_build_report_model_handles_missing_fields_without_none_text():
    config = load_report_config("missing-config-dir")
    report = build_report_model(_snapshot([{"repo_full_name": "owner/repo", "radar_bucket": "watchlist"}]), config)

    assert report["sections"]["watchlist"][0]["repo_full_name"] == "owner/repo"
    assert "None" not in str(report)
    assert "null" not in str(report)


def test_bucket_selection_limit_and_llm_sorting():
    candidates = [
        _candidate("owner/a", llm=0.4),
        _candidate("owner/b", llm=0.9),
        _candidate("owner/c", llm=0.7),
    ]

    selected = select_bucket_items(candidates, "breakout", 2)

    assert [item["repo_full_name"] for item in selected] == ["owner/b", "owner/c"]


def test_find_latest_snapshot_prefers_latest_date_and_enriched_same_day(tmp_path):
    reports = tmp_path / "reports"
    snapshots = tmp_path / "snapshots"
    save_json({"kind": "old"}, snapshots / "2026-05-20-daily-llm-scored.json")
    save_json({"kind": "new-scored"}, snapshots / "2026-05-21-daily-scored.json")
    save_json({"kind": "new-enriched"}, reports / "2026-05-21-daily-report-enriched.json")

    resolved = find_latest_snapshot("daily", [reports, snapshots])

    assert resolved.date.isoformat() == "2026-05-21"
    assert resolved.kind == "report-enriched"


def test_latest_does_not_select_other_period(tmp_path):
    snapshots = tmp_path / "snapshots"
    save_json({"kind": "weekly"}, snapshots / "2026-05-22-weekly-scored.json")
    save_json({"kind": "daily"}, snapshots / "2026-05-21-daily-scored.json")

    resolved = find_latest_snapshot("daily", [snapshots])

    assert resolved.date.isoformat() == "2026-05-21"
    assert resolved.period == "daily"


def test_resolve_render_input_explicit_date_over_latest(tmp_path):
    snapshots = tmp_path / "snapshots"
    reports = tmp_path / "reports"
    save_json({"kind": "older"}, snapshots / "2026-05-20-daily-scored.json")
    save_json({"kind": "latest"}, snapshots / "2026-05-21-daily-scored.json")

    payload, resolved = resolve_render_input("daily", "2026-05-20", snapshot_dir=snapshots, report_dir=reports)

    assert payload["kind"] == "older"
    assert resolved.date.isoformat() == "2026-05-20"


def test_find_latest_snapshot_missing_error_is_clear(tmp_path):
    with pytest.raises(SnapshotNotFoundError) as exc:
        find_latest_snapshot("daily", [tmp_path])

    assert "No snapshot found for period=daily" in str(exc.value)
