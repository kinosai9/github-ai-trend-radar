"""Command line entry point for github-ai-trend-radar."""

from __future__ import annotations

import argparse
import logging
import webbrowser
from dataclasses import replace
from collections.abc import Sequence
from datetime import UTC, date, datetime
from pathlib import Path

from rich.console import Console

from github_ai_trend_radar.collectors.github_repo import GitHubRepoClient
from github_ai_trend_radar.collectors.github_search import collect_github_search
from github_ai_trend_radar.collectors.ossinsight import fetch_trending_repos
from github_ai_trend_radar.config.env import load_local_env
from github_ai_trend_radar.config_loader import load_topics_config
from github_ai_trend_radar.diagnostics.doctor import run_doctor
from github_ai_trend_radar.llm.client import LLMClient
from github_ai_trend_radar.llm.config import LLMConfig
from github_ai_trend_radar.processors.dedupe import dedupe_candidates, merge_candidates
from github_ai_trend_radar.processors.llm_ranker import action_distribution, enrich_with_llm
from github_ai_trend_radar.processors.normalize import (
    full_name_from_ossinsight_item,
    normalize_candidate,
    split_repo_full_name,
)
from github_ai_trend_radar.processors.scoring import load_scoring_config, score_snapshot_payload
from github_ai_trend_radar.push.pushplus import PushPlusConfig, send_pushplus
from github_ai_trend_radar.renderers.html_ink import write_html_report
from github_ai_trend_radar.renderers.markdown import write_markdown_report
from github_ai_trend_radar.renderers.pushplus_summary import full_report_url_from_env, write_pushplus_summary
from github_ai_trend_radar.renderers.report_enrichment import (
    enrich_report_model,
    enrich_report_overview,
    ensure_report_enrichment_status,
)
from github_ai_trend_radar.renderers.report_model import (
    SnapshotNotFoundError,
    build_report_model,
    load_report_config,
    resolve_render_input,
)
from github_ai_trend_radar.storage.files import load_json, save_json, snapshot_path


console = Console()
LOGGER = logging.getLogger(__name__)


def _add_common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--config-dir",
        default="config",
        help="Directory containing runtime configuration files.",
    )
    parser.add_argument(
        "--period",
        choices=("daily", "weekly", "monthly"),
        default="daily",
        help="Report period to process.",
    )
    parser.add_argument(
        "--snapshot-dir",
        default="data/snapshots",
        help="Directory for raw and normalized collection snapshots.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=20,
        help="HTTP timeout in seconds.",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="HTTP retry attempts.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Return a failure when the first required upstream source fails.",
    )
    parser.add_argument(
        "--allow-empty",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Allow writing an empty candidates snapshot when collection yields no repositories.",
    )
    parser.add_argument(
        "--focus-topics",
        default=None,
        help="Comma-separated focus topic names to enable.",
    )
    parser.add_argument(
        "--max-candidates",
        type=int,
        default=200,
        help="Maximum merged candidates to keep before enrichment.",
    )
    parser.add_argument(
        "--enrich-top-n",
        type=int,
        default=100,
        help="Number of top merged candidates to enrich with GitHub Repo API and README.",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=10,
        help="Number of top items to print in command summaries.",
    )
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Enable LLM semantic calibration after rule-based scoring.",
    )
    parser.add_argument(
        "--llm-top-n",
        type=int,
        default=30,
        help="Maximum candidates to analyze with LLM.",
    )
    parser.add_argument(
        "--llm-breakout-n",
        type=int,
        default=15,
        help="Maximum breakout candidates to analyze with LLM.",
    )
    parser.add_argument(
        "--llm-mature-n",
        type=int,
        default=10,
        help="Maximum valuable_mature candidates to analyze with LLM.",
    )
    parser.add_argument(
        "--llm-watchlist-n",
        type=int,
        default=5,
        help="Maximum watchlist candidates to analyze with LLM.",
    )


def _placeholder(command: str, args: argparse.Namespace) -> int:
    console.print(
        f"[bold cyan]{command}[/bold cyan] command is ready. "
        "Implementation will be added in a future iteration."
    )
    console.print(f"config_dir={args.config_dir}")
    if hasattr(args, "period"):
        console.print(f"period={args.period}")
    return 0


