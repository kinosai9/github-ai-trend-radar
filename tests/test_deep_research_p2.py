import json
from pathlib import Path

import yaml

from github_ai_trend_radar.deep_research import write_deep_research_report
from github_ai_trend_radar.llm.errors import LLMResult
from github_ai_trend_radar.research.collector import ResearchCollector, _prioritize_files
from github_ai_trend_radar.research.code_analyzer import analyze_code_architecture
from github_ai_trend_radar.research.comparable_finder import find_comparable_projects
from github_ai_trend_radar.research.diagram_builder import build_architecture_diagram, build_mindmap
from github_ai_trend_radar.research.enterprise_fit import evaluate_enterprise_fit
from github_ai_trend_radar.research.ecosystem_search import search_ecosystem_context
from github_ai_trend_radar.research.issue_analyzer import analyze_issues_and_limitations
from github_ai_trend_radar.research.llm_analyzer import _safe_excerpt, _stage_payload, run_staged_llm_analysis
from github_ai_trend_radar.research.profile import load_company_profile
from github_ai_trend_radar.research.repo_analyzer import analyze_repo_structure
from github_ai_trend_radar.research.report_writer import render_html, render_markdown
from github_ai_trend_radar.research.verdict import build_final_verdict


def test_company_profile_loads_default_and_local_override(tmp_path):
    config = tmp_path / "config"
    config.mkdir()
    (config / "company_profile.default.yaml").write_text(
        yaml.safe_dump({"company": {"role": "default", "focus_domains": ["MCP"]}, "deep_research": {"report_language": "zh-CN"}}),
        encoding="utf-8",
    )
    (config / "company_profile.local.yaml").write_text(
        yaml.safe_dump({"company": {"role": "local"}}),
        encoding="utf-8",
    )

    profile = load_company_profile(config)

    assert profile["company"]["role"] == "local"
    assert profile["company"]["focus_domains"] == ["MCP"]
    assert profile["deep_research"]["report_language"] == "zh-CN"


def test_repo_context_collector_mock_github_api():
    collector = ResearchCollector(client=FakeClient())

    context = collector.collect_project_context("owner", "repo", max_files=10, max_issues=5)

    assert context["metadata"]["full_name"] == "owner/repo"
    assert "README" in context["readme"]
    assert "pyproject.toml" in context["files"]
    assert context["open_issues"][0]["title"] == "bug: broken auth"


def test_key_files_are_preserved_before_max_files_cutoff():
    paths = [f"docs/translations/{index}.md" for index in range(200)] + ["pyproject.toml", "src/graphify/parser.py", "docs/index.md", "tests/test_app.py"]

    selected = _prioritize_files(paths, max_files=5)

    assert "pyproject.toml" in selected
    assert "src/graphify/parser.py" in selected
    assert "docs/index.md" in selected
    assert "tests/test_app.py" in selected


def test_repo_structure_analyzer_identifies_docs_examples_tests_package_files():
    context = {
        "metadata": {"language": "Python"},
        "files": ["README.md", "docs/index.md", "examples/demo.py", "tests/test_app.py", "pyproject.toml", "src/app.py"],
        "package_files": ["pyproject.toml"],
    }

    structure = analyze_repo_structure(context)

    assert "docs/index.md" in structure["docs_paths"]
    assert "examples/demo.py" in structure["examples_paths"]
    assert "tests/test_app.py" in structure["tests_paths"]
    assert "pyproject.toml" in structure["package_files"]


def test_tests_and_fixtures_are_not_core_modules():
    context = {
        "files": [
            "tests/fixtures/parser.py",
            "tests/test_graph.py",
            "src/graphify/parser.py",
            "src/graphify/graph_builder.py",
        ],
        "readme": "code knowledge graph tree-sitter graph builder",
    }
    architecture = analyze_code_architecture(context, {"entrypoints": [], "package_files": []})

    paths = [item["path"] for item in architecture["core_modules"]]
    assert "src/graphify/parser.py" in paths
    assert all(not path.startswith("tests/") for path in paths)


