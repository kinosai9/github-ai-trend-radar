# github-ai-trend-radar

`github-ai-trend-radar` 是一个公开能力库，用于自动生成 GitHub AI 开源趋势日报、周报和月报。项目目标是把采集、清洗、评分、渲染、推送和后续深度研究整理成可复用的 Python 包与自动化工作流基础设施。

## 设计原则

本仓库只保存通用代码、默认配置、示例 workflow、prompt 模板和 skill 文档。个人关注列表、私有运行配置、API key、PushPlus token、钉钉 webhook、企业微信 webhook、GitHub token 等敏感内容应放在私有仓库、CI secrets、环境变量或本地未跟踪文件中。

默认配置以 `config/*.default.yaml` 形式提交，真实运行时建议复制为私有配置文件或通过命令行参数、环境变量注入。

## 不要提交 Secrets

请不要提交任何以下内容：

- API key、访问令牌、cookie、session
- PushPlus token、钉钉或企业微信 webhook
- 私人 watchlist、私有仓库列表、内部账号信息
- 任何包含个人偏好、公司内部策略或未公开项目信息的配置

建议在提交前运行 `git diff --cached` 检查暂存内容。

## 基础安装

推荐使用 Python 3.12。项目主验证目标是 GitHub Actions 的 Python 3.12 环境，`pyproject.toml` 将运行版本约束为 `>=3.12,<3.14`。当前本机 Python 3.14 可以运行测试，但它不是主验证目标；开发时不要引入只支持 Python 3.14 的语法或依赖。

```bash
python -m pip install -e .
python -m github_ai_trend_radar.main --help
pytest
```

## 本地开发配置

本地调试时可以复制示例环境文件，并在未跟踪的 `.env.local` 中填写自己的 token：

```bash
cp .env.example .env.local
```

Windows PowerShell：

```powershell
Copy-Item .env.example .env.local
```

然后在 `.env.local` 中填写 `GH_PAT`。CLI 启动时会自动尝试加载 `.env` 和 `.env.local`；文件不存在不会报错。`doctor` 只会显示 `GH_PAT` 是否存在，不会打印 token 值。

## Topics 配置

默认主题配置位于 `config/topics.default.yaml`，覆盖 AI Agent、MCP、Coding Agent、RAG/Knowledge、LLM Infra、Vector DB 六类方向。公开仓库只提交默认配置；本地私有偏好请写入未跟踪的 `config/topics.local.yaml`，或通过环境变量 `TOPICS_JSON` 注入。

配置优先级：

1. `config/topics.default.yaml`
2. `config/topics.local.yaml`
3. `TOPICS_JSON`
4. CLI `--focus-topics` 选择主题子集

示例：

```bash
python -m github_ai_trend_radar.main collect --period daily --focus-topics ai_agent,mcp,coding_agent
```

第一版会限制 GitHub Search 调用量：每个 focus topic 最多 3 条 query，每条 query 最多 2 页，每页 50 条。合并去重后默认最多保留 200 个候选，并只对 top 100 做 GitHub Repo API 和 README 增强。

## 规则评分

采集完成后可以运行规则评分，不依赖 LLM：

```bash
python -m github_ai_trend_radar.main score --period daily
```

评分会读取 `data/snapshots/YYYY-MM-DD-period-candidates.json`，输出 `data/snapshots/YYYY-MM-DD-period-scored.json`。当前评分包含增长热度、主题相关性、工程质量、新颖性、社区活跃、业务匹配、多源置信度和噪声降权。`run` 命令当前等价于 `collect + score`：

```bash
python -m github_ai_trend_radar.main run --period daily
```

## LLM 语义校准

可选启用 OpenAI-compatible Chat Completions API，对规则评分后的重点候选做语义校准、噪声复核、技术价值摘要和最终建议动作判断：

```bash
python -m github_ai_trend_radar.main score --period daily --use-llm
```

本地 `.env.local` 可以配置：

```bash
LLM_PROVIDER=
LLM_API_STYLE=
LLM_API_KEY=
LLM_API_BASE=
LLM_MODEL=
LLM_THINKING=
LLM_TEMPERATURE=
LLM_MAX_TOKENS=
```

