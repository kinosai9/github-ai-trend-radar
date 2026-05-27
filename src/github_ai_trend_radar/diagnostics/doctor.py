"""Network and API diagnostics for github-ai-trend-radar."""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass
from dataclasses import replace

import requests
from rich.console import Console

from github_ai_trend_radar.llm.client import LLMClient
from github_ai_trend_radar.llm.config import LLMConfig
from github_ai_trend_radar.llm.json_utils import parse_json_or_error


USER_AGENT = "github-ai-trend-radar/0.1 doctor"
BODY_PREVIEW_LIMIT = 500

@dataclass(frozen=True)
class DoctorTarget:
    label: str
    url: str


def env_exists(name: str) -> bool:
    return bool(os.getenv(name))


def _token() -> str | None:
    return os.getenv("GH_PAT") or os.getenv("GITHUB_TOKEN")


def _headers_for(url: str) -> dict[str, str]:
    headers = {"User-Agent": USER_AGENT}
    if url.startswith("https://api.github.com/"):
        token = _token()
        if token:
            headers["Authorization"] = f"Bearer {token}"
            headers["Accept"] = "application/vnd.github+json"
    return headers


def _print_environment(console: Console) -> None:
    console.print("[bold]Runtime[/bold]")
    console.print(f"Python: {sys.version.split()[0]}")
    console.print(f"requests: {requests.__version__}")

    console.print("\n[bold]Environment[/bold]")
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY"):
        console.print(f"{name}: {'present' if env_exists(name) else 'missing'}")
    for name in ("GH_PAT", "GITHUB_TOKEN", "OPENAI_API_KEY"):
        console.print(f"{name}: {'present' if env_exists(name) else 'missing'}")


def _request_once(target: DoctorTarget, *, timeout: float, console: Console) -> int | None:
    console.print(f"\n[bold cyan]{target.label}[/bold cyan]")
    started_at = time.perf_counter()
    try:
        response = requests.get(target.url, headers=_headers_for(target.url), timeout=timeout)
        response_time_ms = int((time.perf_counter() - started_at) * 1000)
        content_type = response.headers.get("content-type", "")
        body_preview = response.text[:BODY_PREVIEW_LIMIT]

        console.print(f"status_code: {response.status_code}")
        console.print(f"final_url: {response.url}")
        console.print(f"content_type: {content_type}")
        console.print(f"response_time_ms: {response_time_ms}")
        console.print("body_preview:")
        console.print(body_preview)
        return response.status_code
    except Exception as exc:
        response_time_ms = int((time.perf_counter() - started_at) * 1000)
        console.print("status_code: <none>")
        console.print(f"final_url: {target.url}")
        console.print("content_type: <none>")
        console.print(f"response_time_ms: {response_time_ms}")
        console.print("body_preview:")
        console.print("")
        console.print(f"exception_type: {type(exc).__name__}")
        console.print(f"exception_message: {exc}")
        return None


def _print_llm_diagnostics(*, timeout: float, console: Console, research: bool = False) -> None:
    config = replace(LLMConfig.from_research_env() if research else LLMConfig.from_env(), timeout=timeout)
    prefix = "RESEARCH_LLM" if research else "LLM"
    console.print(f"\n[bold]{'Research LLM Provider' if research else 'LLM Provider'}[/bold]")
    console.print(f"{prefix}_PROVIDER: {config.provider}")
    console.print(f"{prefix}_API_STYLE: {config.api_style}")
    console.print(f"{prefix}_API_BASE: {'present host=' + config.api_base_host if config.api_base else 'missing'}")
    console.print(f"{prefix}_MODEL: {config.model}")
    console.print(f"{prefix}_API_KEY: {'present' if config.api_key_present else 'missing'}")
    console.print(f"{prefix}_THINKING: {config.thinking}")
    console.print(f"{prefix}_TEMPERATURE: {config.temperature}")
    console.print(f"{prefix}_MAX_TOKENS: {config.max_tokens}")
    console.print(f"{prefix}_TIMEOUT: {config.timeout}")
    if config.provider == "kimi_code" and config.api_style == "openai_compatible":
        console.print(
            "[yellow]warning: Kimi Code / Coding Plan may reject OpenAI-compatible requests from "
            "non-whitelisted clients with 403. Use LLM_API_STYLE=anthropic_compatible if you encounter 403.[/yellow]"
        )

    client = LLMClient(config)
    result = client.complete_json(
        [
            {"role": "system", "content": "Only output JSON."},
            {"role": "user", "content": '{"task":"Return {\\"ok\\": true, \\"provider\\": \\"diagnostic\\"}"}'},
        ],
        max_tokens=128,
    )
    parsed, parse_error = parse_json_or_error(result.content) if result.content else (None, "empty content")
    console.print("LLM test request")
    console.print(f"ok: {result.ok and parsed is not None and parse_error is None}")
    console.print(f"content_preview: {result.content[:300]}")
    console.print(f"error_type: {result.error_type or ('parse_failed' if parse_error and result.ok else None)}")
    console.print(f"error_message: {result.error_message or parse_error}")
    console.print(f"usage: {result.usage}")
    console.print(f"reasoning_content_present: {bool(result.reasoning_content)}")


def run_doctor(*, timeout: float = 20, console: Console | None = None, llm: bool = False, research_llm: bool = False) -> int:
    output = console or Console()
    _print_environment(output)
    if llm:
        _print_llm_diagnostics(timeout=timeout, console=output)
    if research_llm:
        _print_llm_diagnostics(timeout=timeout, console=output, research=True)

    targets = [
        DoctorTarget("GitHub rate limit", "https://api.github.com/rate_limit"),
        DoctorTarget("OSSInsight trending page", "https://ossinsight.io/trending"),
        DoctorTarget(
            "OSSInsight trends past_24_hours All",
            "https://api.ossinsight.io/v1/trends/repos/?period=past_24_hours&language=All",
        ),
        DoctorTarget(
            "OSSInsight trends past_24_hours without language",
            "https://api.ossinsight.io/v1/trends/repos/?period=past_24_hours",
        ),
        DoctorTarget(
            "OSSInsight trends past_week",
            "https://api.ossinsight.io/v1/trends/repos/?period=past_week",
        ),
        DoctorTarget(
            "OSSInsight trends past_month",
            "https://api.ossinsight.io/v1/trends/repos/?period=past_month",
        ),
        DoctorTarget(
            "OSSInsight trends past_24_hours Python",
            "https://api.ossinsight.io/v1/trends/repos/?period=past_24_hours&language=Python",
        ),
        DoctorTarget(
            "OSSInsight trends past_24_hours TypeScript",
            "https://api.ossinsight.io/v1/trends/repos/?period=past_24_hours&language=TypeScript",
        ),
    ]

    for target in targets:
        _request_once(target, timeout=timeout, console=output)

    return 0