def test_pyproject_entrypoints_are_detected_from_clone(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project.scripts]\ngraphify = \"graphify.cli:main\"\n", encoding="utf-8")
    architecture = analyze_code_architecture({"files": ["src/graphify/cli.py"], "readme": ""}, {"entrypoints": []}, clone_path=tmp_path)

    assert any("graphify" in item["path"] for item in architecture["entrypoints"])


def test_module_roles_are_not_all_graph_pipeline():
    architecture = analyze_code_architecture(
        {
            "files": ["src/graph.py", "src/cache.py", "src/cli.py", "src/render_html.py"],
            "readme": "graph cache cli html",
        },
        {"entrypoints": [], "package_files": []},
    )
    roles = {item["role"] for item in architecture["core_modules"]}

    assert len(roles) > 1


def test_issue_analyzer_extracts_negative_keywords():
    context = {"open_issues": [{"number": 1, "state": "open", "title": "security: api_key leak", "body": "secret leak", "html_url": "u"}], "closed_issues": [], "pull_requests": [], "readme": "unsupported beta"}

    signals = analyze_issues_and_limitations(context)

    assert signals["issue_hotspots"]
    assert signals["recurring_complaints"][0]["keywords"]
    assert signals["negative_evidence"][0]["category"] == "security"
    assert signals["negative_evidence"][0]["severity"] == "high"
    assert "unsupported" in signals["missing_capabilities"]


def test_bugfix_pr_and_feature_enhancement_are_classified():
    context = {
        "open_issues": [{"number": 2, "state": "open", "title": "feature: add neo4j export", "body": "enhancement", "html_url": "u2"}],
        "closed_issues": [{"number": 1, "state": "closed", "title": "fix broken parser", "body": "not working", "html_url": "u1"}],
        "pull_requests": [],
        "readme": "",
    }

    signals = analyze_issues_and_limitations(context)
    kinds = {item["evidence_kind"]: item["risk_status"] for item in signals["negative_evidence"]}

    assert kinds["merged_fix_pr"] in {"fixed", "mitigated"}
    assert kinds["feature_enhancement"] == "not_a_risk"


def test_comparable_finder_limits_projects():
    result = find_comparable_projects(
        {"repo": "owner/repo", "metadata": {"description": "target", "stargazers_count": 100}},
        {
            "primary_domain": "mcp",
            "notable_projects": [
                {"repo": f"other/repo-{index}", "description": "mcp server", "stars": index * 100}
                for index in range(10)
            ],
        },
        max_comparables=5,
    )

    assert len(result["comparables"]) == 5
    assert len(result["table"]["rows"]) <= 6


def test_comparable_finder_filters_weak_unrelated_projects():
    result = find_comparable_projects(
        {"repo": "owner/repo", "metadata": {"description": "code knowledge graph"}},
        {
            "primary_domain": "rag_knowledge",
            "notable_projects": [
                {"repo": "x/awesome-prompts", "description": "awesome prompt collection", "stars": 1000},
                {"repo": "x/code-graph", "description": "code knowledge graph for repo context", "stars": 100},
            ],
        },
        max_comparables=5,
    )

    assert [item["repo"] for item in result["comparables"]] == ["x/code-graph"]
    assert result["filtered_weak_projects"]


def test_final_verdict_upgrades_security_risk_from_low():
    verdict = build_final_verdict(
        {
            "context": {"readme": "x", "metadata": {"stargazers_count": 1000}},
            "architecture": {"core_modules": ["src/app.py"], "graph_pipeline": ["graph builder"]},
            "negative_signals": {"negative_evidence": [{"category": "security", "severity": "high", "title": "api_key leak"}]},
            "enterprise_fit": {"final_rating": {"risk_level": "low", "enterprise_fit": 4, "implementation_feasibility": 4}},
            "source_quality": {"code_analyzed": True, "issues_analyzed": True, "llm_stage_success": 5},
        }
    )

    assert verdict["risk_level"] == "high"
    assert "enterprise_readiness" in verdict
    assert "open_source_engineering_maturity" in verdict
    assert verdict["recommendation"] in {"watch", "hold"}


