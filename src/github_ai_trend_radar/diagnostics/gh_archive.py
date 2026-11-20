"""Read-only GH Archive feasibility probe; not a production trend collector."""

from __future__ import annotations

import gzip
import io
import json
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

import requests


GH_ARCHIVE_URL = "https://data.gharchive.org/{stamp}.json.gz"
USER_AGENT = "github-ai-trend-radar/0.1 gh-archive-probe"


def _last_completed_hour(now: datetime | None = None) -> datetime:
    value = (now or datetime.now(UTC)).astimezone(UTC).replace(minute=0, second=0, microsecond=0)
    return value - timedelta(hours=1)


def _archive_url(moment: datetime) -> str:
    # `% -H` is not supported by Windows' strftime implementation.
    return GH_ARCHIVE_URL.format(stamp=f"{moment:%Y-%m-%d}-{moment.hour}")


def probe_gh_archive(
    *,
    timeout: float = 30,
    max_events: int = 1000,
    now: datetime | None = None,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    """Sample one completed hourly archive without persisting any event data.

    A successful probe proves delivery and parseability only. It deliberately
    does not claim that GH Archive is ready to become the report's trend source.
    """
    moment = _last_completed_hour(now)
    url = _archive_url(moment)
    http = session or requests.Session()
    response = http.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout, stream=True)
    result: dict[str, Any] = {
        "kind": "gh_archive_feasibility_probe",
        "archive_hour_utc": moment.isoformat(),
        "url": url,
        "http_status": response.status_code,
        "http_ok": response.ok,
        "parse_ok": False,
        "production_ready": False,
        "limitations": [
            "This sample only validates archive delivery and JSON event shape.",
            "A separate coverage and query-cost benchmark is required before production scoring.",
        ],
    }
    if not response.ok:
        result["error"] = response.text[:300]
        return result

    event_types: Counter[str] = Counter()
    timestamps: list[datetime] = []
    repositories: set[str] = set()
    parsed_count = 0
    try:
        raw = response.raw
        raw.decode_content = False
        with gzip.GzipFile(fileobj=raw) as gzip_stream:
            text = io.TextIOWrapper(gzip_stream, encoding="utf-8")
            for line in text:
                if not line.strip():
                    continue
                event = json.loads(line)
                parsed_count += 1
                event_types[str(event.get("type") or "unknown")] += 1
                repo = event.get("repo")
                if isinstance(repo, dict) and isinstance(repo.get("name"), str):
                    repositories.add(repo["name"])
                created_at = event.get("created_at")
                if isinstance(created_at, str):
                    try:
                        timestamps.append(datetime.fromisoformat(created_at.replace("Z", "+00:00")))
                    except ValueError:
                        pass
                if parsed_count >= max(1, max_events):
                    break
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result
    finally:
        response.close()

    result.update(
        {
            "parse_ok": parsed_count > 0,
            "sample_event_count": parsed_count,
            "event_type_counts": dict(event_types.most_common()),
            "sample_unique_repo_count": len(repositories),
            "sample_repositories": sorted(repositories)[:10],
            "sample_earliest_event_utc": min(timestamps).isoformat() if timestamps else None,
            "sample_latest_event_utc": max(timestamps).isoformat() if timestamps else None,
            "topic_metadata_available": False,
            "topic_enrichment_required": True,
        }
    )
    return result
