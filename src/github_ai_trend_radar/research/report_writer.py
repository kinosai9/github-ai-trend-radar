"""Deep research report rendering."""

from __future__ import annotations

import html
from datetime import date, datetime
from pathlib import Path
from typing import Any

from github_ai_trend_radar.research.models import ResearchOptions, repo_slug
from github_ai_trend_radar.storage.files import load_json, save_json


def research_root(options: ResearchOptions, *, report_date: str | None = None) -> Path:
    day = report_date or date.today().isoformat()
    return Path(options.output_dir) / repo_slug(options.repo) / day


def write_research_outputs(payload: dict[str, Any], options: ResearchOptions, *, report_date: str | None = None) -> tuple[Path, Path, Path, Path]:
    root = research_root(options, report_date=report_date)
    (root / "intermediate").mkdir(parents=True, exist_ok=True)
    (root / "raw").mkdir(parents=True, exist_ok=True)
    (root / "assets").mkdir(parents=True, exist_ok=True)
    _write_intermediates(root, payload)
    md_path = root / "research.md"
    html_path = root / "research.html"
    json_path = root / "research.json"
    summary_path = root / "research-summary.json"
    markdown = render_markdown(payload)
    md_path.write_text(markdown, encoding="utf-8")
    html_path.write_text(render_html(payload, markdown), encoding="utf-8")
    save_json(payload, json_path)
    save_json(_summary(payload, md_path, html_path), summary_path)
    _update_research_index(Path(options.output_dir), payload, md_path, html_path, summary_path)
    return md_path, html_path, json_path, summary_path