说明：

- 支持 OpenAI-compatible API；`OPENAI_API_BASE` 不填时使用默认 OpenAI endpoint。
- 兼容旧环境变量：`OPENAI_API_KEY`、`OPENAI_API_BASE`、`MODEL_NAME` 会作为 `LLM_API_KEY`、`LLM_API_BASE`、`LLM_MODEL` 的 fallback。
- `LLM_MODEL` 不填时默认使用 `gpt-4o-mini`。
- Moonshot/Kimi K2.6 这类 thinking model 会自动关闭 thinking，并使用兼容温度；也可通过 `LLM_TEMPERATURE`、`LLM_MAX_TOKENS`、`LLM_THINKING` 做本地覆盖。
- 没有 `LLM_API_KEY` / `OPENAI_API_KEY` 时不会崩溃，会自动降级为规则评分结果，并仍写出 `llm-scored` snapshot 便于验证链路。
- LLM 默认只分析 Top 30：breakout 15、valuable_mature 10、watchlist 5，避免成本失控。
- 不要提交 `.env.local` 或任何真实 API key。

### LLM Provider 配置

Kimi Open Platform / Moonshot OpenAI-compatible 推荐配置：

```bash
LLM_PROVIDER=moonshot
LLM_API_STYLE=openai_compatible
LLM_API_BASE=https://api.moonshot.ai/v1
LLM_MODEL=kimi-k2.6
LLM_API_KEY=
LLM_THINKING=disabled
LLM_TEMPERATURE=0.6
```

Kimi Code / Coding Plan 说明：如果 OpenAI-compatible 返回 `403`，可能是非白名单客户端限制。请改用 Anthropic-compatible 协议，并填写对应服务地址：

```bash
LLM_PROVIDER=kimi_code
LLM_API_STYLE=anthropic_compatible
LLM_API_BASE=
LLM_API_KEY=
LLM_MODEL=
```

通用 OpenAI-compatible 配置：

```bash
LLM_PROVIDER=openai_compatible
LLM_API_STYLE=openai_compatible
LLM_API_BASE=
LLM_MODEL=
LLM_API_KEY=
```

不同 provider 的 OpenAI-compatible 并不完全等价。`temperature`、`thinking`、`reasoning_content`、JSON mode 都可能需要 provider profile；项目会通过 provider adapter 隔离这些差异。

## 报告生成

评分完成后可以把 `scored` / `llm-scored` snapshot，或已缓存的 `report-enriched` 报告模型渲染为 Markdown 和墨水风单文件 HTML：

```bash
python -m github_ai_trend_radar.main render --period daily
python -m github_ai_trend_radar.main render --period daily --date latest
python -m github_ai_trend_radar.main render --period daily --date latest --enrich-report --enrich-overview
python -m github_ai_trend_radar.main render --period daily --format html --open
python -m github_ai_trend_radar.main run --period daily --use-llm --render
```

`render` 会优先读取报告层缓存；如果不存在，再回退到 scored snapshot 构建报告模型。输入优先级为：

1. `data/reports/YYYY-MM-DD-period-report-enriched.json`
2. `data/snapshots/YYYY-MM-DD-period-llm-scored.json`
3. `data/snapshots/YYYY-MM-DD-period-scored.json`

输出文件位于：

- `data/reports/YYYY-MM-DD-period-report.md`
- `data/reports/YYYY-MM-DD-period-report.html`

HTML 报告复用 AI Ink Times 的墨水风视觉体系，但内容组织面向中文技术情报阅读：优先展示“本期判断”“趋势突破”“值得深研”“长期观察”，噪声项目默认只做摘要聚合，不再用完整卡片刷屏。HTML 是完整静态单文件，后续可直接发布到 GitHub Pages。

本地补跑或调试时推荐使用 `--date latest`，它会在 `data/reports` 和 `data/snapshots` 中自动选择最近可用输入。`report-enriched.json` 是报告层缓存，可用于重复渲染 Markdown/HTML，避免重复执行报告层 LLM 补齐。

报告层 LLM 补齐是可选能力，不改变评分、排序或 bucket：

