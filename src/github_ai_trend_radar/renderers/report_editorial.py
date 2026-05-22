"""Report-level editorial summary helpers."""

from __future__ import annotations

from typing import Any

from github_ai_trend_radar.llm.client import LLMClient
from github_ai_trend_radar.renderers.report_enrichment import enrich_report_overview


def enrich_editorial_judgement(report: dict[str, Any], client: LLMClient) -> dict[str, Any]:
    """Generate three Chinese editorial judgements for the report hero."""

    return enrich_report_overview(report, client)