def render_markdown(payload: dict[str, Any]) -> str:
    context = payload.get("context", {})
    metadata = context.get("metadata", {}) if isinstance(context.get("metadata"), dict) else {}
    repo = payload.get("repo", context.get("repo", ""))
    enterprise = payload.get("enterprise_fit", {})
    llm = payload.get("llm_analysis", {}) if isinstance(payload.get("llm_analysis"), dict) else {}
    final_llm = _llm_stage_data(llm, "final_report_synthesis")
    verdict = payload.get("final_verdict", {}) if isinstance(payload.get("final_verdict"), dict) else {}
    rating = enterprise.get("final_rating", {}) if isinstance(enterprise.get("final_rating"), dict) else {}
    structure = payload.get("repo_structure", {})
    architecture = payload.get("architecture", {})
    negative = payload.get("negative_signals", {})
    ecosystem = payload.get("ecosystem_context", {})
    comparison = payload.get("comparison", {})
    diagrams = payload.get("diagrams", {})
    return f"""# 项目专项深度研究报告：{repo}

## 1. 情况摘要

- 最终结论：{verdict.get('one_sentence') or _one_line_judgement(payload)}
- 推荐动作：{_action_label(verdict.get('recommendation', 'watch'))}
- 技术潜力 / 社区信号 / 开源工程成熟度 / 企业就绪度 / 实施可行性 / 风险等级：{verdict.get('technical_potential', 'unknown')} / {verdict.get('community_signal', 'unknown')} / {verdict.get('open_source_engineering_maturity', verdict.get('engineering_maturity', 'unknown'))} / {verdict.get('enterprise_readiness', verdict.get('enterprise_fit', 'unknown'))} / {verdict.get('implementation_feasibility', 'unknown')} / {verdict.get('risk_level', 'unknown')}

| 评分项 | 结论 |
| --- | --- |
| 技术潜力 | {verdict.get('technical_potential', 'unknown')} |
| 社区信号 | {verdict.get('community_signal', 'unknown')} |
| 开源工程成熟度 | {verdict.get('open_source_engineering_maturity', verdict.get('engineering_maturity', 'unknown'))} |
| 企业就绪度 | {verdict.get('enterprise_readiness', verdict.get('enterprise_fit', 'unknown'))} |
| 实施可行性 | {verdict.get('implementation_feasibility', 'unknown')} |
| 风险等级 | {verdict.get('risk_level', 'unknown')} |
| 推荐动作 | {_action_label(verdict.get('recommendation', 'watch'))} |

- 投入判断：{_investment_decision(payload)}
- 是否值得继续关注：建议继续关注，但以本地 PoC 和权限/部署验证为前置。
- 是否建议深研/试用/暂缓：{enterprise.get('short_term_action', '建议先做资料复核。')}
- 企业落地结论：{enterprise.get('deployment_feasibility', '信息不足')}
- 报告模式：{_report_mode_text(llm)}
- LLM 分析状态：{_llm_status_text(llm)}
{_llm_final_block(final_llm)}

## 2. 关键发现

{_bullets(_key_findings(payload))}

## 3. 证据看板

### 正向证据
{_bullets(payload.get('evidence', {}).get('positive', []) or ['暂无明确正向证据。'])}

### 负向证据
{_negative_evidence_table(negative)}

### 待验证信息
{_bullets(payload.get('evidence', {}).get('uncertainty', []) or ['暂无额外待验证项。'])}

### 信息缺口
{_bullets(verdict.get('blocking_risks', []) or ['暂无阻塞级信息缺口。'])}

## 4. 项目基本信息

- GitHub 链接：{metadata.get('html_url', f'https://github.com/{repo}')}
- Stars/Forks/Issues：{metadata.get('stargazers_count', '')} / {metadata.get('forks_count', '')} / {metadata.get('open_issues_count', '')}
- License：{_license(metadata)}
- Languages：{', '.join(structure.get('main_languages', []) or [])}
- Topics：{', '.join(metadata.get('topics', []) or [])}
- 最近更新：{metadata.get('pushed_at', '')}
- Release 情况：{len(context.get('releases', []) or [])} 个 release 样本

## 5. 生态位置与同类项目

- 所属技术方向：{ecosystem.get('primary_domain', 'other')}
- 当前生态趋势：{ecosystem.get('market_stage', 'unclear')}
- 项目位置：{ecosystem.get('target_project_position', '')}
- 近期动态：{ecosystem.get('recent_dynamics', '')}
- 同类项目样本：
{_notable_projects(ecosystem)}

## 6. 代码结构与架构拆解

- 文件类型统计：
{_file_type_table(structure.get('file_type_counts', {}))}
- 入口模块：{', '.join(structure.get('entrypoints', []) or ['未识别'])}
- 核心模块：{', '.join(_module_paths(architecture.get('core_modules', []))[:12] or ['未识别'])}
- 模块角色：
{_module_role_table(architecture.get('module_roles', {}))}
- Graph Pipeline：{_pipeline_summary(architecture.get('graph_pipeline', {}))}
- 扩展点：{', '.join(architecture.get('extension_points', [])[:8] or ['未识别'])}
- 依赖关系：{', '.join(architecture.get('external_dependencies', [])[:10] or ['未识别'])}

```mermaid
{diagrams.get('architecture', '')}
```

## 7. 核心技术与实现机制

- 关键机制：基于 README、目录结构、入口模块和 LLM 分阶段分析做综合判断。
- 解决的问题：{metadata.get('description', '需要结合 README 进一步判断。')}
- 技术路线：{', '.join(structure.get('main_languages', []) or ['未识别'])}
- 创新点：信息不足，需在 P2.2 中结合源码摘要判断。
- 局限：不执行代码、不安装依赖，本报告只做只读分析。

## 8. 横向对比分析

{_comparison_table(comparison)}

### 相邻生态参考
{_adjacent_comparables(comparison)}

## 9. 负面信息与限制

- 主要风险摘要：{_risk_summary(payload)}
- Issue 关键词统计：
{_keyword_table(negative.get('keyword_counts', []))}
- 未解决风险：
{_negative_evidence_table(negative, group='unresolved')}
- 已修复但需复核：
{_negative_evidence_table(negative, group='fixed')}
- 用户抱怨 / 使用限制：
{_negative_evidence_table(negative, group='complaint')}
- 正向维护信号：
{_negative_evidence_table(negative, group='positive')}
- 维护风险：{', '.join(negative.get('maintenance_risks', []) or ['未发现明确维护风险'])}
- 安全风险：{_inline_titles(negative.get('security_risks', [])) or '未发现明确安全 issue 样本'}
- 企业落地阻塞点：{', '.join(negative.get('enterprise_blockers', []) or ['暂未识别'])}

## 10. 企业落地适配

- 与我司当前技术栈关系：{enterprise.get('fit_with_existing_stack', '')}
- 可接入场景：{', '.join(enterprise.get('applicable_scenarios', []) or [])}
- 二次开发成本：需要结合核心模块复杂度、文档质量和部署方式进一步评估。
- 私有化部署可行性：{enterprise.get('deployment_feasibility', '')}
- 数据安全和权限边界：{'; '.join(enterprise.get('data_security_considerations', []) or [])}
- 推荐落地路径：{enterprise.get('medium_term_action', '')}
- 评分：技术价值 {rating.get('technical_value', '')}/5，企业适配 {rating.get('enterprise_fit', '')}/5，可实施性 {rating.get('implementation_feasibility', '')}/5，战略相关 {rating.get('strategic_relevance', '')}/5，风险 {rating.get('risk_level', '')}
- 质量闸门：{_quality_gate_text(payload)}
- 公司方向相关性：
{_action_plan_table(enterprise.get('company_direction_fit', {}))}
- 可落地场景：{'; '.join(enterprise.get('landing_scenarios', []) or [])}
- 不可直接落地原因：{'; '.join(enterprise.get('direct_blockers', []) or [])}
- 行动计划：
{_action_plan_table(enterprise.get('enterprise_action_plan', {}))}

## 11. 架构图与思维导图

```mermaid
{diagrams.get('mindmap', '')}
```

## 12. 结论与行动计划

- 立即行动：{'; '.join(verdict.get('next_actions', []) or [enterprise.get('short_term_action', '')])}
- 后续观察：关注 release、issue 热点、权限/审计能力和企业部署案例。
- 不建议投入的条件：{', '.join(enterprise.get('not_recommended_if', []) or verdict.get('blocking_risks', []) or ['无法确认许可证、权限边界或部署可控性'])}
- 是否加入长期 watchlist：建议加入，除非后续 PoC 发现安全或维护风险不可接受。
"""