def _generated_at() -> str:
    return datetime.now(UTC).isoformat()


def _print_scored_group(title: str, candidates: list[dict[str, object]], *, limit: int) -> None:
    console.print(f"[bold]{title}[/bold]")
    if not candidates:
        console.print("[dim]No candidates.[/dim]")
        return
    for candidate in candidates[:limit]:
        scores = candidate.get("scores", {}) if isinstance(candidate.get("scores"), dict) else {}
        noise = candidate.get("noise", {}) if isinstance(candidate.get("noise"), dict) else {}
        console.print(
            f"{candidate.get('repo_full_name')} | "
            f"radar={candidate.get('radar_score')} | "
            f"trend={candidate.get('trend_score')} | "
            f"value={candidate.get('value_score')} | "
            f"bucket={candidate.get('radar_bucket')} | "
            f"action={candidate.get('recommended_action_rule_based')} | "
            f"sources={candidate.get('source_hits', [])} | "
            f"topics={candidate.get('matched_focus_topics', [])} | "
            f"confidence={candidate.get('topic_match_confidence')} | "
            f"noise={noise.get('is_noise')} | "
            f"topic={scores.get('topic_relevance_score')}"
        )


def _print_llm_group(title: str, candidates: list[dict[str, object]], *, limit: int) -> None:
    console.print(f"[bold]{title}[/bold]")
    if not candidates:
        console.print("[dim]No candidates.[/dim]")
        return
    for candidate in candidates[:limit]:
        analysis = candidate.get("llm_analysis", {}) if isinstance(candidate.get("llm_analysis"), dict) else {}
        console.print(
            f"{candidate.get('repo_full_name')} | "
            f"radar={candidate.get('radar_score')} | "
            f"llm_adjusted={candidate.get('llm_adjusted_score')} | "
            f"bucket={candidate.get('radar_bucket')} | "
            f"trend={analysis.get('llm_trend_judgement')} | "
            f"action={candidate.get('final_recommended_action')} | "
            f"topic={analysis.get('llm_primary_topic')} | "
            f"llm_noise={analysis.get('llm_is_noise')} | "
            f"sources={candidate.get('source_hits', [])}"
        )


def _source_status(ok: bool, *, error: str | None = None, status_code: int | None = None, raw_snapshot: object = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "ok": ok,
        "error": error,
        "status_code": status_code,
    }
    if raw_snapshot is not None:
        payload["raw_snapshot"] = str(raw_snapshot)
    return payload


def _save_ossinsight_error_snapshot(args: argparse.Namespace, exc: Exception) -> object:
    error_payload = {
        "period": args.period,
        "generated_at": _generated_at(),
        "source": "ossinsight",
        "ok": False,
        "error": str(exc),
        "status_code": getattr(exc, "status_code", None),
    }
    error_path = snapshot_path(args.snapshot_dir, args.period, "ossinsight-error")
    save_json(error_payload, error_path)
    return error_path


def _save_empty_collect_snapshots(args: argparse.Namespace, exc: Exception) -> tuple[object, object]:
    status_code = getattr(exc, "status_code", None)
    error_payload = {
        "period": args.period,
        "generated_at": _generated_at(),
        "source": "ossinsight",
        "ok": False,
        "error": str(exc),
        "status_code": status_code,
    }
    candidates_payload = {
        "period": args.period,
        "generated_at": error_payload["generated_at"],
        "sources": {
            "ossinsight": {
                "ok": False,
                "error": str(exc),
                "status_code": status_code,
            }
        },
        "candidates": [],
    }

    error_path = snapshot_path(args.snapshot_dir, args.period, "ossinsight-error")
    candidates_path = snapshot_path(args.snapshot_dir, args.period, "candidates")
    save_json(error_payload, error_path)
    save_json(candidates_payload, candidates_path)
    return error_path, candidates_path


