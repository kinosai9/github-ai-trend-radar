from datetime import date

from github_ai_trend_radar.diagnostics.gh_archive_bigquery import (
    BigQueryConfig,
    build_trend_query,
    validate_bigquery_trend_query,
    window_dates,
)


class Response:
    status_code = 200
    ok = True

    def json(self):
        return {"jobComplete": True, "totalBytesProcessed": "1099511627776"}


class Session:
    def __init__(self):
        self.payload = None

    def post(self, *args, **kwargs):
        self.payload = kwargs["json"]
        return Response()


def test_weekly_and_monthly_windows_exclude_the_current_partial_day():
    today = date(2026, 9, 7)
    assert window_dates("weekly", today=today) == (date(2026, 8, 31), date(2026, 9, 6))
    assert window_dates("monthly", today=today) == (date(2026, 8, 10), date(2026, 9, 6))


def test_query_uses_daily_wildcard_and_event_velocity_fields():
    query = build_trend_query()
    assert "`githubarchive.day.*`" in query
    assert "WatchEvent" in query
    assert "PushEvent" in query
    assert "_TABLE_SUFFIX BETWEEN @start_date AND @end_date" in query


def test_dry_run_returns_estimated_bytes_without_execution():
    session = Session()
    result = validate_bigquery_trend_query(
        period="weekly",
        today=date(2026, 9, 7),
        config=BigQueryConfig(project="test-project"),
        headers={"Authorization": "Bearer test"},
        session=session,
    )
    assert result["ok"] is True
    assert result["dry_run"] is True
    assert result["estimated_bytes_processed"] == 1024**4
    assert result["estimated_on_demand_cost_usd_before_free_tier"] == 6.25
    assert session.payload["dryRun"] is True
    assert "maximumBytesBilled" not in session.payload


def test_execution_requires_a_cost_guard():
    result = validate_bigquery_trend_query(period="monthly", execute=True)
    assert result["ok"] is False
    assert result["error_type"] == "missing_cost_guard"


def test_missing_project_is_a_clear_non_network_failure(monkeypatch):
    monkeypatch.delenv("GH_ARCHIVE_BIGQUERY_PROJECT", raising=False)
    result = validate_bigquery_trend_query(period="weekly")
    assert result["error_type"] == "missing_bigquery_project"
