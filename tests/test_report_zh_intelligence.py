from github_ai_trend_radar.renderers.html_ink import render_html
from github_ai_trend_radar.renderers.i18n import zh_label
from github_ai_trend_radar.renderers.markdown import render_markdown
from github_ai_trend_radar.renderers.report_enrichment import enrich_report_model, enrich_report_overview
from github_ai_trend_radar.renderers.report_model import build_noise_summary, build_report_model, load_report_config
from github_ai_trend_radar.llm.client import LLMClient
from github_ai_trend_radar.llm.config import LLMConfig


def _candidate(name, bucket, action="watch", noise=False, reason=None, score=0.7):
    return {
        "repo_full_name": name,
        "html_url": f"https://github.com/{name}",
        "description": "AI agent framework",
        "radar_bucket": bucket,
        "final_recommended_action": action,
        "radar_score": score,
        "trend_score": score - 0.1,
        "value_score": score - 0.2,
        "source_hits": ["ossinsight", "github_search"],
        "matched_focus_topics": ["ai_agent"],
        "noise": {"is_noise": noise, "noise_reasons": [reason] if reason else []},
        "llm_analysis": {"llm_is_noise": noise},
    }


def test_i18n_label_mapping():
    assert zh_label("Candidates") == "候选项目"
    assert zh_label("Deep Research") == "深研"
    assert zh_label("GitHub AI Trend Radar") == "GitHub AI 开源趋势雷达"


def test_report_sections_are_deduplicated_and_ignore_excluded():
    snapshot = {
        "period": "daily",
        "candidates": [
            _candidate("owner/breakout", "breakout", "deep_research", score=0.9),
            _candidate("owner/deep", "valuable_mature", "deep_research", score=0.8),
            _candidate("owner/watch", "watchlist", "watch", score=0.7),
            _candidate("owner/noise", "breakout", "deep_research", noise=True, reason="keyword:tutorial", score=0.95),
            _candidate("owner/ignore", "valuable_mature", "ignore", score=0.85),
        ],
    }
    report = build_report_model(snapshot, load_report_config("missing-config-dir"))
    main_names = [
        item["repo_full_name"]
        for key in ("breakout", "deep_research", "long_term")
        for item in report["sections"][key]
    ]

    assert len(main_names) == len(set(main_names))
    assert "owner/noise" not in main_names
    assert "owner/ignore" not in main_names
    assert "owner/breakout" in main_names


def test_noise_summary_groups_friendly_reasons():
    summary = build_noise_summary(
        [
            _candidate("owner/prompts", "noise", "ignore", True, "keyword:prompts"),
            _candidate("owner/clone", "noise", "ignore", True, "keyword:clone"),
        ]
    )
    reasons = {item["reason"] for item in summary["reason_counts"]}

    assert "资料集合 / 教程 / prompt 类内容" in reasons
    assert "封装 / 克隆 / 模板类项目" in reasons
    assert "keyword:" not in str(summary)


def test_html_has_no_empty_analysis_and_no_major_english_ui_labels():
    snapshot = {"period": "daily", "candidates": [_candidate("owner/repo", "breakout", "read")]}
    report = build_report_model(snapshot, load_report_config("missing-config-dir"))

    html = render_html(report)

    assert '<div class="analysis"></div>' not in html
    for label in [
        "Candidates",
        "Valuable Mature",
        "Worth Watching",
        "Filtered",
        "Deep Research",
        "Noise Reasons",
    ]:
        assert label not in html


def test_keyword_learning_does_not_leak_into_html_and_noise_actions_are_filtered():
    snapshot = {
        "period": "daily",
        "candidates": [
            _candidate("owner/learning", "noise", "read", True, "keyword:learning"),
            _candidate("owner/main", "breakout", "read"),
        ],
    }
    report = build_report_model(snapshot, load_report_config("missing-config-dir"))
    html = render_html(report)

    assert "keyword:learning" not in html
    assert "阅读" not in str(report["noise_summary"]["examples"])
    assert all(item["action"] in {"过滤", "建议忽略"} for item in report["noise_summary"]["examples"])


