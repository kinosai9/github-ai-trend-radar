from datetime import UTC, datetime

from github_ai_trend_radar.collectors.github_search import build_search_queries, collect_github_search


def test_github_search_query_contains_required_qualifiers():
    queries = build_search_queries(
        "ai_agent",
        {"include_queries": ['"ai agent"'], "github_topics": ["ai-agents"]},
        "daily",
        now=datetime(2026, 5, 20, tzinfo=UTC),
    )

    assert "archived:false" in queries[0]
    assert "fork:false" in queries[0]
    assert "pushed:>2026-04-20" in queries[0]


def test_github_search_rate_limit_returns_soft_failure(tmp_path):
    class Response:
        status_code = 403
        url = "https://api.github.com/search/repositories?q=x"
        headers = {"X-RateLimit-Remaining": "0"}
        text = '{"message":"rate limit exceeded"}'

        def json(self):
            return {"message": "rate limit exceeded"}

        def raise_for_status(self):
            raise AssertionError("should not raise before soft failure")

    class Session:
        def get(self, *args, **kwargs):
            return Response()

    candidates, raw_path, status = collect_github_search(
        {"ai_agent": {"include_queries": ['"ai agent"']}},
        "daily",
        snapshot_dir=tmp_path,
        session=Session(),
    )

    assert candidates == []
    assert raw_path.exists()
    assert status.ok is False
    assert status.error == "rate_limit_exhausted"
