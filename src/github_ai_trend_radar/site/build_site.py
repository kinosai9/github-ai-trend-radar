"""Build a small GitHub Pages site from generated reports."""

from __future__ import annotations

import html
import shutil
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from github_ai_trend_radar.renderers.report_model import ResolvedSnapshot, find_latest_snapshot
from github_ai_trend_radar.storage.files import ensure_directory, load_json, save_json

REPORT_PERIODS = ("daily", "weekly", "monthly")


@dataclass(frozen=True)
class SiteBuildResult:
    site_dir: Path
    reports_dir: Path
    index_path: Path
    reports_json_path: Path
    copied_reports: list[dict[str, Any]]


def build_site(
    *,
    reports_dir: str | Path = "data/reports",
    site_dir: str | Path = "site",
    period: str | None = None,
    date_value: str | date | None = None,
    all_periods: bool = False,
) -> SiteBuildResult:
    """Copy generated reports to ``site/reports`` and write site indexes."""

    source_root = Path(reports_dir)
    target_root = ensure_directory(Path(site_dir))
    target_reports = ensure_directory(target_root / "reports")
    selected = _select_reports(source_root, period=period, date_value=date_value, all_periods=all_periods)

    copied: list[dict[str, Any]] = []
    for resolved in selected:
        copied.append(_copy_report_bundle(source_root, target_reports, resolved))

    all_reports = _discover_site_reports(target_reports)
    reports_json_path = save_json(all_reports, target_root / "reports.json")
    index_path = _write_index(target_root / "index.html", all_reports)
    return SiteBuildResult(
        site_dir=target_root,
        reports_dir=target_reports,
        index_path=index_path,
        reports_json_path=reports_json_path,
        copied_reports=copied,
    )


def infer_site_base_url(*, repository_owner: str | None, repository_name: str | None) -> str:
    if not repository_owner or not repository_name:
        return ""
    return f"https://{repository_owner}.github.io/{repository_name}"


def _select_reports(
    source_root: Path,
    *,
    period: str | None,
    date_value: str | date | None,
    all_periods: bool,
) -> list[ResolvedSnapshot]:
    periods = REPORT_PERIODS if all_periods else (period or "daily",)
    selected: list[ResolvedSnapshot] = []
    for item_period in periods:
        try:
            if date_value == "latest" or date_value is None:
                resolved = find_latest_snapshot(item_period, [source_root])
            else:
                day = date.fromisoformat(date_value) if isinstance(date_value, str) else date_value
                path = source_root / f"{day.isoformat()}-{item_period}-report-enriched.json"
                if not path.exists():
                    continue
                resolved = ResolvedSnapshot(item_period, day, path, "report-enriched", True)
            selected.append(resolved)
        except FileNotFoundError:
            continue
    return selected


def _copy_report_bundle(source_root: Path, target_reports: Path, resolved: ResolvedSnapshot) -> dict[str, Any]:
    prefix = f"{resolved.date.isoformat()}-{resolved.period}"
    copied_files: dict[str, str] = {}
    for suffix, key in (
        ("report.html", "html"),
        ("report.md", "markdown"),
        ("report-enriched.json", "report_model"),
    ):
        source = source_root / f"{prefix}-{suffix}"
        if not source.exists():
            continue
        target = target_reports / source.name
        shutil.copy2(source, target)
        copied_files[key] = f"reports/{target.name}"

    title = _title_from_report_model(source_root / f"{prefix}-report-enriched.json", resolved.period)
    return {
        "period": resolved.period,
        "date": resolved.date.isoformat(),
        "title": title,
        "files": copied_files,
    }


def _discover_site_reports(target_reports: Path) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    for html_path in target_reports.glob("*-report.html"):
        parsed = _parse_report_name(html_path.name)
        if not parsed:
            continue
        day, period = parsed
        prefix = f"{day}-{period}"
        model_path = target_reports / f"{prefix}-report-enriched.json"
        reports.append(
            {
                "period": period,
                "date": day,
                "title": _title_from_report_model(model_path, period),
                "html": f"reports/{html_path.name}",
                "markdown": f"reports/{prefix}-report.md" if (target_reports / f"{prefix}-report.md").exists() else "",
                "report_model": f"reports/{prefix}-report-enriched.json" if model_path.exists() else "",
            }
        )
    reports.sort(key=lambda item: (item["date"], _period_sort_value(str(item["period"]))), reverse=True)
    return reports


