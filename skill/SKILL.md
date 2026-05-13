---
name: wechat-rss-to-wechat
description: 安装、初始化、诊断并运行一套基于 wewe-rss 与 md2wechat 的微信公众号内容工作流。适用于同步订阅源、生成每日候选、人工选题、提取正文、改写、生成封面图，并上传到微信公众号草稿箱。
---

# WeChat RSS to WeChat

当用户想初始化、检查或运行这套微信公众号内容工作流时使用本 Skill。

优先读取：

- `references/prerequisites.md`
- `references/setup.md`
- `references/config.md`
- `references/workflow.md`
- `references/troubleshooting.md`

## 触发场景

- 帮我初始化这套微信公众号自动化项目
- 帮我检查环境能不能跑
- 我第一次用，先帮我检查缺什么
- 帮我同步 `wewe-rss` 订阅源
- 帮我生成今日候选池
- 我已经选好题了，继续改写并发草稿
- 帮我只测试正文提取或只测试草稿上传

## 工作原则

- Skill 负责入口、参数约定、初始化、诊断和命令封装
- 仓库负责抓取、提取、转换、改写、配图、发布和状态管理
- 默认工作节奏是：`先候选，再选题，再进入生产链`
- 保持 Skill 薄，长期状态与复杂业务逻辑都留在仓库里

## 默认动作

1. 先确认 `references/prerequisites.md` 里的前置条件
2. 先运行 `python skill/scripts/run_pipeline.py prepare`
3. 如果缺本地配置，再运行 `python skill/scripts/run_pipeline.py bootstrap`
4. 然后运行 `python skill/scripts/run_pipeline.py doctor`
5. 日常先看候选，再跑生产链

## 日常入口

- 准备检查：`python skill/scripts/run_pipeline.py prepare`
- 初始化：`python skill/scripts/run_pipeline.py bootstrap`
- 诊断：`python skill/scripts/run_pipeline.py doctor`
- 同步源：`python skill/scripts/run_pipeline.py sync`
- 生成候选：`python skill/scripts/run_pipeline.py candidates`
- 先验证链路：`python skill/scripts/run_pipeline.py run --source <SOURCE_ID> --item-id <ITEM_ID> --auto-cover --dry-run`
- 再验证改写：`python skill/scripts/run_pipeline.py run --source <SOURCE_ID> --item-id <ITEM_ID> --rewrite --auto-cover --dry-run`
- 真实上传：`python skill/scripts/run_pipeline.py run --source <SOURCE_ID> --item-id <ITEM_ID> --rewrite --auto-cover`

## 推荐对话方式

- `我是第一次用，先告诉我需要准备哪些 key 和账号`
- `我还没有自己的订阅源，先引导我去配置 wewe-rss`
- `先帮我同步订阅源，再生成今天的候选清单`
- `把候选清单发我，我来选题`
- `我选第 3 条了，继续跑改写、配图和草稿`
- `先 dry-run 一次，我想确认链路没问题`
- `这次为什么失败了，先帮我判断卡在哪一层`

## 决策边界

- 如果用户还没有自己的 `wewe-rss` 订阅源，先引导他去 `wewe-rss` 后台完成订阅，再谈 `sync`
- 如果用户还没填 `LLM`、`IMAGE`、`WECHAT` 相关密钥，先引导补配置，不直接进入生产链
- 第一次使用时，先跑 `prepare`，不要一上来就直接跑生产链
- 如果用户还没确定今天做哪篇，优先进入候选模式，不直接发布
- 如果用户已经给了 `source_id + item_id`，直接进入生产链
- 如果用户只想验证链路，优先建议先跑不带 `--rewrite` 的 `--dry-run`