def collect(args: argparse.Namespace) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    sources: dict[str, dict[str, object]] = {}
    candidates: list[dict[str, object]] = []

    console.print(f"Collecting OSSInsight trending repositories for [bold]{args.period}[/bold]...")
    try:
        source_items, raw_path = fetch_trending_repos(
            args.period,
            snapshot_dir=args.snapshot_dir,
            timeout=args.timeout,
            retries=args.retries,
        )
        sources["ossinsight"] = _source_status(True, status_code=200, raw_snapshot=raw_path)
        console.print(f"Saved raw OSSInsight response: {raw_path}")
        for rank, item in enumerate(source_items, start=1):
            full_name = full_name_from_ossinsight_item(item)
            if not full_name:
                LOGGER.warning("Skipping OSSInsight item without a recognizable repo full name: %s", item)
                continue
            try:
                split_repo_full_name(full_name)
            except ValueError as exc:
                LOGGER.warning("Skipping invalid repo name from OSSInsight item: %s", exc)
                continue
            ranked_item = dict(item)
            ranked_item.setdefault("ossinsight_rank", rank)
            ranked_item.setdefault("source_rank", rank)
            candidates.append(normalize_candidate(full_name, source_item=ranked_item))
    except Exception as exc:
        error_path = _save_ossinsight_error_snapshot(args, exc)
        sources["ossinsight"] = _source_status(
            False,
            error=str(exc),
            status_code=getattr(exc, "status_code", None),
        )
        console.print(f"[bold red]Collect failed while calling OSSInsight:[/bold red] {exc}")
        console.print(f"Saved OSSInsight error snapshot: {error_path}")
        if args.fail_fast or not args.allow_empty:
            _, candidates_path = _save_empty_collect_snapshots(args, exc)
            console.print(f"Saved empty candidates snapshot: {candidates_path}")
            return 1

    try:
        topics = load_topics_config(args.config_dir, focus_topics=args.focus_topics)
        search_candidates, search_raw_path, search_status = collect_github_search(
            topics,
            args.period,
            snapshot_dir=args.snapshot_dir,
            timeout=args.timeout,
        )
        candidates.extend(search_candidates)
        sources["github_search"] = _source_status(
            search_status.ok,
            error=search_status.error,
            status_code=search_status.status_code,
            raw_snapshot=search_raw_path,
        )
        console.print(f"Saved raw GitHub Search response: {search_raw_path}")
    except Exception as exc:
        LOGGER.warning("GitHub Search collection failed: %s", exc)
        sources["github_search"] = _source_status(False, error=str(exc), status_code=getattr(exc, "status_code", None))

    client = GitHubRepoClient(timeout=min(args.timeout, 8), retries=1)
    merged_candidates = dedupe_candidates(candidates)[: args.max_candidates]
    enrich_limit = min(args.enrich_top_n, len(merged_candidates))
    enriched_count = 0
    repo_errors: list[str] = []

    for index, candidate in enumerate(merged_candidates[:enrich_limit], start=1):
        full_name = str(candidate.get("repo_full_name") or "")
        try:
            owner, repo = split_repo_full_name(full_name)
        except ValueError as exc:
            LOGGER.warning("Skipping GitHub enrichment for invalid repo name %s: %s", full_name, exc)
            continue

        console.print(f"[dim]{index}/{enrich_limit}[/dim] Enriching {owner}/{repo}")
        repo_metadata: dict[str, object] = {}
        readme_text = ""
        try:
            repo_metadata = client.get_repo(owner, repo)
        except Exception as exc:
            repo_errors.append(str(exc))
            LOGGER.warning("GitHub repo metadata fetch failed for %s/%s: %s", owner, repo, exc)

        if repo_metadata:
            readme_text = client.get_readme(owner, repo)
            enriched = normalize_candidate(
                full_name,
                repo_metadata=repo_metadata,
                readme_text=readme_text,
            )
            enriched["source_hits"] = candidate.get("source_hits", [])
            merged_candidates[index - 1] = merge_candidates(candidate, enriched)
            enriched_count += 1

    sources["github_repo"] = {
        "ok": enriched_count > 0 or enrich_limit == 0,
        "error": None if not repo_errors else repo_errors[0],
        "status_code": None,
        "enriched_count": enriched_count,
        "requested_count": enrich_limit,
    }

    output_path = snapshot_path(args.snapshot_dir, args.period, "candidates")
    save_json(
        {
            "period": args.period,
            "generated_at": _generated_at(),
            "sources": sources,
            "candidates": merged_candidates,
        },
        output_path,
    )
    console.print(f"[bold green]Saved {len(merged_candidates)} candidates:[/bold green] {output_path}")
    if not merged_candidates and not args.allow_empty:
        return 1
    return 0