def render_html(payload: dict[str, Any], markdown: str) -> str:
    title = f"项目专项深度研究报告：{payload.get('repo', '')}"
    body = _markdown_to_html(markdown)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    body {{ margin:0; background:#f7f3ea; color:#132238; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; line-height:1.72; }}
    main {{ max-width:1040px; margin:0 auto; padding:32px 18px 56px; }}
    article {{ background:#fffdf8; border:1px solid #d8d1c2; padding:28px; box-shadow:0 12px 32px rgba(25,31,44,.08); }}
    h1,h2,h3 {{ color:#0d1f35; line-height:1.25; }}
    h1 {{ font-size:28px; border-bottom:2px solid #1f2d3d; padding-bottom:14px; }}
    h2 {{ margin-top:34px; font-size:21px; }}
    pre {{ overflow:auto; background:#f1efe8; padding:14px; border:1px solid #ddd5c7; white-space:pre-wrap; }}
    code {{ font-family:ui-monospace,SFMono-Regular,Consolas,monospace; }}
    p {{ margin:8px 0; }}
    ul {{ padding-left:22px; }}
    table {{ border-collapse:collapse; width:100%; margin:12px 0; }}
    th,td {{ border:1px solid #d8d1c2; padding:8px; vertical-align:top; }}
    th {{ background:#f1efe8; }}
    .toc {{ background:#f8f6ef; border:1px solid #ded7ca; padding:14px 18px; margin:18px 0; }}
    .meta {{ color:#667085; font-size:13px; }}
    .section {{ border-top:1px solid #e7decd; padding-top:8px; }}
    .mermaid {{ background:#fbfaf5; border:1px dashed #cfc6b4; }}
    .risk-low {{ color:#166534; font-weight:700; }}
    .risk-medium {{ color:#b45309; font-weight:700; }}
    .risk-high {{ color:#b91c1c; font-weight:700; }}
    @media (max-width: 720px) {{ article {{ padding:18px; }} h1 {{ font-size:23px; }} table {{ font-size:13px; }} }}
  </style>
</head>
<body><main><article>
<div class="meta">本地私有尽调报告 · 不发布到 GitHub Pages · 生成时间 {html.escape(str(payload.get('generated_at', '')))}</div>
<div class="toc"><strong>目录</strong><ol>
<li>情况摘要</li><li>关键发现</li><li>项目基本信息</li><li>广度搜索与生态位置</li><li>代码结构与架构拆解</li><li>核心技术与实现思路</li><li>横向对比分析</li><li>负面信息与限制</li><li>企业落地适配</li><li>思维导图</li><li>结论与建议</li>
</ol></div>
{body}
</article></main></body></html>"""


def _write_intermediates(root: Path, payload: dict[str, Any]) -> None:
    mapping = {
        "01_repo_context.json": payload.get("context", {}),
        "02_code_architecture.json": {"repo_structure": payload.get("repo_structure", {}), "architecture": payload.get("architecture", {})},
        "03_ecosystem.json": payload.get("ecosystem_context", {}),
        "04_comparison.json": payload.get("comparison", {}),
        "05_negative_signals.json": payload.get("negative_signals", {}),
        "06_enterprise_fit.json": payload.get("enterprise_fit", {}),
        "07_final_report.json": {"repo": payload.get("repo"), "generated_at": payload.get("generated_at")},
        "08_llm_analysis.json": payload.get("llm_analysis", {}),
        "09_final_verdict.json": payload.get("final_verdict", {}),
        "10_evidence.json": payload.get("evidence", {}),
    }
    for name, data in mapping.items():
        save_json(data, root / "intermediate" / name)
    save_json(payload.get("context", {}), root / "raw" / "github_context.json")


def _summary(payload: dict[str, Any], md_path: Path, html_path: Path) -> dict[str, Any]:
    verdict = payload.get("final_verdict", {}) if isinstance(payload.get("final_verdict"), dict) else {}
    return {
        "repo": payload.get("repo"),
        "generated_at": payload.get("generated_at"),
        "status": "success" if not payload.get("errors") else "partial_success",
        "depth": payload.get("options", {}).get("depth"),
        "private": payload.get("options", {}).get("private", True),
        "outputs": {"markdown": str(md_path), "html": str(html_path)},
        "errors": payload.get("errors", []),
        "investment_decision": _investment_decision(payload),
        "risk_level": verdict.get("risk_level", "unknown"),
        "final_verdict": verdict,
        "llm_analysis": {
            "enabled": payload.get("llm_analysis", {}).get("enabled", False) if isinstance(payload.get("llm_analysis"), dict) else False,
            "ok_count": payload.get("llm_analysis", {}).get("ok_count", 0) if isinstance(payload.get("llm_analysis"), dict) else 0,
            "failed_count": payload.get("llm_analysis", {}).get("failed_count", 0) if isinstance(payload.get("llm_analysis"), dict) else 0,
            "model": payload.get("llm_analysis", {}).get("model", "") if isinstance(payload.get("llm_analysis"), dict) else "",
        },
    }


def _one_line_judgement(payload: dict[str, Any]) -> str:
    final_llm = _llm_stage_data(payload.get("llm_analysis", {}), "final_report_synthesis")
    for key in ("one_line_judgement", "summary", "final_conclusion", "核心判定", "最终结论"):
        if final_llm.get(key):
            return str(final_llm[key])
    enterprise = payload.get("enterprise_fit", {})
    rating = enterprise.get("final_rating", {}) if isinstance(enterprise.get("final_rating"), dict) else {}
    return f"该项目具备进一步评估价值，当前企业适配 {rating.get('enterprise_fit', '?')}/5，风险等级 {rating.get('risk_level', 'unknown')}。"


def _investment_decision(payload: dict[str, Any]) -> str:
    verdict = payload.get("final_verdict", {}) if isinstance(payload.get("final_verdict"), dict) else {}
    if verdict.get("next_actions"):
        return "；".join(str(item) for item in verdict.get("next_actions", [])[:3])
    final_llm = _llm_stage_data(payload.get("llm_analysis", {}), "final_report_synthesis")
    for key in ("investment_suggestion", "recommended_action", "最终建议", "投入建议"):
        if final_llm.get(key):
            return str(final_llm[key])
    enterprise = payload.get("enterprise_fit", {}) if isinstance(payload.get("enterprise_fit"), dict) else {}
    rating = enterprise.get("final_rating", {}) if isinstance(enterprise.get("final_rating"), dict) else {}
    technical = int(rating.get("technical_value") or 0)
    fit = int(rating.get("enterprise_fit") or 0)
    feasibility = int(rating.get("implementation_feasibility") or 0)
    risk = str(rating.get("risk_level") or "unknown")
    if risk == "high" or min(technical, fit, feasibility) <= 2:
        return "暂缓投入，只保留观察；除非后续补齐许可证、部署和权限边界证据。"
    if technical >= 4 and fit >= 4 and feasibility >= 3:
        return "建议进入小范围 PoC，先验证私有化部署、数据边界和二开成本。"
    return "建议加入 watchlist，先做资料复核和轻量本地验证。"


def _key_findings(payload: dict[str, Any]) -> list[str]:
    final_llm = _llm_stage_data(payload.get("llm_analysis", {}), "final_report_synthesis")
    findings = final_llm.get("key_findings")
    if isinstance(findings, list) and findings:
        return [str(item) for item in findings[:8]]
    structure = payload.get("repo_structure", {})
    negative = payload.get("negative_signals", {})
    enterprise = payload.get("enterprise_fit", {})
    return [
        f"技术发现：主要语言/技术栈为 {', '.join(structure.get('main_languages', []) or ['未识别'])}。",
        f"工程发现：识别到 docs {len(structure.get('docs_paths', []) or [])} 个、examples {len(structure.get('examples_paths', []) or [])} 个、tests {len(structure.get('tests_paths', []) or [])} 个。",
        f"风险发现：企业阻塞点 {len(negative.get('enterprise_blockers', []) or [])} 个，issue 热点 {len(negative.get('issue_hotspots', []) or [])} 类。",
        f"落地发现：{enterprise.get('deployment_feasibility', '部署可行性需要验证')}。",
        "安全发现：本阶段不执行目标代码、不安装依赖，只做只读资料与结构分析。",
    ]


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _license(metadata: dict[str, Any]) -> str:
    license_data = metadata.get("license")
    if isinstance(license_data, dict):
        return license_data.get("spdx_id") or license_data.get("name") or ""
    return str(license_data or "")


def _comparison_table(comparison: dict[str, Any]) -> str:
    table = comparison.get("table", {}) if isinstance(comparison.get("table"), dict) else {}
    columns = table.get("columns", [])
    rows = table.get("rows", [])
    if not columns:
        return "P2.1 暂无横向对比数据。"
    header = "| " + " | ".join(columns) + " |"
    sep = "| " + " | ".join("---" for _ in columns) + " |"
    body = "\n".join("| " + " | ".join(str(cell) for cell in row) + " |" for row in rows)
    return "\n".join([header, sep, body])


def _file_type_table(counts: dict[str, Any]) -> str:
    if not isinstance(counts, dict) or not counts:
        return "未识别。"
    rows = ["| 类型 | 数量 |", "| --- | --- |"]
    for key, value in list(counts.items())[:12]:
        rows.append(f"| {key} | {value} |")
    return "\n".join(rows)


def _module_role_table(roles: dict[str, Any]) -> str:
    if not isinstance(roles, dict) or not roles:
        return "未识别。"
    rows = ["| 模块 | 角色 |", "| --- | --- |"]
    for path, role in list(roles.items())[:12]:
        rows.append(f"| {path} | {role} |")
    return "\n".join(rows)


def _keyword_table(items: list[dict[str, Any]]) -> str:
    if not items:
        return "无明显关键词热点。"
    rows = ["| 关键词 | 次数 |", "| --- | --- |"]
    for item in items[:10]:
        if isinstance(item, dict):
            rows.append(f"| {item.get('keyword', '')} | {item.get('count', 0)} |")
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            rows.append(f"| {item[0]} | {item[1]} |")
    return "\n".join(rows)


def _negative_evidence_table(negative: dict[str, Any], group: str | None = None) -> str:
    evidence = negative.get("negative_evidence", []) if isinstance(negative, dict) else []
    if group:
        evidence = [item for item in evidence if _evidence_group(item) == group]
    if not evidence:
        return "暂无 issue/PR 级负面证据。"
    rows = ["| 证据 | 类型 | 状态 | 严重度 | 企业影响 | 置信度 |", "| --- | --- | --- | --- | --- | --- |"]
    for item in evidence[:8]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", ""))
        url = str(item.get("url", ""))
        evidence_link = f"[{title}]({url})" if url else title
        rows.append(
            f"| {evidence_link} | {item.get('evidence_kind', item.get('category', ''))} | {item.get('risk_status', '')} | {item.get('severity', '')} | {item.get('enterprise_impact', '')} | {item.get('confidence', '')} |"
        )
    return "\n".join(rows)


def _action_plan_table(plan: dict[str, Any]) -> str:
    if not isinstance(plan, dict) or not plan:
        return "暂无结构化行动计划。"
    rows = ["| 项 | 内容 |", "| --- | --- |"]
    for key, value in plan.items():
        rows.append(f"| {key} | {_format_value(value)} |")
    return "\n".join(rows)


def _risk_summary(payload: dict[str, Any]) -> str:
    verdict = payload.get("final_verdict", {}) if isinstance(payload.get("final_verdict"), dict) else {}
    if verdict.get("blocking_risks"):
        return "；".join(str(item) for item in verdict.get("blocking_risks", [])[:3])
    return verdict.get("one_sentence", "暂无明确风险摘要。")


def _evidence_group(item: dict[str, Any]) -> str:
    status = item.get("risk_status")
    kind = item.get("evidence_kind")
    if status == "unresolved" or kind in {"security_signal", "unresolved_issue", "performance_claim_challenge"}:
        return "unresolved"
    if status in {"fixed", "mitigated"} or kind in {"merged_fix_pr", "closed_issue"}:
        return "fixed"
    if kind in {"user_complaint", "feature_enhancement"}:
        return "complaint"
    if kind == "maintenance_signal" or status == "not_a_risk":
        return "positive"
    return "unresolved"


def _module_paths(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    return [str(item.get("path", "")) if isinstance(item, dict) else str(item) for item in items if item]


def _pipeline_summary(graph_pipeline: Any) -> str:
    if isinstance(graph_pipeline, dict):
        stages = graph_pipeline.get("stages", [])
        if isinstance(stages, list) and stages:
            return " → ".join(str(stage.get("name", "")) for stage in stages if isinstance(stage, dict))
    if isinstance(graph_pipeline, list):
        return " → ".join(str(item) for item in graph_pipeline)
    return "待验证"


def _adjacent_comparables(comparison: dict[str, Any]) -> str:
    adjacent = comparison.get("adjacent_comparables", []) if isinstance(comparison, dict) else []
    if not adjacent:
        return "暂无相邻生态参考。"
    lines = []
    for item in adjacent[:8]:
        repo = item.get("repo", "")
        url = item.get("html_url", "")
        label = f"[{repo}]({url})" if url else repo
        lines.append(f"- {label}：{item.get('reason_selected', '')}")
    return "\n".join(lines)


def _action_label(action: str) -> str:
    return {
        "deep_research": "继续深研",
        "try_locally": "本地试用",
        "watch": "观察",
        "hold": "暂缓",
        "reject": "拒绝投入",
    }.get(str(action), str(action))


def _format_value(value: Any) -> str:
    if isinstance(value, list):
        return "；".join(str(item) for item in value)
    if isinstance(value, dict):
        return "；".join(f"{key}: {_format_value(val)}" for key, val in value.items())
    return str(value)


def _quality_gate_text(payload: dict[str, Any]) -> str:
    structure = payload.get("repo_structure", {}) if isinstance(payload.get("repo_structure"), dict) else {}
    context = payload.get("context", {}) if isinstance(payload.get("context"), dict) else {}
    readme_len = len(str(context.get("readme") or ""))
    signals = []
    if readme_len >= 1500:
        signals.append("README 信息较充分")
    elif readme_len:
        signals.append("README 偏短，需补充源码验证")
    else:
        signals.append("README 缺失")
    if structure.get("docs_paths"):
        signals.append("有 docs")
    if structure.get("examples_paths"):
        signals.append("有 examples")
    if structure.get("tests_paths"):
        signals.append("有 tests")
    if structure.get("deployment_files"):
        signals.append("有部署文件")
    return "；".join(signals)


def _notable_projects(ecosystem: dict[str, Any]) -> str:
    projects = ecosystem.get("notable_projects", []) if isinstance(ecosystem.get("notable_projects"), list) else []
    if not projects:
        return "  - 暂无足够同类项目样本。"
    lines = []
    for project in projects[:10]:
        repo = project.get("repo", "")
        url = project.get("html_url", "")
        stars = project.get("stars", 0)
        source = project.get("source", "")
        description = project.get("description", "")
        label = f"[{repo}]({url})" if url else repo
        lines.append(f"  - {label}：Star {stars}，来源 {source}。{description}")
    return "\n".join(lines)


def _inline_titles(items: list[dict[str, Any]]) -> str:
    return "; ".join(str(item.get("title", "")) for item in items[:5] if item.get("title"))


def _llm_stage_data(llm: dict[str, Any], stage: str) -> dict[str, Any]:
    if not isinstance(llm, dict):
        return {}
    stages = llm.get("stages", {}) if isinstance(llm.get("stages"), dict) else {}
    item = stages.get(stage, {}) if isinstance(stages.get(stage), dict) else {}
    data = item.get("data", {}) if isinstance(item.get("data"), dict) else {}
    return data


def _llm_status_text(llm: dict[str, Any]) -> str:
    if not isinstance(llm, dict) or not llm.get("enabled"):
        return "未启用或缺少 API key，使用规则资料汇总。"
    return f"已启用，成功 {llm.get('ok_count', 0)} 阶段，失败 {llm.get('failed_count', 0)} 阶段，模型 {llm.get('model', '')}。"


def _report_mode_text(llm: dict[str, Any]) -> str:
    if isinstance(llm, dict) and llm.get("enabled"):
        return "本地资料汇总 + LLM 分阶段企业尽调。"
    return "本地资料汇总版。"


def _llm_final_block(final_llm: dict[str, Any]) -> str:
    if not final_llm:
        return ""
    parts = ["\n### LLM 企业落地综合判断\n"]
    for label, key in (
        ("最终结论", "final_conclusion"),
        ("推荐动作", "recommended_action"),
        ("投入建议", "investment_suggestion"),
        ("风险提示", "risk_note"),
    ):
        if final_llm.get(key):
            parts.append(f"- {label}：{final_llm[key]}")
    chinese_conclusion = final_llm.get("最终企业落地结论")
    if isinstance(chinese_conclusion, dict):
        for key in ("核心判定", "结论等级"):
            if chinese_conclusion.get(key):
                parts.append(f"- {key}：{chinese_conclusion[key]}")
    return "\n".join(parts)


def _markdown_to_html(markdown: str) -> str:
    lines = markdown.splitlines()
    output: list[str] = []
    in_ul = False
    in_code = False
    code_lang = ""
    code_lines: list[str] = []
    in_table = False
    table_rows: list[list[str]] = []

    def close_ul() -> None:
        nonlocal in_ul
        if in_ul:
            output.append("</ul>")
            in_ul = False

    def close_table() -> None:
        nonlocal in_table, table_rows
        if not in_table:
            return
        output.append("<table>")
        for index, row in enumerate(table_rows):
            if index == 1 and all(set(cell) <= {"-"} for cell in row):
                continue
            tag = "th" if index == 0 else "td"
            cells = "".join(f"<{tag}>{_badge_risk(_inline_markdown(cell.strip()))}</{tag}>" for cell in row)
            output.append(f"<tr>{cells}</tr>")
        output.append("</table>")
        table_rows = []
        in_table = False

    for raw_line in lines:
        line = raw_line.rstrip()
        if line.startswith("```"):
            if in_code:
                css_class = "mermaid" if code_lang == "mermaid" else ""
                output.append(f'<pre class="{css_class}"><code>{html.escape(chr(10).join(code_lines))}</code></pre>')
                code_lines = []
                code_lang = ""
                in_code = False
            else:
                close_ul()
                close_table()
                in_code = True
                code_lang = line.strip("`").strip()
            continue
        if in_code:
            code_lines.append(line)
            continue
        if line.startswith("|") and line.endswith("|"):
            close_ul()
            in_table = True
            table_rows.append([cell.strip() for cell in line.strip("|").split("|")])
            continue
        close_table()
        if not line:
            close_ul()
            continue
        if line.startswith("# "):
            close_ul()
            output.append(f"<h1>{html.escape(line[2:].strip())}</h1>")
        elif line.startswith("## "):
            close_ul()
            output.append(f'<h2 class="section">{html.escape(line[3:].strip())}</h2>')
        elif line.startswith("### "):
            close_ul()
            output.append(f"<h3>{html.escape(line[4:].strip())}</h3>")
        elif line.startswith("- "):
            if not in_ul:
                output.append("<ul>")
                in_ul = True
            output.append(f"<li>{_inline_markdown(line[2:].strip())}</li>")
        else:
            close_ul()
            output.append(f"<p>{_inline_markdown(line)}</p>")
    close_ul()
    close_table()
    return "\n".join(output)


def _inline_markdown(text: str) -> str:
    escaped = html.escape(text)
    # Minimal link support for report readability; keep it conservative.
    import re

    return re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\2">\1</a>', escaped)


def _badge_risk(fragment: str) -> str:
    for level in ("high", "medium", "low"):
        fragment = fragment.replace(f">{level}<", f'><span class="risk-{level}">{level}</span><')
        if fragment == level:
            fragment = f'<span class="risk-{level}">{level}</span>'
    return fragment


def _update_research_index(output_dir: Path, payload: dict[str, Any], md_path: Path, html_path: Path, summary_path: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    index_path = output_dir / "index.json"
    html_index_path = output_dir / "index.html"
    entries: list[dict[str, Any]] = []
    if index_path.exists():
        try:
            data = load_json(index_path)
            entries = data.get("reports", []) if isinstance(data, dict) else []
        except Exception:
            entries = []
    entry = {
        "repo": payload.get("repo"),
        "generated_at": payload.get("generated_at"),
        "markdown": str(md_path),
        "html": str(html_path),
        "summary": str(summary_path),
        "investment_decision": _investment_decision(payload),
        "risk_level": ((payload.get("enterprise_fit", {}) or {}).get("final_rating", {}) or {}).get("risk_level", "unknown")
        if isinstance(payload.get("enterprise_fit"), dict)
        else "unknown",
    }
    entries = [item for item in entries if not (item.get("repo") == entry["repo"] and item.get("html") == entry["html"])]
    entries.append(entry)
    entries = sorted(entries, key=lambda item: str(item.get("generated_at") or ""), reverse=True)
    save_json({"reports": entries}, index_path)
    html_items = "\n".join(
        f'<li><a href="{html.escape(Path(item["html"]).name if Path(item["html"]).parent == output_dir else str(item["html"]))}">{html.escape(str(item.get("repo", "")))}</a> '
        f'<span>{html.escape(str(item.get("generated_at", "")))}</span> '
        f'<em>{html.escape(str(item.get("investment_decision", "")))}</em></li>'
        for item in entries[:50]
    )
    html_index_path.write_text(
        f"<!doctype html><html lang=\"zh-CN\"><meta charset=\"utf-8\"><title>Deep Research Index</title>"
        f"<body><h1>本地 Deep Research 索引</h1><ul>{html_items}</ul></body></html>",
        encoding="utf-8",
    )