def test_llm_coverage_stat_exists():
    report = build_report_model({"period": "daily", "candidates": [_candidate("owner/repo", "breakout", "read")]}, load_report_config("missing-config-dir"))
    html = render_html(report)

    assert "主区 LLM 分析覆盖" in html
    assert report["summary"]["main_llm_coverage"]["total"] == 1


def test_enrich_report_without_key_uses_safe_fallback():
    report = build_report_model({"period": "daily", "candidates": [_candidate("owner/repo", "breakout", "read")]}, load_report_config("missing-config-dir"))
    client = LLMClient(LLMConfig(api_key=""))

    enriched = enrich_report_model(report, client, max_items=10)

    assert enriched["report_enrichment"]["requested"] is True
    assert enriched["report_enrichment"]["enabled"] is False
    assert enriched["report_enrichment"]["fallback_count"] >= 1
    assert enriched["sections"]["breakout"][0]["report_enrichment_status"] == "fallback"


def test_enrich_overview_without_key_keeps_statistical_notes_and_adds_editorial_fallback():
    report = build_report_model({"period": "daily", "candidates": [_candidate("owner/repo", "breakout", "read")]}, load_report_config("missing-config-dir"))
    client = LLMClient(LLMConfig(api_key=""))

    enriched = enrich_report_overview(report, client)

    assert enriched["overview_enrichment"]["requested"] is True
    assert enriched["overview_enrichment"]["enabled"] is False
    assert enriched["summary"]["statistical_observations"]
    assert "ai_agent(118)" not in enriched["summary"]["top_observations"][0]


def test_report_level_llm_summary_success_replaces_rule_judgements():
    class Client:
        available = True
        model = "fake"

        def complete_json(self, messages):
            return type(
                "R",
                (),
                {
                    "ok": True,
                    "content": '{"editorial_judgements":["MCP 工具链开始从插件能力转向工程接口，企业应关注权限和可观测性。","Coding Agent 方向继续贴近真实研发流程，但成熟度差异仍需通过 README 复核。","RAG 与知识库项目更强调私有化落地，短期适合做小范围验证。"]}',
                },
            )()

    report = build_report_model({"period": "daily", "candidates": [_candidate("owner/repo", "breakout", "read")]}, load_report_config("missing-config-dir"))
    enriched = enrich_report_overview(report, Client())

    assert enriched["overview_enrichment"]["ok"] is True
    assert enriched["summary"]["top_observations"][0].startswith("MCP 工具链")


def test_report_level_llm_summary_failure_falls_back():
    class Client:
        available = True
        model = "fake"

        def complete_json(self, messages):
            return type("R", (), {"ok": False, "content": ""})()

    report = build_report_model({"period": "daily", "candidates": [_candidate("owner/repo", "breakout", "read")]}, load_report_config("missing-config-dir"))
    enriched = enrich_report_overview(report, Client())

    assert enriched["overview_enrichment"]["failed"] is True
    assert enriched["overview_enrichment"]["fallback"] is True


def test_markdown_uses_chinese_intelligence_sections():
    snapshot = {"period": "daily", "candidates": [_candidate("owner/repo", "breakout", "read")]}
    report = build_report_model(snapshot, load_report_config("missing-config-dir"))

    markdown = render_markdown(report)

    for heading in ["本期判断", "趋势突破", "值得深研", "长期观察", "已过滤信号摘要"]:
        assert heading in markdown


def test_default_main_cards_no_more_than_13_and_noise_cards_hidden():
    candidates = []
    for index in range(20):
        candidates.append(_candidate(f"owner/b{index}", "breakout", "read", score=0.9 - index * 0.01))
        candidates.append(_candidate(f"owner/d{index}", "valuable_mature", "deep_research", score=0.8 - index * 0.01))
        candidates.append(_candidate(f"owner/w{index}", "watchlist", "watch", score=0.7 - index * 0.01))
        candidates.append(_candidate(f"owner/n{index}", "noise", "ignore", True, "keyword:tutorial", score=0.6 - index * 0.01))
    report = build_report_model({"period": "daily", "candidates": candidates}, load_report_config("config"))
    html = render_html(report)
    main_count = sum(len(report["sections"][key]) for key in ("breakout", "deep_research", "long_term"))

    assert main_count <= 13
    assert 'class="card noise"' not in html