- `--enrich-report`：只对最终展示的主区项目补齐中文摘要、关注原因、企业适配和风险；如果项目级 LLM 已返回内容但主体仍是英文，也会重新中文化，避免英文原文直接进入日报正文。
- `--enrich-overview`：基于主区项目生成更像编辑判断的 3 条中文总评，并把统计信号放到“统计信号补充”中。

GitHub Actions 正常日跑仍建议先 `run --use-llm --render` 生成当天报告；本地补跑可以使用 `render --date latest`。

## GitHub Pages 站点

渲染完成后可以把报告复制到 `site/`，用于 GitHub Pages 发布：

```bash
python -m github_ai_trend_radar.main build-site --period daily --date latest
python -m github_ai_trend_radar.main build-site --period weekly --date latest
python -m github_ai_trend_radar.main build-site --all
python -m github_ai_trend_radar.main build-site --period daily --date latest --keep-daily 60 --keep-weekly 8 --keep-monthly 12
```

`build-site` 会从 `data/reports/` 读取 `report.html`、`report.md` 和 `report-enriched.json`，复制到 `site/reports/`，并生成：

- `site/index.html`
- `site/reports.json`

如果某个周期没有报告，例如暂时没有 monthly，会自动跳过，不会让命令失败。

Pages 只用于展示近期归档，不作为永久数据库。默认保留：

- 日报：最近 60 天
- 周报：最近 8 周
- 月报：最近 12 个月

首页只展示最新日报、最新周报、最新月报，以及最近 14 篇日报、4 篇周报、6 篇月报。趋势雷达关注近期变化，日报超过 60 天后价值会快速下降；更长期的数据后续应通过 watchlist、research archive 或私有数据仓库沉淀。

## PushPlus 摘要推送

PushPlus 当前只推送摘要和完整报告链接，不会把完整 HTML 日报塞进消息正文。

本地测试：

```bash
python -m github_ai_trend_radar.main push --period daily --date latest --channel pushplus --dry-run
```

正式推送：

```bash
PUSHPLUS_TOKEN=xxx
SITE_BASE_URL=https://username.github.io/repo
python -m github_ai_trend_radar.main push --period daily --date latest --channel pushplus
```

也可以显式传入完整报告链接：

```bash
python -m github_ai_trend_radar.main push --period daily --date latest --channel pushplus --full-report-url https://example.com/reports/2026-05-21-daily-report.html
```

支持环境变量：

- `PUSHPLUS_TOKEN`：必需；缺失时默认跳过推送但命令返回成功
- `PUSHPLUS_TOPIC`
- `PUSHPLUS_CHANNEL`
- `PUSHPLUS_WEBHOOK`
- `SITE_BASE_URL`：用于推导 GitHub Pages 上的完整报告 URL

如果希望推送失败让命令失败，可增加 `--fail-on-push-error`。

## Watchlist Queue 与本地深研

HTML 报告中的重点项目会生成本期待复核 Watchlist Queue，并在项目卡片右上角显示“加入观察队列”按钮。这个按钮不会直接写仓库文件，也不会触发本地 deep-research；它会打开 GitHub Issue 预填页面，用户确认提交后，该 Issue 就成为远端 Watchlist Queue。

为什么不从 GitHub Pages 静默写入 `watchlist_queue.json`：

- GitHub Pages 是静态站点，不支持服务端写入。
- 前端直接调用 GitHub API 写仓库需要暴露 token，不适合 public Pages。
- GitHub Issue 预填表单可以作为安全的人工确认入口，避免误点和 token 泄露。

Issue body 使用 YAML 风格，便于本地解析。默认 labels 为 `watchlist,pending-review`；如果用户没有仓库 label 权限，GitHub 可能不会自动应用 labels，但 Issue 内容仍然可用。

相关配置：

- `SITE_REPO_URL`：报告按钮使用的仓库地址，例如 `https://github.com/kinosai9/github-ai-trend-radar`
- `GITHUB_REPOSITORY_URL`：可作为 fallback

本地同步 Issue queue 需要 GitHub CLI：

