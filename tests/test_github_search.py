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


def test_github_search_falls_back_from_bad_gh_pat_to_github_token(monkeypatch, tmp_path):
    monkeypatch.setenv("GH_PAT", "bad-token")
    monkeypatch.setenv("GITHUB_TOKEN", "good-token")

    class Response:
        url = "https://api.github.com/search/repositories?q=x"
        headers = {}
        text = "{}"

        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

        def raise_for_status(self):
            if self.status_code >= 400:
                raise AssertionError("good token should be used before raising")

    class Session:
        def __init__(self):
            self.auth_headers = []

        def get(self, *args, **kwargs):
            auth = kwargs.get("headers", {}).get("Authorization", "")
            self.auth_headers.append(auth)
            if auth == "Bearer bad-token":
                return Response(401, {"message": "Bad credentials"})
            return Response(
                200,
                {
                    "items": [
                        {
                            "full_name": "owner/repo",
                            "html_url": "https://github.com/owner/repo",
                            "description": "AI agent",
                            "stargazers_count": 10,
                            "forks_count": 2,
                            "open_issues_count": 1,
                            "owner": {"login": "owner"},
                            "name": "repo",
                            "topics": ["ai-agents"],
                            "pushed_at": "2026-05-20T00:00:00Z",
                        }
                    ]
                },
            )

    session = Session()
    candidates, _, status = collect_github_search(
        {"ai_agent": {"include_queries": ['"ai agent"'], "keywords": ["ai agent"]}},
        "daily",
        snapshot_dir=tmp_path,
        pages_per_query=1,
        session=session,
    )

    assert status.ok is True
    assert candidates[0]["repo_full_name"] == "owner/repo"
    assert "Bearer bad-token" in session.auth_headers
    assert "Bearer good-token" in session.auth_headers


def test_github_search_all_bad_credentials_returns_auth_failed(monkeypatch, tmp_path):
    monkeypatch.setenv("GH_PAT", "bad-token")
    monkeypatch.setenv("GITHUB_TOKEN", "also-bad")

    class Response:
        status_code = 401
        url = "https://api.github.com/search/repositories?q=x"
        headers = {}
        text = '{"message":"Bad credentials"}'

        def json(self):
            return {"message": "Bad credentials"}

        def raise_for_status(self):
            raise AssertionError("auth failure should be reported without crashing")

    class Session:
        def get(self, *args, **kwargs):
            return Response()

    candidates, raw_path, status = collect_github_search(
        {"ai_agent": {"include_queries": ['"ai agent"']}},
        "daily",
        snapshot_dir=tmp_path,
        pages_per_query=1,
        session=Session(),
    )

    assert candidates == []
    assert raw_path.exists()
    assert status.ok is False
    assert status.error == "auth_failed"