def score(args: argparse.Namespace) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    candidates_path = snapshot_path(args.snapshot_dir, args.period, "candidates")
    if not candidates_path.exists():
        console.print(f"[bold red]Candidates snapshot not found:[/bold red] {candidates_path}")
        return 1

    scoring_config = load_scoring_config(args.config_dir)
    topics_config = load_topics_config(args.config_dir, focus_topics=args.focus_topics)
    payload = score_snapshot_payload(
        load_json(candidates_path),
        scoring_config=scoring_config,
        topics_config=topics_config,
        source_snapshot=str(candidates_path),
    )
    scored_path = snapshot_path(args.snapshot_dir, args.period, "scored")
    save_json(payload, scored_path)

    stats = payload["stats"]
    console.print(f"[bold green]Saved scored snapshot:[/bold green] {scored_path}")
    console.print(f"total candidates: {stats['total_candidates']}")
    console.print(f"noise candidates: {stats['noise_candidates']}")
    console.print(f"multi-source candidates: {stats['multi_source_candidates']}")
    console.print(f"bucket counts: {stats.get('bucket_counts', {})}")
    _print_scored_group("Top radar candidates", payload["candidates"], limit=args.top_n)
    _print_scored_group(
        "Top breakout candidates",
        [candidate for candidate in payload["candidates"] if candidate.get("radar_bucket") == "breakout"],
        limit=args.top_n,
    )
    _print_scored_group(
        "Top valuable_mature candidates",
        [candidate for candidate in payload["candidates"] if candidate.get("radar_bucket") == "valuable_mature"],
        limit=args.top_n,
    )

    if args.use_llm:
        client = LLMClient(replace(LLMConfig.from_env(), timeout=args.timeout))
        if not client.available:
            console.print("[yellow]LLM_API_KEY is missing; writing LLM snapshot with rule-based fallback.[/yellow]")
        llm_payload = enrich_with_llm(
            payload,
            client=client,
            scoring_config=scoring_config,
            source_snapshot=str(scored_path),
            llm_top_n=args.llm_top_n,
            breakout_n=args.llm_breakout_n,
            mature_n=args.llm_mature_n,
            watchlist_n=args.llm_watchlist_n,
        )
        llm_path = snapshot_path(args.snapshot_dir, args.period, "llm-scored")
        save_json(llm_payload, llm_path)
        llm_stats = llm_payload["llm"]
        console.print(f"[bold green]Saved LLM scored snapshot:[/bold green] {llm_path}")
        console.print(
            "LLM stats: "
            f"selected={llm_stats['candidate_count']} "
            f"ok={llm_stats['ok_count']} "
            f"api_failed={llm_stats['api_failed_count']} "
            f"parse_failed={llm_stats['parse_failed_count']} "
            f"skipped={llm_stats['skipped_count']}"
        )
        _print_llm_group("Top LLM adjusted candidates", llm_payload["candidates"], limit=args.top_n)
        _print_llm_group(
            "Top breakout candidates after LLM",
            [candidate for candidate in llm_payload["candidates"] if candidate.get("radar_bucket") == "breakout"],
            limit=args.top_n,
        )
        _print_llm_group(
            "LLM marked noise candidates",
            [
                candidate
                for candidate in llm_payload["candidates"]
                if (candidate.get("llm_analysis", {}) or {}).get("llm_is_noise") is True
            ],
            limit=args.top_n,
        )
        console.print(f"recommended_action distribution: {action_distribution(llm_payload['candidates'])}")
    return 0


def run(args: argparse.Namespace) -> int:
    collect_exit = collect(args)
    if collect_exit != 0:
        return collect_exit
    score_exit = score(args)
    if score_exit != 0:
        return score_exit
    if getattr(args, "render", False):
        return render(args)
    return 0


