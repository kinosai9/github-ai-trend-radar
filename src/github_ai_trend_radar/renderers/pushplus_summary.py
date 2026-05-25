"""Render compact PushPlus summary HTML from a report model."""

from __future__ import annotations

import html
import os
from pathlib import Path
from typing import Any

from github_ai_trend_radar.storage.files import ensure_directory


def build_full_report_url(
    *,
    explicit_url: str | None,
    site_base_url: str | None,
    report_path: Path,
    resolved_date: str,
    period: str,
) -> tuple[str, bool]:
    if explicit_url:
        return explicit_url, True
    if site_base_url:
        base = site_base_url.rstrip("/")
        return f"{base}/reports/{resolved_date}-{period}-report.html", True
    return str(report_path), False


def render_pushplus_summary(report: dict[str, Any], *, full_report_url: str, full_report_is_url: bool) -> str:
    title = f"{report.get('title', 'GitHub AI 开源趋势雷达')} · {report.get('period_label', '')}".strip()
    stats = report.get("stats", {}) if isinstance(report.get("stats"), dict) else {}
    summary = report.get("summary", {}) if isinstance(report.get("summary"), dict) else {}
    run_summary = report.get("run_summary", {}) if isinstance(report.get("run_summary"), dict) else {}
    coverage = summary.get("main_llm_coverage", {}) if isinstance(summary.get("main_llm_coverage"), dict) else {}
    status_label = _run_status_label(run_summary)
    watchlist_count = (report.get("watchlist_queue") or {}).get("count", 0) if isinstance(report.get("watchlist_queue"), dict) else 0
    watchlist_text = f"{watchlist_count} 个" if int(watchlist_count or 0) > 0 else "0 个（本期无强候选）"
    parts = [
        "<div style='font-family:-apple-system,BlinkMacSystemFont,\"Segoe UI\",sans-serif;color:#10233f;line-height:1.65;'>",
        f"<h2 style='margin:0 0 12px;font-size:20px;'>{_e(title)}</h2>",
        _section("本期判断", _ordered(report.get("summary", {}).get("top_observations", [])[:3])),
        _projects("趋势突破", report.get("sections", {}).get("breakout", [])[:3], show_action=True),
        _projects("值得深研", report.get("sections", {}).get("deep_research", [])[:2], show_action=False),
    ]
    if full_report_is_url:
        parts.append(
            "<p style='margin:18px 0;padding:12px;background:#f1f3f5;border-left:3px solid #0a1f3d;'>"
            f"阅读全文：<a href='{_e(full_report_url)}'>{_e(full_report_url)}</a></p>"
        )
    else:
        parts.append(
            "<p style='margin:18px 0;padding:12px;background:#f1f3f5;border-left:3px solid #0a1f3d;'>"
            f"完整报告已生成在本地：{_e(full_report_url)}</p>"
        )
    parts.append(
        "<p style='margin-top:18px;color:#667085;font-size:12px;'>"
        f"候选数：{_e(stats.get('total_candidates', ''))} · "
        f"多源命中：{_e(summary.get('multi_source_candidates', ''))} · "
        f"本期待复核 Watchlist：{_e(watchlist_text)} · "
        f"主区 LLM 覆盖：{_e(coverage.get('analyzed', 0))}/{_e(coverage.get('total', 0))} · "
        f"运行状态：{_e(status_label)} · "
        f"生成时间：{_e(report.get('generated_at', ''))}</p>"
    )
    parts.append("</div>")
    return "\n".join(parts)


def write_pushplus_summary(
    report: dict[str, Any],
    output_path: str | Path,
    *,
    full_report_url: str,
    full_report_is_url: bool,
) -> Path:
    target = Path(output_path)
    ensure_directory(target.parent)
    target.write_text(
        render_pushplus_summary(report, full_report_url=full_report_url, full_report_is_url=full_report_is_url),
        encoding="utf-8",
    )
    return target


def full_report_url_from_env(*, explicit_url: str | None, report_path: Path, resolved_date: str, period: str) -> tuple[str, bool]:
    return build_full_report_url(
        explicit_url=explicit_url,
        site_base_url=os.getenv("SITE_BASE_URL"),
        report_path=report_path,
        resolved_date=resolved_date,
        period=period,
    )


def _run_status_label(run_summary: dict[str, Any]) -> str:
    status = str(run_summary.get("status", "success"))
    base = {"success": "成功", "partial_success": "部分完成", "failed": "失败"}.get(status, "成功")
    project_llm = run_summary.get("llm", {}).get("project_analysis", {}) if isinstance(run_summary.get("llm"), dict) else {}
    candidate_count = project_llm.get("candidate_count")
    ok_count = project_llm.get("ok_count")
    failed_count = project_llm.get("failed_count") or project_llm.get("api_failed_count")
    if status == "partial_success" and candidate_count:
        return f"{base}（项目级 LLM {ok_count}/{candidate_count} 成功，失败 {failed_count} 个，报告已生成）"
    return base


def _projects(title: str, projects: list[dict[str, Any]], *, show_action: bool) -> str:
    if not projects:
        return _section(title, "<p style='margin:0;color:#667085;'>暂无。</p>")
    blocks = []
    for item in projects:
        action = f" · {_e(item.get('recommended_action_label', ''))}" if show_action and item.get("recommended_action_label") else ""
        link = item.get("html_url", "")
        blocks.append(
            "<div style='margin:0 0 12px;padding:12px;border:1px solid #d9dee5;background:#fbfaf7;'>"
            f"<div style='font-weight:700;'><a href='{_e(link)}'>{_e(item.get('repo_full_name', ''))}</a>{action}</div>"
            f"<div style='margin-top:6px;color:#344054;'>{_e(item.get('summary', ''))}</div>"
            f"<div style='margin-top:6px;font-size:12px;'><a href='{_e(link)}'>GitHub 链接</a></div>"
            "</div>"
        )
    return _section(title, "\n".join(blocks))


def _ordered(items: list[Any]) -> str:
    if not items:
        return "<p style='margin:0;color:#667085;'>暂无。</p>"
    return "<ol style='margin:0;padding-left:20px;'>" + "".join(f"<li>{_e(item)}</li>" for item in items) + "</ol>"


def _section(title: str, body: str) -> str:
    return f"<h3 style='margin:18px 0 8px;font-size:16px;'>{_e(title)}</h3>\n{body}"


def _e(value: Any) -> str:
    return html.escape(str(value), quote=True)
