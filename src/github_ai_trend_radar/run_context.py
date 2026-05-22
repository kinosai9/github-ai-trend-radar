"""Resolve GitHub Actions trigger context into a report period."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date


SCHEDULE_PERIODS = {
    "45 0 * * *": "daily",
    "30 13 * * 0": "weekly",
    "30 1 1 * *": "monthly",
}

PERIOD_LABEL_ZH = {"daily": "日报", "weekly": "周报", "monthly": "月报"}


@dataclass(frozen=True)
class RunContext:
    period: str
    report_date: str
    period_label: str
    pushplus: bool
    trigger: str

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)


def resolve_run_context(*, event_name: str | None, schedule: str | None, manual_period: str | None) -> RunContext:
    trigger = "workflow_dispatch" if event_name == "workflow_dispatch" else "schedule"
    if manual_period:
        period = manual_period
        trigger = "workflow_dispatch"
    elif schedule:
        period = SCHEDULE_PERIODS.get(schedule, "daily")
    else:
        period = "daily"
    if period not in PERIOD_LABEL_ZH:
        period = "daily"
    return RunContext(
        period=period,
        report_date=date.today().isoformat(),
        period_label=PERIOD_LABEL_ZH[period],
        pushplus=True,
        trigger=trigger,
    )
