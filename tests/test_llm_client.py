from github_ai_trend_radar.llm.client import LLMClient
from github_ai_trend_radar.llm.config import LLMConfig
from github_ai_trend_radar.llm.errors import (
    ERROR_AUTH_FAILED,
    ERROR_EMPTY_CONTENT,
    ERROR_PROVIDER_PARAMETER,
    ERROR_RATE_LIMITED,
)
from github_ai_trend_radar.llm.providers.anthropic_compatible import (
    openai_to_anthropic_messages,
    parse_anthropic_content,
)
from github_ai_trend_radar.llm.providers.kimi_code import KimiCodeProvider


def test_new_and_old_env_fallback(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_BASE", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "old-key")
    monkeypatch.setenv("OPENAI_API_BASE", "https://old.example/v1")
    monkeypatch.setenv("MODEL_NAME", "old-model")

    config = LLMConfig.from_env()

    assert config.api_key == "old-key"
    assert config.api_base == "https://old.example/v1"
    assert config.model == "old-model"


def test_research_llm_env_falls_back_to_general(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "general-key")
    monkeypatch.setenv("LLM_API_BASE", "https://general.example/v1")
    monkeypatch.setenv("LLM_MODEL", "general-model")
    for name in (
        "RESEARCH_LLM_API_KEY",
        "RESEARCH_LLM_API_BASE",
        "RESEARCH_LLM_MODEL",
        "RESEARCH_LLM_PROVIDER",
        "RESEARCH_LLM_API_STYLE",
    ):
        monkeypatch.delenv(name, raising=False)

    config = LLMConfig.from_research_env()

    assert config.api_key == "general-key"
    assert config.api_base == "https://general.example/v1"
    assert config.model == "general-model"


def test_research_llm_env_overrides_general(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "general-key")
    monkeypatch.setenv("LLM_API_BASE", "https://general.example/v1")
    monkeypatch.setenv("LLM_MODEL", "general-model")
    monkeypatch.setenv("RESEARCH_LLM_API_KEY", "research-key")
    monkeypatch.setenv("RESEARCH_LLM_API_BASE", "https://research.example/v1")
    monkeypatch.setenv("RESEARCH_LLM_MODEL", "research-model")
    monkeypatch.setenv("RESEARCH_LLM_TIMEOUT", "120")
    monkeypatch.setenv("RESEARCH_LLM_MAX_TOKENS", "4096")

    config = LLMConfig.from_research_env()

    assert config.api_key == "research-key"
    assert config.api_base == "https://research.example/v1"
    assert config.model == "research-model"
    assert config.timeout == 120
    assert config.max_tokens == 4096


def test_deep_research_llm_env_overrides_research_and_general(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "general-key")
    monkeypatch.setenv("RESEARCH_LLM_API_KEY", "research-key")
    monkeypatch.setenv("RESEARCH_LLM_MODEL", "research-model")
    monkeypatch.setenv("DEEP_RESEARCH_LLM_API_KEY", "deep-key")
    monkeypatch.setenv("DEEP_RESEARCH_LLM_MODEL", "deep-model")

    config = LLMConfig.from_research_env()

    assert config.api_key == "deep-key"
    assert config.model == "deep-model"


def test_moonshot_defaults(monkeypatch):
    monkeypatch.delenv("LLM_THINKING", raising=False)
    monkeypatch.delenv("LLM_TEMPERATURE", raising=False)
    config = LLMConfig(
        provider="moonshot",
        api_base="https://api.moonshot.ai/v1",
        model="kimi-k2.6",
    ).with_provider_defaults()

    assert config.thinking == "disabled"
    assert config.temperature == 0.6


def test_moonshot_thinking_enabled_temperature():
    config = LLMConfig(
        provider="moonshot",
        api_base="https://api.moonshot.ai/v1",
        model="kimi-k2.6",
        thinking="enabled",
        thinking_explicit=True,
    ).with_provider_defaults()

    assert config.temperature == 1.0


def test_openai_compatible_response_parse():
    class Response:
        status_code = 200

        def json(self):
            return {
                "choices": [{"message": {"content": "{\"ok\": true}"}, "finish_reason": "stop"}],
                "usage": {"total_tokens": 3},
            }

    class Session:
        def post(self, *args, **kwargs):
            return Response()

    client = LLMClient(LLMConfig(api_key="key"), session=Session())
    result = client.complete_json([{"role": "user", "content": "hi"}])

    assert result.ok is True
    assert result.content == '{"ok": true}'
    assert result.usage == {"total_tokens": 3}


def test_empty_content_with_reasoning_content():
    class Response:
        status_code = 200

        def json(self):
            return {"choices": [{"message": {"content": "", "reasoning_content": "thinking"}}]}

    class Session:
        def post(self, *args, **kwargs):
            return Response()

    client = LLMClient(LLMConfig(api_key="key"), session=Session())
    result = client.complete_json([{"role": "user", "content": "hi"}])

    assert result.ok is False
    assert result.error_type == ERROR_EMPTY_CONTENT
    assert result.reasoning_content == "thinking"


def test_moonshot_provider_adds_thinking_disabled_body():
    class Response:
        status_code = 200

        def json(self):
            return {"choices": [{"message": {"content": "{\"ok\": true}"}}]}

    class Session:
        def __init__(self):
            self.payload = None

        def post(self, *args, **kwargs):
            self.payload = kwargs["json"]
            return Response()

    session = Session()
    config = LLMConfig(
        provider="moonshot",
        api_key="key",
        api_base="https://api.moonshot.ai/v1",
        model="kimi-k2.6",
    ).with_provider_defaults()
    LLMClient(config, session=session).complete_json([{"role": "user", "content": "hi"}])

    assert session.payload["thinking"] == {"type": "disabled"}
    assert session.payload["temperature"] == 0.6


def test_anthropic_messages_conversion_and_response_parse():
    system, messages = openai_to_anthropic_messages(
        [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]
    )

    assert system == "sys"
    assert messages == [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]
    assert parse_anthropic_content([{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]) == "a\nb"


def test_kimi_code_anthropic_endpoint_adds_v1_messages():
    config = LLMConfig(
        provider="kimi_code",
        api_style="anthropic_compatible",
        api_base="https://api.kimi.com/coding/",
        model="kimi-for-coding",
    ).with_provider_defaults()

    assert KimiCodeProvider(config).messages_url == "https://api.kimi.com/coding/v1/messages"


def test_http_error_mapping():
    class Response:
        def __init__(self, status_code, message):
            self.status_code = status_code
            self.url = "https://example.test"
            self.text = message
            self._message = message

        def json(self):
            return {"error": {"message": self._message}}

    class Session:
        def __init__(self, response):
            self.response = response

        def post(self, *args, **kwargs):
            return self.response

    for status, message, expected in [
        (403, "forbidden", ERROR_AUTH_FAILED),
        (429, "rate limited", ERROR_RATE_LIMITED),
        (400, "invalid temperature", ERROR_PROVIDER_PARAMETER),
        (422, "invalid thinking", ERROR_PROVIDER_PARAMETER),
    ]:
        result = LLMClient(LLMConfig(api_key="key"), session=Session(Response(status, message))).complete_json(
            [{"role": "user", "content": "hi"}]
        )
        assert result.error_type == expected
