"""OSSInsight Trending API collector."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

import requests

from github_ai_trend_radar.storage.files import save_json, snapshot_path


LOGGER = logging.getLogger(__name__)

OSSINSIGHT_TRENDS_URL = "https://api.ossinsight.io/v1/trends/repos/"
PERIOD_TO_OSSINSIGHT = {
    "daily": "past_24_hours",
    "weekly": "past_week",
    "monthly": "past_month",
}
DEFAULT_USER_AGENT = "github-ai-trend-radar/0.1 (+https://github.com/)"


class OSSInsightError(RuntimeError):
    """Raised when OSSInsight collection fails."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def ossinsight_period(period: str) -> str:
    try:
        return PERIOD_TO_OSSINSIGHT[period]
    except KeyError as exc:
        raise ValueError(f"Unsupported period: {period!r}") from exc


def _request_json_with_retry(
    session: requests.Session,
    url: str,
    *,
    params: dict[str, str],
    timeout: float,
    retries: int,
) -> dict[str, Any]:
    last_error: Exception | None = None
    last_status_code: int | None = None
    for attempt in range(1, retries + 1):
        try:
            response = session.get(url, params=params, timeout=timeout)
            last_status_code = response.status_code
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            response = getattr(exc, "response", None)
            if response is not None:
                last_status_code = response.status_code
            LOGGER.warning("OSSInsight request failed on attempt %s/%s: %s", attempt, retries, exc)
            if attempt < retries:
                time.sleep(min(2 ** (attempt - 1), 5))

    raise OSSInsightError(
        f"OSSInsight API request failed after {retries} attempts: {last_error}",
        status_code=last_status_code,
    ) from last_error


def _find_repo_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if not isinstance(payload, dict):
        return []

    for key in ("rows", "repos", "repositories", "items"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]

    data = payload.get("data")
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        return _find_repo_items(data)

    return []


def fetch_trending_repos(
    period: str,
    *,
    snapshot_dir: Path | str = "data/snapshots",
    timeout: float = 20,
    retries: int = 3,
    session: requests.Session | None = None,
) -> tuple[list[dict[str, Any]], Path]:
    oss_period = ossinsight_period(period)
    http = session or requests.Session()
    http.headers.update(
        {
            "Accept": "application/json",
            "User-Agent": DEFAULT_USER_AGENT,
        }
    )
    params = {"period": oss_period, "language": "All"}
    try:
        payload = _request_json_with_retry(
            http,
            OSSINSIGHT_TRENDS_URL,
            params=params,
            timeout=timeout,
            retries=retries,
        )
    except OSSInsightError as exc:
        if exc.status_code != 500:
            raise
        LOGGER.warning(
            "OSSInsight returned 500 with language=All for %s; retrying without language",
            period,
        )
        params = {"period": oss_period}
        payload = _request_json_with_retry(
            http,
            OSSINSIGHT_TRENDS_URL,
            params=params,
            timeout=timeout,
            retries=retries,
        )
    raw_path = snapshot_path(snapshot_dir, period, "ossinsight-raw")
    save_json(payload, raw_path)

    items = _find_repo_items(payload)
    LOGGER.info("Fetched %s OSSInsight trending repositories for %s", len(items), period)
    return items, raw_path
