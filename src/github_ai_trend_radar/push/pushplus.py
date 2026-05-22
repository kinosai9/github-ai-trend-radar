"""PushPlus sender."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

import requests


PUSHPLUS_ENDPOINT = "https://www.pushplus.plus/send"
USER_AGENT = "github-ai-trend-radar/0.1"


@dataclass(frozen=True)
class PushPlusConfig:
    token: str = ""
    topic: str = ""
    channel: str = ""
    webhook: str = ""
    template: str = "html"
    timeout: float = 20.0
    retries: int = 2

    @classmethod
    def from_env(cls, *, timeout: float = 20.0, retries: int = 2) -> "PushPlusConfig":
        return cls(
            token=os.getenv("PUSHPLUS_TOKEN", "").strip(),
            topic=os.getenv("PUSHPLUS_TOPIC", "").strip(),
            channel=os.getenv("PUSHPLUS_CHANNEL", "").strip(),
            webhook=os.getenv("PUSHPLUS_WEBHOOK", "").strip(),
            timeout=timeout,
            retries=retries,
        )


@dataclass(frozen=True)
class PushPlusResult:
    ok: bool
    skipped: bool = False
    status_code: int | None = None
    response_text: str = ""
    error: str = ""


def send_pushplus(
    *,
    title: str,
    content: str,
    config: PushPlusConfig,
    session: requests.Session | None = None,
) -> PushPlusResult:
    if not config.token:
        return PushPlusResult(ok=False, skipped=True, error="PUSHPLUS_TOKEN is missing")

    payload: dict[str, Any] = {
        "token": config.token,
        "title": title,
        "content": content,
        "template": config.template,
    }
    if config.topic:
        payload["topic"] = config.topic
    if config.channel:
        payload["channel"] = config.channel
    if config.webhook:
        payload["webhook"] = config.webhook

    http = session or requests.Session()
    last_error = ""
    for attempt in range(max(1, config.retries + 1)):
        try:
            response = http.post(
                PUSHPLUS_ENDPOINT,
                json=payload,
                timeout=config.timeout,
                headers={"User-Agent": USER_AGENT},
            )
            text = response.text[:500]
            if response.ok:
                return PushPlusResult(ok=True, status_code=response.status_code, response_text=text)
            last_error = f"HTTP {response.status_code}: {text}"
            if response.status_code < 500:
                return PushPlusResult(ok=False, status_code=response.status_code, response_text=text, error=last_error)
        except requests.RequestException as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        if attempt < config.retries:
            time.sleep(0.5 * (attempt + 1))
    return PushPlusResult(ok=False, error=last_error)
