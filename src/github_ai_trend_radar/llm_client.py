"""Backward-compatible imports for the LLM provider adapter layer."""

from __future__ import annotations

from github_ai_trend_radar.llm.client import LLMClient as OpenAICompatibleClient
from github_ai_trend_radar.llm.config import DEFAULT_MODEL
from github_ai_trend_radar.llm.errors import LLMError as LLMClientError
from github_ai_trend_radar.llm.errors import LLMResult as LLMResponse

DEFAULT_OPENAI_API_BASE = "https://api.openai.com/v1"

__all__ = [
    "DEFAULT_MODEL",
    "DEFAULT_OPENAI_API_BASE",
    "LLMClientError",
    "LLMResponse",
    "OpenAICompatibleClient",
]
