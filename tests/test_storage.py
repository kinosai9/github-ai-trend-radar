import json

from github_ai_trend_radar.storage.files import save_json, snapshot_path


def test_snapshot_save(tmp_path):
    path = snapshot_path(tmp_path, "daily", "candidates")
    save_json([{"repo_full_name": "owner/repo"}], path)

    assert path.exists()
    assert path.name.endswith("-daily-candidates.json")
    assert json.loads(path.read_text(encoding="utf-8")) == [{"repo_full_name": "owner/repo"}]
