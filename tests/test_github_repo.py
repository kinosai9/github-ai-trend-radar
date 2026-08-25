from github_ai_trend_radar.collectors.github_repo import GitHubRepoClient


def test_github_repo_client_falls_back_from_bad_gh_pat_to_github_token(monkeypatch):
    monkeypatch.setenv("GH_PAT", "bad-token")
    monkeypatch.setenv("GITHUB_TOKEN", "good-token")

    class Response:
        url = "https://api.github.com/repos/owner/repo"
        headers = {}
        text = "{}"

        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

        def raise_for_status(self):
            if self.status_code >= 400:
                raise AssertionError("good token should be tried before raising")

    class Session:
        def __init__(self):
            self.headers = {}
            self.auth_headers = []

        def get(self, *args, **kwargs):
            auth = kwargs.get("headers", {}).get("Authorization", "")
            self.auth_headers.append(auth)
            if auth == "Bearer bad-token":
                return Response(401, {"message": "Bad credentials"})
            return Response(200, {"full_name": "owner/repo"})

    session = Session()
    client = GitHubRepoClient(session=session, retries=1)

    assert client.get_repo("owner", "repo") == {"full_name": "owner/repo"}
    assert "Bearer bad-token" in session.auth_headers
    assert "Bearer good-token" in session.auth_headers
