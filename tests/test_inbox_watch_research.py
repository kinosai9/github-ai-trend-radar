import json

from github_ai_trend_radar.deep_research import write_deep_research_report
from github_ai_trend_radar.inbox import _run_gh, parse_issue, sync_inbox
from github_ai_trend_radar.main import main
from github_ai_trend_radar.watchlist import add_watch_item, load_watchlist
from github_ai_trend_radar.watchlist_queue import issue_body_yaml


def test_inbox_issue_json_is_parsed():
    issue = {
        "number": 123,
        "title": "Watchlist: owner/repo",
        "url": "https://github.com/x/y/issues/123",
        "createdAt": "2026-05-24T00:00:00Z",
        "body": issue_body_yaml(
            {
                "repo": "owner/repo",
                "html_url": "https://github.com/owner/repo",
                "source_report": "2026-05-22-daily",
                "source_section": "breakout",
                "recommended_action": "deep_research",
                "topics": ["mcp"],
                "reason": "reason",
            }
        ),
    }
    parsed = parse_issue(issue)
    assert parsed["repo"] == "owner/repo"
    assert parsed["topics"] == ["mcp"]


def test_gh_missing_returns_clear_error(monkeypatch):
    monkeypatch.setattr("github_ai_trend_radar.inbox.shutil.which", lambda name: None)
    ok, message, items = sync_inbox("owner/repo")
    assert ok is False
    assert "GitHub CLI" in message
    assert items == []


def test_gh_runner_uses_utf8_with_replacement(monkeypatch):
    captured = {}

    def fake_run(args, **kwargs):
        captured.update(kwargs)
        return type("Result", (), {"returncode": 0, "stdout": "[]", "stderr": ""})()

    monkeypatch.setattr("github_ai_trend_radar.inbox.subprocess.run", fake_run)
    _run_gh(["gh", "issue", "list"])

    assert captured["encoding"] == "utf-8"
    assert captured["errors"] == "replace"


def test_sync_inbox_invalid_json_returns_clear_error(monkeypatch):
    def fake_run(args):
        if args[1:3] == ["auth", "status"]:
            return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        return type("Result", (), {"returncode": 0, "stdout": "not json", "stderr": ""})()

    monkeypatch.setattr("github_ai_trend_radar.inbox.shutil.which", lambda name: "gh")
    monkeypatch.setattr("github_ai_trend_radar.inbox._run_gh", fake_run)

    ok, message, items = sync_inbox("owner/repo")

    assert ok is False
    assert "Failed to parse GitHub CLI JSON output" in message
    assert items == []


def test_watch_add_duplicate_updates(tmp_path):
    path = tmp_path / "watchlist.yaml"
    add_watch_item("owner/repo", reason="old", topics=["mcp"], path=path)
    add_watch_item("owner/repo", reason="new", topics=["coding_agent"], path=path)
    payload = load_watchlist(path)
    assert len(payload["items"]) == 1
    assert payload["items"][0]["reason"] == "new"
    assert sorted(payload["items"][0]["topics"]) == ["coding_agent", "mcp"]


def test_inbox_add_command_promotes_issue(tmp_path):
    inbox_path = tmp_path / "inbox.json"
    watchlist_path = tmp_path / "watchlist.yaml"
    inbox_path.write_text(json.dumps({"items": [{"number": 123, "repo": "owner/repo", "reason": "reason", "topics": ["mcp"]}]}), encoding="utf-8")

    exit_code = main(["watch", "promote", "--issue", "123", "--inbox-path", str(inbox_path), "--watchlist-path", str(watchlist_path)])

    assert exit_code == 0
    assert load_watchlist(watchlist_path)["items"][0]["repo"] == "owner/repo"


def test_deep_research_without_llm_writes_summary(tmp_path):
    class Client:
        def get_repo(self, owner, repo):
            return {"full_name": f"{owner}/{repo}", "html_url": f"https://github.com/{owner}/{repo}", "description": "desc"}

        def get_readme(self, owner, repo):
            return "README"

    md, html = write_deep_research_report("owner/repo", output_dir=tmp_path, client=Client(), use_llm=False)
    assert md.exists()
    assert html.exists()
    assert "本地资料汇总版" in md.read_text(encoding="utf-8")
