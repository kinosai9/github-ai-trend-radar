"""Optional lightweight LLM enrichment for rendered report cards."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from github_ai_trend_radar.llm.client import LLMClient
from github_ai_trend_radar.llm.json_utils import parse_json_or_error

REPORT_ENRICH_PROMPT = """你是企业 AI 工程技术情报编辑。请只基于输入项目字段，补齐中文日报卡片内容。
只输出 JSON，不要输出 Markdown。
字段要求：
{
  "summary_for_report": "中文，80字以内",
  "why_it_matters": "中文，120字以内",
  "enterprise_fit": "中文，120字以内",
  "risks": ["中文风险，最多3条"]
}
不要夸大，不要仅根据 star 数判断价值。"""

OVERVIEW_ENRICH_PROMPT = """你是企业 AI 工程技术情报日报主编。请基于输入的主区项目，生成 3 条中文编辑判断。
要求：
1. 每条 50-90 字。
2. 不要写成统计复述，不要出现 ai_agent(118) 这类计数格式。
3. 重点写方向变化、技术含义、企业工程启发。
4. 只输出 JSON：{"editorial_judgements":["...","...","..."]}"""


def enrich_report_model(report: dict[str, Any], client: LLMClient, *, max_items: int = 10) -> dict[str, Any]:
    enriched = deepcopy(report)
    targets = _select_targets(enriched, max_items=max_items)
    meta = {
        "requested": True,
        "enabled": client.available,
        "ok_count": 0,
        "fallback_count": 0,
        "failed_count": 0,
        "candidate_count": len(targets),
        "model": client.model if client.available else "",
    }

    if not client.available:
        for item in targets:
            _apply_rule_fallback(item)
            item["report_enrichment_status"] = "fallback"
            meta["fallback_count"] += 1
        _mark_unselected(enriched, targets)
        enriched["report_enrichment"] = meta
        enriched["summary"]["main_llm_coverage"] = _coverage(enriched)
        return enriched

    for item in targets:
        if _has_chinese_report_fields(item):
            item["report_enrichment_status"] = "skipped"
            continue
        result = client.complete_json(
            [
                {"role": "system", "content": REPORT_ENRICH_PROMPT},
                {"role": "user", "content": _project_payload(item)},
            ]
        )
        if not result.ok:
            _apply_rule_fallback(item)
            item["report_enrichment_status"] = "failed"
            meta["failed_count"] += 1
            meta["fallback_count"] += 1
            continue
        payload, error = parse_json_or_error(result.content)
        if error or not isinstance(payload, dict):
            _apply_rule_fallback(item)
            item["report_enrichment_status"] = "failed"
            meta["failed_count"] += 1
            meta["fallback_count"] += 1
            continue
        _apply_llm_payload(item, payload)
        item["report_enrichment_status"] = "ok"
        meta["ok_count"] += 1

    _mark_unselected(enriched, targets)
    enriched["report_enrichment"] = meta
    enriched["summary"]["main_llm_coverage"] = _coverage(enriched)
    return enriched


def ensure_report_enrichment_status(report: dict[str, Any]) -> dict[str, Any]:
    """Backfill report_enrichment_status for older report-enriched caches."""

    for section in ("breakout", "deep_research", "long_term", "noise"):
        for item in report.get("sections", {}).get(section, []):
            if item.get("report_enrichment_status"):
                continue
            if item.get("analysis_source") == "LLM 报告补齐":
                item["report_enrichment_status"] = "ok"
            elif item.get("analysis_source") == "规则评分":
                item["report_enrichment_status"] = "fallback"
            else:
                item["report_enrichment_status"] = "skipped"
    return report


def enrich_report_overview(report: dict[str, Any], client: LLMClient) -> dict[str, Any]:
    enriched = deepcopy(report)
    rule_observations = list(enriched.get("summary", {}).get("top_observations") or [])
    enriched.setdefault("summary", {})["statistical_observations"] = rule_observations
    meta = {
        "requested": True,
        "enabled": client.available,
        "ok": False,
        "fallback": False,
        "failed": False,
        "model": client.model if client.available else "",
    }

    if not client.available:
        enriched["summary"]["top_observations"] = _fallback_editorial_judgements(enriched)
        meta["fallback"] = True
        enriched["overview_enrichment"] = meta
        return enriched

    result = client.complete_json(
        [
            {"role": "system", "content": OVERVIEW_ENRICH_PROMPT},
            {"role": "user", "content": _overview_payload(enriched)},
        ]
    )
    if not result.ok:
        enriched["summary"]["top_observations"] = _fallback_editorial_judgements(enriched)
        meta["failed"] = True
        meta["fallback"] = True
        enriched["overview_enrichment"] = meta
        return enriched

    payload, error = parse_json_or_error(result.content)
    judgements = payload.get("editorial_judgements") if isinstance(payload, dict) else None
    if error or not isinstance(judgements, list):
        enriched["summary"]["top_observations"] = _fallback_editorial_judgements(enriched)
        meta["failed"] = True
        meta["fallback"] = True
        enriched["overview_enrichment"] = meta
        return enriched

    clean = [str(item).strip() for item in judgements if str(item).strip()][:3]
    enriched["summary"]["top_observations"] = clean or _fallback_editorial_judgements(enriched)
    meta["ok"] = bool(clean)
    meta["fallback"] = not bool(clean)
    enriched["overview_enrichment"] = meta
    return enriched


def _overview_payload(report: dict[str, Any]) -> str:
    lines = []
    for section_name in ("breakout", "deep_research", "long_term"):
        for item in report.get("sections", {}).get(section_name, []):
            lines.append(
                f"- [{section_name}] {item.get('repo_full_name')}: "
                f"{item.get('summary', '')} / {item.get('reason_to_watch', '')} / "
                f"主题={','.join(str(topic) for topic in item.get('matched_focus_topics', []))}"
            )
    return "\n".join(lines[:10])


def _fallback_editorial_judgements(report: dict[str, Any]) -> list[str]:
    breakout = report.get("sections", {}).get("breakout", [])
    deep = report.get("sections", {}).get("deep_research", [])
    long_term = report.get("sections", {}).get("long_term", [])
    judgements = []
    if breakout:
        names = "、".join(item.get("repo_full_name", "") for item in breakout[:2])
        judgements.append(f"本期突破信号集中在可执行工具和 Agent 工作流基础设施，{names} 代表了工具协议化和开发入口重构的方向。")
    if deep:
        names = "、".join(item.get("repo_full_name", "") for item in deep[:2])
        judgements.append(f"值得深研的项目更偏工程降本和上下文管理，{names} 适合优先复核 README、架构和真实落地成本。")
    if long_term:
        judgements.append("长期观察区以成熟基础设施为主，它们未必是本期爆发点，但对企业知识库、Agent 记忆和自动化工作流仍有参考价值。")
    return judgements[:3]


def _select_targets(report: dict[str, Any], *, max_items: int) -> list[dict[str, Any]]:
    items = []
    for section in ("breakout", "deep_research", "long_term"):
        for item in report.get("sections", {}).get(section, []):
            if len(items) >= max_items:
                return items
            if not _has_chinese_report_fields(item):
                items.append(item)
    return items


def _has_chinese_report_fields(item: dict[str, Any]) -> bool:
    return all(item.get(key) for key in ("summary", "reason_to_watch", "engineering_takeaway")) and item.get("analysis_source") == "LLM 校准"


def _project_payload(item: dict[str, Any]) -> str:
    return (
        f"项目：{item.get('repo_full_name', '')}\n"
        f"描述：{item.get('description') or item.get('summary', '')}\n"
        f"主题：{', '.join(str(topic) for topic in item.get('matched_focus_topics', []))}\n"
        f"来源：{', '.join(str(source) for source in item.get('source_hits', []))}\n"
        f"分数：trend={item.get('trend_score')} value={item.get('value_score')} radar={item.get('radar_score')}\n"
    )


def _apply_llm_payload(item: dict[str, Any], payload: dict[str, Any]) -> None:
    summary = str(payload.get("summary_for_report") or "").strip()
    why = str(payload.get("why_it_matters") or "").strip()
    fit = str(payload.get("enterprise_fit") or "").strip()
    risks = payload.get("risks") if isinstance(payload.get("risks"), list) else []
    if summary:
        item["summary"] = summary[:120]
    if why:
        item["reason_to_watch"] = why[:180]
    if fit:
        item["engineering_takeaway"] = fit[:180]
    clean_risks = [str(risk).strip() for risk in risks if str(risk).strip()][:3]
    if clean_risks:
        item["risks"] = clean_risks
    item["analysis_source"] = "LLM 报告补齐"


def _apply_rule_fallback(item: dict[str, Any]) -> None:
    if not item.get("summary"):
        topics = "、".join(str(topic) for topic in item.get("matched_focus_topics", [])[:3]) or "相关技术"
        item["summary"] = f"该项目围绕 {topics} 方向出现趋势信号，建议结合 README 复核成熟度。"
    if not item.get("reason_to_watch"):
        source = "多源命中" if len(item.get("source_hits", [])) > 1 else "近期更新"
        item["reason_to_watch"] = f"入选原因：{source}，且主题相关度达到报告展示阈值。"
    if not item.get("engineering_takeaway"):
        item["engineering_takeaway"] = "工程启发：可评估其在企业私有化、知识库、Agent 工作流或研发效率场景中的复用价值。"
    item["analysis_source"] = item.get("analysis_source") or "规则评分"


def _mark_unselected(report: dict[str, Any], targets: list[dict[str, Any]]) -> None:
    target_ids = {id(item) for item in targets}
    for section in ("breakout", "deep_research", "long_term", "noise"):
        for item in report.get("sections", {}).get(section, []):
            if id(item) not in target_ids and not item.get("report_enrichment_status"):
                item["report_enrichment_status"] = "skipped"


def _coverage(report: dict[str, Any]) -> dict[str, int]:
    items = [
        item
        for section in ("breakout", "deep_research", "long_term")
        for item in report.get("sections", {}).get(section, [])
    ]
    analyzed = sum(1 for item in items if item.get("analysis_source") in {"LLM 校准", "LLM 报告补齐"})
    return {"analyzed": analyzed, "total": len(items)}