def _report_output_path(output_dir: str | Path, period: str, suffix: str, *, date_value: str | None = None) -> Path:
    day = date.fromisoformat(date_value) if date_value else date.today()
    return Path(output_dir) / f"{day.isoformat()}-{period}-report.{suffix}"


def render(args: argparse.Namespace) -> int:
    output_dir = Path(getattr(args, "output_dir", "data/reports"))
    try:
        input_payload, resolved = resolve_render_input(
            args.period,
            getattr(args, "date", None),
            snapshot_dir=args.snapshot_dir,
            report_dir=output_dir,
        )
    except SnapshotNotFoundError as exc:
        console.print(f"[bold red]{exc}[/bold red]")
        return 1

    report_config = load_report_config(args.config_dir)
    top_overrides = {
        "breakout": getattr(args, "top_breakout", None),
        "valuable_mature": getattr(args, "top_mature", None),
        "watchlist": getattr(args, "top_watchlist", None),
        "noise": getattr(args, "top_noise", None),
    }
    for key, value in top_overrides.items():
        if value is not None:
            report_config.setdefault("top_n", {})[key] = value

    if resolved.is_report_model:
        report = ensure_report_enrichment_status(input_payload)
        save_json(report, resolved.path)
        console.print("[green]Using enriched report model.[/green]")
    else:
        report = build_report_model(
            input_payload,
            report_config,
            source_snapshot=resolved.path,
            snapshot_kind=resolved.kind,
        )

    if getattr(args, "enrich_report", False) and not resolved.is_report_model:
        report = enrich_report_model(report, LLMClient(LLMConfig.from_env()), max_items=10)
    if getattr(args, "enrich_overview", False):
        report = enrich_report_overview(report, LLMClient(LLMConfig.from_env()))

    output_format = getattr(args, "format", "all")
    md_path = _report_output_path(output_dir, args.period, "md", date_value=resolved.date.isoformat())
    html_path = _report_output_path(output_dir, args.period, "html", date_value=resolved.date.isoformat())
    debug_path = output_dir / f"{resolved.date.isoformat()}-{args.period}-report-enriched.json"

    written_md: Path | None = None
    written_html: Path | None = None
    if output_format in ("md", "all"):
        written_md = write_markdown_report(report, md_path)
    if output_format in ("html", "all"):
        written_html = write_html_report(report, html_path)
    if (getattr(args, "enrich_report", False) and not resolved.is_report_model) or getattr(args, "enrich_overview", False):
        save_json(report, debug_path)

    console.print(f"resolved date: {resolved.date.isoformat()}")
    console.print(f"selected input file: {resolved.path}")
    console.print(f"selected input kind: {resolved.kind}")
    console.print(f"LLM: {'enabled' if report['uses_llm'] else 'not enabled'}")
    console.print(
        "LLM report enrichment: "
        f"{'enabled' if report['report_enrichment']['enabled'] else 'not enabled'} "
        f"({report['report_enrichment']['ok_count']} ok, "
        f"{report['report_enrichment']['fallback_count']} fallback)"
    )
    if getattr(args, "enrich_overview", False):
        console.print(f"overview enrichment: {report.get('overview_enrichment', {})}")
    if written_md:
        console.print(f"Markdown output: {written_md}")
    if written_html:
        console.print(f"HTML output: {written_html}")
    if (getattr(args, "enrich_report", False) and not resolved.is_report_model) or getattr(args, "enrich_overview", False):
        console.print(f"Report model debug output: {debug_path}")
    console.print(f"bucket_counts: {report['summary']['bucket_counts']}")
    console.print(f"main_card_count: {report['summary'].get('main_card_count', 0)}")
    console.print(f"report enrichment status: {report.get('report_enrichment', {})}")
    console.print(
        "Top breakout: "
        + ", ".join(item.get("repo_full_name", "") for item in report["sections"]["breakout"][:5])
    )
    console.print(
        "Top deep_research: "
        + ", ".join(item.get("repo_full_name", "") for item in report["sections"]["deep_research"][:5])
    )
    if getattr(args, "open", False) and written_html:
        webbrowser.open(written_html.resolve().as_uri())
    return 0


