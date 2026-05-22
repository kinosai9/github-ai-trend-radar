"""Build a presentation-friendly report model from scored snapshots."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

from github_ai_trend_radar.renderers.i18n import ACTION_ZH, BUCKET_ZH, ZH_LABELS
from github_ai_trend_radar.storage.files import load_json

PERIOD_LABELS = {
    "daily": "Daily",
    "weekly": "Weekly",
    "monthly": "Monthly",
}


class SnapshotNotFoundError(FileNotFoundError):
    """Raised when no scored snapshot exists for a render request."""


@dataclass(frozen=True)
class ResolvedSnapshot:
    period: str
    date: date
    path: Path
    kind: str
    is_report_model: bool


def load_report_config(config_dir: str | Path = "config") -> dict[str, Any]:
    path = Path(config_dir) / "report.default.yaml"
    if not path.exists():
        return _default_report_config()
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    config = payload.get("report", payload)
    if not isinstance(config, dict):
        return _default_report_config()
    merged = _default_report_config()
    _deep_update(merged, config)
    return merged


def _default_report_config() -> dict[str, Any]:
    return {
        "title": "GitHub AI 开源趋势雷达",
        "language": "zh-CN",
        "top_n": {
            "breakout": 5,
            "deep_research": 5,
            "valuable_mature": 3,
            "watchlist": 3,
            "noise": 5,
        },
        "show_noise_section": True,
        "show_noise_cards": False,
        "compact_noise_summary": True,
        "show_raw_scores": False,
        "show_debug_fields": False,
        "min_items_for_section": 1,
        "html_theme": "ink",
        "include_data_source_section": True,
        "include_generation_metadata": True,
    }


def _deep_update(base: dict[str, Any], override: dict[str, Any]) -> None:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_update(base[key], value)
        else:
            base[key] = deepcopy(value)


def load_best_snapshot(
    period: str,
    date_value: str | date | None = None,
    *,
    snapshot_dir: str | Path = "data/snapshots",
) -> tuple[dict[str, Any], Path, str]:
    """Load llm-scored if present, otherwise scored."""

    day = _coerce_date(date_value).isoformat()
    root = Path(snapshot_dir)
    llm_path = root / f"{day}-{period}-llm-scored.json"
    scored_path = root / f"{day}-{period}-scored.json"
    if llm_path.exists():
        return load_json(llm_path), llm_path, "llm-scored"
    if scored_path.exists():
        return load_json(scored_path), scored_path, "scored"
    message = (
        f"No scored snapshot found for {day} {period}. "
        f"Expected {llm_path} or {scored_path}. "
        f"Run: python -m github_ai_trend_radar.main run --period {period} --use-llm "
        f"or: python -m github_ai_trend_radar.main run --period {period}"
    )
    raise SnapshotNotFoundError(message)


def find_latest_snapshot(period: str, search_dirs: list[Path]) -> ResolvedSnapshot:
    candidates = _find_snapshot_candidates(period, search_dirs)
    if not candidates:
        raise SnapshotNotFoundError(f"No snapshot found for period={period}. Run collect/score first.")
    return candidates[0]


def resolve_render_input(
    period: str,
    date_value: str | date | None = None,
    *,
    snapshot_dir: str | Path = "data/snapshots",
    report_dir: str | Path = "data/reports",
) -> tuple[dict[str, Any], ResolvedSnapshot]:
    snapshot_root = Path(snapshot_dir)
    report_root = Path(report_dir)
    if date_value == "latest":
        resolved = find_latest_snapshot(period, [report_root, snapshot_root])
        return load_json(resolved.path), resolved

    day = _coerce_date(date_value)
    for kind, path, is_report_model in _paths_for_day(period, day, report_root, snapshot_root):
        if path.exists():
            return load_json(path), ResolvedSnapshot(period, day, path, kind, is_report_model)

    message = (
        f"No scored snapshot found for {day.isoformat()} {period}. "
        f"Expected {report_root / f'{day.isoformat()}-{period}-report-enriched.json'} or "
        f"{snapshot_root / f'{day.isoformat()}-{period}-llm-scored.json'} or "
        f"{snapshot_root / f'{day.isoformat()}-{period}-scored.json'}. "
        f"Run: python -m github_ai_trend_radar.main run --period {period} --use-llm "
        f"or: python -m github_ai_trend_radar.main run --period {period}"
    )
    raise SnapshotNotFoundError(message)


def _find_snapshot_candidates(period: str, search_dirs: list[Path]) -> list[ResolvedSnapshot]:
    candidates: list[tuple[date, int, ResolvedSnapshot]] = []
    for root in search_dirs:
        if not root.exists():
            continue
        for path in root.glob(f"*-{period}-report-enriched.json"):
            day = _date_from_name(path.name)
            if day:
                candidates.append((day, 3, ResolvedSnapshot(period, day, path, "report-enriched", True)))
        for path in root.glob(f"*-{period}-llm-scored.json"):
            day = _date_from_name(path.name)
            if day:
                candidates.append((day, 2, ResolvedSnapshot(period, day, path, "llm-scored", False)))
        for path in root.glob(f"*-{period}-scored.json"):
            day = _date_from_name(path.name)
            if day:
                candidates.append((day, 1, ResolvedSnapshot(period, day, path, "scored", False)))
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [item[2] for item in candidates]


def _paths_for_day(
    period: str,
    day: date,
    report_root: Path,
    snapshot_root: Path,
) -> list[tuple[str, Path, bool]]:
    prefix = f"{day.isoformat()}-{period}"
    return [
        ("report-enriched", report_root / f"{prefix}-report-enriched.json", True),
        ("llm-scored", snapshot_root / f"{prefix}-llm-scored.json", False),
        ("scored", snapshot_root / f"{prefix}-scored.json", False),
    ]


def _date_from_name(name: str) -> date | None:
    try:
        return date.fromisoformat(name[:10])
    except ValueError:
        return None


def _coerce_date(value: str | date | None) -> date:
    if value is None:
        return date.today()
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def build_report_model(
    snapshot: dict[str, Any],
    config: dict[str, Any],
    *,
    source_snapshot: str | Path | None = None,
    snapshot_kind: str | None = None,
) -> dict[str, Any]:
    candidates = [item for item in snapshot.get("candidates", []) if isinstance(item, dict)]
    stats = snapshot.get("stats", {}) if isinstance(snapshot.get("stats"), dict) else {}
    llm_meta = snapshot.get("llm", {}) if isinstance(snapshot.get("llm"), dict) else {}
    top_n = config.get("top_n", {}) if isinstance(config.get("top_n"), dict) else {}
    generated_at = _safe_text(snapshot.get("generated_at"))
    if not generated_at:
        generated_at = datetime.now().isoformat()

    bucket_counts = _bucket_counts(candidates, stats)
    sections = build_report_sections(candidates, top_n)
    if not config.get("show_noise_section", True):
        sections["noise"] = []

    top_radar = sorted((extract_project_summary(item) for item in candidates), key=_project_sort_key, reverse=True)[:5]
    topics = _top_topics(candidates)
    noise_summary = build_noise_summary(candidates, limit=_limit(top_n, "noise"))
    main_llm_coverage = _main_llm_coverage(sections)

    return {
        "title": config.get("title") or "GitHub AI 开源趋势雷达",
        "language": config.get("language") or "zh-CN",
        "labels": ZH_LABELS,
        "period": snapshot.get("period") or "daily",
        "period_label": format_period_label(str(snapshot.get("period") or "daily")),
        "generated_at": generated_at,
        "source_snapshot": str(source_snapshot or snapshot.get("source_snapshot") or ""),
        "snapshot_kind": snapshot_kind or ("llm-scored" if llm_meta else "scored"),
        "uses_llm": bool(llm_meta),
        "llm_status_label": _llm_status_label(bool(llm_meta), main_llm_coverage),
        "llm": llm_meta,
        "model": _safe_text(llm_meta.get("model")) if llm_meta else "",
        "stats": {
            **stats,
            "total_candidates": stats.get("total_candidates", len(candidates)),
            "llm_analyzed_candidates": stats.get("llm_analyzed_candidates", llm_meta.get("candidate_count", 0) if llm_meta else 0),
            "bucket_counts": bucket_counts,
        },
        "summary": {
            "bucket_counts": bucket_counts,
            "multi_source_candidates": stats.get("multi_source_candidates", _count_multi_source(candidates)),
            "top_observations": _build_observations(candidates, bucket_counts, topics, sections),
            "top_topics": topics,
            "main_card_count": sum(len(sections[key]) for key in ("breakout", "deep_research", "long_term")),
            "main_llm_coverage": main_llm_coverage,
        },
        "sections": sections,
        "noise_summary": noise_summary,
        "report_enrichment": {
            "requested": False,
            "enabled": False,
            "ok_count": 0,
            "fallback_count": 0,
            "failed_count": 0,
            "candidate_count": 0,
        },
        "top_radar": top_radar,
        "data_sources": _data_sources(snapshot, bool(llm_meta)),
        "config": config,
    }


def _limit(top_n: dict[str, Any], key: str) -> int:
    try:
        return int(top_n.get(key, 10))
    except (TypeError, ValueError):
        return 10


def select_bucket_items(candidates: list[dict[str, Any]], bucket: str, limit: int) -> list[dict[str, Any]]:
    selected = []
    for candidate in candidates:
        noise = candidate.get("noise", {}) if isinstance(candidate.get("noise"), dict) else {}
        if bucket == "noise":
            if candidate.get("radar_bucket") == "noise" or noise.get("is_noise") is True:
                selected.append(extract_project_summary(candidate))
        elif candidate.get("radar_bucket") == bucket:
            selected.append(extract_project_summary(candidate))
    return sorted(selected, key=_project_sort_key, reverse=True)[:limit]


def build_report_sections(candidates: list[dict[str, Any]], top_n: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Build de-duplicated intelligence sections with readable priorities."""

    used: set[str] = set()
    summaries = [extract_project_summary(candidate) for candidate in candidates]

    def pick(predicate, limit: int) -> list[dict[str, Any]]:
        selected = []
        for item in sorted(summaries, key=_project_sort_key, reverse=True):
            name = item.get("repo_full_name", "")
            if not name or name in used:
                continue
            if not predicate(item):
                continue
            selected.append(item)
            used.add(name)
            if len(selected) >= limit:
                break
        return selected

    breakout = pick(
        lambda item: item.get("radar_bucket") == "breakout"
        and item.get("recommended_action") != "ignore"
        and not _is_noise_summary(item),
        _limit(top_n, "breakout"),
    )
    deep_research = pick(
        lambda item: item.get("recommended_action") in {"deep_research", "try_locally", "read"}
        and not _is_noise_summary(item),
        _limit(top_n, "deep_research"),
    )
    long_term = pick(
        lambda item: item.get("radar_bucket") in {"valuable_mature", "watchlist"}
        and item.get("recommended_action") in {"watch", "read"}
        and not _is_noise_summary(item),
        min(_limit(top_n, "valuable_mature"), _limit(top_n, "watchlist")),
    )
    noise = [
        item
        for item in sorted(summaries, key=_project_sort_key, reverse=True)
        if _is_noise_summary(item) or item.get("recommended_action") == "ignore"
    ][:_limit(top_n, "noise")]
    return {
        "breakout": breakout,
        "deep_research": deep_research,
        "long_term": long_term,
        "noise": noise,
        "valuable_mature": long_term,
        "watchlist": long_term,
    }