def test_ecosystem_search_uses_github_search_projects():
    context = {
        "repo": "owner/repo",
        "metadata": {"full_name": "owner/repo", "topics": ["mcp"], "stargazers_count": 100},
        "readme": "model context protocol mcp server",
    }

    ecosystem = search_ecosystem_context(context, {}, client=SearchFakeClient(), max_projects=3, snapshot_dir="missing")

    assert ecosystem["primary_domain"] == "mcp"
    assert ecosystem["notable_projects"]
    assert ecosystem["sources"]["github_search_count"] > 0
    assert "other/mcp-server" in {item["repo"] for item in ecosystem["notable_projects"]}


def test_enterprise_fit_uses_company_profile():
    context = {"metadata": {"topics": ["mcp"], "license": {"spdx_id": "MIT"}}, "readme": "mcp self-hosted docker"}
    structure = {"docs_paths": ["docs/a.md"], "examples_paths": ["examples/a.py"], "deployment_files": ["Dockerfile"], "package_files": ["pyproject.toml"], "main_languages": ["Python"]}
    architecture = {"api_surface": ["api.py"], "cli_surface": [], "security_boundary": ["token"]}
    profile = {"company": {"focus_domains": ["MCP"], "current_stack": ["Python"], "integration_targets": ["MCP 工具生态"], "unacceptable_risks": ["数据外传"]}}

    fit = evaluate_enterprise_fit(context, structure, architecture, {"enterprise_blockers": []}, profile)

    assert "公司关注方向" in fit["relevance_to_company"]
    assert fit["final_rating"]["enterprise_fit"] >= 3


def test_mermaid_generators_contain_required_keywords():
    flow = build_architecture_diagram({"repo": "owner/repo"}, {}, {"api_surface": ["api.py"]})
    mindmap = build_mindmap({"repo": "owner/repo"}, {"final_rating": {"risk_level": "medium"}})

    assert "flowchart TD" in flow
    assert "输入资产" in flow
    assert "tests/test_" not in flow
    assert "mindmap" in mindmap


def test_html_tables_render_links_and_do_not_show_python_repr():
    payload = {
        "repo": "owner/repo",
        "generated_at": "now",
        "context": {"metadata": {"html_url": "https://github.com/owner/repo"}, "releases": []},
        "repo_structure": {"file_type_counts": {".py": 1}, "entrypoints": [], "main_languages": ["Python"]},
        "architecture": {"core_modules": ["src/app.py"], "module_roles": {"src/app.py": "core logic"}},
        "negative_signals": {
            "keyword_counts": [{"keyword": "security", "count": 1}],
            "negative_evidence": [{"title": "api leak", "url": "https://example.com/i/1", "category": "security", "severity": "high", "enterprise_impact": "risk", "confidence": "high"}],
        },
        "enterprise_fit": {
            "final_rating": {"risk_level": "high"},
            "company_direction_fit": {"coding_agent_context": "Coding Agent 上下文增强"},
            "enterprise_action_plan": {"go_no_go_criteria": ["Go：可离线运行", "No-go：泄露 secret"]},
        },
        "final_verdict": {"recommendation": "hold", "risk_level": "high", "next_actions": ["暂停"], "blocking_risks": ["risk"]},
        "evidence": {"positive": [], "uncertainty": []},
        "llm_analysis": {"enabled": False},
        "ecosystem_context": {},
        "comparison": {"table": {"columns": ["项目"], "rows": [["[repo](https://example.com)"]]}},
        "diagrams": {"architecture": "flowchart TD\nA-->B", "mindmap": "mindmap\n root"},
    }
    markdown = render_markdown(payload)
    html = render_html(payload, markdown)

    assert '<a href="https://example.com">repo</a>' in html
    assert "{'.py':" not in html
    assert "[('fail'," not in html
    assert "risk-high" in html
    assert "Coding Agent 上下文增强" in markdown
    assert "Go：" in markdown


def test_deep_research_without_llm_writes_structured_outputs(tmp_path):
    md, html = write_deep_research_report("owner/repo", output_dir=tmp_path, client=FakeClient(), use_llm=False)
    root = md.parent
    summary = json.loads((root / "research-summary.json").read_text(encoding="utf-8"))

    assert md.exists()
    assert html.exists()
    assert (root / "research.json").exists()
    assert (root / "research-summary.json").exists()
    assert (root / "intermediate" / "01_repo_context.json").exists()
    assert (tmp_path / "index.json").exists()
    assert (tmp_path / "index.html").exists()
    assert summary["investment_decision"]
    assert "项目专项深度研究报告" in md.read_text(encoding="utf-8")
    assert "<h1>" in html.read_text(encoding="utf-8")
    assert "<pre># 项目专项深度研究报告" not in html.read_text(encoding="utf-8")


