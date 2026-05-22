"""Kimi Code provider profile."""

from github_ai_trend_radar.llm.providers.anthropic_compatible import AnthropicCompatibleProvider


class KimiCodeProvider(AnthropicCompatibleProvider):
    """Kimi Code should normally use the Anthropic-compatible protocol."""

    @property
    def messages_url(self) -> str:
        base = self.config.api_base.rstrip("/")
        if base.endswith("/v1"):
            return f"{base}/messages"
        return f"{base}/v1/messages"