def format_period_label(period: str) -> str:
    return PERIOD_LABELS.get(period, period.title())


def extract_project_summary(candidate: dict[str, Any]) -> dict[str, Any]:
    metrics = candidate.get("metrics", {}) if isinstance(candidate.get("metrics"), dict) else {}
    metadata = candidate.get("metadata", {}) if isinstance(candidate.get("metadata"), dict) else {}
    scores = candidate.get("scores", {}) if isinstance(candidate.get("scores"), dict) else {}
    noise = candidate.get("noise", {}) if isinstance(candidate.get("noise"), dict) else {}
    llm_analysis = candidate.get("llm_analysis", {}) if isinstance(candidate.get("llm_analysis"), dict) else {}
    llm_scores = candidate.get("llm_scores", {}) if isinstance(candidate.get("llm_scores"), dict) else {}

    summary = _build_summary(candidate, llm_analysis)
    action = _first_text(candidate.get("final_recommended_action"), candidate.get("recommended_action_rule_based"))
    if not action:
        bucket = _safe_text(candidate.get("radar_bucket"))
        action = "ignore" if bucket == "noise" else "read" if bucket == "breakout" else "watch"
    pushed_at = _first_text(candidate.get("pushed_at"), metadata.get("pushed_at"))
    topics = _safe_list(candidate.get("matched_focus_topics"))
    source_hits = _safe_list(candidate.get("source_hits"))
    llm_is_noise = llm_analysis.get("llm_is_noise") is True

    return _strip_empty(
        {
            "repo_full_name": _safe_text(candidate.get("repo_full_name")),
            "html_url": _safe_text(candidate.get("html_url")),
            "description": _safe_text(candidate.get("description")),
            "radar_bucket": _safe_text(candidate.get("radar_bucket")),
            "radar_bucket_label": BUCKET_ZH.get(_safe_text(candidate.get("radar_bucket")), _safe_text(candidate.get("radar_bucket"))),
            "recommended_action": action,
            "recommended_action_label": ACTION_ZH.get(action, action),
            "source_hits": source_hits,
            "matched_focus_topics": topics,
            "matched_keywords": _safe_list(candidate.get("matched_keywords")),
            "language": _first_text(candidate.get("language"), metrics.get("language"), metadata.get("language")),
            "stars": _first_number(metrics.get("stars"), candidate.get("stars")),
            "forks": _first_number(metrics.get("forks"), candidate.get("forks")),
            "open_issues": _first_number(metrics.get("open_issues"), candidate.get("open_issues")),
            "pushed_at": pushed_at,
            "created_at": _first_text(candidate.get("created_at"), metadata.get("created_at")),
            "radar_score": _score(candidate.get("radar_score")),
            "trend_score": _score(candidate.get("trend_score")),
            "value_score": _score(candidate.get("value_score")),
            "llm_adjusted_score": _score(candidate.get("llm_adjusted_score")),
            "display_score": _score(candidate.get("llm_adjusted_score", candidate.get("radar_score"))),
            "scores": scores,
            "topic_match_confidence": _safe_text(candidate.get("topic_match_confidence")),
            "llm_status": _safe_text(candidate.get("llm_status")),
            "llm_primary_topic": _safe_text(llm_analysis.get("llm_primary_topic")),
            "llm_project_type": _safe_text(llm_analysis.get("llm_project_type")),
            "llm_maturity": _safe_text(llm_analysis.get("llm_maturity")),
            "llm_trend_judgement": _safe_text(llm_analysis.get("llm_trend_judgement")),
            "summary": summary,
            "reason_to_watch": _first_text(
                llm_analysis.get("why_it_matters"),
                llm_analysis.get("technical_value"),
                _fallback_reason(candidate, source_hits),
            ),
            "engineering_takeaway": _first_text(
                llm_analysis.get("enterprise_fit"),
                _fallback_takeaway(topics),
            ),
            "analysis_source": "LLM 校准" if candidate.get("llm_status") == "ok" else "规则评分",
            "core_idea": _safe_text(llm_analysis.get("core_idea")),
            "technical_value": _safe_text(llm_analysis.get("technical_value")),
            "why_it_matters": _safe_text(llm_analysis.get("why_it_matters")),
            "enterprise_fit": _safe_text(llm_analysis.get("enterprise_fit")),
            "risks": _safe_list(llm_analysis.get("risks"))[:3],
            "noise": {
                "is_noise": bool(noise.get("is_noise", False)) or llm_is_noise,
                "noise_reasons": _safe_list(noise.get("noise_reasons")),
                "penalty": _score(noise.get("penalty")),
            },
            "llm_noise_reason": _safe_text(llm_analysis.get("llm_noise_reason")),
            "llm_scores": llm_scores,
            "report_enrichment_status": _safe_text(candidate.get("report_enrichment_status")) or "skipped",
        }
    )


