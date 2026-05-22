"""Anthropic-compatible provider adapter."""

from __future__ import annotations

from typing import Any

from github_ai_trend_radar.llm.errors import ERROR_EMPTY_CONTENT, ERROR_MISSING_API_KEY, LLMResult
from github_ai_trend_radar.llm.providers.base import BaseProvider, USER_AGENT, classify_http_error


class AnthropicCompatibleProvider(BaseProvider):
    @property
    def messages_url(self) -> str:
        return f"{self.config.api_base.rstrip('/')}/messages"

    def complete(self, messages: list[dict], *, json_mode: bool = False, **kwargs) -> LLMResult:
        if not self.config.api_key:
            return self._result(
                ok=False,
                content="",
                raw=None,
                error_type=ERROR_MISSING_API_KEY,
                error_message="LLM_API_KEY is missing",
            )
        system, anthropic_messages = openai_to_anthropic_messages(messages)
        payload = {
            "model": self.config.model,
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "temperature": kwargs.get("temperature", self.config.temperature),
            "messages": anthropic_messages,
        }
        if system:
            payload["system"] = system
        payload.update(kwargs.get("provider_extra_body") or {})
        headers = {
            "x-api-key": self.config.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
            "user-agent": USER_AGENT,
        }
        try:
            response = self.session.post(self.messages_url, headers=headers, json=payload, timeout=self.config.timeout)
            if response.status_code >= 400:
                message = _response_message(response)
                return self._result(
                    ok=False,
                    content="",
                    raw=_safe_json(response),
                    error_type=classify_http_error(response.status_code, message),
                    error_message=f"{response.status_code} error for {response.url}: {message}",
                )
            raw = response.json()
        except Exception as exc:
            return self._exception_result(exc)
        content = parse_anthropic_content(raw.get("content") or [])
        return self._result(
            ok=bool(content),
            content=content,
            raw=raw,
            error_type=None if content else ERROR_EMPTY_CONTENT,
            error_message=None if content else "Model returned empty content",
            usage=raw.get("usage"),
            finish_reason=raw.get("stop_reason"),
        )


def openai_to_anthropic_messages(messages: list[dict]) -> tuple[str, list[dict]]:
    system_parts: list[str] = []
    converted: list[dict] = []
    for message in messages:
        role = message.get("role")
        content = message.get("content") or ""
        if role == "system":
            system_parts.append(str(content))
        elif role in {"user", "assistant"}:
            converted.append({"role": role, "content": str(content)})
    return "\n\n".join(system_parts), converted


def parse_anthropic_content(blocks: list[Any]) -> str:
    parts: list[str] = []
    for block in blocks:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(str(block.get("text") or ""))
        elif isinstance(block, str):
            parts.append(block)
    return "\n".join(part for part in parts if part)


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
