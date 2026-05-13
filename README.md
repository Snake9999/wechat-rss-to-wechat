# werss2md

一个面向微信公众号内容工作流的可复用仓库：

- 用 `wewe-rss` 发现公众号新文章
- 生成人工可选的候选池
- 提取正文、转 Markdown、按规则改写
- 生成封面图
- 通过 `md2wechat` 上传到微信公众号草稿箱

如果你是第一次把它交给另一个 Agent 用，先看这两处：

- `skill/SKILL.md`
- `skill/scripts/run_pipeline.py`

它们分别是 Skill 入口和命令入口。

如果你是第一次使用，优先看：

- [skill/references/prerequisites.md](skill/references/prerequisites.md)
- [skill/SKILL.md](skill/SKILL.md)
- [skill/references/setup.md](skill/references/setup.md)
- [skill/references/config.md](skill/references/config.md)
- [skill/references/troubleshooting.md](skill/references/troubleshooting.md)

## 文档分层

- `skill/`
  给外部用户和 Agent 的成品入口，只放可安装、可调用、可排错的 Skill 内容
- `vendor/`
  需要随仓库一起对外提供的第三方 Skill 或素材
- `output/`
  运行时产物目录，只保留 `.gitkeep`

## 系统支持

- `macOS`：已验证可用
- `Linux`：按当前依赖设计可用
- `Windows`：优先使用 `python skill/scripts/run_pipeline.py ...` 或 `skill\\scripts\\run_pipeline.cmd ...`
- `Windows + WSL`：当你的 `md2wechat` 仍只提供 `run.sh` 时，这是最稳妥的方案

这套仓库现在的主入口已经是 Python，不再要求所有用户都从 `.sh` 启动。

## 让你的 Agent 自动识别这个 Skill

如果你只是把仓库 clone 到本地，`skill/SKILL.md` 不一定会自动出现在 Agent 的可用技能列表里。

原因不是仓库坏了，而是大多数 Agent 只会扫描它们自己的技能目录。不同工具的目录不一样，所以这里不要把某一个产品的路径当成通用规则。

你真正需要做的事情只有一件：

- 把当前仓库里的 `skill/` 目录，链接或复制到你所使用的 Agent 的技能目录里

通用安装命令：

```bash
python skill/scripts/install_skill_link.py --target-dir /path/to/your/agent/skills
```

例如，某些工具常见的技能目录可能像这样：

- `~/.codex/skills/`
- `~/.claude/skills/`
- `~/.agents/skills/`
- 你自己为其他 Agent 指定的 skills 目录

如果你明确知道自己的 Agent 技能目录，可以直接这样装：

```bash
python skill/scripts/install_skill_link.py --target-dir ~/.codex/skills
python skill/scripts/install_skill_link.py --target-dir ~/.claude/skills
```

安装完成后，重新开一个新的 Agent 会话，让它刷新技能列表。

如果你的 Agent 根本没有“技能目录”这一套机制，那就不要强行套这个模式，直接让它读取仓库内的：

```text
skill/SKILL.md
```

如果你只是在当前这一个仓库里临时跑一次，也可以不安装，直接让 Agent 先读 `skill/SKILL.md`，再按里面的 `prepare -> sync -> candidates -> run` 流程执行。

## Windows 首次使用指南

如果你是第一次在 Windows 上跑这套流程，建议按这个顺序来：

1. 先确认你的机器上能用 `Python 3.10+`
2. 部署好你自己的 `wewe-rss`
3. 部署好你自己的 `md2wechat`
4. 判断你的 `md2wechat` 提供的是哪种启动脚本：
   - 如果有 `run.cmd` 或 `run.ps1`，可以直接走 Windows 原生
   - 如果只有 `run.sh`，建议改用 `WSL` 跑这套流程
5. 把仓库拉到本地后，先运行：

```powershell
python skill/scripts/run_pipeline.py prepare
```

6. 按 `prepare` 的提示补齐 `.env`、`MD2WECHAT_RUN_SCRIPT`、`WEWE_RSS_BASE_URL`
7. 再运行：