def _build_summary(candidate: dict[str, Any], llm_analysis: dict[str, Any]) -> str:
    summary = _first_text(llm_analysis.get("summary_for_report"), llm_analysis.get("core_idea"))
    if summary:
        return summary
    description = _safe_text(candidate.get("description"))
    if description:
        return f"项目描述：{description}"
    topics = "、".join(_safe_list(candidate.get("matched_focus_topics"))) or "当前命中主题"
    return f"该项目围绕 {topics} 方向，近期在 GitHub 出现趋势信号，建议结合 README 判断真实成熟度。"


def _fallback_reason(candidate: dict[str, Any], source_hits: list[Any]) -> str:
    source_text = "多源命中" if len(source_hits) > 1 else "近期更新"
    bucket = _safe_text(candidate.get("radar_bucket"))
    if bucket == "breakout":
        return f"入选原因：{source_text}，且趋势分较高，可能代表近期升温方向。"
    if bucket == "valuable_mature":
        return "入选原因：工程价值和主题相关性较高，适合作为长期观察对象。"
    return f"入选原因：{source_text}，主题相关度达到观察阈值。"


def _fallback_takeaway(topics: list[Any]) -> str:
    topic_text = "、".join(str(topic) for topic in topics[:3]) or "相关技术"
    return f"工程启发：可从 {topic_text} 方向评估其在企业知识库、Agent 工作流或本地部署中的复用价值。"


