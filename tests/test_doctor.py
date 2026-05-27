from github_ai_trend_radar.diagnostics.doctor import env_exists
from github_ai_trend_radar.main import main


def test_env_exists_reports_presence_without_exposing_value(monkeypatch):
    monkeypatch.setenv("GH_PAT", "secret-value")

    assert env_exists("GH_PAT") is True


def test_doctor_command_outputs_diagnostics(monkeypatch, capsys):
    class Response:
        status_code = 200
        url = "https://example.test/"
        headers = {"content-type": "application/json"}
        text = '{"ok": true}'

    calls = []

    def fake_get(url, *, headers, timeout):
        calls.append((url, headers, timeout))
        response = Response()
        response.url = url
        return response

    monkeypatch.setattr("github_ai_trend_radar.diagnostics.doctor.requests.get", fake_get)

    assert main(["doctor", "--timeout", "1"]) == 0

    output = capsys.readouterr().out
    assert "Python:" in output
    assert "requests:" in output
    assert "HTTP_PROXY:" in output
    assert "GITHUB_TOKEN:" in output
    assert "OPENAI_API_KEY:" in output
    assert "GitHub rate limit" in output
    assert "OSSInsight trends past_24_hours TypeScript" in output
    assert len(calls) == 8


def test_doctor_llm_without_api_key_does_not_crash(monkeypatch, capsys):
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setattr("github_ai_trend_radar.diagnostics.doctor.requests.get", lambda *args, **kwargs: type("R", (), {"status_code": 200, "url": args[0], "headers": {}, "text": "{}"})())

    assert main(["doctor", "--llm", "--timeout", "1"]) == 0

    output = capsys.readouterr().out
    assert "LLM Provider" in output
    assert "LLM_API_KEY: missing" in output
    assert "missing_api_key" in output


def test_doctor_warns_for_kimi_code_openai_style(monkeypatch, capsys):
    monkeypatch.setenv("LLM_PROVIDER", "kimi_code")
    monkeypatch.setenv("LLM_API_STYLE", "openai_compatible")
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setattr("github_ai_trend_radar.diagnostics.doctor.requests.get", lambda *args, **kwargs: type("R", (), {"status_code": 200, "url": args[0], "headers": {}, "text": "{}"})())

    assert main(["doctor", "--llm", "--timeout", "1"]) == 0

    assert "may reject OpenAI-compatible requests" in capsys.readouterr().out


def test_doctor_research_llm_uses_research_prefix(monkeypatch, capsys):
    for name in ("LLM_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr("github_ai_trend_radar.main.load_local_env", lambda: None)
    monkeypatch.setenv("RESEARCH_LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("RESEARCH_LLM_API_STYLE", "openai_compatible")
    monkeypatch.setenv("RESEARCH_LLM_API_KEY", "")
    monkeypatch.setenv("RESEARCH_LLM_MODEL", "research-model")
    monkeypatch.setattr("github_ai_trend_radar.diagnostics.doctor.requests.get", lambda *args, **kwargs: type("R", (), {"status_code": 200, "url": args[0], "headers": {}, "text": "{}"})())

    assert main(["doctor", "--research-llm", "--timeout", "1"]) == 0

    output = capsys.readouterr().out
    assert "Research LLM Provider" in output
    assert "RESEARCH_LLM_MODEL: research-model" in output
    assert "RESEARCH_LLM_API_KEY: missing" in output
