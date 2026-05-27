"""Rule-based enterprise fit evaluation."""

from __future__ import annotations

from typing import Any


def evaluate_enterprise_fit(
    context: dict[str, Any],
    repo_structure: dict[str, Any],
    architecture: dict[str, Any],
    negative_signals: dict[str, Any],
    company_profile: dict[str, Any],
) -> dict[str, Any]:
    company = company_profile.get("company", {}) if isinstance(company_profile.get("company"), dict) else {}
    metadata = context.get("metadata", {}) if isinstance(context.get("metadata"), dict) else {}
    readme = str(context.get("readme", "")).lower()
    private_deploy = any(keyword in readme for keyword in ("self-hosted", "local", "docker", "on-prem", "private"))
    docs_ready = bool(repo_structure.get("docs_paths") or repo_structure.get("examples_paths"))
    high_evidence = [
        item
        for item in negative_signals.get("negative_evidence", []) or []
        if isinstance(item, dict) and item.get("severity") == "high"
    ]
    risk_level = "high" if negative_signals.get("enterprise_blockers") or high_evidence else "medium" if negative_signals.get("maturity_risks") else "low"
    maturity_penalty = bool(high_evidence or negative_signals.get("enterprise_blockers"))
    return {
        "relevance_to_company": _relevance(company, metadata, readme),
        "applicable_scenarios": _scenarios(company, readme),
        "company_direction_fit": {
            "coding_agent_context": "可作为 Coding Agent 上下文增强的候选方向，但需验证图谱构建质量。",
            "business_understanding_layer": "可探索为开发前业务理解编译层，把代码/文档结构化为可查询资产。",
            "enterprise_knowledge_graph": "可与企业知识库 / GraphRAG / 知识图谱方向形成概念互补。",
            "claude_codex_workflow": "可验证 Claude Code / Codex 查询图谱后的上下文压缩效果。",
            "neo4j_pgvector_obsidian_llm_wiki": "优先验证 Neo4j 或本地知识库导出，再考虑 pgvector/Obsidian/llm_wiki 联动。",
        },
        "landing_scenarios": [
            "内部代码库理解",
            "项目交接/维护",
            "开发前业务理解",
            "Coding Agent 上下文压缩",
            "行业项目知识资产结构化",
        ],
        "direct_blockers": [
            "权限审计缺失",
            "多租户隔离缺失",
            "secret/path 泄露风险需复核",
            "企业部署文档不足",
            "输出结果可控性待验证",
        ],
        "integration_paths": _integration_paths(company, architecture),
        "required_adaptations": _adaptations(private_deploy, docs_ready),
        "deployment_feasibility": "需要进一步验证" if maturity_penalty else "较高" if private_deploy or repo_structure.get("deployment_files") else "需要进一步验证",
        "data_security_considerations": _security_considerations(architecture),
        "permission_audit_considerations": "需要确认权限模型、日志审计和租户隔离能力。",
        "fit_with_existing_stack": _stack_fit(company, repo_structure),
        "short_term_action": "先完成安全/源码证据复核；不要直接进入生产依赖。" if maturity_penalty else "阅读 README 与 examples，完成本地只读验证；不要直接进入生产依赖。",
        "medium_term_action": "仅在阻塞风险清除后再做 PoC，重点验证私有化部署、权限边界和二开成本。" if maturity_penalty else "若核心能力匹配，可做 PoC，重点验证私有化部署、权限边界和二开成本。",
        "not_recommended_if": company.get("unacceptable_risks", []),
        "final_rating": {
            "technical_value": 4 if docs_ready else 3,
            "enterprise_fit": 2 if maturity_penalty else 4 if private_deploy else 3,
            "implementation_feasibility": 2 if maturity_penalty else 4 if repo_structure.get("package_files") else 3,
            "strategic_relevance": 4,
            "risk_level": risk_level,
        },
        "enterprise_action_plan": {
            "poc_scope": "仅使用非敏感测试仓库验证核心流程，不接入客户数据或内部生产代码。",
            "required_checks": [
                "选择一个非敏感内部 demo repo",
                "禁止外部 API 上传内部代码",
                "验证 graph 构建质量",
                "验证 Claude Code / Codex 查询效果",
                "验证增量更新、删除文件一致性",
                "验证是否可导出到 Neo4j 或本地知识库",
                "许可证复核",
                "issue 安全证据复核",
                "权限与审计能力确认",
            ],
            "integration_design": _integration_paths(company, architecture),
            "security_checklist": _security_considerations(architecture),
            "estimated_effort": "0.5-2 人日资料复核；若进入 PoC，额外 2-5 人日。",
            "go_no_go_criteria": [
                "Go：核心流程可本地闭环、无高危安全 issue、权限/数据边界清晰。",
                "No-go：凭据泄露、内部代码外传、核心模块缺失或维护信号不足。",
            ],
        },
    }


def _relevance(company: dict[str, Any], metadata: dict[str, Any], readme: str) -> str:
    topics = " ".join(metadata.get("topics", []) or [])
    focus = " ".join(company.get("focus_domains", []) or []).lower()
    if any(keyword.lower() in f"{topics} {readme}" for keyword in company.get("focus_domains", []) or []):
        return "与公司关注方向存在直接交集。"
    if any(keyword in f"{topics} {readme}" for keyword in ("agent", "mcp", "rag", "llm", "coding")):
        return "与企业 AI 工程方向存在潜在交集。"
    return f"与当前重点方向相关性需要人工复核：{focus[:80]}"


def _scenarios(company: dict[str, Any], readme: str) -> list[str]:
    scenarios = []
    if "mcp" in readme:
        scenarios.append("作为 MCP 工具或插件生态候选")
    if "agent" in readme:
        scenarios.append("作为 Agent 工作流或自动化能力候选")
    if "rag" in readme or "search" in readme:
        scenarios.append("作为知识库 / 检索增强能力候选")
    return scenarios or list(company.get("integration_targets", []) or [])[:3]


def _integration_paths(company: dict[str, Any], architecture: dict[str, Any]) -> list[str]:
    paths = list(company.get("integration_targets", []) or [])[:3]
    if architecture.get("api_surface"):
        paths.append("通过 API 接入现有服务")
    if architecture.get("cli_surface"):
        paths.append("通过 CLI 纳入本地自动化工作流")
    return paths


def _adaptations(private_deploy: bool, docs_ready: bool) -> list[str]:
    adaptations = []
    if not private_deploy:
        adaptations.append("补充私有化部署验证")
    if not docs_ready:
        adaptations.append("补充安装、示例和运维文档")
    adaptations.append("补充权限、审计和数据隔离方案")
    return adaptations


def _security_considerations(architecture: dict[str, Any]) -> list[str]:
    return [
        "确认 API key / token 存储方式",
        "确认是否会上传内部代码、文档或客户数据到第三方服务",
        "确认日志中是否包含敏感上下文",
        f"当前轻量扫描安全线索：{architecture.get('security_boundary', [])}",
    ]


def _stack_fit(company: dict[str, Any], repo_structure: dict[str, Any]) -> str:
    stack = set(str(item).lower() for item in company.get("current_stack", []) or [])
    languages = set(str(item).lower() for item in repo_structure.get("main_languages", []) or [])
    overlap = sorted(stack & languages)
    return f"与当前技术栈交集：{', '.join(overlap)}" if overlap else "未发现明显技术栈交集，需要结合二开计划判断。"