```bash
gh auth login
python -m github_ai_trend_radar.main inbox sync --repo kinosai9/github-ai-trend-radar
python -m github_ai_trend_radar.main inbox list
python -m github_ai_trend_radar.main inbox
```

本地 watchlist 管理：

```bash
python -m github_ai_trend_radar.main watch add owner/repo --reason "值得观察" --priority high --topics mcp,coding_agent
python -m github_ai_trend_radar.main watch list
python -m github_ai_trend_radar.main watch remove owner/repo
python -m github_ai_trend_radar.main watch promote --issue 123
```

本地 deep-research：

```bash
python -m github_ai_trend_radar.main deep-research --repo owner/repo --depth quick --open
python -m github_ai_trend_radar.main deep-research --repo owner/repo --depth standard --compare --open
python -m github_ai_trend_radar.main deep-research --repo owner/repo --depth standard --compare --llm-timeout 90 --llm-stages enterprise_fit_summary,final_report_synthesis --open
python -m github_ai_trend_radar.main deep-research --from-inbox --limit 3
```

deep-research 是本地企业技术尽调工具，不是更长的日报卡片。它回答的是：这个项目是否值得公司投入时间、纳入工具链、二开或长期跟踪。它默认只在本地执行，不接入 GitHub Actions schedule，不发布到 GitHub Pages。

常用参数：

- `--depth quick|standard|full`：研究深度，默认 `standard`
- `--profile enterprise_ai_service`：公司背景配置 profile
- `--compare`：启用横向同类项目搜索与对比，结合 GitHub Search 和历史趋势雷达快照生成 comparable projects
- `--clone` / `--no-clone`：是否 clone 仓库做只读源码结构分析，默认 `--no-clone`
- `--max-files`：最多分析的文件路径数量，默认 80
- `--max-issues`：最多抓取的 issue / PR 样本数量，默认 50
- `--output-dir`：默认 `data/research/`
- `--private`：默认启用，表示报告不进入 Pages、不提交 Git
- `--no-llm`：禁用 P2.2 分阶段 LLM 分析，只生成确定性资料汇总
- `--llm-timeout`：deep-research LLM 阶段超时时间，例如 `--llm-timeout 90`
- `--llm-stages`：只运行指定 LLM 阶段。Kimi Code 下建议先用 `enterprise_fit_summary,final_report_synthesis`，稳定后再跑全阶段。

deep-research 可以使用独立的长上下文模型配置，避免和日报/周报的轻量 LLM 配置互相影响。优先级是 `DEEP_RESEARCH_LLM_*` → `RESEARCH_LLM_*` → 通用 `LLM_*`：

```bash
DEEP_RESEARCH_LLM_PROVIDER=
DEEP_RESEARCH_LLM_API_STYLE=
DEEP_RESEARCH_LLM_API_KEY=
DEEP_RESEARCH_LLM_API_BASE=
DEEP_RESEARCH_LLM_MODEL=
DEEP_RESEARCH_LLM_TEMPERATURE=
DEEP_RESEARCH_LLM_MAX_TOKENS=
DEEP_RESEARCH_LLM_TIMEOUT=180
DEEP_RESEARCH_LLM_THINKING=

RESEARCH_LLM_PROVIDER=
RESEARCH_LLM_API_STYLE=
RESEARCH_LLM_API_KEY=
RESEARCH_LLM_API_BASE=
RESEARCH_LLM_MODEL=
RESEARCH_LLM_TEMPERATURE=
RESEARCH_LLM_MAX_TOKENS=
RESEARCH_LLM_TIMEOUT=120
RESEARCH_LLM_THINKING=
```

建议：日报/周报可以继续使用响应较快的模型；deep-research 更适合配置长上下文、长输出更稳定的模型。当前深研管线按阶段输出结构化 JSON：源码结构摘要、负面信息摘要、横向对比摘要、企业落地适配摘要、最终裁决。最终报告会再经过一致性裁决，避免“严重风险”和“risk low”同时出现。

公司背景配置：

```bash
config/company_profile.default.yaml
config/company_profile.local.yaml
```

`company_profile.local.yaml` 用于本地私有配置，默认不提交。配置会影响企业适配评估，例如私有化部署、权限审计、当前技术栈、不可接受风险和集成目标。

