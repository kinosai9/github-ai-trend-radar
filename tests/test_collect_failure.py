import json

from github_ai_trend_radar.collectors.ossinsight import OSSInsightError
from github_ai_trend_radar.main import main


def _raise_ossinsight_500(*args, **kwargs):
    raise OSSInsightError("500 Server Error: Internal Server Error", status_code=500)


def test_collect_ossinsight_500_writes_error_snapshot(monkeypatch, tmp_path):
    monkeypatch.setattr("github_ai_trend_radar.main.fetch_trending_repos", _raise_ossinsight_500)
    monkeypatch.setattr(
        "github_ai_trend_radar.main.collect_github_search",
        lambda *args, **kwargs: ([], tmp_path / "search.json", type("S", (), {"ok": True, "error": None, "status_code": 200})()),
    )

    exit_code = main(["collect", "--period", "daily", "--snapshot-dir", str(tmp_path)])

    assert exit_code == 0
    error_files = list(tmp_path.glob("*-daily-ossinsight-error.json"))
    assert len(error_files) == 1
    payload = json.loads(error_files[0].read_text(encoding="utf-8"))
    assert payload["source"] == "ossinsight"
    assert payload["ok"] is False
    assert payload["status_code"] == 500


def test_collect_ossinsight_500_writes_empty_candidates_snapshot(monkeypatch, tmp_path):
    monkeypatch.setattr("github_ai_trend_radar.main.fetch_trending_repos", _raise_ossinsight_500)
    monkeypatch.setattr(
        "github_ai_trend_radar.main.collect_github_search",
        lambda *args, **kwargs: ([], tmp_path / "search.json", type("S", (), {"ok": True, "error": None, "status_code": 200})()),
    )

    exit_code = main(["collect", "--period", "weekly", "--snapshot-dir", str(tmp_path)])

    assert exit_code == 0
    candidate_files = list(tmp_path.glob("*-weekly-candidates.json"))
    assert len(candidate_files) == 1
    payload = json.loads(candidate_files[0].read_text(encoding="utf-8"))
    assert payload["period"] == "weekly"
    assert payload["sources"]["ossinsight"]["ok"] is False
    assert payload["sources"]["ossinsight"]["status_code"] == 500
    assert payload["candidates"] == []


def test_collect_ossinsight_500_fail_fast_returns_failure(monkeypatch, tmp_path):
    monkeypatch.setattr("github_ai_trend_radar.main.fetch_trending_repos", _raise_ossinsight_500)
    monkeypatch.setattr(
        "github_ai_trend_radar.main.collect_github_search",
        lambda *args, **kwargs: ([], tmp_path / "search.json", type("S", (), {"ok": True, "error": None, "status_code": 200})()),
    )

    exit_code = main(
        [
            "collect",
            "--period",
            "monthly",
            "--snapshot-dir",
            str(tmp_path),
            "--fail-fast",
        ]
    )

    assert exit_code == 1
    assert list(tmp_path.glob("*-monthly-ossinsight-error.json"))
    assert list(tmp_path.glob("*-monthly-candidates.json"))