def _is_noise_summary(item: dict[str, Any]) -> bool:
    noise = item.get("noise", {}) if isinstance(item.get("noise"), dict) else {}
    return bool(noise.get("is_noise")) or item.get("radar_bucket") == "noise"


def _project_sort_key(project: dict[str, Any]) -> tuple[float, float, float]:
    return (
        float(project.get("display_score") or 0.0),
        float(project.get("trend_score") or 0.0),
        float(project.get("value_score") or 0.0),
    )


def _score(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return round(float(value), 3)
    except (TypeError, ValueError):
        return None


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"none", "null"}:
        return ""
    return text


def _safe_list(value: Any) -> list[Any]:
    if not value:
        return []
    if isinstance(value, list):
        return [item for item in value if item not in (None, "", "None", "null")]
    return [value]


def _first_text(*values: Any) -> str:
    for value in values:
        text = _safe_text(value)
        if text:
            return text
    return ""


def _first_number(*values: Any) -> int | float | None:
    for value in values:
        if value is None or value == "":
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        return int(number) if number.is_integer() else number
    return None


def _strip_empty(payload: dict[str, Any]) -> dict[str, Any]:
    cleaned = {}
    for key, value in payload.items():
        if value in ("", [], None):
            continue
        if isinstance(value, dict):
            nested = _strip_empty(value)
            if nested:
                cleaned[key] = nested
            continue
        cleaned[key] = value
    return cleaned


