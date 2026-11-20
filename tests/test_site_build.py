import json
from types import SimpleNamespace

from github_ai_trend_radar.main import main
from github_ai_trend_radar.site.build_site import build_site, infer_site_base_url, restore_published_reports
from github_ai_trend_radar.storage.files import save_json


def _report_model(period="daily", title="GitHub AI 开源趋势雷达", period_label="Daily"):
    return {
        "title": title,
        "period": period,
        "period_label": period_label,
        "generated_at": "2026-05-21T00:00:00+00:00",
        "summary": {"top_observations": []},
        "sections": {"breakout": [], "deep_research": [], "long_term": [], "noise": []},
    }


def _write_report_bundle(root, day, period):
    prefix = f"{day}-{period}"
    label = {"daily": "Daily", "weekly": "Weekly", "monthly": "Monthly"}[period]
    save_json(_report_model(period=period, period_label=label), root / f"{prefix}-report-enriched.json")
    (root / f"{prefix}-report.html").write_text(f"<html>{prefix}</html>", encoding="utf-8")
    (root / f"{prefix}-report.md").write_text(f"# {prefix}", encoding="utf-8")


def test_build_site_generates_index_and_reports_json(tmp_path):
    reports = tmp_path / "reports"
    site = tmp_path / "site"
    reports.mkdir()
    _write_report_bundle(reports, "2026-05-21", "daily")

    result = build_site(reports_dir=reports, site_dir=site, period="daily", date_value="latest")

    assert result.index_path.exists()
    assert result.reports_json_path.exists()
    assert (site / "reports" / "2026-05-21-daily-report.html").exists()
    assert "GitHub AI 开源趋势雷达" in result.index_path.read_text(encoding="utf-8")


def test_build_site_ignores_missing_periods(tmp_path):
    reports = tmp_path / "reports"
    site = tmp_path / "site"
    reports.mkdir()
    _write_report_bundle(reports, "2026-05-21", "daily")

    result = build_site(reports_dir=reports, site_dir=site, all_periods=True)

    assert len(result.copied_reports) == 1
    assert result.copied_reports[0]["period"] == "daily"


def test_fresh_runner_restores_reports_before_deploying_next_period(tmp_path, monkeypatch):
    first_reports = tmp_path / "first-reports"
    first_reports.mkdir()
    _write_report_bundle(first_reports, "2026-11-08", "weekly")
    first_site = tmp_path / "first-site"
    build_site(reports_dir=first_reports, site_dir=first_site, period="weekly")

    def get(_, url, *, timeout):
        path = first_site / url.removeprefix("https://example.com/")
        return SimpleNamespace(
            status_code=200, raise_for_status=lambda: None,
            json=lambda: json.loads(path.read_text(encoding="utf-8")),
            content=path.read_bytes(),
        )

    monkeypatch.setattr("requests.Session.get", get)
    second_site = tmp_path / "second-site"
    assert restore_published_reports("https://example.com", second_site) == 1
    second_reports = tmp_path / "second-reports"
    second_reports.mkdir()
    _write_report_bundle(second_reports, "2026-12-01", "monthly")
    build_site(reports_dir=second_reports, site_dir=second_site, period="monthly")
    published = json.loads((second_site / "archive.json").read_text(encoding="utf-8"))
    assert [item["period"] for item in published] == ["monthly", "weekly"]
    assert (second_site / "reports" / "2026-11-08-weekly-report.md").is_file()


def test_reports_index_sorted_by_date_desc(tmp_path):
    reports = tmp_path / "reports"
    site = tmp_path / "site"
    reports.mkdir()
    _write_report_bundle(reports, "2026-05-20", "daily")
    _write_report_bundle(reports, "2026-05-21", "daily")

    build_site(reports_dir=reports, site_dir=site, period="daily", date_value="latest")
    payload = json.loads((site / "reports.json").read_text(encoding="utf-8"))

    assert payload[0]["date"] == "2026-05-21"


def test_full_report_url_inference():
    assert (
        infer_site_base_url(repository_owner="kinosai9", repository_name="github-ai-trend-radar")
        == "https://kinosai9.github.io/github-ai-trend-radar"
    )


def test_build_site_prunes_retention_by_period(tmp_path):
    reports = tmp_path / "reports"
    site = tmp_path / "site"
    reports.mkdir()
    for day in range(1, 6):
        _write_report_bundle(reports, f"2026-05-0{day}", "daily")

    build_site(reports_dir=reports, site_dir=site, all_periods=True, keep_daily=2, keep_weekly=8, keep_monthly=12)

    html_files = sorted(path.name for path in (site / "reports").glob("*-daily-report.html"))
    assert html_files == ["2026-05-04-daily-report.html", "2026-05-05-daily-report.html"]


def test_index_limits_recent_reports(tmp_path):
    reports = tmp_path / "reports"
    site = tmp_path / "site"
    reports.mkdir()
    for day in range(1, 20):
        _write_report_bundle(reports, f"2026-05-{day:02d}", "daily")
    for day in range(1, 8):
        _write_report_bundle(reports, f"2026-04-{day:02d}", "weekly")
    for month in range(1, 9):
        _write_report_bundle(reports, f"2026-{month:02d}-01", "monthly")

    build_site(reports_dir=reports, site_dir=site, all_periods=True)
    payload = json.loads((site / "reports.json").read_text(encoding="utf-8"))

    assert sum(1 for item in payload if item["period"] == "daily") == 14
    assert sum(1 for item in payload if item["period"] == "weekly") == 4
    assert sum(1 for item in payload if item["period"] == "monthly") == 6


def test_build_site_command_writes_site(tmp_path):
    reports = tmp_path / "reports"
    site = tmp_path / "site"
    reports.mkdir()
    _write_report_bundle(reports, "2026-05-21", "daily")

    exit_code = main(
        [
            "build-site",
            "--period",
            "daily",
            "--date",
            "latest",
            "--reports-dir",
            str(reports),
            "--site-dir",
            str(site),
        ]
    )

    assert exit_code == 0
    assert (site / "index.html").exists()
    assert (site / "reports.json").exists()
