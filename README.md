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

- `--enrich-report`：只对最终展示的主区项目补齐中文摘要、关注原因、企业适配和风险。
- `--enrich-overview`：基于主区项目生成更像编辑判断的 3 条中文总评，并把统计信号放到“统计信号补充”中。

GitHub Actions 正常日跑仍建议先 `run --use-llm --render` 生成当天报告；本地补跑可以使用 `render --date latest`。

## GitHub Pages 站点

渲染完成后可以把报告复制到 `site/`，用于 GitHub Pages 发布：

```bash
python -m github_ai_trend_radar.main build-site --period daily --date latest
python -m github_ai_trend_radar.main build-site --period weekly --date latest
python -m github_ai_trend_radar.main build-site --all
```

`build-site` 会从 `data/reports/` 读取 `report.html`、`report.md` 和 `report-enriched.json`，复制到 `site/reports/`，并生成：

- `site/index.html`
- `site/reports.json`

如果某个周期没有报告，例如暂时没有 monthly，会自动跳过，不会让命令失败。

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

## GitHub Actions 自动化

仓库已提供 `.github/workflows/ai-trend-radar.yml`。启用后可以手动触发或按计划自动生成日报，流程是：

1. 采集 GitHub AI 趋势候选
2. 规则评分
3. 可选 LLM 校准
4. 渲染 Markdown / HTML / report-enriched
5. 构建 `site/`
6. 发布 GitHub Pages
7. 通过 PushPlus 推送摘要和完整报告链接

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
python -m github_ai_trend_radar.main run --period daily --use-llm --render --enrich-report --enrich-overview
python -m github_ai_trend_radar.main build-site --period daily --date latest
python -m github_ai_trend_radar.main push --period daily --date latest --channel pushplus --dry-run
```

Actions 会同时上传 `data/reports` 和 `data/snapshots` 为 workflow artifact，便于排查采集、评分、渲染或推送问题。

如果报告包含内部业务判断、客户信息、私有仓库或非公开策略，不要发布到公开 GitHub Pages；应改为私有 artifact、本地查看或受控静态站点。

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
