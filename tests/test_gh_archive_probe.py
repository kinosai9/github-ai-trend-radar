import gzip
import io
from datetime import UTC, datetime

from github_ai_trend_radar.diagnostics.gh_archive import probe_gh_archive


class Response:
    status_code = 200
    ok = True
    text = ""

    def __init__(self, body: bytes):
        self.raw = io.BytesIO(body)

    def close(self):
        pass


class Session:
    def __init__(self, response):
        self.response = response

    def get(self, *args, **kwargs):
        return self.response


def test_gh_archive_probe_reads_only_a_bounded_event_sample():
    lines = "\n".join(
        [
            '{"type":"WatchEvent","created_at":"2026-09-07T01:00:00Z","repo":{"name":"owner/repo"}}',
            '{"type":"PushEvent","created_at":"2026-09-07T01:05:00Z"}',
        ]
    ).encode()
    result = probe_gh_archive(
        now=datetime(2026, 9, 7, 2, 20, tzinfo=UTC),
        max_events=1,
        session=Session(Response(gzip.compress(lines))),
    )

    assert result["http_ok"] is True
    assert result["parse_ok"] is True
    assert result["sample_event_count"] == 1
    assert result["event_type_counts"] == {"WatchEvent": 1}
    assert result["sample_repositories"] == ["owner/repo"]
    assert result["topic_enrichment_required"] is True
    assert result["production_ready"] is False
    assert result["url"].endswith("2026-09-07-1.json.gz")
