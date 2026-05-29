"""Deep research report rendering."""

from __future__ import annotations

import html
from datetime import date, datetime
from pathlib import Path
from typing import Any

from github_ai_trend_radar.research.models import ResearchOptions, repo_slug
from github_ai_trend_radar.research.report_polish import polish_report_text
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
    return polish_report_text(_render_markdown_v2(payload))


def _render_markdown_v2(payload: dict[str, Any]) -> str:
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
    archetype = payload.get("project_archetype", {}) if isinstance(payload.get("project_archetype"), dict) else {}
    return _compose_report_markdown(payload)
    markdown = f"""# 项目专项深度研究报告：{repo}

## 1. 情况摘要

- 最终结论：{verdict.get('one_sentence') or _one_line_judgement(payload)}
- 推荐动作：{_action_label(verdict.get('recommendation', 'watch'))}
- 项目类型：{_archetype_label(archetype.get('primary', 'unknown'))}
- 识别置信度：{archetype.get('confidence', 'low')}
- 类型证据：{'; '.join(str(item) for item in archetype.get('evidence', [])[:6]) or '未识别'}
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

> 技术潜力表示是否值得跟踪技术路线；开源工程成熟度表示项目自身工程完整性；企业就绪度表示是否具备企业交付所需的权限、审计、隔离和运维能力；实施可行性表示我司短期 PoC 与二开可行性。

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
- Monorepo Workspace：
{_workspace_table(structure.get('monorepo_structure', {}))}
- 核心模块：{', '.join(_module_paths(architecture.get('core_modules', []))[:12] or ['未识别'])}
- 模块角色：
{_module_role_table(architecture.get('module_roles', {}))}
- {_architecture_summary_label(archetype)}：{_architecture_summary(architecture, archetype)}
- 扩展点：{', '.join(architecture.get('extension_points', [])[:8] or ['未识别'])}
- 依赖关系：{', '.join(architecture.get('external_dependencies', [])[:10] or ['未识别'])}

### {_diagram_title(archetype)}

```mermaid
{diagrams.get('architecture', '')}
```

## 7. 核心技术与实现机制

{_implementation_mechanism(payload)}

## 8. 横向对比分析

{comparison.get('note', '') if isinstance(comparison, dict) else ''}

{_comparison_table(comparison)}

### 相邻生态参考
{_adjacent_comparables(comparison)}

## 9. 负面信息与限制

- 主要风险摘要：{_risk_summary(payload)}
- Issue 关键词统计：
{_keyword_table(negative.get('keyword_counts', []))}
- 未解决风险：
{_negative_evidence_table(negative, group='unresolved')}
- 待合并修复：
{_negative_evidence_table(negative, group='pending')}
- 已修复但需复核：
{_negative_evidence_table(negative, group='fixed')}
- 用户抱怨 / 使用限制：
{_negative_evidence_table(negative, group='complaint')}
- 正向维护信号：
{_negative_evidence_table(negative, group='positive')}
- 维护风险：{', '.join(negative.get('maintenance_risks', []) or ['未发现明确维护风险'])}
- 安全风险：{_inline_titles(negative.get('security_risks', [])) or '未发现明确安全 issue 样本'}
- 企业落地阻塞点：{_enterprise_blockers_text(payload)}

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
    return polish_report_text(markdown)


def _compose_report_markdown(payload: dict[str, Any]) -> str:
    context = payload.get("context", {}) if isinstance(payload.get("context"), dict) else {}
    metadata = context.get("metadata", {}) if isinstance(context.get("metadata"), dict) else {}
    repo = str(payload.get("repo") or context.get("repo") or "")
    enterprise = payload.get("enterprise_fit", {}) if isinstance(payload.get("enterprise_fit"), dict) else {}
    rating = enterprise.get("final_rating", {}) if isinstance(enterprise.get("final_rating"), dict) else {}
    llm = payload.get("llm_analysis", {}) if isinstance(payload.get("llm_analysis"), dict) else {}
    final_llm = _llm_stage_data(llm, "final_report_synthesis")
    verdict = payload.get("final_verdict", {}) if isinstance(payload.get("final_verdict"), dict) else {}
    structure = payload.get("repo_structure", {}) if isinstance(payload.get("repo_structure"), dict) else {}
    architecture = payload.get("architecture", {}) if isinstance(payload.get("architecture"), dict) else {}
    negative = payload.get("negative_signals", {}) if isinstance(payload.get("negative_signals"), dict) else {}
    ecosystem = payload.get("ecosystem_context", {}) if isinstance(payload.get("ecosystem_context"), dict) else {}
    comparison = payload.get("comparison", {}) if isinstance(payload.get("comparison"), dict) else {}
    diagrams = payload.get("diagrams", {}) if isinstance(payload.get("diagrams"), dict) else {}
    archetype = payload.get("project_archetype", {}) if isinstance(payload.get("project_archetype"), dict) else {}
    evidence = payload.get("evidence", {}) if isinstance(payload.get("evidence"), dict) else {}
    confidence = payload.get("analysis_confidence", {}) if isinstance(payload.get("analysis_confidence"), dict) else {}

    return f"""# 项目专项深度研究报告：{repo}

## 1. 执行摘要

- 项目一句话：{_project_one_liner(payload)}
- 核心能力：
{_bullets(_core_capabilities(payload), indent=2)}
- 主要解决的问题：{_problem_solved(payload)}
- 为什么值得关注：{_why_it_matters(payload)}
- 当前不适合直接落地的原因：
{_bullets(_why_not_direct_landing(payload), indent=2)}
- 最终结论：{verdict.get('one_sentence') or _one_line_judgement(payload)}
- 推荐动作：{_action_label(verdict.get('recommendation', 'watch'))}
- 项目类型：{_archetype_label(archetype.get('primary', 'unknown'))}
- 识别置信度：{archetype.get('confidence', 'low')}
- 类型证据：{'; '.join(str(item) for item in archetype.get('evidence', [])[:6]) or '未识别'}

| 评分项 | 结论 |
| --- | --- |
| 技术潜力 | {verdict.get('technical_potential', 'unknown')} |
| 社区信号 | {verdict.get('community_signal', 'unknown')} |
| 开源工程成熟度 | {verdict.get('open_source_engineering_maturity', verdict.get('engineering_maturity', 'unknown'))} |
| 企业就绪度 | {verdict.get('enterprise_readiness', verdict.get('enterprise_fit', 'unknown'))} |
| 实施可行性 | {verdict.get('implementation_feasibility', 'unknown')} |
| 风险等级 | {_risk_level_label(verdict.get('risk_level', 'unknown'))} |
| 推荐动作 | {_action_label(verdict.get('recommendation', 'watch'))} |

> 技术潜力表示是否值得跟踪技术路线；开源工程成熟度表示项目自身工程完整性；企业就绪度表示是否具备企业交付所需的权限、审计、隔离和运维能力；实施可行性表示我司短期 PoC 与二开可行性。

- 投入判断：{_investment_decision(payload)}
- 是否值得继续关注：建议继续关注技术路线，但投入前必须完成安全、权限、审计和模型边界验证。
- 是否建议深研/试用/暂缓：{enterprise.get('short_term_action', '建议先做资料复核。')}
- 企业落地结论：{enterprise.get('deployment_feasibility', '信息不足')}
- 报告模式：{_report_mode_text(llm)}
- LLM 分析状态：{_llm_status_text(llm)}
{_llm_final_block(final_llm)}

## 2. 关键发现

{_bullets(_key_findings(payload))}

### 证据看板

#### 正向证据

{_bullets(evidence.get('positive', []) or ['暂无明确正向证据。'])}

#### 待验证信息

{_bullets(evidence.get('uncertainty', []) or ['暂无额外待验证项。'])}

#### 信息缺口

{_bullets(_information_gaps(payload))}

## 3. 企业落地判断

- 企业落地结论：{enterprise.get('deployment_feasibility', '信息不足')}
- 私有化部署可行性：{enterprise.get('private_deployment_feasibility', enterprise.get('deployment_feasibility', '信息不足'))}
- 与我司方向的相关性：{enterprise.get('fit_with_existing_stack', _company_fit_fallback(archetype))}
### 公司方向相关性