def _bucket_counts(candidates: list[dict[str, Any]], stats: dict[str, Any]) -> dict[str, int]:
    existing = stats.get("bucket_counts")
    if isinstance(existing, dict) and existing:
        return {key: int(existing.get(key, 0) or 0) for key in ("breakout", "valuable_mature", "watchlist", "noise")}
    counter = Counter(str(candidate.get("radar_bucket") or "watchlist") for candidate in candidates)
    return {key: counter.get(key, 0) for key in ("breakout", "valuable_mature", "watchlist", "noise")}


def _count_multi_source(candidates: list[dict[str, Any]]) -> int:
    return sum(1 for candidate in candidates if len(_safe_list(candidate.get("source_hits"))) > 1)


def _top_topics(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    for candidate in candidates:
        counter.update(str(topic) for topic in _safe_list(candidate.get("matched_focus_topics")))
    return [{"topic": topic, "count": count} for topic, count in counter.most_common(5)]


def build_noise_summary(candidates: list[dict[str, Any]], *, limit: int = 5) -> dict[str, Any]:
    noise_items = []
    reason_counter: Counter[str] = Counter()
    for candidate in candidates:
        item = extract_project_summary(candidate)
        if not (_is_noise_summary(item) or item.get("recommended_action") == "ignore"):
            continue
        reasons = _noise_reasons_for_summary(item)
        if not reasons:
            reasons = ["建议忽略或主题相关性不足"]
        reason_counter.update(reasons)
        noise_items.append(
            {
                "repo_full_name": item.get("repo_full_name", ""),
                "reason": reasons[0],
                "score": item.get("display_score") or item.get("radar_score") or 0.0,
                "action": "建议忽略" if item.get("recommended_action") == "ignore" else "过滤",
            }
        )
    examples = sorted(noise_items, key=lambda item: float(item.get("score") or 0.0), reverse=True)[:limit]
    return {
        "total": len(noise_items),
        "reason_counts": [
            {"reason": reason, "count": count}
            for reason, count in reason_counter.most_common(5)
        ],
        "examples": examples,
    }


def _noise_reasons_for_summary(item: dict[str, Any]) -> list[str]:
    noise = item.get("noise", {}) if isinstance(item.get("noise"), dict) else {}
    raw_reasons = [str(reason).lower() for reason in _safe_list(noise.get("noise_reasons"))]
    if item.get("llm_noise_reason"):
        raw_reasons.append(str(item["llm_noise_reason"]).lower())
    grouped = []
    joined = " ".join(raw_reasons + [_safe_text(item.get("repo_full_name")).lower(), _safe_text(item.get("description")).lower()])
    if any(token in joined for token in ("awesome", "prompt", "prompts", "tutorial", "course", "learning")):
        grouped.append("资料集合 / 教程 / prompt 类内容")
    if any(token in joined for token in ("wrapper", "clone", "boilerplate")):
        grouped.append("封装 / 克隆 / 模板类项目")
    if any(token in joined for token in ("topic", "mismatch", "weak")):
        grouped.append("主题相关性不足")
    if any(token in joined for token in ("archived", "fork")):
        grouped.append("归档或 fork 项目")
    return grouped or [_safe_text(reason) for reason in raw_reasons if _safe_text(reason)]


def _build_observations(
    candidates: list[dict[str, Any]],
    bucket_counts: dict[str, int],
    topics: list[dict[str, Any]],
    sections: dict[str, list[dict[str, Any]]],
) -> list[str]:
    observations = []
    if topics:
        topic_text = "、".join(f"{item['topic']}({item['count']})" for item in topics[:3])
        observations.append(f"本期信号最集中在 {topic_text}，这些方向适合作为后续技术情报主线。")
    else:
        observations.append("本期主题分布较分散，建议优先看趋势突破和多源命中项目。")
    multi_source = _count_multi_source(candidates)
    observations.append(f"多源命中项目 {multi_source} 个；这类项目比单一搜索召回更值得优先复核 README 和 release。")
    if sections.get("breakout"):
        names = "、".join(item.get("repo_full_name", "") for item in sections["breakout"][:2])
        observations.append(f"趋势突破区以 {names} 为代表，更偏近期升温和可验证的新信号。")
    else:
        observations.append("本期没有足够强的突破项，建议把注意力放在值得深研和长期观察区。")
    return observations[:3]


def _data_sources(snapshot: dict[str, Any], uses_llm: bool) -> list[dict[str, str]]:
    sources = snapshot.get("sources", {}) if isinstance(snapshot.get("sources"), dict) else {}
    names = [
        ("ossinsight", "OSSInsight", "趋势候选"),
        ("github_search", "GitHub Search", "主题召回"),
        ("github_repo", "GitHub Repo API", "metadata / README 增强"),
    ]
    result = []
    for key, name, note in names:
        status = sources.get(key, {}) if isinstance(sources.get(key), dict) else {}
        result.append({"name": name, "note": note, "status": "可用" if status.get("ok", True) else "失败"})
    result.append({"name": "规则评分", "note": "趋势 / 价值 / 雷达分层评分", "status": "已执行"})
    if uses_llm:
        result.append({"name": "LLM 语义校准", "note": "用于解释技术价值和复核噪声，不替代规则评分", "status": "部分执行"})
    return result


def _main_llm_coverage(sections: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
    items = [item for key in ("breakout", "deep_research", "long_term") for item in sections.get(key, [])]
    analyzed = sum(1 for item in items if item.get("analysis_source") == "LLM 校准")
    return {"analyzed": analyzed, "total": len(items)}


def _llm_status_label(uses_llm_snapshot: bool, coverage: dict[str, int]) -> str:
    if not uses_llm_snapshot:
        return "规则评分"
    total = coverage.get("total", 0)
    analyzed = coverage.get("analyzed", 0)
    if total and analyzed < total:
        return "规则评分 + LLM 局部校准"
    return "规则评分 + LLM 校准"
