import json

from github_ai_trend_radar.main import main


class Status:
    def __init__(self, ok=True, error=None, status_code=200):
        self.ok = ok
        self.error = error
        self.status_code = status_code


class RepoClient:
    def __init__(self, *args, **kwargs):
        pass

    def get_repo(self, owner, repo):
        return {
            "full_name": f"{owner}/{repo}",
            "name": repo,
            "html_url": f"https://github.com/{owner}/{repo}",
            "description": "repo",
            "stargazers_count": 10,
            "forks_count": 2,
            "open_issues_count": 1,
            "language": "Python",
            "topics": ["ai"],
            "owner": {"login": owner},
            "pushed_at": "2026-05-20T00:00:00Z",
        }

    def get_readme(self, owner, repo):
        return "readme"


def test_collect_ossinsight_and_github_search_merge(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "github_ai_trend_radar.main.fetch_trending_repos",
        lambda *args, **kwargs: ([{"repo_name": "owner/repo", "stars": "1"}], tmp_path / "oss.json"),
    )
    monkeypatch.setattr(
        "github_ai_trend_radar.main.collect_github_search",
        lambda *args, **kwargs: (
            [
                {
                    "repo_full_name": "owner/repo",
                    "html_url": "https://github.com/owner/repo",
                    "source_hits": ["github_search"],
                    "matched_focus_topics": ["ai_agent"],
                    "matched_keywords": ["ai agent"],
                    "metrics": {"stars": 5},
                    "metadata": {"pushed_at": "2026-05-20T00:00:00Z"},
                    "readme_excerpt": "",
                }
            ],
            tmp_path / "search.json",
            Status(),
        ),
    )
    monkeypatch.setattr("github_ai_trend_radar.main.GitHubRepoClient", RepoClient)

    assert main(["collect", "--period", "daily", "--snapshot-dir", str(tmp_path), "--focus-topics", "ai_agent"]) == 0

    payload = json.loads(next(tmp_path.glob("*-daily-candidates.json")).read_text(encoding="utf-8"))
    assert payload["sources"]["ossinsight"]["ok"] is True
    assert payload["sources"]["github_search"]["ok"] is True
    assert payload["candidates"][0]["source_hits"] == ["ossinsight", "github_search"]


def test_collect_ossinsight_fails_but_github_search_succeeds(monkeypatch, tmp_path):
    monkeypatch.setattr("github_ai_trend_radar.main.fetch_trending_repos", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("oss down")))
    monkeypatch.setattr(
        "github_ai_trend_radar.main.collect_github_search",
        lambda *args, **kwargs: (
            [
                {
                    "repo_full_name": "owner/repo",
                    "html_url": "https://github.com/owner/repo",
                    "source_hits": ["github_search"],
                    "metrics": {"stars": 5},
                    "metadata": {"pushed_at": "2026-05-20T00:00:00Z"},
                    "readme_excerpt": "",
                }
            ],
            tmp_path / "search.json",
            Status(),
        ),
    )
    monkeypatch.setattr("github_ai_trend_radar.main.GitHubRepoClient", RepoClient)

    assert main(["collect", "--period", "daily", "--snapshot-dir", str(tmp_path), "--focus-topics", "ai_agent"]) == 0

    payload = json.loads(next(tmp_path.glob("*-daily-candidates.json")).read_text(encoding="utf-8"))
    assert payload["sources"]["ossinsight"]["ok"] is False
    assert payload["sources"]["github_search"]["ok"] is True
    assert payload["candidates"]
