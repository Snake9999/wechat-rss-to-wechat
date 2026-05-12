# Setup

这个 Skill 的目标是让你用最少配置把项目初始化，并进入“先候选、后生产”的日常节奏。

## 初始化顺序

1. 先确认前置条件已经准备好
2. 先运行 `prepare`
3. 复制默认配置模板
4. 填好必需的 key 和路径
5. 在自己的 `wewe-rss` 里订阅公众号源
6. 安装 Python 依赖
7. 运行环境诊断
8. 同步源并生成候选池
9. 选定一篇后再跑 dry-run
10. 确认无误后真实上传

## 项目与 Skill 的关系

- Skill 负责让你更容易启动和排错
- 仓库承载真正的抓取、转换、改写和发布逻辑
- 长期状态、个人密钥和复杂实现都留在仓库里

## 首次运行建议

首次优先验证四件事：

1. 你的 `wewe-rss` 已经订阅好公众号
2. `wewe-rss` 能返回订阅源与文章元信息
3. 候选池能正确生成
4. `md2wechat` 能上传一个草稿

## 第一次使用前必须完成的准备

### 1. 先配置你自己的 `wewe-rss`

这套 Skill 不会替别人凭空生成订阅源。

外部使用者第一次来时，必须先在自己的 `wewe-rss` 里完成公众号订阅。只有订阅完成后，`sync` 才有东西可同步。

如果这一步没做：

- `sync` 可能只会返回空列表
- `candidates` 也不会有可选内容

所以正确顺序不是“先 sync 再去想订阅源”，而是：

`先在 wewe-rss 后台订阅自己的源 -> 再 sync -> 再 candidates`

### 2. 再填必须的 key

最少要确认这几类配置：

- 改写：`LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL`
- 配图：`IMAGE_API_KEY` / `IMAGE_BASE_URL` / `IMAGE_MODEL`
- 发布：先在 `md2wechat` 自己的配置里完成公众号发布配置
- 路径：`MD2WECHAT_RUN_SH`
- 服务地址：`WEWE_RSS_BASE_URL`

如果 `wewe-rss` 或 `md2wechat` 还没装好，先停在这里，不要直接往下跑。
可以先让 Agent 帮你判断是：

- 连接已有部署
- 还是按官方仓库重新部署

## 推荐首次命令

```bash
./skill/scripts/run_pipeline.sh prepare
./skill/scripts/run_pipeline.sh bootstrap
./skill/scripts/run_pipeline.sh sync
./skill/scripts/run_pipeline.sh candidates
./skill/scripts/run_pipeline.sh run --source <SOURCE_ID> --item-id <ITEM_ID> --auto-cover --dry-run
./skill/scripts/run_pipeline.sh run --source <SOURCE_ID> --item-id <ITEM_ID> --rewrite --auto-cover --dry-run
```

## 推荐验证顺序

第一次给别人用时，建议区分成两层验证：

1. 内容链验证
   `run --source <SOURCE_ID> --item-id <ITEM_ID> --auto-cover --dry-run`
   这一步先验证正文提取、配图、dry-run 上传链是否整体成立
2. 传输链验证
   在第一步通过后，再继续验证：
   `run --source <SOURCE_ID> --item-id <ITEM_ID> --rewrite --auto-cover --dry-run`
   这一步验证“提取 -> 改写 -> 配图 -> dry-run 上传”是否成立

这样就能分清是“工作流坏了”，还是“改写质量门槛太严格”。

## 给外部使用者的第一句说明

如果这是别人第一次接触这套 Skill，建议直接这么说：

1. 先确认 `wewe-rss` 和 `md2wechat` 已经可用
2. 再在你自己的 `wewe-rss` 后台订阅公众号源
3. 再把 `.env` 和环境变量里的 key 配好
4. 先跑 `prepare`
5. 如果缺本地配置，再跑 `bootstrap`
6. 再跑 `sync` 和 `candidates`
7. 你选好题以后，再跑 `run --dry-run`
8. 确认没问题后再真实上传

这样对方不会一上来就被一堆工程细节吓住。

## 常见卡点

- `candidates` 和 `run` 在执行中可能持续几十秒没有中间输出
- `rewrite.required=true` 时，第一次 dry-run 可能会因为数字一致性校验失败而退出
- 这不一定代表项目坏了，很多时候只是说明当前文章不适合直接通过强约束改写
