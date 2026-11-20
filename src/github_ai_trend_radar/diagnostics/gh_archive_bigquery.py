"""Cost-gated BigQuery validation for GH Archive weekly/monthly trend queries."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

import requests


BIGQUERY_SCOPE = "https://www.googleapis.com/auth/bigquery"
BIGQUERY_QUERY_URL = "https://bigquery.googleapis.com/bigquery/v2/projects/{project}/queries"
WINDOW_DAYS = {"weekly": 7, "monthly": 28}
EVENT_TYPES = ["WatchEvent", "ForkEvent", "PushEvent", "PullRequestEvent", "IssuesEvent", "ReleaseEvent"]


@dataclass(frozen=True)
class BigQueryConfig:
    project: str
    location: str = "US"
    timeout: float = 60.0

    @classmethod
    def from_env(cls, *, timeout: float = 60.0) -> "BigQueryConfig | None":
        project = os.getenv("GH_ARCHIVE_BIGQUERY_PROJECT", "").strip()
        if not project:
            return None
        return cls(
            project=project,
            location=os.getenv("GH_ARCHIVE_BIGQUERY_LOCATION", "US").strip() or "US",
            timeout=timeout,
        )


def window_dates(period: str, *, today: date | None = None) -> tuple[date, date]:
    if period not in WINDOW_DAYS:
        raise ValueError("GH Archive BigQuery validation only supports weekly or monthly periods.")
    end = (today or datetime.now(UTC).date()) - timedelta(days=1)
    return end - timedelta(days=WINDOW_DAYS[period] - 1), end


def build_trend_query() -> str:
    """Aggregate public GitHub event velocity without claiming topic relevance."""
    return """
SELECT
  repo.name AS repo_full_name,
  COUNT(*) AS total_events,
  COUNTIF(type = 'WatchEvent') AS watch_events,
  COUNTIF(type = 'ForkEvent') AS fork_events,
  COUNTIF(type = 'PushEvent') AS push_events,
  COUNTIF(type = 'PullRequestEvent') AS pull_request_events,
  COUNTIF(type = 'IssuesEvent') AS issue_events,
  COUNTIF(type = 'ReleaseEvent') AS release_events
FROM `githubarchive.day.*`
WHERE _TABLE_SUFFIX BETWEEN @start_date AND @end_date
  AND type IN UNNEST(@event_types)
  AND repo.name IS NOT NULL
GROUP BY repo_full_name
ORDER BY total_events DESC, watch_events DESC
LIMIT @limit
""".strip()


def _query_parameters(start: date, end: date, limit: int) -> list[dict[str, Any]]:
    return [
        {
            "name": "start_date",
            "parameterType": {"type": "STRING"},
            "parameterValue": {"value": start.strftime("%Y%m%d")},
        },
        {
            "name": "end_date",
            "parameterType": {"type": "STRING"},
            "parameterValue": {"value": end.strftime("%Y%m%d")},
        },
        {
            "name": "event_types",
            "parameterType": {"type": "ARRAY", "arrayType": {"type": "STRING"}},
            "parameterValue": {"arrayValues": [{"value": value} for value in EVENT_TYPES]},
        },
        {"name": "limit", "parameterType": {"type": "INT64"}, "parameterValue": {"value": str(limit)}},
    ]


def _credentials_headers() -> tuple[dict[str, str], str | None]:
    try:
        import google.auth
        from google.auth.transport.requests import Request
    except ImportError:
        return {}, "google-auth is not installed"
    try:
        credentials, _ = google.auth.default(scopes=[BIGQUERY_SCOPE])
        credentials.refresh(Request())
    except Exception as exc:  # credentials are external configuration, not report data.
        return {}, f"BigQuery credentials unavailable: {type(exc).__name__}: {exc}"
    return {"Authorization": f"Bearer {credentials.token}", "Content-Type": "application/json"}, None


def _estimate_cost_usd(bytes_processed: int) -> float:
    return round((bytes_processed / (1024**4)) * 6.25, 6)


def validate_bigquery_trend_query(
    *,
    period: str,
    execute: bool = False,
    max_bytes_billed: int | None = None,
    limit: int = 500,
    timeout: float = 60.0,
    today: date | None = None,
    session: requests.Session | None = None,
    config: BigQueryConfig | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Dry-run by default; execution requires an explicit bytes-billed ceiling."""
    start, end = window_dates(period, today=today)
    result: dict[str, Any] = {
        "kind": "gh_archive_bigquery_validation",
        "period": period,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "dry_run": not execute,
        "topic_enrichment_required": True,
        "production_ready": False,
    }
    if execute and not max_bytes_billed:
        result.update({"ok": False, "error_type": "missing_cost_guard", "error": "--execute requires --max-bytes-billed."})
        return result

    active_config = config or BigQueryConfig.from_env(timeout=timeout)
    if not active_config:
        result.update({"ok": False, "error_type": "missing_bigquery_project", "error": "Set GH_ARCHIVE_BIGQUERY_PROJECT before validation."})
        return result

    active_headers, auth_error = (headers, None) if headers is not None else _credentials_headers()
    if auth_error:
        result.update({"ok": False, "error_type": "missing_bigquery_credentials", "error": auth_error})
        return result

    payload: dict[str, Any] = {
        "query": build_trend_query(),
        "useLegacySql": False,
        "parameterMode": "NAMED",
        "queryParameters": _query_parameters(start, end, max(1, min(limit, 1000))),
        "location": active_config.location,
        "dryRun": not execute,
        "timeoutMs": int(active_config.timeout * 1000),
        "labels": {"component": "trendradar", "purpose": "gharchivevalidation"},
    }
    if execute:
        payload["maximumBytesBilled"] = str(max_bytes_billed)

    try:
        response = (session or requests.Session()).post(
            BIGQUERY_QUERY_URL.format(project=active_config.project),
            headers=active_headers,
            json=payload,
            timeout=active_config.timeout,
        )
        body = response.json()
    except (requests.RequestException, ValueError) as exc:
        result.update({"ok": False, "error_type": "network_or_response_error", "error": f"{type(exc).__name__}: {exc}"})
        return result

    if not response.ok or body.get("error"):
        error = body.get("error", {}) if isinstance(body, dict) else {}
        message = error.get("message") if isinstance(error, dict) else str(body)
        result.update({"ok": False, "http_status": response.status_code, "error_type": "bigquery_error", "error": str(message)[:500]})
        return result

    bytes_processed = int(body.get("totalBytesProcessed", 0) or 0)
    result.update(
        {
            "ok": True,
            "http_status": response.status_code,
            "estimated_bytes_processed": bytes_processed,
            "estimated_tib_processed": round(bytes_processed / (1024**4), 6),
            "estimated_on_demand_cost_usd_before_free_tier": _estimate_cost_usd(bytes_processed),
            "maximum_bytes_billed": max_bytes_billed if execute else None,
            "job_complete": body.get("jobComplete"),
            "query_result_rows_returned": len(body.get("rows", []) or []),
        }
    )
    return result