def doctor(args: argparse.Namespace) -> int:
    return run_doctor(timeout=args.timeout, console=console, llm=args.llm)


def _load_report_for_delivery(args: argparse.Namespace, *, output_dir: Path) -> tuple[dict[str, object], object]:
    payload, resolved = resolve_render_input(
        args.period,
        getattr(args, "date", None),
        snapshot_dir=args.snapshot_dir,
        report_dir=output_dir,
    )
    if resolved.is_report_model:
        report = ensure_report_enrichment_status(payload)
        save_json(report, resolved.path)
    else:
        report = build_report_model(
            payload,
            load_report_config(args.config_dir),
            source_snapshot=resolved.path,
            snapshot_kind=resolved.kind,
        )
    return report, resolved


def push(args: argparse.Namespace) -> int:
    if args.channel != "pushplus":
        console.print("[bold red]Only --channel pushplus is implemented for now.[/bold red]")
        return 1

    output_dir = Path(args.output_dir)
    try:
        report, resolved = _load_report_for_delivery(args, output_dir=output_dir)
    except SnapshotNotFoundError as exc:
        console.print(f"[bold red]{exc}[/bold red]")
        return 1

    html_report_path = _report_output_path(output_dir, args.period, "html", date_value=resolved.date.isoformat())
    full_report_url, full_report_is_url = full_report_url_from_env(
        explicit_url=args.full_report_url,
        report_path=html_report_path,
        resolved_date=resolved.date.isoformat(),
        period=args.period,
    )
    summary_path = output_dir / f"{resolved.date.isoformat()}-{args.period}-pushplus-summary.html"
    write_pushplus_summary(
        report,
        summary_path,
        full_report_url=full_report_url,
        full_report_is_url=full_report_is_url,
    )
    title = f"{report.get('title', 'GitHub AI 开源趋势雷达')} · {report.get('period_label', args.period.title())}"
    console.print(f"resolved date: {resolved.date.isoformat()}")
    console.print(f"selected input file: {resolved.path}")
    console.print(f"selected input kind: {resolved.kind}")
    console.print(f"summary html: {summary_path}")
    console.print(f"full_report_url: {full_report_url}")

    if args.dry_run:
        console.print(f"[green]dry-run: PushPlus API not called.[/green] title={title}")
        return 0

    content = summary_path.read_text(encoding="utf-8")
    result = send_pushplus(
        title=title,
        content=content,
        config=PushPlusConfig.from_env(timeout=args.timeout, retries=args.retries),
    )
    if result.skipped:
        console.print(f"[yellow]PushPlus skipped:[/yellow] {result.error}")
        return 1 if args.fail_on_push_error else 0
    if result.ok:
        console.print(f"[green]PushPlus sent.[/green] status={result.status_code} body={result.response_text[:200]}")
        return 0
    console.print(f"[red]PushPlus failed.[/red] status={result.status_code} error={result.error} body={result.response_text[:200]}")
    return 1 if args.fail_on_push_error else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="github-ai-trend-radar",
        description="Generate GitHub AI open source trend reports.",
    )
    subparsers = parser.add_subparsers(dest="command")

    commands = {
        "deep-research": "Prepare deep research notes for selected repositories.",
    }

    run_parser = subparsers.add_parser(
        "run",
        help="Run collect and rule-based score.",
        description="Run collect and rule-based score.",
    )
    _add_common_options(run_parser)
    run_parser.add_argument(
        "--render",
        action="store_true",
        help="Render Markdown and HTML reports after collect and score.",
    )
    run_parser.add_argument(
        "--format",
        choices=("md", "html", "all"),
        default="all",
        help="Report output format when --render is used.",
    )
    run_parser.add_argument(
        "--output-dir",
        default="data/reports",
        help="Directory for rendered reports when --render is used.",
    )
    run_parser.add_argument("--top-breakout", type=int, default=None)
    run_parser.add_argument("--top-mature", type=int, default=None)
    run_parser.add_argument("--top-watchlist", type=int, default=None)
    run_parser.add_argument("--top-noise", type=int, default=None)
    run_parser.add_argument("--open", action="store_true", help="Open HTML report after rendering.")
    run_parser.set_defaults(handler=run)

    collect_parser = subparsers.add_parser(
        "collect",
        help="Collect candidate repositories and source signals.",
        description="Collect candidate repositories and source signals.",
    )
    _add_common_options(collect_parser)
    collect_parser.set_defaults(handler=collect)

    score_parser = subparsers.add_parser(
        "score",
        help="Score collected repositories and trend signals.",
        description="Score collected repositories and trend signals.",
    )
    _add_common_options(score_parser)
    score_parser.set_defaults(handler=score)

    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Diagnose network, API, proxy, and token configuration.",
        description="Diagnose network, API, proxy, and token configuration.",
    )
    doctor_parser.add_argument(
        "--timeout",
        type=float,
        default=20,
        help="HTTP timeout in seconds.",
    )
    doctor_parser.add_argument(
        "--llm",
        action="store_true",
        help="Run LLM provider diagnostics.",
    )
    doctor_parser.set_defaults(handler=doctor)

    render_parser = subparsers.add_parser(
        "render",
        help="Render Markdown and ink-style HTML reports from scored trend data.",
        description="Render Markdown and ink-style HTML reports from scored trend data.",
    )
    render_parser.add_argument("--config-dir", default="config")
    render_parser.add_argument("--period", choices=("daily", "weekly", "monthly"), default="daily")
    render_parser.add_argument("--snapshot-dir", default="data/snapshots")
    render_parser.add_argument("--date", default=None, help="Snapshot date in YYYY-MM-DD format. Defaults to today.")
    render_parser.add_argument("--format", choices=("md", "html", "all"), default="all")
    render_parser.add_argument("--output-dir", default="data/reports")
    render_parser.add_argument("--open", action="store_true", help="Open HTML report with the default browser.")
    render_parser.add_argument("--enrich-report", dest="enrich_report", action="store_true", help="Use LLM to fill missing Chinese report fields for displayed projects.")
    render_parser.add_argument("--no-enrich-report", dest="enrich_report", action="store_false", help="Disable report-only LLM enrichment.")
    render_parser.add_argument("--enrich-overview", dest="enrich_overview", action="store_true", help="Use LLM to rewrite top observations as editorial judgements.")
    render_parser.add_argument("--no-enrich-overview", dest="enrich_overview", action="store_false", help="Disable overview enrichment.")
    render_parser.set_defaults(enrich_report=False)
    render_parser.set_defaults(enrich_overview=False)
    render_parser.add_argument("--top-breakout", type=int, default=None)
    render_parser.add_argument("--top-mature", type=int, default=None)
    render_parser.add_argument("--top-watchlist", type=int, default=None)
    render_parser.add_argument("--top-noise", type=int, default=None)
    render_parser.set_defaults(handler=render)

    push_parser = subparsers.add_parser(
        "push",
        help="Push a compact report summary to configured channels.",
        description="Push a compact report summary to configured channels.",
    )
    push_parser.add_argument("--config-dir", default="config")
    push_parser.add_argument("--period", choices=("daily", "weekly", "monthly"), default="daily")
    push_parser.add_argument("--snapshot-dir", default="data/snapshots")
    push_parser.add_argument("--output-dir", default="data/reports")
    push_parser.add_argument("--date", default=None, help="YYYY-MM-DD, latest, or omitted for today.")
    push_parser.add_argument("--channel", choices=("pushplus",), required=True)
    push_parser.add_argument("--full-report-url", default=None)
    push_parser.add_argument("--dry-run", action="store_true")
    push_parser.add_argument("--fail-on-push-error", action="store_true")
    push_parser.add_argument("--timeout", type=float, default=20)
    push_parser.add_argument("--retries", type=int, default=2)
    push_parser.set_defaults(handler=push)

    for name, help_text in commands.items():
        subparser = subparsers.add_parser(name, help=help_text, description=help_text)
        _add_common_options(subparser)
        subparser.set_defaults(handler=lambda args, command=name: _placeholder(command, args))

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    load_local_env()
    parser = build_parser()
    args = parser.parse_args(argv)

    if not hasattr(args, "handler"):
        parser.print_help()
        return 0

    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
