"""OpenAI-compatible provider adapter."""

from __future__ import annotations

from typing import Any

from github_ai_trend_radar.llm.errors import ERROR_EMPTY_CONTENT, ERROR_MISSING_API_KEY, LLMResult
from github_ai_trend_radar.llm.providers.base import (
    BaseProvider,
    USER_AGENT,
    classify_http_error,
    provider_parameter_hint,
)


class OpenAICompatibleProvider(BaseProvider):
    @property
    def chat_url(self) -> str:
        return f"{self.config.api_base.rstrip('/')}/chat/completions"

    def provider_extra_body(self) -> dict[str, Any]:
        return {}

    def complete(self, messages: list[dict], *, json_mode: bool = False, **kwargs) -> LLMResult:
        if not self.config.api_key:
            return self._result(
                ok=False,
                content="",
                raw=None,
                error_type=ERROR_MISSING_API_KEY,
                error_message="LLM_API_KEY is missing",
            )

        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", self.config.temperature),
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        payload.update(self.provider_extra_body())
        payload.update(kwargs.get("provider_extra_body") or {})

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        }
        try:
            response = self.session.post(self.chat_url, headers=headers, json=payload, timeout=self.config.timeout)
            if response.status_code >= 400:
                message = _response_message(response)
                error_type = classify_http_error(response.status_code, message)
                if error_type == "provider_parameter_error":
                    message = provider_parameter_hint(message)
                return self._result(
                    ok=False,
                    content="",
                    raw=_safe_json(response),
                    error_type=error_type,
                    error_message=f"{response.status_code} error for {response.url}: {message}",
                )
            raw = response.json()
        except Exception as exc:
            return self._exception_result(exc)

        choice = (raw.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        content = str(message.get("content") or "")
        reasoning_content = message.get("reasoning_content")
        finish_reason = choice.get("finish_reason")
        if not content and reasoning_content:
            return self._result(
                ok=False,
                content="",
                raw=raw,
                error_type=ERROR_EMPTY_CONTENT,
                error_message="Model returned reasoning_content but empty content",
                usage=raw.get("usage"),
                reasoning_content=str(reasoning_content),
                finish_reason=finish_reason,
            )
        return self._result(
            ok=bool(content),
            content=content,
            raw=raw,
            error_type=None if content else ERROR_EMPTY_CONTENT,
            error_message=None if content else "Model returned empty content",
            usage=raw.get("usage"),
            reasoning_content=str(reasoning_content) if reasoning_content else None,
            finish_reason=finish_reason,
        )


def _safe_json(response) -> dict[str, Any] | str:
    try:
        return response.json()
    except ValueError:
        return response.text[:500]


def _response_message(response) -> str:
    raw = _safe_json(response)
    if isinstance(raw, dict):
        error = raw.get("error")
        if isinstance(error, dict):
            return str(error.get("message") or raw)
        return str(raw.get("message") or raw)
    return str(raw)
