# Workflow

## 当前主链路

`wewe-rss -> sync-sources -> daily-candidates -> 人工选题 -> run-once --rewrite --auto-cover -> 草稿箱`

## 推荐工作节奏

1. `prepare`
   第一次使用先检查 `wewe-rss`、`md2wechat`、订阅源和本地配置是否齐全
2. `sync-sources`
   从 `wewe-rss /feeds` 同步当前订阅源，避免手填 `sources.yaml`
3. `daily-candidates`
   从所有 enabled 源抓最近一批文章，按新鲜度筛出候选，并生成可读版清单
4. `human pick`
   人工从 `output/candidates/latest.md` 里决定今天要做哪篇
5. `run-once`
   只对选中的文章执行正文提取、清洗、改写、封面图生成与草稿上传
6. `state`
   把处理状态、改写结果、封面结果、发布结果写进状态文件，方便去重和追溯

## 唯一推荐的公共 Skill 路径

公共 Skill 默认只推荐：

`prepare -> bootstrap -> doctor -> sync -> candidates -> 人工选题 -> run --source <SOURCE_ID> --item-id <ITEM_ID>`

原因：

- 候选池是跨源可读入口
- 人工选题能保证可控性
- 显式 `source_id + item_id` 比“自动挑最新文章”更稳定
- 不同部署环境下，“某个源的最新一篇”并不总是同一个结果

## 三种输入模式

## 模式 A：生成今日候选

- 输入：无，或可选 `--source`
- 命令：`python skill/scripts/run_pipeline.py candidates`
- 输出：
  - `output/candidates/latest.json`
  - `output/candidates/latest.md`
- 适用场景：
  - 还没定今天做哪篇
  - 想先看一周内所有源的新内容

## 模式 B：执行选中的候选

- 输入：`source_id + item_id`
- 命令：
  - `python skill/scripts/run_pipeline.py run --source <SOURCE_ID> --item-id <ITEM_ID> --rewrite --auto-cover --dry-run`
  - `python skill/scripts/run_pipeline.py run --source <SOURCE_ID> --item-id <ITEM_ID> --rewrite --auto-cover`
- 输出：
  - `output/raw/*.html`
  - `output/markdown/*.md`
  - `output/rewritten/*.md`
  - `output/covers/*`
  - `data/state/run_history.jsonl`
- 适用场景：
  - 已经完成选题
  - 只希望跑这一篇，不自动乱挑

## 为什么不把“直接处理最新文章”当成公共默认模式

- 它会绕过候选池
- 它会把“今天要做哪篇”的决策交给环境状态
- 它不适合作为跨用户、跨机器复用时的稳定入口

如果你是仓库维护者，仍然可以直接调用底层 CLI 做这种高级用法；但它不应该成为公共 Skill 的默认路径。

## 关键产物

- 候选清单：`output/candidates/latest.md`
- 机器报告：`output/candidates/latest.json`
- 正文提取：`output/raw/`
- 原始 Markdown：`output/markdown/`
- 改写稿：`output/rewritten/`
- 封面图：`output/covers/`
- 状态日志：`data/state/run_history.jsonl`

## 出错时先查哪里

- 发现失败：先查 `WEWE_RSS_BASE_URL`
- 候选为空：先看 `latest.json` 里的 `skipped`，再看 `freshness.max_age_hours`
- 提取失败：先查微信页面结构是否变动
- 改写不理想：先查 `rewrite` 风格和 `quality` 约束
- 封面失败：先查 `IMAGE_*` / `image.*` 配置与 provider 可用性
- 上传失败：先查 `MD2WECHAT_RUN_SCRIPT`、微信白名单和本地 `md2wechat` 版本