deep-research 输出目录：

```bash
data/research/owner__repo/YYYY-MM-DD/
  research.md
  research.html
  research.json
  research-summary.json
  intermediate/
  raw/
  assets/
```

P2 分阶段实现：

- P2.1：结构与资料汇总版，包含 GitHub metadata、README、docs/examples/package files、issues/releases、company profile、Markdown/HTML 报告骨架和 Mermaid 图。
- P2.2：LLM 分阶段分析版，补充 repo overview、代码架构、负面信息、企业适配和最终报告合成。任一阶段失败时仍生成报告，并在 `research-summary.json` 中记录失败阶段。
- P2.3：横向竞品和生态广度版，接入 GitHub Search 同类项目、对比表、生态位置判断和趋势雷达历史快照联动。

自动生成的 queue 位于：

```bash
data/watchlist_queue/YYYY-MM-DD-period-watchlist-queue.json
```

它只作为自动候选和报告调试产物，不是用户点击按钮后的唯一事实来源。`data/watchlist.yaml` 是本地私有 watchlist，默认不提交；如果包含内部判断、客户线索或私有项目，请继续保持在 `.gitignore` 中。

## GitHub Actions 自动化

仓库已提供 `.github/workflows/ai-trend-radar.yml`。启用后可以手动触发或按计划自动生成日报，流程是：

1. 采集 GitHub AI 趋势候选
2. 规则评分
3. 可选 LLM 校准
4. 渲染 Markdown / HTML / report-enriched
5. 构建 `site/`
6. 发布 GitHub Pages
7. 通过 PushPlus 推送摘要和完整报告链接

定时触发周期：

- 日报：北京时间每天 08:45，对应 UTC `45 0 * * *`
- 周报：北京时间每周日 21:30，对应 UTC `30 13 * * 0`
- 月报：北京时间每月 1 日 09:30，对应 UTC `30 1 1 * *`

GitHub Actions schedule 使用 UTC，并且可能存在数分钟到十几分钟延迟。workflow 会根据 `github.event.schedule` 自动解析 period；手动触发时 `inputs.period` 优先。

建议配置 GitHub Pages：

1. 进入仓库 Settings。
2. 打开 Pages。
3. Source 选择 `GitHub Actions`。

建议配置 Secrets：

- `GH_PAT`
- `LLM_API_KEY`
- `PUSHPLUS_TOKEN`

建议配置 Variables：

- `LLM_PROVIDER`
- `LLM_API_STYLE`
- `LLM_API_BASE`
- `LLM_MODEL`
- `LLM_THINKING`
- `LLM_TEMPERATURE`
- `LLM_MAX_TOKENS`
- `LLM_TIMEOUT`
- `SITE_BASE_URL`
- `SITE_REPO_URL`
- `TOPICS_JSON`，可选

`SITE_BASE_URL` 建议显式设置，例如：

```bash
https://username.github.io/github-ai-trend-radar
```

如果不设置，workflow 会按 `https://owner.github.io/repo` 推导。使用自定义域名或仓库名变化时，显式配置更稳。

手动运行 workflow：

1. 打开 GitHub 仓库 Actions。
2. 选择 `GitHub AI Trend Radar`。
3. 点击 `Run workflow`。
4. 选择 `period`、是否 `use_llm`、是否 `enrich_report`、是否 `pushplus`。

本地对应验证命令：

```bash
python -m github_ai_trend_radar.main resolve-run-context --event-name schedule --schedule "45 0 * * *"
python -m github_ai_trend_radar.main run --period daily --use-llm --render --enrich-report --enrich-overview --llm-top-n 5 --report-enrich-top-n 5
python -m github_ai_trend_radar.main build-site --period daily --date latest --keep-daily 60 --keep-weekly 8 --keep-monthly 12
python -m github_ai_trend_radar.main push --period daily --date latest --channel pushplus --dry-run
```

Actions 会上传 `data/snapshots`、`data/reports/*run-summary.json` 和 `data/reports/*report-enriched.json` 为 workflow artifact，便于排查采集、评分、渲染或推送问题。debug artifacts 默认保留 7 天，不长期保留所有 raw API snapshot。

