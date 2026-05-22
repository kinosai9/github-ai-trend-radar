# github-ai-trend-radar Skill

## 用途

这个 skill 用于调用 `github-ai-trend-radar` 公开能力库，自动生成 GitHub AI 开源趋势日报、周报或月报。它适合把公开采集逻辑、评分规则、报告渲染和推送流程组合为可复用的自动化任务。

## 输入

- 报告周期：`daily`、`weekly` 或 `monthly`
- 运行配置目录：默认 `config/`
- 私有关注列表：建议使用未提交的 `data/watchlist.yaml` 或 CI secret 注入
- 可选 token：通过环境变量或 CI secrets 提供，不写入仓库
- 可选输出目录：默认 `data/reports/`

## 输出

- GitHub AI 开源趋势报告
- 候选仓库、评分结果和快照缓存
- 可供 deep research 使用的项目清单
- 可推送到 PushPlus、钉钉、企业微信、飞书等渠道的消息内容

## 常用命令

```bash
python -m pip install -e .
python -m github_ai_trend_radar.main --help
python -m github_ai_trend_radar.main run --period daily
python -m github_ai_trend_radar.main collect --period weekly
python -m github_ai_trend_radar.main score --period weekly
python -m github_ai_trend_radar.main render --period monthly
python -m github_ai_trend_radar.main push --period daily
python -m github_ai_trend_radar.main deep-research --period weekly
pytest
```

## 注意事项

- 公开仓库只保存通用代码、默认配置、示例 workflow 和 skill 文档。
- 不要提交 API key、PushPlus token、钉钉 webhook、企业微信 webhook 或任何私人关注配置。
- 默认配置文件使用 `*.default.yaml` 命名，真实运行配置应放在私有仓库、环境变量、CI secrets 或未跟踪的本地文件中。
- 运行推送前确认目标渠道和密钥来自安全来源。
- 发布报告前检查是否包含私人 watchlist 或内部项目信息。

## 适合 Claude Code / Codex 调用的场景

- 定时生成 AI 开源趋势日报、周报、月报
- 从 GitHub Trending 和搜索结果中筛选新兴 AI 项目
- 对候选仓库进行评分、归类和报告渲染
- 将报告推送到个人或团队消息渠道
- 为重点项目生成 deep research 候选清单
- 在私有运行仓库中复用公开能力库，同时隔离 secrets 和个人配置
