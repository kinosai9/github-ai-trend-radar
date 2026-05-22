"""Shared LLM result and error types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


ERROR_MISSING_API_KEY = "missing_api_key"
ERROR_HTTP = "http_error"
ERROR_RATE_LIMITED = "rate_limited"
ERROR_AUTH_FAILED = "auth_failed"
ERROR_PROVIDER_PARAMETER = "provider_parameter_error"
ERROR_EMPTY_CONTENT = "empty_content"
ERROR_PARSE_FAILED = "parse_failed"
ERROR_TIMEOUT = "timeout"
ERROR_NETWORK = "network_error"
ERROR_UNKNOWN = "unknown_error"


@dataclass(frozen=True)
class LLMResult:
    ok: bool
    content: str
    raw: dict[str, Any] | str | None
    provider: str
    model: str
    error_type: str | None = None
    error_message: str | None = None
    usage: dict[str, Any] | None = None
    reasoning_content: str | None = None
    finish_reason: str | None = None


class LLMError(RuntimeError):
    def __init__(self, result: LLMResult) -> None:
        super().__init__(result.error_message or result.error_type or "LLM error")
        self.result = result