{_action_plan_table(enterprise.get('company_direction_fit', {}))}
- 可落地场景：
{_bullets(enterprise.get('landing_scenarios', []) or enterprise.get('applicable_scenarios', []) or _landing_scenarios(payload), indent=2)}
- 不可直接落地原因：
{_bullets(enterprise.get('direct_blockers', []) or _why_not_direct_landing(payload), indent=2)}
- 推荐落地路径：{enterprise.get('medium_term_action', '仅限隔离环境安全验证型 PoC。')}
- 评分：技术价值 {rating.get('technical_value', '')}/5，企业适配 {rating.get('enterprise_fit', '')}/5，可实施性 {rating.get('implementation_feasibility', '')}/5，战略相关 {rating.get('strategic_relevance', '')}/5，风险 {_risk_level_label(rating.get('risk_level', ''))}
- 质量闸门：{_quality_gate_text(payload)}

### GUI Agent 企业安全检查矩阵

{_enterprise_security_matrix(payload)}

### 最小 PoC 路径

{_bullets(_minimum_poc_path(payload))}

### Go / No-Go 标准

{_go_no_go_table(enterprise)}

## 4. 项目能力与实现机制

### 代码结构摘要

- 仓库形态：{_repo_shape_summary(payload)}
- 主要分层：
{_bullets(_layer_summary(payload), indent=2)}
- 源码分析置信度：{confidence.get('architecture', 'medium')}，证据来自 README、package/workspace 文件、目录树和核心源码路径。
- 链路摘要：{_architecture_summary(architecture, archetype)}

{_gui_diagram_sections(diagrams, archetype)}

### 核心模块角色表

{_core_module_role_table(payload)}

{_non_gui_architecture_section(diagrams, archetype)}


### 核心技术与实现机制

{_implementation_mechanism(payload)}

## 5. 生态位置与横向对比

- 所属技术方向：{ecosystem.get('primary_domain', 'other')}
- 当前生态趋势：{ecosystem.get('market_stage', 'unclear')}
- 项目位置：{ecosystem.get('target_project_position', '')}
- 近期动态：{ecosystem.get('recent_dynamics', '')}
{comparison.get('note', '') if isinstance(comparison, dict) else ''}

{_comparison_table(comparison)}

### 相邻生态参考

{_adjacent_comparables(comparison)}

## 6. 负面信息与限制

- 主要风险摘要：{_risk_summary(payload)}
- 安全历史风险摘要：安全相关 PR/Issue 不等于当前未解决风险；已合并修复仍需在企业 PoC 中复核影响面。

### 当前未解决风险

{_negative_evidence_table(negative, group='unresolved', limit=8)}

### 待合并修复

{_negative_evidence_table(negative, group='pending', limit=8)}

### 已修复但需复核

{_negative_evidence_table(negative, group='fixed', limit=8)}

### 用户抱怨 / 使用限制

{_negative_evidence_table(negative, group='complaint', limit=8)}

### 正向维护信号

{_negative_evidence_table(negative, group='positive', limit=8)}

### 企业影响判断

{_enterprise_blockers_text(payload)}

## 7. 技术附录

<details>
<summary>展开技术附录</summary>

### 项目基本信息

- GitHub 链接：{metadata.get('html_url', f'https://github.com/{repo}')}
- Stars/Forks/Issues：{metadata.get('stargazers_count', '')} / {metadata.get('forks_count', '')} / {metadata.get('open_issues_count', '')}
- License：{_license(metadata)}
- Languages：{', '.join(structure.get('main_languages', []) or [])}
- Topics：{', '.join(metadata.get('topics', []) or [])}
- 最近更新：{metadata.get('pushed_at', '')}
- Release 情况：{len(context.get('releases', []) or [])} 个 release 样本

### 文件类型统计

{_file_type_table(structure.get('file_type_counts', {}))}

### 入口模块列表

{_bullets(structure.get('entrypoints', []) or ['未识别'])}

### Monorepo Workspace 明细

{_workspace_table(structure.get('monorepo_structure', {}))}

### 依赖关系

{_bullets(architecture.get('external_dependencies', [])[:30] or ['未识别'])}

### Issue keyword counts

{_keyword_table(negative.get('keyword_counts', []))}

### 原始 comparable 列表

{_notable_projects(ecosystem)}

### 完整 Issue / PR evidence

{_negative_evidence_table(negative, limit=50)}

### 思维导图

```mermaid
{diagrams.get('mindmap', '')}
```

</details>