```powershell
python skill/scripts/run_pipeline.py bootstrap
python skill/scripts/run_pipeline.py sync
python skill/scripts/run_pipeline.py candidates
```

8. 选好题后，先跑不带改写的 dry-run：

```powershell
python skill/scripts/run_pipeline.py run --source <SOURCE_ID> --item-id <ITEM_ID> --auto-cover --dry-run
```

9. 传输链确认没问题后，再继续跑改写版 dry-run 和真实上传

Windows 用户最需要先确认的不是正文提取，而是这两件事：

- `MD2WECHAT_RUN_SCRIPT` 到底应该指向 `run.cmd`、`run.ps1`，还是你其实应该走 `WSL`
- `WEWE_RSS_BASE_URL` 指向的是 `localhost`，还是你那台跑 `wewe-rss` 的机器局域网地址

## 公开使用路径

外部用户第一次上手，建议按这个顺序：

1. 先运行 `prepare`
2. 在自己的 `wewe-rss` 后台订阅公众号源
3. 填好 `.env`，并完成 `md2wechat` 自己的发布配置
4. 运行 `bootstrap`
5. 运行 `sync`
6. 运行 `candidates`
7. 选好题后再运行 `run --dry-run`
8. 确认无误后真实上传

## 适合谁

- 已经有自己的 `wewe-rss`
- 已经有自己的 `md2wechat`
- 想把候选、改写、配图、草稿上传串成稳定流程

## 不适合谁

- 想零配置直接开跑
- 还没准备自己的订阅源
- 希望仓库静默替你安装外部依赖

## 当前能力

当前仓库已经支持这条最小可用闭环：

1. 读取配置与环境变量
2. 从所有源发现“今日候选”
3. 人工确定今天要做哪一篇
4. 抓取微信文章并提取正文
5. 转换为 Markdown
6. 调用 `md2wechat` 上传草稿
7. 记录处理状态，避免重复处理

当前已经接入大模型改写、微信封面 Prompt 和文生图调用。

## 目录

```text
app/        Python 主控代码
config/     配置模板
scripts/    项目脚本
skill/      对外 Skill 成品壳层
vendor/     随仓库分发的外部 Skill
data/       状态与缓存
output/     中间产物与发布产物
prompts/    提示词模板
```

## Quick Start

1. 先检查前置条件

```bash
python skill/scripts/run_pipeline.py prepare
```

如果这里提示缺少 `wewe-rss`、`md2wechat`、订阅源或配置文件，先补齐，再继续。

如果这里提示 `WEWE_RSS_BASE_URL` 不可达，而你确认 `wewe-rss` 明明已经在本机跑着，再多看一眼当前执行环境：

- 在普通本机终端里，`http://localhost:4000` 往往没问题
- 在某些 sandboxed agent 环境里，`localhost` 可能会被拦住
- 这时不要急着怀疑 `wewe-rss` 挂了，先把 `.env` 里的 `WEWE_RSS_BASE_URL` 改成局域网地址再试

如果你还没有部署外部依赖，可以先看它们的官方仓库：

