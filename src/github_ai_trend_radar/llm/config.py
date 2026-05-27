"""LLM provider configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse


DEFAULT_API_BASE = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"


@dataclass(frozen=True)
class LLMConfig:
    provider: str = "openai_compatible"
    api_style: str = "openai_compatible"
    api_key: str = ""
    api_base: str = DEFAULT_API_BASE
    model: str = DEFAULT_MODEL
    temperature: float = 0.6
    max_tokens: int = 2048
    timeout: float = 60.0
    thinking: str = "disabled"
    temperature_explicit: bool = False
    thinking_explicit: bool = False

    @property
    def api_key_present(self) -> bool:
        return bool(self.api_key)

    @property
    def api_base_host(self) -> str:
        parsed = urlparse(self.api_base)
        return parsed.netloc or self.api_base

    @classmethod
    def from_env(cls) -> "LLMConfig":
        api_key = _env("LLM_API_KEY", _env("OPENAI_API_KEY", ""))
        api_base = _env("LLM_API_BASE", _env("OPENAI_API_BASE", DEFAULT_API_BASE))
        model = _env("LLM_MODEL", _env("MODEL_NAME", DEFAULT_MODEL))
        provider = _env("LLM_PROVIDER", "openai_compatible")
        api_style = _env("LLM_API_STYLE", "openai_compatible")
        thinking_raw = os.getenv("LLM_THINKING")
        temperature_raw = os.getenv("LLM_TEMPERATURE")
        thinking = _normalize_thinking(thinking_raw or "disabled")
        config = cls(
            provider=provider,
            api_style=api_style,
            api_key=api_key,
            api_base=api_base,
            model=model,
            temperature=_float(temperature_raw, 0.6),
            max_tokens=_int(os.getenv("LLM_MAX_TOKENS"), 2048),
            timeout=_float(os.getenv("LLM_TIMEOUT"), 60.0),
            thinking=thinking,
            temperature_explicit=temperature_raw is not None and temperature_raw.strip() != "",
            thinking_explicit=thinking_raw is not None and thinking_raw.strip() != "",
        )
        return config.with_provider_defaults()

    @classmethod
    def from_research_env(cls) -> "LLMConfig":
        base = cls.from_env()
        research_api_key = _research_env("API_KEY")
        research_api_base = _research_env("API_BASE")
        research_model = _research_env("MODEL")
        research_provider = _research_env("PROVIDER")
        research_api_style = _research_env("API_STYLE")
        research_temperature = _research_env("TEMPERATURE")
        research_max_tokens = _research_env("MAX_TOKENS")
        research_timeout = _research_env("TIMEOUT")
        research_thinking = _research_env("THINKING")
        config = cls(
            provider=_value_or(research_provider, base.provider),
            api_style=_value_or(research_api_style, base.api_style),
            api_key=_value_or(research_api_key, base.api_key),
            api_base=_value_or(research_api_base, base.api_base),
            model=_value_or(research_model, base.model),
            temperature=_float(research_temperature, base.temperature),
            max_tokens=_int(research_max_tokens, base.max_tokens),
            timeout=_float(research_timeout, base.timeout),
            thinking=_normalize_thinking(_value_or(research_thinking, base.thinking)),
            temperature_explicit=research_temperature is not None and research_temperature.strip() != "" or base.temperature_explicit,
            thinking_explicit=research_thinking is not None and research_thinking.strip() != "" or base.thinking_explicit,
        )
        return config.with_provider_defaults()

    def with_provider_defaults(self) -> "LLMConfig":
        provider = self.provider
        text = f"{self.provider} {self.api_base} {self.model}".lower()
        if provider == "openai_compatible" and ("moonshot" in text or "kimi" in text):
            provider = "moonshot"

        thinking = self.thinking
        if provider in {"moonshot", "kimi_code"} and not self.thinking_explicit:
            thinking = "disabled"

        temperature = self.temperature
        if provider in {"moonshot", "kimi_code"} and not self.temperature_explicit:
            temperature = 1.0 if thinking == "enabled" else 0.6

        api_style = self.api_style
        if provider in {"anthropic", "anthropic_compatible"}:
            api_style = "anthropic_compatible"
        elif provider == "kimi_code" and self.api_style == "anthropic_compatible":
            api_style = "anthropic_compatible"

        return LLMConfig(
            provider=provider,
            api_style=api_style,
            api_key=self.api_key,
            api_base=self.api_base,
            model=self.model,
            temperature=temperature,
            max_tokens=self.max_tokens,
            timeout=self.timeout,
            thinking=thinking,
            temperature_explicit=self.temperature_explicit,
            thinking_explicit=self.thinking_explicit,
        )


def _env(name: str, default: str) -> str:
    value = os.getenv(name)
    return default if value is None or value.strip() == "" else value.strip()


def _research_env(suffix: str) -> str | None:
    return os.getenv(f"DEEP_RESEARCH_LLM_{suffix}") or os.getenv(f"RESEARCH_LLM_{suffix}")


def _value_or(value: str | None, default: str) -> str:
    return default if value is None or value.strip() == "" else value.strip()


def _float(value: str | None, default: float) -> float:
    if value is None or value.strip() == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _int(value: str | None, default: int) -> int:
    if value is None or value.strip() == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _normalize_thinking(value: str) -> str:
    lowered = value.strip().lower()
    if lowered in {"enabled", "enable", "on", "true", "1"}:
        return "enabled"
    if lowered in {"auto"}:
        return "auto"
    return "disabled"