def _parse_report_name(name: str) -> tuple[str, str] | None:
    if not name.endswith("-report.html") or len(name) < 24:
        return None
    day = name[:10]
    try:
        date.fromisoformat(day)
    except ValueError:
        return None
    rest = name[11 : -len("-report.html")]
    if rest not in REPORT_PERIODS:
        return None
    return day, rest


def _title_from_report_model(path: Path, period: str) -> str:
    period_label = {"daily": "Daily", "weekly": "Weekly", "monthly": "Monthly"}.get(period, period.title())
    if not path.exists():
        return f"GitHub AI 开源趋势雷达 · {period_label}"
    try:
        payload = load_json(path)
    except Exception:
        return f"GitHub AI 开源趋势雷达 · {period_label}"
    return f"{payload.get('title', 'GitHub AI 开源趋势雷达')} · {payload.get('period_label', period_label)}"


def _period_sort_value(period: str) -> int:
    return {"daily": 3, "weekly": 2, "monthly": 1}.get(period, 0)


def _write_index(path: Path, reports: list[dict[str, Any]]) -> Path:
    ensure_directory(path.parent)
    latest_by_period = {period: _latest_for_period(reports, period) for period in REPORT_PERIODS}
    report_items = "\n".join(_report_card(report) for report in reports[:30])
    period_cards = "\n".join(_period_card(period, latest_by_period[period]) for period in REPORT_PERIODS)
    generated_at = datetime.now().isoformat(timespec="seconds")
    path.write_text(
        f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>GitHub AI 开源趋势雷达</title>
  <style>
    body {{ margin: 0; background: #f4f1ea; color: #10233f; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    main {{ max-width: 980px; margin: 0 auto; padding: 40px 20px 64px; }}
    h1 {{ margin: 0 0 10px; font-size: 34px; line-height: 1.15; }}
    h2 {{ margin: 34px 0 14px; font-size: 20px; }}
    p {{ line-height: 1.7; }}
    .muted {{ color: #667085; font-size: 13px; }}
    .grid {{ display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }}
    .card {{ background: #fffdf8; border: 1px solid #d9dee5; border-radius: 8px; padding: 16px; box-shadow: 0 1px 0 rgba(16, 35, 63, 0.04); }}
    .card strong {{ display: block; margin-bottom: 8px; }}
    a {{ color: #0a58ca; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .reports {{ display: grid; gap: 10px; }}
    .report {{ display: flex; justify-content: space-between; gap: 14px; align-items: baseline; background: #fffdf8; border: 1px solid #d9dee5; border-radius: 8px; padding: 14px 16px; }}
    @media (max-width: 640px) {{ .report {{ display: block; }} h1 {{ font-size: 28px; }} }}
  </style>
</head>
<body>
<main>
  <h1>GitHub AI 开源趋势雷达</h1>
  <p class="muted">自动归档 Daily / Weekly / Monthly 报告。生成时间：{html.escape(generated_at)}</p>
  <section>
    <h2>最新报告</h2>
    <div class="grid">
      {period_cards}
    </div>
  </section>
  <section>
    <h2>报告归档</h2>
    <div class="reports">
      {report_items or "<p class='muted'>暂无报告。</p>"}
    </div>
  </section>
</main>
</body>
</html>
""",
        encoding="utf-8",
    )
    return path


def _latest_for_period(reports: list[dict[str, Any]], period: str) -> dict[str, Any] | None:
    for report in reports:
        if report.get("period") == period:
            return report
    return None


def _period_card(period: str, report: dict[str, Any] | None) -> str:
    label = {"daily": "Daily 日报", "weekly": "Weekly 周报", "monthly": "Monthly 月报"}[period]
    if not report:
        return f"<div class='card'><strong>{html.escape(label)}</strong><span class='muted'>暂无可发布报告</span></div>"
    return (
        "<div class='card'>"
        f"<strong>{html.escape(label)}</strong>"
        f"<a href='{html.escape(str(report.get('html', '')))}'>{html.escape(str(report.get('date', '')))} 完整报告</a>"
        "</div>"
    )


def _report_card(report: dict[str, Any]) -> str:
    title = html.escape(str(report.get("title", "")))
    day = html.escape(str(report.get("date", "")))
    period = html.escape(str(report.get("period", "")))
    href = html.escape(str(report.get("html", "")))
    markdown = report.get("markdown")
    markdown_link = f" · <a href='{html.escape(str(markdown))}'>Markdown</a>" if markdown else ""
    return (
        "<div class='report'>"
        f"<div><a href='{href}'>{title}</a><div class='muted'>{day} · {period}</div></div>"
        f"<div class='muted'><a href='{href}'>HTML</a>{markdown_link}</div>"
        "</div>"
    )
