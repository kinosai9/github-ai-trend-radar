"""Moonshot/Kimi Open Platform provider profile."""

from __future__ import annotations

from typing import Any

from github_ai_trend_radar.llm.providers.openai_compatible import OpenAICompatibleProvider


class MoonshotProvider(OpenAICompatibleProvider):
    def provider_extra_body(self) -> dict[str, Any]:
        if self.config.thinking == "disabled":
            return {"thinking": {"type": "disabled"}}
        return {}
