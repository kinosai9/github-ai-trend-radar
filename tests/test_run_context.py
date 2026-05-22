import json

from github_ai_trend_radar.main import main
from github_ai_trend_radar.run_context import resolve_run_context


def test_daily_cron_resolves_daily():
    context = resolve_run_context(event_name="schedule", schedule="45 0 * * *", manual_period=None)
    assert context.period == "daily"


def test_weekly_cron_resolves_weekly():
    context = resolve_run_context(event_name="schedule", schedule="30 13 * * 0", manual_period=None)
    assert context.period == "weekly"


def test_monthly_cron_resolves_monthly():
    context = resolve_run_context(event_name="schedule", schedule="30 1 1 * *", manual_period=None)
    assert context.period == "monthly"


def test_manual_period_takes_priority(capsys):
    exit_code = main(["resolve-run-context", "--event-name", "workflow_dispatch", "--schedule", "45 0 * * *", "--manual-period", "weekly"])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["period"] == "weekly"
    assert payload["trigger"] == "workflow_dispatch"
