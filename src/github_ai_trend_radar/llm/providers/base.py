"""Base provider adapter utilities."""

from __future__ import annotations

import requests

from github_ai_trend_radar.llm.config import LLMConfig
from github_ai_trend_radar.llm.errors import (
    ERROR_AUTH_FAILED,
    ERROR_HTTP,
    ERROR_NETWORK,
    ERROR_PROVIDER_PARAMETER,
    ERROR_RATE_LIMITED,
    ERROR_TIMEOUT,
    ERROR_UNKNOWN,
    LLMResult,
)


USER_AGENT = "github-ai-trend-radar/0.1"


class BaseProvider:
    def __init__(self, config: LLMConfig, *, session: requests.Session | None = None) -> None:
        self.config = config
        self.session = session or requests.Session()

    def complete(self, messages: list[dict], *, json_mode: bool = False, **kwargs) -> LLMResult:
        raise NotImplementedError

    def _result(self, **kwargs) -> LLMResult:
        return LLMResult(provider=self.config.provider, model=self.config.model, **kwargs)

    def _exception_result(self, exc: Exception) -> LLMResult:
        if isinstance(exc, requests.Timeout):
            return self._result(ok=False, content="", raw=None, error_type=ERROR_TIMEOUT, error_message=str(exc))
        if isinstance(exc, requests.RequestException):
            return self._result(ok=False, content="", raw=None, error_type=ERROR_NETWORK, error_message=str(exc))
        return self._result(ok=False, content="", raw=None, error_type=ERROR_UNKNOWN, error_message=str(exc))


def classify_http_error(status_code: int, message: str) -> str:
    lowered = message.lower()
    if status_code in {401, 403}:
        return ERROR_AUTH_FAILED
    if status_code == 429:
        return ERROR_RATE_LIMITED
    if status_code in {400, 422} and any(
        term in lowered for term in ("temperature", "thinking", "tool", "response_format")
    ):
        return ERROR_PROVIDER_PARAMETER
    return ERROR_HTTP


def provider_parameter_hint(message: str) -> str:
    lowered = message.lower()
    if "temperature" in lowered or "thinking" in lowered:
        return (
            f"{message} | Hint: Kimi K2.6 thinking disabled uses temperature=0.6; "
            "thinking enabled uses temperature=1.0."
        )
    return message
