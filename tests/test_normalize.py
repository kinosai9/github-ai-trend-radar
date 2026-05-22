from github_ai_trend_radar.processors.normalize import normalize_repo_full_name


def test_normalize_repo_full_name_from_url():
    assert normalize_repo_full_name("https://github.com/OpenAI/openai-python.git") == "OpenAI/openai-python"


def test_normalize_repo_full_name_from_owner_repo():
    assert normalize_repo_full_name(owner="modelcontextprotocol", repo="python-sdk") == "modelcontextprotocol/python-sdk"