资源限制提醒：

- GitHub-hosted runner 单 job 最长 6 小时，本项目 workflow 设置为 45 分钟超时。
- GitHub Pages 站点大小有软限制，建议控制在 1GB 以内。
- Pages 部署超过 10 分钟可能超时。
- PushPlus 只推摘要和完整报告链接，不推完整 HTML。

如果报告包含内部业务判断、客户信息、私有仓库或非公开策略，不要发布到公开 GitHub Pages；应改为私有 artifact、本地查看或受控静态站点。

## 质量闸门与报告级总结

规则评分之后会执行质量闸门，避免低 Star、低成熟度、README 信息不足但描述好听的项目直接进入“趋势突破”或“值得深研”。不是高热项目都会进入深研；低成熟度项目会被标记为早期观察，深研建议需要同时满足趋势、主题和工程信号。

质量闸门会记录：

- README 是否充分
- 是否有 license
- 是否包含安装、示例、文档、测试信号
- 最近是否更新
- 是否归档或 fork
- 是否多源命中或来自 OSSInsight

报告级 LLM 总结只调用一次，仅用于优化顶部“本期判断”的表达质量，不改变项目排序、bucket 或推荐动作。如果没有 LLM key 或调用失败，会自动 fallback 到规则判断，并在 `run-summary.json` 中记录状态。

## Troubleshooting

如果采集命令无法访问 OSSInsight 或 GitHub API，可以先运行 doctor 诊断网络、代理和 token 配置：

```bash
python -m github_ai_trend_radar.main doctor
```

doctor 会检查 Python 和 `requests` 版本，显示 `HTTP_PROXY`、`HTTPS_PROXY`、`NO_PROXY`、`GH_PAT`、`GITHUB_TOKEN`、`OPENAI_API_KEY` 是否存在，并请求 GitHub rate limit、OSSInsight trending 页面和多组 OSSInsight trends API 参数。它只显示变量是否存在，不会打印任何 secret 值，也不会写入正式 snapshots。

判断方向：

- GitHub rate limit 返回 `200`，但 OSSInsight trends 返回 `500`：通常是 OSSInsight 服务端或该参数组合临时异常。
- GitHub 和 OSSInsight 都超时、DNS 失败或连接失败：优先检查本地网络、代理、公司网络策略或 CI 网络出口。
- GitHub 返回 `401` 或 `403`：检查 `GH_PAT` / `GITHUB_TOKEN` 是否存在、是否有效、是否触发 rate limit；doctor 只显示 token 是否存在，不会打印值。
- OSSInsight 页面 `https://ossinsight.io/trending` 可访问，但 API 失败：更可能是 API endpoint 或参数组合问题。
- GitHub Actions 的 `Configure Pages` 步骤报 `Get Pages site failed` / `Not Found`：先确认仓库是 public，或账号计划支持 private Pages；确认 Settings → Pages → Source 是 GitHub Actions；确认 workflow 使用 `actions/configure-pages@v5` 并设置 `enablement: true`；确认 workflow permissions 包含 `pages: write` 和 `id-token: write`。

Windows PowerShell 临时设置代理：

```powershell
$env:HTTP_PROXY = "http://127.0.0.1:7890"
$env:HTTPS_PROXY = "http://127.0.0.1:7890"
python -m github_ai_trend_radar.main doctor
```

清除当前 PowerShell 会话里的代理：

```powershell
Remove-Item Env:\HTTP_PROXY -ErrorAction SilentlyContinue
Remove-Item Env:\HTTPS_PROXY -ErrorAction SilentlyContinue
```

## 后续计划

- 实现 GitHub Trending、GitHub Search、RSS、HN、Reddit、X/Twitter 等来源采集器
- 增加仓库元数据快照、增量缓存和去重逻辑
- 建立可解释评分模型，支持日报、周报、月报不同权重
- 使用 Jinja2 渲染 Markdown、HTML、邮件和消息推送版本
- 增加钉钉、企业微信、飞书等推送适配器
- 增加 deep-research 流程，把候选项目扩展为技术分析和趋势洞察
- 增加 Pages 报告历史保留和索引增量合并
