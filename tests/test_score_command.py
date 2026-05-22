import json

from github_ai_trend_radar.main import main
from github_ai_trend_radar.storage.files import save_json, snapshot_path


def test_score_command_reads_candidates_and_writes_scored_snapshot(tmp_path):
    candidates_path = snapshot_path(tmp_path, "daily", "candidates")
    save_json(
        {
            "period": "daily",
            "generated_at": "2026-05-20T00:00:00+00:00",
            "sources": {},
            "candidates": [
                {
                    "repo_full_name": "owner/repo",
                    "html_url": "https://github.com/owner/repo",
                    "description": "AI agent memory framework",
                    "source_hits": ["ossinsight", "github_search"],
                    "matched_focus_topics": ["ai_agent"],
                    "matched_keywords": ["ai agent"],
                    "metrics": {"stars": 100, "forks": 10},
                    "metadata": {
                        "topics": ["ai-agents"],
                        "license": "MIT",
                        "pushed_at": "2026-05-20T00:00:00Z",
                        "default_branch": "main",
                    },
                    "readme_excerpt": "quickstart installation examples docker api tests",
                }
            ],
        },
        candidates_path,
    )

    exit_code = main(["score", "--period", "daily", "--snapshot-dir", str(tmp_path), "--top-n", "1"])

    assert exit_code == 0
    scored_path = snapshot_path(tmp_path, "daily", "scored")
    payload = json.loads(scored_path.read_text(encoding="utf-8"))
    assert payload["period"] == "daily"
    assert payload["stats"]["total_candidates"] == 1
    assert payload["stats"]["bucket_counts"]
    assert payload["stats"]["top_source_hits"]["multi_source"] == 1
    assert payload["candidates"][0]["final_score"] >= 0
    assert payload["candidates"][0]["radar_score"] == payload["candidates"][0]["final_score"]
    assert payload["candidates"][0]["radar_bucket"] in {
        "breakout",
        "valuable_mature",
        "watchlist",
        "noise",
    }
    assert payload["candidates"][0]["recommended_action_rule_based"] in {
        "ignore",
        "watch",
        "read",
        "deep_research",
    }
