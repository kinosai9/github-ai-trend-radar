from github_ai_trend_radar.config.env import load_local_env


def test_load_local_env_reads_env_local_without_real_file(monkeypatch, tmp_path):
    monkeypatch.delenv("GH_PAT", raising=False)
    (tmp_path / ".env.local").write_text("GH_PAT=test-token\n", encoding="utf-8")

    load_local_env(tmp_path)

    assert __import__("os").getenv("GH_PAT") == "test-token"