def test_llm_stage_failure_not_required_for_report(tmp_path):
    md, html = write_deep_research_report("owner/repo", output_dir=tmp_path, client=FakeClient(), llm_client=FailingLLM())
    summary = json.loads((md.parent / "research-summary.json").read_text(encoding="utf-8"))

    assert summary["status"] == "partial_success"
    assert summary["llm_analysis"]["failed_count"] > 0
    assert html.exists()


def test_no_clone_does_not_execute_target_code(tmp_path, monkeypatch):
    called = False

    def fake_run(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr("github_ai_trend_radar.research.collector.subprocess.run", fake_run)
    write_deep_research_report("owner/repo", output_dir=tmp_path, client=FakeClient(), clone=False, use_llm=False)

    assert called is False


def test_data_research_is_gitignored():
    text = Path(".gitignore").read_text(encoding="utf-8")
    assert "data/research/*" in text


def test_staged_llm_success_writes_analysis(tmp_path):
    md, _ = write_deep_research_report("owner/repo", output_dir=tmp_path, client=FakeClient(), llm_client=SuccessfulLLM())
    payload = json.loads((md.parent / "research.json").read_text(encoding="utf-8"))
    summary = json.loads((md.parent / "research-summary.json").read_text(encoding="utf-8"))

    assert payload["llm_analysis"]["ok_count"] == 6
    assert (md.parent / "intermediate" / "08_llm_analysis.json").exists()
    assert summary["llm_analysis"]["ok_count"] == 6
    assert "LLM 企业落地综合判断" in md.read_text(encoding="utf-8")


def test_llm_stage_payload_is_compact():
    payload = {
        "repo": "owner/repo",
        "context": {"metadata": {"license": {"spdx_id": "MIT"}, "topics": list(range(20))}, "readme": "x" * 5000},
        "company_profile": {"company": {"focus_domains": list(range(20)), "current_stack": list(range(20)), "role": "role"}},
        "repo_structure": {"docs_paths": [str(i) for i in range(30)], "package_files": ["pyproject.toml"], "main_languages": ["Python"]},
    }

    stage = _stage_payload("repo_overview_summary", payload, {})

    assert len(stage["readme_excerpt"]) == 1200
    assert len(stage["metadata"]["topics"]) == 12
    assert len(stage["company_profile"]["focus_domains"]) == 8
    assert len(stage["repo_structure"]["docs_paths"]) == 12


def test_staged_llm_can_select_subset_and_sets_max_tokens():
    client = RecordingLLM()
    result = run_staged_llm_analysis(
        {"repo": "owner/repo", "context": {"metadata": {}, "readme": "README"}},
        client=client,
        stages=["enterprise_fit_summary", "final_report_synthesis"],
    )

    assert result["selected_stages"] == ["enterprise_fit_summary", "final_report_synthesis"]
    assert result["ok_count"] == 2
    assert [call["max_tokens"] for call in client.calls] == [1800, 2200]


def test_negative_signal_stage_has_enough_output_budget():
    client = RecordingLLM()
    run_staged_llm_analysis(
        {"repo": "owner/repo", "context": {"metadata": {}, "readme": "README"}, "negative_signals": {}},
        client=client,
        stages=["negative_signal_summary"],
    )

    assert client.calls[0]["max_tokens"] >= 1000


def test_code_architecture_stage_has_enough_output_budget():
    client = RecordingLLM()
    run_staged_llm_analysis(
        {"repo": "owner/repo", "context": {"metadata": {}, "readme": "README"}, "repo_structure": {}, "architecture": {}},
        client=client,
        stages=["code_architecture_summary"],
    )

    assert client.calls[0]["max_tokens"] >= 2000


def test_overview_and_comparison_stages_have_enough_output_budget():
    client = RecordingLLM()
    run_staged_llm_analysis(
        {"repo": "owner/repo", "context": {"metadata": {}, "readme": "README"}, "comparison": {}},
        client=client,
        stages=["repo_overview_summary", "comparison_summary"],
    )

    assert [call["max_tokens"] for call in client.calls] == [1200, 2200]


def test_safe_excerpt_removes_code_fences_and_urls():
    text = "intro ```python\nsecret_code()\n``` https://example.com/path tail"
    assert "secret_code" not in _safe_excerpt(text, 200)
    assert "http" not in _safe_excerpt(text, 200)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


class FakeClient:
    def get_repo(self, owner, repo):
        return {
            "full_name": f"{owner}/{repo}",
            "html_url": f"https://github.com/{owner}/{repo}",
            "description": "MCP agent tool",
            "language": "Python",
            "default_branch": "main",
            "topics": ["mcp"],
            "stargazers_count": 100,
            "forks_count": 10,
            "open_issues_count": 2,
            "license": {"spdx_id": "MIT"},
            "pushed_at": "2026-05-25T00:00:00Z",
        }

    def get_readme(self, owner, repo):
        return "README mcp self-hosted docker api cli examples"

    def _get(self, path):
        if path.startswith("/search/repositories"):
            return FakeResponse({"items": []})
        if "/git/trees/" in path:
            return FakeResponse(
                {
                    "tree": [
                        {"type": "blob", "path": "README.md"},
                        {"type": "blob", "path": "pyproject.toml"},
                        {"type": "blob", "path": "docs/index.md"},
                        {"type": "blob", "path": "examples/demo.py"},
                        {"type": "blob", "path": "tests/test_app.py"},
                        {"type": "blob", "path": "src/cli.py"},
                        {"type": "blob", "path": "src/api.py"},
                    ]
                }
            )
        if "/releases" in path:
            return FakeResponse([{"name": "v1"}])
        if "state=open" in path:
            return FakeResponse([{"title": "bug: broken auth", "body": "not working", "html_url": "u"}])
        if "state=closed" in path:
            return FakeResponse([])
        if "/pulls" in path:
            return FakeResponse([{"title": "fix performance", "body": "slow", "html_url": "p"}])
        return FakeResponse({})


class SearchFakeClient(FakeClient):
    def _get(self, path):
        if path.startswith("/search/repositories"):
            return FakeResponse(
                {
                    "items": [
                        {
                            "full_name": "other/mcp-server",
                            "html_url": "https://github.com/other/mcp-server",
                            "description": "MCP server framework",
                            "stargazers_count": 1200,
                            "forks_count": 100,
                            "language": "TypeScript",
                            "topics": ["mcp", "model-context-protocol"],
                            "pushed_at": "2026-05-20T00:00:00Z",
                        },
                        {
                            "full_name": "owner/repo",
                            "html_url": "https://github.com/owner/repo",
                            "description": "target",
                            "stargazers_count": 100,
                            "topics": ["mcp"],
                        },
                    ]
                }
            )
        return super()._get(path)


class SuccessfulLLM:
    available = True
    model = "test-model"

    def chat_json(self, *, system_prompt, user_payload, **kwargs):
        stage_data = {
            "one_line_judgement": "值得进入企业 PoC。",
            "summary": "项目具备代码知识图谱价值。",
            "final_conclusion": "建议小范围试用。",
            "recommended_action": "try_locally",
            "investment_suggestion": "投入 1-2 天做本地验证。",
            "risk_note": "注意权限和数据边界。",
            "key_findings": ["适合 Coding Agent 知识增强", "需验证私有化部署"],
        }
        return LLMResult(ok=True, content=json.dumps(stage_data, ensure_ascii=False), raw={}, provider="test", model="test-model")


class FailingLLM:
    available = True
    model = "test-model"

    def chat_json(self, *, system_prompt, user_payload, **kwargs):
        return LLMResult(ok=False, content="", raw={}, provider="test", model="test-model", error_type="timeout", error_message="timeout")


class RecordingLLM(SuccessfulLLM):
    def __init__(self):
        self.calls = []

    def chat_json(self, *, system_prompt, user_payload, **kwargs):
        self.calls.append({"system_prompt": system_prompt, "user_payload": user_payload, **kwargs})
        return super().chat_json(system_prompt=system_prompt, user_payload=user_payload)
