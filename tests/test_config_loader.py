import json

from github_ai_trend_radar.config_loader import load_topics_config


def test_topics_default_yaml_can_be_loaded():
    topics = load_topics_config("config")

    assert "ai_agent" in topics
    assert "mcp" in topics


def test_topics_local_overrides_default(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "topics.default.yaml").write_text(
        "topics:\n  ai_agent:\n    weight: 1.0\n    include_queries: [default]\n",
        encoding="utf-8",
    )
    (config_dir / "topics.local.yaml").write_text(
        "topics:\n  ai_agent:\n    weight: 2.0\n",
        encoding="utf-8",
    )

    topics = load_topics_config(config_dir)

    assert topics["ai_agent"]["weight"] == 2.0
    assert topics["ai_agent"]["include_queries"] == ["default"]


def test_topics_json_overrides_config(monkeypatch, tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "topics.default.yaml").write_text(
        "topics:\n  ai_agent:\n    weight: 1.0\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("TOPICS_JSON", json.dumps({"topics": {"mcp": {"weight": 3.0}}}))

    topics = load_topics_config(config_dir)

    assert list(topics) == ["mcp"]
    assert topics["mcp"]["weight"] == 3.0


def test_focus_topics_selects_subset():
    topics = load_topics_config("config", focus_topics="ai_agent,mcp")

    assert list(topics) == ["ai_agent", "mcp"]
