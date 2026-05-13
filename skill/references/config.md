# Config

## 配置分两层

### 通用可复用部分

这些应该保留在 Skill 说明或仓库模板里，不绑定某个人：

- `config/pipeline.yaml` 的工作流结构
- `rewrite.style`、`quality.*` 这类改写规则
- `image.wechat_cover` 这类封面图规则
- `scripts/` 和 `skill/scripts/` 这些执行入口

### 个人或部署相关部分

这些不应该写死在 Skill 里，而应由使用者自己提供：

- `.env` 里的 API Key / Secret
- `WEWE_RSS_BASE_URL`
- `MD2WECHAT_RUN_SCRIPT`
- `config/sources.yaml` 里的订阅源选择
- 默认使用哪个 `cover_profile` / `rewrite_profile`

这里要特别强调一件事：

`config/sources.yaml` 不是这套 Skill 替别人“创造内容源”的地方，它只是把你已经在 `wewe-rss` 里订阅好的源同步过来，再决定哪些启用。

## `.env`

- `WEWE_RSS_BASE_URL`: `wewe-rss` 服务地址，可用 `http://localhost:4000` 或 `http://<LAN_IP>:4000`
- `MD2WECHAT_RUN_SCRIPT`: `md2wechat` 的运行脚本路径，支持 `run.sh`、`run.cmd`、`run.ps1`
- `MD2WECHAT_RUN_SH`: 兼容旧变量名，仍可继续使用
- `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL`: 改写阶段使用
- `IMAGE_API_KEY` / `IMAGE_BASE_URL` / `IMAGE_MODEL`: 封面图阶段使用
- `TZ`: 时区，默认 `Asia/Shanghai`

## 还需要的 `md2wechat` 发布配置

发布到微信公众号草稿箱时，还需要 `md2wechat` 自己能读取到公众号发布配置。

推荐做法：

```bash
bash /path/to/md2wechat/scripts/run.sh config init
```

如果你在 Windows 原生环境下使用，也可以把 `MD2WECHAT_RUN_SCRIPT` 指向 `run.cmd` 或 `run.ps1`。

然后在 `md2wechat` 自己的配置里完成公众号发布配置。

注意：

- `werss2md` 不直接消费 `WECHAT_APPID` / `WECHAT_SECRET`
- 当前发布适配层会优先让 `md2wechat` 读取它自己的配置，而不是依赖 `werss2md` 的 `.env`

## 推荐最小起步配置

适合第一次复用这套 Skill 的人先跑通：

```env
WEWE_RSS_BASE_URL=http://localhost:4000
MD2WECHAT_RUN_SCRIPT=/absolute/path/to/md2wechat/scripts/run.sh
LLM_API_KEY=your_key_here
LLM_BASE_URL=https://your-llm-provider.example.com/v1
LLM_MODEL=gpt-5.4
IMAGE_API_KEY=your_image_key_here
IMAGE_BASE_URL=https://your-image-provider.example.com/v1/images/generations
IMAGE_MODEL=gpt-image-2
TZ=Asia/Shanghai
```

如果不是本机跑，而是让另一个环境来执行，把 `WEWE_RSS_BASE_URL` 改成局域网地址。

第一次填完后，建议立刻运行：

```bash
python skill/scripts/run_pipeline.py prepare
```

它会告诉你当前卡在 `wewe-rss`、`md2wechat`、订阅源，还是本地配置文件。

## `config/sources.yaml`

推荐先保持为空，或先通过 `sync-sources` 自动生成，再人工决定哪些源启用。

可选长期字段：

- `rewrite_profile`
- `cover_profile`

推荐第一版先把真实订阅源同步进来，确认可跑通后再按需保留更多源。

如果用户自己的 `wewe-rss` 里还没有订阅任何公众号，这里就不会有可同步的内容。

## `config/pipeline.yaml`

- `pipeline.fetch_limit`: 每次拉取文章数量
- `pipeline.skip_if_processed`: 是否跳过已处理文章
- `freshness.max_age_hours`: 候选池的新鲜度窗口
- `freshness.pick_mode`: `latest` 或 `source_order`
- `publish.upload_draft`: 是否执行草稿上传
- `rewrite.required`: 开了改写后是否必须成功
- `image.fallback_to_source_cover`: AI 出图失败时是否回退原文封面

推荐做法：

- `model.base_url` 和 `model.api_key` 默认留空
- 优先通过 `.env` 里的 `LLM_BASE_URL` / `LLM_API_KEY` 驱动改写
- `image.base_url` 和 `image.api_key` 也建议留空，优先走 `.env`

## 配置注意

- 不要把真实账号密钥提交进仓库
- 不要把某个局域网 IP 当成所有环境都适用的默认值
- 如果 `sync` 后没有源，先检查自己的 `wewe-rss` 是否已经订阅公众号