- `md2wechat`: [https://github.com/geekjourneyx/md2wechat-skill](https://github.com/geekjourneyx/md2wechat-skill)
- `wewe-rss`: [https://github.com/cooderl/wewe-rss](https://github.com/cooderl/wewe-rss)

2. 初始化本地项目

```bash
python skill/scripts/run_pipeline.py bootstrap
```

`bootstrap` 会自动补齐缺失的本地配置模板、安装 Python 依赖，并跑一次基础诊断。

如果这里提示 `WEWE_RSS_BASE_URL` 不可达，先检查两件事：

- `wewe-rss` 服务是否真的在运行
- 当前 `.env` 里的 `WEWE_RSS_BASE_URL` 是否该用 `http://localhost:4000`，还是应该改成 `http://<LAN_IP>:4000`

3. 如果你已经在 `wewe-rss` 里订阅了很多公众号，不想手填 `sources.yaml`，可以先自动同步一次：

```bash
python skill/scripts/run_pipeline.py sync
```

4. 先生成今日候选池

```bash
python skill/scripts/run_pipeline.py candidates
```

候选报告会同时保存到：

- `output/candidates/latest.json`
- `output/candidates/latest.md`

候选清单里的 `source_id` 和 `item_id`，直接拿来填下面的占位符即可。

5. 选中一篇后，先跑不带改写的 dry-run 传输测试：

```bash
python skill/scripts/run_pipeline.py run --source <SOURCE_ID> --item-id <ITEM_ID> --auto-cover --dry-run
```

如果这一步能过，再继续验证改写链：

```bash
python skill/scripts/run_pipeline.py run --source <SOURCE_ID> --item-id <ITEM_ID> --rewrite --auto-cover --dry-run
```

6. 确认无误后，真实上传：

```bash
python skill/scripts/run_pipeline.py run --source <SOURCE_ID> --item-id <ITEM_ID> --rewrite --auto-cover
```

如果改写链因为质量门禁失败，不代表提取、配图和上传链本身坏了。此时先保留不带改写的 dry-run 结果，再决定是否调整 `quality.*` 或换一篇更适合改写的文章。

如果你的 `wewe-rss` feed 路径不是默认规则，可以在 `config/pipeline.yaml` 里配置 `pipeline.feed_url_templates`。
模板支持占位符：`{base_url}`、`{source_id}`、`{source_id_escaped}`、`{limit}`、`{query}`。

`WEWE_RSS_BASE_URL` 默认适合本机直接跑：

- `http://localhost:4000`

如果你希望另一个执行环境也能访问这套服务，可以把 `.env` 里的地址改成局域网地址，例如：

- `http://192.168.1.23:4000`

改写模型可配在 `config/pipeline.yaml` 的 `model` 段，也可直接放在 `.env`。
推荐做法是把密钥放在 `.env`：
- `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL`
- `IMAGE_API_KEY` / `IMAGE_BASE_URL` / `IMAGE_MODEL`
- `pipeline.yaml` 里可只保留模型名和空白占位，不影响使用

改写质量检查可在 `quality` 段调节：
- `min_length_ratio` 与 `max_length_ratio`：限制改写长度偏差
- `require_numbers_consistency`：检查关键数字是否丢失
- `max_missing_numbers`：允许缺失的数字 token 数量阈值，建议监管资讯设为 `0`
- `forbid_new_numbers`：禁止改写时凭空新增数字
- `max_extra_numbers`：允许新增数字 token 的阈值，建议设为 `0`
- `enforce_number_frequency`：校验同一数字是否被写少，防止把重复强调的关键数字写丢
- `require_exact_number_frequency`：如需连“重复提到一次”也严格一致，可开启；默认关闭

这里要注意：

- 当前没有“原文字数超过多少就直接失败”的硬阈值
- 长度门禁看的是改写后和原文的比例，默认要求落在 `0.6 ~ 2.0`
- 更常见的失败原因其实是数字一致性门禁
- 如果原文里数字很多、日期很多、分点很多，这篇文章就更容易在改写阶段被拦下

改写强约束可在 `rewrite` 段调节：
- `rewrite.required`：开启改写后是否必须成功；默认 `true`
- `rewrite.max_attempts`：改写失败或质量不达标时的最大重试次数
- `rewrite.retry_delay_seconds`：每次重试前等待秒数
- `rewrite.retry_on_quality_fail`：质量不达标时是否继续重试
- `rewrite.style`：当前内置 `wechat-structured` 和 `dan-koe`
- `rewrite.humanize.enabled`：是否在风格改写后再做一轮去 AI 痕处理
- `rewrite.humanize.intensity`：`gentle` / `medium` / `aggressive`

状态输出说明：
- 最终 JSON 中的 `status` 是总状态
- `status_reply` 是为人看准备的摘要状态，会单独概括改写、数字校验、尾部清理、封面和发布结果
- `rewrite_quality` 仍保留完整机器校验细节，适合排错或后续自动化判断

自动配图可在 `image` 段开启：
- `image.enabled`: 为 `true` 时在未传 `--cover` 的情况下自动生成封面
- `image.model` / `image.size`: 控制文生图模型与尺寸
- `image.fallback_models`: 主模型不可用时按顺序回退
- `image.fallback_to_source_cover`: AI 出图失败时回退下载原文封面图
- `image.base_url` / `image.api_key`: 可单独配置；留空时会按 `IMAGE_* -> model.* -> LLM_*` 顺序回退
- `image.wechat_cover`: 微信封面图 payload/profile 配置，支持：
  - `style`: `swiss` / `editorial`
  - `accent`: `ikb` / `lemon-yellow` / `lemon-green` / `safety-orange` / `none`
  - `variant`: `wechat-21x9` / `wechat-share-1x1`
  - `render_sizes`: 图像接口请求尺寸
  - `output_sizes`: 最终落盘尺寸；`wechat-21x9` 会裁切为真实 21:9
  - `profiles`: 可把现有 `sources.yaml` 的 `cover_profile` 映射到上面这些枚举

微信封面图模块：
- 外部 skill 已 vendoring 到 `vendor/wechat-cover-skill/`
- 项目内接入链路是：上游文章/Markdown -> 归一化 payload -> schema 校验 -> `build-prompt.mjs` -> 图像生成调用
- 生成结果会按 `slug.variant.style.accent.*` 命名，避免不同样式或比例互相覆盖
- `run-once --auto-cover` 会自动走这套链路
- 也可以单独调用：
  - `python -m app.main generate-cover --markdown /path/to/article.md`
  - `python -m app.main generate-cover --source <SOURCE_ID>`

正文图片策略建议：
- 默认 `content.keep_original_images: false`，会剥离原文正文图片，降低版权与坏链风险
- 建议只使用生成封面图，正文图走自有素材或后续单独生成
- `content.strip_footer: true` 可裁剪原文尾部（推荐阅读/原作者署名等）
- `content.unified_footer` 预留统一署名文案（你确认后再填）

多源抓取与新鲜度筛选：
- `sync-sources` 会直接读取 `wewe-rss` 的 `/feeds` 源列表，并合并写回 `config/sources.yaml`
- `daily-candidates` 会从所有 enabled 源抓最近 `pipeline.fetch_limit` 篇，合并成候选池，并产出一份可读版 `output/candidates/latest.md`
- `run-once` 适合在你已经选定一篇后继续跑生产链
- `fetch-latest` / `run-once` 可不传 `--source`，系统会在所有 enabled 源里自动挑选
- `freshness.max_age_hours` 控制“最新鲜”窗口
- `freshness.pick_mode`:
  - `latest`: 选时间最新
  - `source_order`: 按 `sources.yaml` 顺序优先

## 当前 CLI

```bash
python -m app.main doctor
python -m app.main prepare
python -m app.main bootstrap
python -m app.main sync-sources
python -m app.main daily-candidates
python -m app.main daily-candidates --include-processed
python -m app.main daily-candidates --source <SOURCE_ID>
python -m app.main fetch-latest --source <SOURCE_ID>
python -m app.main fetch-latest
python -m app.main extract-url "https://mp.weixin.qq.com/s/xxxx"
python -m app.main run-once --source <SOURCE_ID>
python -m app.main run-once --source <SOURCE_ID> --item-id <ITEM_ID> --rewrite --auto-cover --dry-run
python -m app.main run-once --force --rewrite --auto-cover
python -m app.main run-once --source <SOURCE_ID> --cover /path/to/cover.jpg
python -m app.main run-once --source <SOURCE_ID> --auto-cover --rewrite --dry-run
python -m app.main run-once --source <SOURCE_ID> --rewrite --dry-run
```

## 已知假设

- `wewe-rss` 的具体 feed 路径在不同部署里可能有差异，当前实现会按一组常见路径顺序尝试。
- `md2wechat` 的实际 CLI 参数可能因本地版本不同略有区别，当前先按 `convert <markdown> --draft [--cover ...]` 形式封装。
- 第一版优先把链路串起来，不追求微信页面结构的全量兼容。