### 结论与行动计划

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
    details {{ border:1px solid #ded7ca; background:#fbfaf5; padding:12px 14px; margin:18px 0; }}
    summary {{ cursor:pointer; font-weight:700; }}
    .toc {{ background:#f8f6ef; border:1px solid #ded7ca; padding:14px 18px; margin:18px 0; }}
    .meta {{ color:#667085; font-size:13px; }}
    .section {{ border-top:1px solid #e7decd; padding-top:8px; }}
    .mermaid {{ background:#fbfaf5; border:1px dashed #cfc6b4; }}
    .local-diagram {{ background:#fbfaf5; border:1px dashed #cfc6b4; padding:14px; margin:14px 0; overflow-x:auto; }}
    .local-diagram svg {{ width:100%; height:auto; min-width:920px; display:block; }}
    .diagram-source {{ margin-top:10px; }}
    .diagram-source pre {{ max-height:260px; }}
    .risk-low {{ color:#166534; font-weight:700; }}
    .risk-medium {{ color:#b45309; font-weight:700; }}
    .risk-high {{ color:#b91c1c; font-weight:700; }}
    @media (max-width: 720px) {{ article {{ padding:18px; }} h1 {{ font-size:23px; }} table {{ font-size:13px; }} }}
  </style>
</head>
<body><main><article>
<div class="meta">本地私有尽调报告 · 不发布到 GitHub Pages · 生成时间 {html.escape(str(payload.get('generated_at', '')))}</div>
<div class="toc"><strong>目录</strong><ol>
<li>执行摘要</li><li>关键发现</li><li>企业落地判断</li><li>项目能力与实现机制</li><li>生态位置与横向对比</li><li>负面信息与限制</li><li>技术附录</li>
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


def _bullets(items: list[str], *, indent: int = 0) -> str:
    prefix = " " * indent
    return "\n".join(f"{prefix}- {item}" for item in items)


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


def _negative_evidence_table(negative: dict[str, Any], group: str | None = None, *, limit: int = 8) -> str:
    evidence = negative.get("negative_evidence", []) if isinstance(negative, dict) else []
    if group:
        evidence = [item for item in evidence if _evidence_group(item) == group]
    if not evidence:
        return "暂无 issue/PR 级负面证据。"
    rows = ["| 证据 | 类型 | 状态 | 严重度 | 企业影响 | 置信度 |", "| --- | --- | --- | --- | --- | --- |"]
    for item in evidence[:limit]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", ""))
        url = str(item.get("url", ""))
        evidence_link = f"[{title}]({url})" if url else title
        rows.append(
            f"| {evidence_link} | {_evidence_type_label(item)} | {_evidence_status_label(item)} | {_severity_label(item.get('severity', ''))} | {item.get('enterprise_impact', '')} | {_confidence_label(item.get('confidence', ''))} |"
        )
    return "\n".join(rows)


def _action_plan_table(plan: dict[str, Any]) -> str:
    if not isinstance(plan, dict) or not plan:
        return "暂无结构化行动计划。"
    rows = ["| 项 | 内容 |", "| --- | --- |"]
    for key, value in plan.items():
        rows.append(f"| {key} | {_format_value(value)} |")
    return "\n".join(rows)


def _enterprise_blockers_text(payload: dict[str, Any]) -> str:
    negative = payload.get("negative_signals", {}) if isinstance(payload.get("negative_signals"), dict) else {}
    verdict = payload.get("final_verdict", {}) if isinstance(payload.get("final_verdict"), dict) else {}
    blockers = list(negative.get("enterprise_blockers", []) or [])
    if blockers:
        return "；".join(str(item) for item in blockers)
    if verdict.get("enterprise_readiness") == "low" or verdict.get("risk_level") == "high":
        return "；".join(
            [
                "高权限桌面/浏览器/文件系统操作缺少白名单控制",
                "缺少权限审计与日志脱敏",
                "多租户隔离不足",
                "安全修复历史需逐项复核",
                "模型 provider 和截图/上下文上传边界需验证",
                "高危操作缺少人工确认或审批中断机制",
            ]
        )
    return "暂无明确阻塞点，但仍需在 PoC 中复核权限、数据和部署边界。"


def _project_one_liner(payload: dict[str, Any]) -> str:
    archetype = payload.get("project_archetype", {}) if isinstance(payload.get("project_archetype"), dict) else {}
    context = payload.get("context", {}) if isinstance(payload.get("context"), dict) else {}
    description = (context.get("metadata", {}) or {}).get("description", "") if isinstance(context.get("metadata"), dict) else ""
    if archetype.get("primary") == "gui_agent":
        return "该项目是一个面向 GUI / Browser / Desktop / Terminal 操作的多模态 Agent 桌面应用与运行时项目。"
    if archetype.get("primary") == "code_knowledge_graph":
        return "该项目围绕代码库知识图谱、Repo Context 或 GraphRAG 能力，帮助 Agent 理解代码资产。"
    return description or _one_line_judgement(payload)


def _core_capabilities(payload: dict[str, Any]) -> list[str]:
    archetype = payload.get("project_archetype", {}) if isinstance(payload.get("project_archetype"), dict) else {}
    if archetype.get("primary") == "gui_agent":
        return [
            "多模态 GUI Agent / Computer Use 能力",
            "桌面、浏览器、终端、文件系统等真实环境操作",
            "Model Provider / VLM / LLM 接入",
            "Action Parser / Operator 执行链路",
            "MCP / Tool 扩展与工具调用面",
        ]
    if archetype.get("primary") == "code_knowledge_graph":
        return ["代码结构解析", "知识图谱构建", "Repo Context / GraphRAG 检索", "Coding Agent 上下文增强"]
    architecture = payload.get("architecture", {}) if isinstance(payload.get("architecture"), dict) else {}
    modules = [str(item.get("role") or item.get("path")) for item in architecture.get("core_modules", [])[:5] if isinstance(item, dict)]
    return modules or ["核心能力仍需结合 README 和源码进一步确认。"]


def _problem_solved(payload: dict[str, Any]) -> str:
    archetype = payload.get("project_archetype", {}) if isinstance(payload.get("project_archetype"), dict) else {}
    if archetype.get("primary") == "gui_agent":
        return "解决传统 LLM 难以稳定操作真实软件环境的问题，把自然语言任务、视觉感知、模型推理和真实环境操作连接起来。"
    if archetype.get("primary") == "code_knowledge_graph":
        return "解决 Coding Agent 缺少代码库结构化上下文的问题，把源码、依赖和模块关系转成可检索、可推理的知识层。"
    context = payload.get("context", {}) if isinstance(payload.get("context"), dict) else {}
    return (context.get("metadata", {}) or {}).get("description", "需要结合源码和 README 继续确认。")


def _why_it_matters(payload: dict[str, Any]) -> str:
    archetype = payload.get("project_archetype", {}) if isinstance(payload.get("project_archetype"), dict) else {}
    metadata = (payload.get("context", {}) or {}).get("metadata", {}) if isinstance(payload.get("context"), dict) else {}
    stars = metadata.get("stargazers_count", "")
    if archetype.get("primary") == "gui_agent":
        return f"GUI Agent / Computer Use 正在成为企业自动化和 Agent 工具执行的重要方向；该项目具备较高关注度（Star {stars}），适合作为技术路线和安全边界研究对象。"
    if archetype.get("primary") == "code_knowledge_graph":
        return "代码知识图谱和 Repo Context 是 Coding Agent 可靠落地的关键基础设施，值得跟踪其真实解析质量和可集成性。"
    return "项目在趋势候选中具备关注价值，但真实落地价值仍需用 PoC 验证。"


def _why_not_direct_landing(payload: dict[str, Any]) -> list[str]:
    archetype = payload.get("project_archetype", {}) if isinstance(payload.get("project_archetype"), dict) else {}
    if archetype.get("primary") == "gui_agent":
        return [
            "高权限桌面、浏览器、终端和文件系统操作需要明确白名单边界。",
            "日志脱敏、权限审计、多租户隔离和人工确认断点尚需企业级验证。",
            "安全修复历史需要逐项复核，确认是否覆盖企业 PoC 的真实威胁面。",
            "模型 provider、截图和上下文上传边界必须先验证。",
        ]
    verdict = payload.get("final_verdict", {}) if isinstance(payload.get("final_verdict"), dict) else {}
    return [str(item) for item in verdict.get("blocking_risks", [])[:5]] or ["部署、权限、数据边界和维护状态需要进一步验证。"]


def _information_gaps(payload: dict[str, Any]) -> list[str]:
    archetype = payload.get("project_archetype", {}) if isinstance(payload.get("project_archetype"), dict) else {}
    gaps = []
    if archetype.get("primary") == "gui_agent":
        gaps.extend(
            [
                "未验证是否支持完全离线或受控网络下运行。",
                "未验证是否可替换为企业批准模型并禁止截图外传。",
                "未验证 Shell / Browser / Filesystem / MCP 工具权限是否可白名单控制。",
                "未验证日志脱敏、审计留痕和高危操作人工确认是否完备。",
            ]
        )
    verdict = payload.get("final_verdict", {}) if isinstance(payload.get("final_verdict"), dict) else {}
    for item in verdict.get("blocking_risks", []) or []:
        text = str(item)
        if text not in gaps:
            gaps.append(text)
    return gaps or ["暂无额外信息缺口。"]


def _company_fit_fallback(archetype: dict[str, Any]) -> str:
    if archetype.get("primary") == "gui_agent":
        return "与 AI Agent、MCP 工具生态、工作流自动化方向存在明确相关性；与 Coding Agent 上下文增强和业务理解编译层为间接相关；不适合作为知识库/RAG 底座优先评估，更适合作为 GUI Agent / Computer Use 自动化能力储备。"
    return "需要结合公司画像进一步判断。"


def _landing_scenarios(payload: dict[str, Any]) -> list[str]:
    archetype = payload.get("project_archetype", {}) if isinstance(payload.get("project_archetype"), dict) else {}
    if archetype.get("primary") == "gui_agent":
        return ["非敏感桌面任务自动化", "浏览器操作验证", "GUI Agent 执行链路评估", "MCP 工具权限模型 PoC", "受控环境下的人机协作自动化"]
    return ["非生产环境 PoC", "技术路线验证", "与现有工具链的集成可行性评估"]


def _enterprise_security_matrix(payload: dict[str, Any]) -> str:
    archetype = payload.get("project_archetype", {}) if isinstance(payload.get("project_archetype"), dict) else {}
    if archetype.get("primary") != "gui_agent":
        return "该项目不是 GUI Agent 类型，暂不生成 GUI Agent 专项安全矩阵。"
    rows = [
        ("模型 Provider 替换", "需验证", "必须可替换为私有模型或企业批准模型", "配置企业模型，禁止未经批准的外部 API。"),
        ("截图上传边界", "需验证", "截图、OCR、上下文不得外传敏感数据", "抓包与日志检查，确认敏感截图不出受控环境。"),
        ("Shell 权限", "高风险", "默认禁用或白名单控制", "仅开放只读命令，验证高危命令会被拦截。"),
        ("Browser 权限", "需验证", "限制域名、Cookie、下载和表单提交", "用测试账号验证域名白名单和敏感操作拦截。"),
        ("Filesystem 权限", "高风险", "限制目录和文件类型", "只挂载临时目录，验证越权读写失败。"),
        ("MCP 工具权限", "需验证", "工具白名单、参数审计和最小权限", "逐项注册工具，验证危险工具默认不可用。"),
        ("日志脱敏", "需验证", "日志不得包含密钥、截图、客户数据", "注入假 token，检查日志和缓存是否脱敏。"),
        ("人工确认断点", "需补强", "高危操作必须人工确认", "设置删除、提交、支付、外发等操作的审批断点。"),
        ("审计留痕", "需补强", "任务、工具、参数、结果可追溯", "复盘一次任务，确认完整操作链可审计。"),
        ("多租户隔离", "不足", "租户数据、凭据、缓存隔离", "模拟两个用户任务，验证数据和状态不串扰。"),
    ]
    lines = ["| 检查项 | 当前状态 | 企业要求 | PoC 验证方式 |", "| --- | --- | --- | --- |"]
    lines.extend(f"| {a} | {b} | {c} | {d} |" for a, b, c, d in rows)
    return "\n".join(lines)


def _minimum_poc_path(payload: dict[str, Any]) -> list[str]:
    archetype = payload.get("project_archetype", {}) if isinstance(payload.get("project_archetype"), dict) else {}
    if archetype.get("primary") == "gui_agent":
        return [
            "选择一个非敏感桌面任务和测试账号，不接入真实客户数据。",
            "在受控网络中运行，优先使用私有模型或企业批准模型。",
            "配置工具权限白名单，默认禁用 Shell、Filesystem 等高危能力。",
            "验证日志脱敏、截图边界、审计留痕和缓存清理。",
            "为高危操作设置人工确认断点。",
            "重复运行同一任务，验证稳定性、可复现性和失败恢复。",
        ]
    return ["选择非生产样例数据。", "验证部署、权限、日志和集成边界。", "形成 Go / No-Go 复核结论。"]


def _go_no_go_table(enterprise: dict[str, Any]) -> str:
    plan = enterprise.get("enterprise_action_plan", {}) if isinstance(enterprise.get("enterprise_action_plan"), dict) else {}
    criteria = plan.get("go_no_go_criteria") if isinstance(plan, dict) else None
    go = ["支持受控或本地化部署", "工具权限可白名单控制", "日志脱敏和审计留痕可验证", "高危操作可人工确认"]
    no_go = ["需要上传内部截图或代码到第三方", "无法限制 Shell / Browser / Filesystem 权限", "无审计留痕", "任务执行无法稳定复现"]
    if isinstance(criteria, list) and criteria:
        go = [str(item) for item in criteria if str(item).lower().startswith("go")]
        no_go = [str(item) for item in criteria if str(item).lower().startswith("no")]
    return "\n".join(["| Go 条件 | No-Go 条件 |", "| --- | --- |", f"| {_format_value(go)} | {_format_value(no_go)} |"])


def _repo_shape_summary(payload: dict[str, Any]) -> str:
    archetype = payload.get("project_archetype", {}) if isinstance(payload.get("project_archetype"), dict) else {}
    structure = payload.get("repo_structure", {}) if isinstance(payload.get("repo_structure"), dict) else {}
    languages = ", ".join(structure.get("main_languages", []) or ["未识别"])
    if archetype.get("primary") == "gui_agent":
        return f"{languages} monorepo / Electron desktop app / Agent runtime / GUI Agent SDK。"
    if structure.get("monorepo_structure"):
        return f"{languages} monorepo。"
    return f"{languages} 仓库。"


def _layer_summary(payload: dict[str, Any]) -> list[str]:
    architecture = payload.get("architecture", {}) if isinstance(payload.get("architecture"), dict) else {}
    modules = architecture.get("core_modules", []) if isinstance(architecture.get("core_modules"), list) else []
    lines = []
    preferred = ("apps/ui-tars", "multimodal/agent-tars", "multimodal/gui-agent", "infra/pdk", "multimodal/tarko")
    for prefix in preferred:
        match = next((item for item in modules if isinstance(item, dict) and str(item.get("path", "")).startswith(prefix)), None)
        if match:
            lines.append(f"{match.get('path')}：{match.get('role', '职责待验证')}")
    if lines:
        return lines
    return [f"{item.get('path')}：{item.get('role', '职责待验证')}" for item in modules[:6] if isinstance(item, dict)] or ["核心分层仍需进一步源码复核。"]


def _core_module_role_table(payload: dict[str, Any]) -> str:
    architecture = payload.get("architecture", {}) if isinstance(payload.get("architecture"), dict) else {}
    modules = architecture.get("core_modules", []) if isinstance(architecture.get("core_modules"), list) else []
    if not modules:
        return "未识别核心模块；原因可能是仓库文件列表不足、未启用 clone，或源码入口需要人工确认。"
    rows = ["| 模块 | 职责 | 关键路径/证据 | 企业评估关注点 |", "| --- | --- | --- | --- |"]
    for item in modules[:12]:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", ""))
        role = str(item.get("role", "职责待验证"))
        evidence = _format_value(item.get("evidence") or item.get("key_files") or item.get("key_functions") or path)
        concern = _enterprise_concern_for_module(path, role)
        rows.append(f"| {path} | {role} | {evidence} | {concern} |")
    return "\n".join(rows)


def _gui_diagram_sections(diagrams: dict[str, Any], archetype: dict[str, Any]) -> str:
    if archetype.get("primary") != "gui_agent":
        return ""
    execution = diagrams.get("gui_execution_flow") or diagrams.get("architecture") or ""
    security = diagrams.get("gui_security_boundary") or ""
    module_map = diagrams.get("gui_module_map") or ""
    parts = [
        "### GUI Agent 任务执行链路图",
        "",
        "这张图只表达一次任务从用户目标到真实环境操作再回到反馈循环的主路径。",
        "",
        "```mermaid",
        str(execution),
        "```",
    ]
    if security:
        parts.extend(
            [
                "",
                "### GUI Agent 企业安全边界图",
                "",
                "这张图突出企业 PoC 必须验证的模型、工具、执行和日志边界。",
                "",
                "```mermaid",
                str(security),
                "```",
            ]
        )
    if module_map:
        parts.extend(
            [
                "",
                "### Monorepo 模块关系图",
                "",
                "这张图用于和后面的核心模块角色表配合阅读，帮助快速定位模块职责。",
                "",
                "```mermaid",
                str(module_map),
                "```",
            ]
        )
    return "\n".join(parts)


def _non_gui_architecture_section(diagrams: dict[str, Any], archetype: dict[str, Any]) -> str:
    if archetype.get("primary") == "gui_agent":
        return ""
    return "\n".join(
        [
            f"### {_diagram_title(archetype)}",
            "",
            "```mermaid",
            str(diagrams.get("architecture", "")),
            "```",
        ]
    )


def _enterprise_concern_for_module(path: str, role: str) -> str:
    text = f"{path} {role}".lower()
    if any(term in text for term in ("ui-tars", "electron", "renderer", "preload", "ipc", "store")):
        return "本地数据、日志、权限边界、桌面环境访问。"
    if any(term in text for term in ("agent-tars", "runtime", "planner", "environment")):
        return "任务调度、工具执行边界、模型 provider 接入。"
    if any(term in text for term in ("action-parser", "gui-agent")):
        return "动作误判、注入风险、操作可审计性。"
    if "operator" in text:
        return "高危操作、权限白名单、人工确认断点。"
    if any(term in text for term in ("mcp", "pdk", "tool")):
        return "MCP 工具权限、审计和隔离。"
    if "model" in text or "provider" in text:
        return "企业批准模型替换、上下文上传边界。"
    return "需结合 PoC 复核权限、维护和集成边界。"


def _implementation_mechanism(payload: dict[str, Any]) -> str:
    archetype = payload.get("project_archetype", {}) if isinstance(payload.get("project_archetype"), dict) else {}
    if archetype.get("primary") == "gui_agent":
        return _gui_agent_mechanism(payload)
    metadata = (payload.get("context", {}) or {}).get("metadata", {}) if isinstance(payload.get("context"), dict) else {}
    structure = payload.get("repo_structure", {}) if isinstance(payload.get("repo_structure"), dict) else {}
    return "\n".join(
        [
            f"- 解决的问题：{metadata.get('description', '需要结合 README 进一步判断。')}",
            f"- 技术路线：{', '.join(structure.get('main_languages', []) or ['未识别'])}",
            "- 局限：不执行代码、不安装依赖，本报告只做只读分析。",
        ]
    )


def _gui_agent_mechanism(payload: dict[str, Any]) -> str:
    architecture = payload.get("architecture", {}) if isinstance(payload.get("architecture"), dict) else {}
    modules = architecture.get("core_modules", []) if isinstance(architecture.get("core_modules"), list) else []
    role_map = {str(item.get("path")): str(item.get("role", "")) for item in modules if isinstance(item, dict)}

    def pick(*terms: str) -> str:
        matches = [path for path, role in role_map.items() if any(term in f"{path} {role}".lower() for term in terms)]
        return "、".join(matches[:5]) if matches else "未在当前扫描中确认，需源码复核"

    return "\n".join(
        [
            "1. Electron Desktop Shell",
            f"   - 相关路径：{pick('apps/ui-tars', 'electron', 'renderer', 'preload', 'ipc', 'window', 'store')}",
            "   - 作用：承载桌面端入口、main/preload/renderer/IPC、窗口与本地状态，是 GUI Agent 与用户桌面环境交互的外壳。",
            "2. Agent Runtime",
            f"   - 相关路径：{pick('agent-tars', 'tarko', 'runtime', 'planner', 'environment')}",
            "   - 作用：组织任务规划、环境抽象、CLI/server/shared/utils，是从用户目标到工具执行的调度层。",
            "3. GUI Agent SDK / Operator",
            f"   - 相关路径：{pick('gui-agent', 'action-parser', 'operator')}",
            "   - 作用：解析模型输出动作，并连接 ADB、Browser、NutJS、AIO 等 operator，把模型决策转换为桌面/浏览器操作。",
            "4. Model Provider / LLM Client",
            f"   - 相关路径：{pick('model-provider', 'llm-client', 'provider')}",
            "   - 作用：封装模型 provider 与 VLM/LLM 调用；企业落地必须验证是否能替换为企业批准模型，并限制截图/上下文上传边界。",
            "5. MCP / Tools",
            f"   - 相关路径：{pick('mcp', 'tool', 'pdk', 'server')}",
            "   - 作用：提供工具扩展与协议集成面；核心风险是工具权限白名单、执行审计和高危操作审批。",
            "6. State / Logs / Store",
            f"   - 相关路径：{pick('store', 'snapshot', 'log', 'state')}",
            "   - 作用：保存任务状态、反馈和日志；企业 PoC 必须验证日志脱敏、审计留痕和敏感信息不落盘。",
        ]
    )


def _risk_summary(payload: dict[str, Any]) -> str:
    verdict = payload.get("final_verdict", {}) if isinstance(payload.get("final_verdict"), dict) else {}
    if verdict.get("blocking_risks"):
        return "；".join(str(item) for item in verdict.get("blocking_risks", [])[:3])
    return verdict.get("one_sentence", "暂无明确风险摘要。")


def _evidence_group(item: dict[str, Any]) -> str:
    status = item.get("risk_status")
    kind = item.get("evidence_kind")
    if status == "pending_fix" or kind == "pending_fix_pr":
        return "pending"
    if status == "unresolved" or kind in {"security_signal", "unresolved_issue", "performance_claim_challenge"}:
        return "unresolved"
    if status in {"fixed", "mitigated", "fixed_but_requires_verification"} or kind in {"merged_fix_pr", "closed_issue", "merged_security_fix", "security_signal_fixed"}:
        return "fixed"
    if kind in {"user_complaint", "feature_enhancement"}:
        return "complaint"
    if kind == "maintenance_signal" or status == "not_a_risk":
        return "positive"
    return "unresolved"


def _evidence_type_label(item: dict[str, Any]) -> str:
    item_type = item.get("item_type")
    if item_type:
        return str(item_type)
    return {
        "merged_security_fix": "Security PR",
        "pending_fix_pr": "Security PR",
        "security_signal": "Issue",
        "feature_enhancement": "Feature Request",
        "maintenance_signal": "Maintenance PR",
        "user_complaint": "Issue",
        "unresolved_issue": "Issue",
    }.get(str(item.get("evidence_kind", "")), str(item.get("evidence_kind") or item.get("category") or "Issue"))


def _risk_status_label(status: Any) -> str:
    return {
        "unresolved": "未解决",
        "pending_fix": "待合并修复",
        "fixed_but_requires_verification": "已修复但需复核",
        "fixed": "已修复",
        "mitigated": "已缓解",
        "not_a_risk": "非风险",
        "unclear": "待确认",
    }.get(str(status), str(status or "待确认"))


def _evidence_status_label(item: dict[str, Any]) -> str:
    if item.get("state_source") == "title_heuristic":
        return "需 API 复核"
    return _risk_status_label(item.get("risk_status", ""))


def _risk_level_label(status: Any) -> str:
    return {"high": "高", "medium": "中", "low": "低"}.get(str(status), str(status or "待确认"))


def _severity_label(severity: Any) -> str:
    return {"high": "高", "medium": "中", "low": "低"}.get(str(severity), str(severity or ""))


def _confidence_label(confidence: Any) -> str:
    return {"high": "高", "medium": "中", "low": "低"}.get(str(confidence), str(confidence or ""))


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


def _architecture_summary(architecture: dict[str, Any], archetype: dict[str, Any]) -> str:
    if archetype.get("primary") == "gui_agent":
        chain = architecture.get("gui_agent_chain", {}) if isinstance(architecture.get("gui_agent_chain"), dict) else {}
        stages = chain.get("stages", []) if isinstance(chain.get("stages"), list) else []
        if stages:
            return "主流程已识别为用户任务、Agent Runtime、模型层、动作解析、Operator 执行和反馈日志闭环；详细路径见下方三张图。"
        return "GUI Agent 主流程仍需源码复核；详细结构见下方图表。"
    return _pipeline_summary(architecture.get("graph_pipeline", {}))


def _architecture_summary_label(archetype: dict[str, Any]) -> str:
    return "GUI Agent 执行链路" if archetype.get("primary") == "gui_agent" else "Graph Pipeline"


def _diagram_title(archetype: dict[str, Any]) -> str:
    return "GUI Agent 执行链路图" if archetype.get("primary") == "gui_agent" else "Graph Pipeline 架构图"


def _archetype_label(value: str) -> str:
    return {
        "gui_agent": "GUI Agent / Computer Use / Desktop Automation",
        "code_knowledge_graph": "Code Knowledge Graph / Repo Context",
        "mcp_tooling": "MCP Tooling",
        "agent_runtime": "Agent Runtime",
        "llm_infra": "LLM Infra",
        "rag_knowledge": "RAG / Knowledge Base",
        "unknown": "未识别",
    }.get(str(value), str(value))


def _workspace_table(monorepo: Any) -> str:
    if not isinstance(monorepo, dict) or not monorepo:
        return "未识别 monorepo workspace。"
    lines = ["| Workspace | 角色 | 证据 |", "| --- | --- | --- |"]
    for path, info in list(monorepo.items())[:18]:
        if not isinstance(info, dict):
            continue
        evidence = "；".join(str(item) for item in info.get("evidence", []) if item)
        lines.append(f"| {path} | {info.get('role', '')} | {evidence} |")
    return "\n".join(lines)


def _adjacent_comparables(comparison: dict[str, Any]) -> str:
    adjacent = comparison.get("adjacent_comparables", []) if isinstance(comparison, dict) else []
    adjacent = [item for item in adjacent if _is_report_adjacent_comparable(item)]
    if not adjacent:
        return "暂无相邻生态参考。"
    lines = []
    for item in adjacent[:8]:
        repo = item.get("repo", "")
        url = item.get("html_url", "")
        label = f"[{repo}]({url})" if url else repo
        lines.append(f"- {label}：{item.get('reason_selected', '')}")
    return "\n".join(lines)


def _is_report_adjacent_comparable(item: dict[str, Any]) -> bool:
    text = " ".join(
        [
            str(item.get("repo", "")),
            str(item.get("reason_selected", "")),
            str(item.get("positioning", "")),
            str(item.get("capabilities", "")),
            " ".join(str(value) for value in item.get("overlap_dimensions", []) or []),
        ]
    ).lower()
    weak_terms = ("skill collection", "video", "html rendering", "trading", "memory", "context db", "generic agent", "generic")
    if any(term in text for term in weak_terms):
        return False
    strong_terms = ("gui agent", "browser agent", "computer use", "computer-use", "browser automation", "desktop automation", "mcp", "devtools", "tool server")
    return any(term in text for term in strong_terms)


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
    list_depth = 0
    in_code = False
    code_lang = ""
    code_lines: list[str] = []
    in_table = False
    table_rows: list[list[str]] = []

    def close_ul() -> None:
        nonlocal list_depth
        while list_depth:
            output.append("</ul>")
            list_depth -= 1

    def set_list_depth(target_depth: int) -> None:
        nonlocal list_depth
        while list_depth < target_depth:
            output.append("<ul>")
            list_depth += 1
        while list_depth > target_depth:
            output.append("</ul>")
            list_depth -= 1

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
                raw_code = chr(10).join(code_lines)
                code_text = html.escape(raw_code)
                if code_lang == "mermaid":
                    output.append(_render_mermaid_local(raw_code))
                else:
                    output.append(f'<pre class="{css_class}"><code>{code_text}</code></pre>')
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
        if line.startswith("<details") or line.startswith("</details") or line.startswith("<summary") or line.startswith("</summary"):
            close_ul()
            output.append(line)
            continue
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
        elif line.startswith("#### "):
            close_ul()
            output.append(f"<h4>{html.escape(line[5:].strip())}</h4>")
        elif line.lstrip().startswith("- "):
            indent = len(line) - len(line.lstrip(" "))
            depth = max(1, indent // 2 + 1)
            set_list_depth(depth)
            output.append(f"<li>{_inline_markdown(line.lstrip()[2:].strip())}</li>")
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


def _render_mermaid_local(code: str) -> str:
    parsed = _parse_mermaid_flowchart(code)
    source = f"<details class=\"diagram-source\"><summary>查看图表数据模型</summary><pre><code>{html.escape(_diagram_model_text(parsed))}</code></pre></details>"
    if not parsed["nodes"] and not parsed["edges"]:
        return f'<div class="local-diagram"><pre><code>{html.escape(code)}</code></pre></div>'
    if _is_gui_execution_flow(parsed):
        svg = _render_gui_execution_svg(parsed)
    elif _is_gui_security_boundary(parsed):
        svg = _render_gui_security_boundary_svg(parsed)
    elif _is_monorepo_layer_map(parsed):
        svg = _render_monorepo_layer_map_svg(parsed)
    else:
        svg = _render_flowchart_svg(parsed)
    return (
        '<div class="local-diagram">'
        f'{svg}'
        f'{source}'
        '</div>'
    )


def _is_gui_execution_flow(parsed: dict[str, Any]) -> bool:
    labels = {str(section.get("label", "")) for section in parsed.get("sections", []) if isinstance(section, dict)}
    node_text = " ".join(str(label) for label in parsed.get("nodes", {}).values()).lower()
    return {"Agent Runtime", "Model Layer", "Action Layer", "受控执行环境"}.issubset(labels) and "operator / executor" in node_text


def _is_gui_security_boundary(parsed: dict[str, Any]) -> bool:
    labels = {str(section.get("label", "")) for section in parsed.get("sections", []) if isinstance(section, dict)}
    return {"输入与上下文", "模型与数据边界", "工具权限边界", "高危执行面", "审计与脱敏"}.issubset(labels)


def _is_monorepo_layer_map(parsed: dict[str, Any]) -> bool:
    labels = {str(section.get("label", "")) for section in parsed.get("sections", []) if isinstance(section, dict)}
    return {"应用层", "Agent Runtime 层", "GUI Agent SDK 层", "扩展与工具层"}.issubset(labels)


def _render_gui_execution_svg(parsed: dict[str, Any]) -> str:
    nodes = parsed.get("nodes", {}) if isinstance(parsed.get("nodes"), dict) else {}

    def label(node_id: str, fallback: str) -> str:
        return _short_svg_label(str(nodes.get(node_id) or fallback))

    cards = [
        ("User", label("User", "用户任务")),
        ("App", label("App", "Desktop App / CLI / Web UI")),
        ("Planner", label("Planner", "Agent Runtime / Planner")),
        ("VLM", label("VLM", "Model Provider / VLM / LLM")),
        ("Parser", label("Parser", "Action Parser")),
        ("Operator", label("Operator", "Operator / Executor")),
        ("Environment", "Browser / Desktop\nTerminal / Filesystem"),
    ]
    node_w = 148
    node_h = 72
    gap_x = 28
    margin_x = 34
    top_y = 104
    width = margin_x * 2 + len(cards) * node_w + (len(cards) - 1) * gap_x
    height = 360
    pos: dict[str, tuple[float, float]] = {}
    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="GUI Agent execution flow">',
        '<title>GUI Agent 任务执行链路</title>',
        '<desc>固定横向主流程图，展示用户任务进入桌面应用、Agent Runtime、模型、动作解析、执行器和受控执行环境的路径，底部反馈带表示日志和结果回流。</desc>',
        '<defs><marker id="arrow-gui" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L0,6 L9,3 z" fill="#64748b"/></marker></defs>',
        '<rect x="0" y="0" width="100%" height="100%" fill="#fbfaf5"/>',
        '<text x="34" y="34" fill="#0f172a" font-size="18" font-weight="700">GUI Agent 任务执行链路</text>',
        '<text x="34" y="58" fill="#64748b" font-size="12">实线：任务执行主流程 · 虚线带：反馈/日志回路 · 橙色角标：企业需验证</text>',
    ]
    for index, (node_id, node_label) in enumerate(cards):
        x = margin_x + index * (node_w + gap_x)
        pos[node_id] = (x + node_w / 2, top_y + node_h / 2)
        parts.extend(_svg_node(x, top_y, node_w, node_label, height=node_h))
        if node_id in {"VLM", "Operator", "Environment"}:
            parts.append(_svg_badge(x + node_w - 56, top_y - 11, "需验证", fill="#fff7ed", stroke="#fb923c", color="#9a3412"))

    def straight(src: str, dst: str) -> None:
        if src not in pos or dst not in pos:
            return
        x1, y1 = pos[src]
        x2, y2 = pos[dst]
        sx = x1 + node_w / 2 + 2
        ex = x2 - node_w / 2
        parts.append(f'<line x1="{sx:.1f}" y1="{y1:.1f}" x2="{ex:.1f}" y2="{y2:.1f}" stroke="#64748b" stroke-width="1.8" marker-end="url(#arrow-gui)"/>')

    for src, dst in [("User", "App"), ("App", "Planner"), ("Planner", "VLM"), ("VLM", "Parser"), ("Parser", "Operator"), ("Operator", "Environment")]:
        straight(src, dst)
    # Feedback is a separate band below the main cards, not a crossing edge.
    feedback_y = top_y + node_h + 70
    start = pos["Operator"][0]
    end = pos["Planner"][0]
    parts.append(f'<rect x="{end - 78:.1f}" y="{feedback_y - 24}" width="{start - end + 156:.1f}" height="50" rx="16" fill="#fff7ed" stroke="#f3c177" stroke-dasharray="6 5"/>')
    parts.append(f'<text x="{end - 58:.1f}" y="{feedback_y + 4}" fill="#9a3412" font-size="13">Feedback / Logs / Store：执行结果回流 Planner，用于下一轮判断</text>')
    parts.append("</svg>")
    return "".join(parts)


def _parse_mermaid_flowchart(code: str) -> dict[str, Any]:
    import re

    nodes: dict[str, str] = {}
    sections: list[dict[str, Any]] = []
    section_stack: list[dict[str, Any]] = []
    edges: list[tuple[str, str]] = []
    section_node_ids: set[str] = set()
    node_pattern = re.compile(r'([A-Za-z][\w]*)\s*\[\s*"([^"]+)"\s*\]')
    subgraph_pattern = re.compile(r'^\s*subgraph\s+([A-Za-z][\w]*)\s*\[\s*"([^"]+)"\s*\]')
    edge_pattern = re.compile(r'([A-Za-z][\w]*)\s*(?:-->|-.+?->)\s*([A-Za-z][\w]*)')

    for line in code.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("flowchart"):
            continue
        subgraph_match = subgraph_pattern.match(line)
        if subgraph_match:
            section = {"id": subgraph_match.group(1), "label": subgraph_match.group(2), "nodes": []}
            sections.append(section)
            section_stack.append(section)
            continue
        if stripped == "end":
            if section_stack:
                section_stack.pop()
            continue
        for node_match in node_pattern.finditer(line):
            node_id, label = node_match.group(1), node_match.group(2)
            nodes[node_id] = label
            if section_stack:
                if node_id not in section_stack[-1]["nodes"]:
                    section_stack[-1]["nodes"].append(node_id)
                section_node_ids.add(node_id)
        for src, dst in edge_pattern.findall(line):
            edges.append((src, dst))
            nodes.setdefault(src, src)
            nodes.setdefault(dst, dst)
    section_ids = {section["id"]: section for section in sections}
    return {"nodes": nodes, "sections": sections, "section_ids": section_ids, "section_node_ids": section_node_ids, "edges": edges}


def _diagram_model_text(parsed: dict[str, Any]) -> str:
    import json

    model = {
        "sections": [
            {
                "id": section.get("id"),
                "label": section.get("label"),
                "nodes": [
                    {"id": node_id, "label": parsed.get("nodes", {}).get(node_id, node_id)}
                    for node_id in section.get("nodes", [])
                ],
            }
            for section in parsed.get("sections", [])
        ],
        "standalone_nodes": [
            {"id": node_id, "label": label}
            for node_id, label in parsed.get("nodes", {}).items()
            if node_id not in parsed.get("section_node_ids", set()) and node_id not in parsed.get("section_ids", {})
        ],
        "raw_edges_for_debug": [
            {"from": src, "to": dst}
            for src, dst in parsed.get("edges", [])
        ],
        "note": "正式报告图使用固定 SVG 模板渲染；这里是图表数据模型，不是正式布局来源。",
    }
    return json.dumps(model, ensure_ascii=False, indent=2)


def _render_flowchart_svg(parsed: dict[str, Any]) -> str:
    sections = list(parsed.get("sections", []) or [])
    nodes: dict[str, str] = parsed.get("nodes", {}) if isinstance(parsed.get("nodes"), dict) else {}
    edges: list[tuple[str, str]] = parsed.get("edges", []) if isinstance(parsed.get("edges"), list) else []
    section_ids: dict[str, dict[str, Any]] = parsed.get("section_ids", {}) if isinstance(parsed.get("section_ids"), dict) else {}
    section_node_ids: set[str] = parsed.get("section_node_ids", set()) if isinstance(parsed.get("section_node_ids"), set) else set()
    ungrouped = [node_id for node_id in nodes if node_id not in section_node_ids and node_id not in section_ids]
    columns: list[dict[str, Any]] = []
    if ungrouped:
        columns.append({"id": "_main", "label": "主流程", "nodes": ungrouped})
    columns.extend(sections)
    if not columns:
        columns = [{"id": "_main", "label": "流程", "nodes": list(nodes.keys())}]

    node_w = 190
    row_h = 86
    gap_x = 42
    margin_x = 28
    margin_y = 44
    header_h = 34
    max_rows = max((len(col.get("nodes", []) or []) for col in columns), default=1)
    width = max(760, margin_x * 2 + len(columns) * node_w + (len(columns) - 1) * gap_x)
    height = margin_y * 2 + header_h + max_rows * row_h + 32
    positions: dict[str, tuple[float, float]] = {}
    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="flowchart">',
        '<title>流程图</title>',
        '<desc>本地生成的固定 SVG 流程图，用于离线展示 Mermaid 草稿中的主要节点和关系。</desc>',
        '<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L0,6 L9,3 z" fill="#64748b"/></marker></defs>',
        '<rect x="0" y="0" width="100%" height="100%" fill="#fbfaf5"/>',
    ]

    for col_index, column in enumerate(columns):
        x = margin_x + col_index * (node_w + gap_x)
        col_nodes = [node_id for node_id in column.get("nodes", []) if node_id in nodes]
        group_h = header_h + max(1, len(col_nodes)) * row_h
        parts.append(f'<rect x="{x - 10}" y="{margin_y - 22}" width="{node_w + 20}" height="{group_h}" rx="10" fill="#fffdf8" stroke="#ddd5c7"/>')
        parts.append(f'<text x="{x}" y="{margin_y}" fill="#334155" font-size="14" font-weight="700">{html.escape(str(column.get("label", "")))}</text>')
        for row_index, node_id in enumerate(col_nodes):
            y = margin_y + header_h + row_index * row_h
            positions[node_id] = (x + node_w / 2, y + 26)
            parts.extend(_svg_node(x, y, node_w, nodes[node_id]))
        if column.get("id"):
            positions[str(column["id"])] = (x + node_w / 2, margin_y + header_h + max(1, len(col_nodes)) * row_h / 2)

    for src, dst in edges:
        if src not in positions or dst not in positions:
            continue
        x1, y1 = positions[src]
        x2, y2 = positions[dst]
        if abs(x1 - x2) < 5 and abs(y1 - y2) < 5:
            continue
        start_x = x1 + (node_w / 2 if x2 >= x1 else -node_w / 2)
        end_x = x2 - (node_w / 2 if x2 >= x1 else -node_w / 2)
        mid_x = (start_x + end_x) / 2
        parts.append(
            f'<path d="M {start_x:.1f} {y1:.1f} C {mid_x:.1f} {y1:.1f}, {mid_x:.1f} {y2:.1f}, {end_x:.1f} {y2:.1f}" '
            'fill="none" stroke="#64748b" stroke-width="1.5" marker-end="url(#arrow)"/>'
        )
    parts.append("</svg>")
    return "".join(parts)


def _render_gui_security_boundary_svg(parsed: dict[str, Any]) -> str:
    width = 980
    panel_w = 850
    panel_h = 88
    margin_x = 52
    y0 = 72
    gap = 22
    controls = [
        ("数据边界", ["Screenshot / OCR / UI State", "User Prompt / Task Context"], "敏感数据不外传、日志脱敏", "需验证", "#fff7ed", "#fb923c"),
        ("模型边界", ["Model Provider", "Provider Isolation"], "企业批准模型、本地化或受控网络", "需验证", "#fff7ed", "#fb923c"),
        ("工具边界", ["MCP / Tools", "Tool Permission Boundary", "Human Approval"], "白名单、参数审计、高危操作确认", "需补强", "#eff6ff", "#64748b"),
        ("执行边界", ["Shell", "Browser", "Filesystem", "Desktop"], "沙箱、目录限制、域名白名单、命令白名单", "高风险", "#fef2f2", "#ef4444"),
        ("审计边界", ["Audit Logs", "Redaction", "Store"], "审计留痕、脱敏、可追溯", "需验证", "#fff7ed", "#fb923c"),
    ]
    height = y0 + len(controls) * panel_h + (len(controls) - 1) * gap + 54
    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="GUI Agent security boundary">',
        '<title>GUI Agent 企业安全边界</title>',
        '<desc>五层安全控制面图，展示数据边界、模型边界、工具边界、执行边界和审计边界，以及每层企业落地前必须验证的要求。</desc>',
        '<defs><marker id="arrow-sec" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L0,6 L9,3 z" fill="#94a3b8"/></marker></defs>',
        '<rect x="0" y="0" width="100%" height="100%" fill="#fbfaf5"/>',
        '<text x="52" y="34" fill="#0f172a" font-size="18" font-weight="700">GUI Agent 企业安全边界</text>',
        '<text x="52" y="56" fill="#64748b" font-size="12">每一层都是企业落地前必须验收的控制面；箭头只表示顺序，不表示调用依赖。</text>',
    ]
    centers = []
    for index, (title, items, requirement, badge, fill, stroke) in enumerate(controls):
        y = y0 + index * (panel_h + gap)
        centers.append((margin_x + panel_w / 2, y + panel_h))
        parts.append(f'<rect x="{margin_x}" y="{y}" width="{panel_w}" height="{panel_h}" rx="12" fill="{fill}" stroke="{stroke}"/>')
        parts.append(f'<text x="{margin_x + 18}" y="{y + 28}" fill="#0f172a" font-size="15" font-weight="700">{title}</text>')
        parts.append(_svg_badge(margin_x + panel_w - 74, y + 14, badge, fill="#fffdf8", stroke=stroke, color="#0f172a"))
        item_text = " · ".join(items)
        parts.append(f'<text x="{margin_x + 18}" y="{y + 53}" fill="#334155" font-size="13">{html.escape(item_text)}</text>')
        parts.append(f'<text x="{margin_x + 18}" y="{y + 74}" fill="#64748b" font-size="12">企业要求：{html.escape(requirement)}</text>')
    for index in range(len(centers) - 1):
        x, y = centers[index]
        next_y = y0 + (index + 1) * (panel_h + gap)
        parts.append(f'<line x1="{x}" y1="{y + 4}" x2="{x}" y2="{next_y - 8}" stroke="#94a3b8" stroke-width="1.5" marker-end="url(#arrow-sec)"/>')
    parts.append("</svg>")
    return "".join(parts)


def _render_monorepo_layer_map_svg(parsed: dict[str, Any]) -> str:
    width = 1120
    margin_x = 48
    y0 = 74
    layer_h = 132
    gap = 22
    layers = [
        ("应用层", [("apps/ui-tars", "Electron desktop shell"), ("apps/ui-tars/src/renderer", "Renderer / UI")], "#eff6ff"),
        ("Agent Runtime 层", [("multimodal/agent-tars", "Runtime / CLI / environments"), ("multimodal/tarko", "Provider / server / snapshot")], "#f8fafc"),
        ("GUI Agent SDK 层", [("gui-agent/action-parser", "Action parser"), ("operator-adb/browser/nutjs", "Operators"), ("operator-aio", "Execution adapter")], "#f0fdf4"),
        ("扩展与工具层", [("infra/pdk", "Development toolkit"), ("MCP / Tools", "Permission & audit surface")], "#fff7ed"),
    ]
    height = y0 + len(layers) * layer_h + (len(layers) - 1) * gap + 42
    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Monorepo layer map">',
        '<title>Monorepo 模块分层地图</title>',
        '<desc>分层卡片图，展示 UI-TARS monorepo 的应用层、Agent Runtime 层、GUI Agent SDK 层和扩展与工具层。</desc>',
        '<defs><marker id="arrow-layer" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L0,6 L9,3 z" fill="#94a3b8"/></marker></defs>',
        '<rect x="0" y="0" width="100%" height="100%" fill="#fbfaf5"/>',
        '<text x="48" y="34" fill="#0f172a" font-size="18" font-weight="700">Monorepo 模块分层地图</text>',
        '<text x="48" y="56" fill="#64748b" font-size="12">只展示主要分层，不画所有 workspace 依赖；详细职责见下方核心模块角色表。</text>',
    ]
    centers = []
    for index, (title, modules, fill) in enumerate(layers):
        y = y0 + index * (layer_h + gap)
        parts.append(f'<rect x="{margin_x}" y="{y}" width="{width - margin_x * 2}" height="{layer_h}" rx="14" fill="{fill}" stroke="#d8d1c2"/>')
        parts.append(f'<text x="{margin_x + 18}" y="{y + 30}" fill="#0f172a" font-size="15" font-weight="700">{title}</text>')
        card_w = 238
        for module_index, (path, role) in enumerate(modules[:4]):
            x = margin_x + 18 + module_index * (card_w + 14)
            card_y = y + 48
            parts.append(f'<rect x="{x}" y="{card_y}" width="{card_w}" height="62" rx="8" fill="#fffdf8" stroke="#c9c0ae"/>')
            parts.append(f'<text x="{x + 10}" y="{card_y + 23}" fill="#0f172a" font-size="12" font-weight="700">{html.escape(_short_svg_label(path, 28))}</text>')
            parts.append(f'<text x="{x + 10}" y="{card_y + 44}" fill="#64748b" font-size="11">{html.escape(role)}</text>')
        centers.append((width / 2, y + layer_h))
    for index in range(len(centers) - 1):
        x, y = centers[index]
        next_y = y0 + (index + 1) * (layer_h + gap)
        parts.append(f'<line x1="{x}" y1="{y + 4}" x2="{x}" y2="{next_y - 8}" stroke="#94a3b8" stroke-width="1.5" marker-end="url(#arrow-layer)"/>')
    parts.append("</svg>")
    return "".join(parts)


def _svg_node(x: float, y: float, width: float, label: str, *, height: float | None = None) -> list[str]:
    lines = _wrap_svg_label(label)
    node_height = height or max(50, 22 + len(lines) * 17)
    result = [f'<rect x="{x}" y="{y}" width="{width}" height="{node_height}" rx="8" fill="#f8f6ef" stroke="#c9c0ae"/>']
    for index, line in enumerate(lines):
        result.append(f'<text x="{x + 10}" y="{y + 22 + index * 17}" fill="#0f172a" font-size="12">{html.escape(line)}</text>')
    return result


def _svg_badge(x: float, y: float, text: str, *, fill: str, stroke: str, color: str) -> str:
    return (
        f'<rect x="{x}" y="{y}" width="58" height="22" rx="11" fill="{fill}" stroke="{stroke}"/>'
        f'<text x="{x + 9}" y="{y + 15}" fill="{color}" font-size="11" font-weight="700">{html.escape(text)}</text>'
    )


def _short_svg_label(label: str, max_chars: int = 32) -> str:
    replacements = {
        "Desktop App / CLI / Web UI": "Desktop App / CLI / Web UI",
        "Model Provider / VLM / LLM Client": "Model Provider / VLM / LLM",
        "multimodal/agent-tars/cli": "multimodal/agent-tars",
        "multimodal/gui-agent/action-parser": "gui-agent/action-parser",
        "multimodal/gui-agent/operator-adb": "operator-adb/browser/nutjs",
    }
    value = str(label).replace("\\n", "\n")
    for src, dst in replacements.items():
        value = value.replace(src, dst)
    lines = []
    for line in value.splitlines():
        line = line.strip()
        if len(line) > max_chars:
            line = line[: max_chars - 1] + "…"
        if line:
            lines.append(line)
    return "\n".join(lines[:2]) or str(label)[:max_chars]


def _wrap_svg_label(label: str, max_chars: int = 24) -> list[str]:
    raw_lines = str(label).replace("\\n", "\n").splitlines() or [str(label)]
    lines: list[str] = []
    for raw in raw_lines:
        text = raw.strip()
        while len(text) > max_chars:
            lines.append(text[:max_chars])
            text = text[max_chars:]
        if text:
            lines.append(text)
    return lines[:4]


def _diagram_label_html(label: str) -> str:
    return html.escape(str(label)).replace("\\n", "<br>")


def _badge_risk(fragment: str) -> str:
    for level in ("high", "medium", "low"):
        fragment = fragment.replace(f">{level}<", f'><span class="risk-{level}">{level}</span><')
        if fragment == level:
            fragment = f'<span class="risk-{level}">{level}</span>'
    for label, level in (("高", "high"), ("中", "medium"), ("低", "low")):
        fragment = fragment.replace(f">{label}<", f'><span class="risk-{level}">{label}</span><')
        if fragment == label:
            fragment = f'<span class="risk-{level}">{label}</span>'
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
