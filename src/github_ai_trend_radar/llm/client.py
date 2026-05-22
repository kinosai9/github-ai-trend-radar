"""Unified LLM client facade."""

from __future__ import annotations

import json
import time
from typing import Any

import requests

from github_ai_trend_radar.llm.config import LLMConfig
from github_ai_trend_radar.llm.errors import LLMResult
from github_ai_trend_radar.llm.providers.anthropic_compatible import AnthropicCompatibleProvider
from github_ai_trend_radar.llm.providers.kimi_code import KimiCodeProvider
from github_ai_trend_radar.llm.providers.moonshot import MoonshotProvider
from github_ai_trend_radar.llm.providers.openai_compatible import OpenAICompatibleProvider


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

    def chat_json(self, *, system_prompt: str, user_payload: dict[str, Any]) -> LLMResult:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ]
        return self.complete_json(messages)

    def _make_provider(self):
        if self.config.provider == "moonshot":
            return MoonshotProvider(self.config, session=self.session)
        if self.config.provider == "kimi_code" and self.config.api_style == "anthropic_compatible":
            return KimiCodeProvider(self.config, session=self.session)
        if self.config.api_style == "anthropic_compatible":
            return AnthropicCompatibleProvider(self.config, session=self.session)
        return OpenAICompatibleProvider(self.config, session=self.session)
