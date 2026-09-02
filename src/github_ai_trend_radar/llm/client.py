"""Unified LLM client facade."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import replace
from typing import Any

import requests

from github_ai_trend_radar.llm.config import LLMConfig
from github_ai_trend_radar.llm.errors import LLMResult
from github_ai_trend_radar.llm.errors import ERROR_AUTH_FAILED, ERROR_QUOTA_EXCEEDED, ERROR_RATE_LIMITED
from github_ai_trend_radar.llm.providers.anthropic_compatible import AnthropicCompatibleProvider
from github_ai_trend_radar.llm.providers.kimi_code import KimiCodeProvider
from github_ai_trend_radar.llm.providers.moonshot import MoonshotProvider
from github_ai_trend_radar.llm.providers.openai_compatible import OpenAICompatibleProvider


LOGGER = logging.getLogger(__name__)


class LLMClient:
    def __init__(self, config: LLMConfig | None = None, *, session: requests.Session | None = None) -> None:
        self.config = config or LLMConfig.from_env()
        self.session = session
        self.provider = self._make_provider()

    @property
    def available(self) -> bool:
        return self.config.api_key_present

    @property
    def model(self) -> str:
        return self.config.model

    def complete_text(self, messages: list[dict], **kwargs) -> LLMResult:
        return self.provider.complete(messages, json_mode=False, **kwargs)

    def complete_json(self, messages: list[dict], **kwargs) -> LLMResult:
        return self.provider.complete(messages, json_mode=True, **kwargs)

    def chat_json(self, *, system_prompt: str, user_payload: dict[str, Any], **kwargs: Any) -> LLMResult:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ]
        return self.complete_json(messages, **kwargs)

    def with_timeout(self, timeout: float) -> "LLMClient":
        """Return an equivalent client with only its request timeout changed."""
        return LLMClient(replace(self.config, timeout=timeout), session=self.session)

    @classmethod
    def for_stage(cls, stage: str, *, session: requests.Session | None = None) -> "LLMClient | FallbackLLMClient":
        primary = LLMConfig.from_env(stage=stage)
        fallback_prefix = f"{stage.upper()}_LLM_FALLBACK_"
        env = os.environ
        # A report fallback is a sensible shared emergency provider for the
        # short-form scoring stage too. A dedicated scoring fallback wins.
        if stage == "scoring" and not env.get(fallback_prefix + "API_KEY"):
            fallback_prefix = "REPORT_LLM_FALLBACK_"
        fallback_key = env.get(fallback_prefix + "API_KEY")
        if not fallback_key:
            return cls(primary, session=session)
        fallback = LLMConfig(
            provider=env.get(fallback_prefix + "PROVIDER", "openai_compatible"),
            api_style=env.get(fallback_prefix + "API_STYLE", "openai_compatible"),
            api_key=fallback_key,
            api_base=env.get(fallback_prefix + "API_BASE", "https://api.deepseek.com/v1"),
            model=env.get(fallback_prefix + "MODEL", "deepseek-chat"),
            temperature=float(env.get(fallback_prefix + "TEMPERATURE", "0.6")),
            max_tokens=int(env.get(fallback_prefix + "MAX_TOKENS", "2048")),
            timeout=float(env.get(fallback_prefix + "TIMEOUT", "60")),
            thinking=env.get(fallback_prefix + "THINKING", "disabled"),
        ).with_provider_defaults()
        return FallbackLLMClient(cls(primary, session=session), cls(fallback, session=session))

    def _make_provider(self):
        if self.config.provider == "moonshot":
            return MoonshotProvider(self.config, session=self.session)
        if self.config.provider == "kimi_code" and self.config.api_style == "anthropic_compatible":
            return KimiCodeProvider(self.config, session=self.session)
        if self.config.api_style == "anthropic_compatible":
            return AnthropicCompatibleProvider(self.config, session=self.session)
        return OpenAICompatibleProvider(self.config, session=self.session)


class FallbackLLMClient:
    """Use the primary provider until it is unavailable, then fail over once."""

    def __init__(self, primary: LLMClient, fallback: LLMClient) -> None:
        self.primary, self.fallback = primary, fallback
        self.active = primary

    @property
    def available(self) -> bool:
        return self.primary.available or self.fallback.available

    @property
    def model(self) -> str:
        return self.active.model

    @property
    def config(self) -> LLMConfig:
        return self.active.config

    def complete_json(self, messages: list[dict], **kwargs) -> LLMResult:
        result = self.active.complete_json(messages, **kwargs)
        if self._should_fail_over(result):
            return self.active.complete_json(messages, **kwargs)
        return result

    def complete_text(self, messages: list[dict], **kwargs) -> LLMResult:
        result = self.active.complete_text(messages, **kwargs)
        if self._should_fail_over(result):
            return self.active.complete_text(messages, **kwargs)
        return result

    def chat_json(self, *, system_prompt: str, user_payload: dict[str, Any], **kwargs: Any) -> LLMResult:
        messages = [{"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)}]
        return self.complete_json(messages, **kwargs)

    def with_timeout(self, timeout: float) -> "FallbackLLMClient":
        """Keep both provider branches when a CLI timeout overrides defaults."""
        client = FallbackLLMClient(
            self.primary.with_timeout(timeout),
            self.fallback.with_timeout(timeout),
        )
        if self.active is self.fallback:
            client.active = client.fallback
        return client

    def _should_fail_over(self, result: LLMResult) -> bool:
        if (
            result.ok
            or result.error_type not in {ERROR_QUOTA_EXCEEDED, ERROR_RATE_LIMITED, ERROR_AUTH_FAILED}
            or self.active is not self.primary
            or not self.fallback.available
        ):
            return False
        LOGGER.warning(
            "LLM failover: provider=%s model=%s error_type=%s -> provider=%s model=%s",
            self.primary.config.provider,
            self.primary.model,
            result.error_type,
            self.fallback.config.provider,
            self.fallback.model,
        )
        self.active = self.fallback
        return True
