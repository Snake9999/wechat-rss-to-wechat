# Prerequisites

在开始跑这套 Skill 之前，先确认下面这些东西已经准备好。

## 必须先有的东西

1. 一个可访问的 `wewe-rss`
2. 一个可用的 `md2wechat`
3. 你自己的公众号订阅源
4. 必要的环境变量和 key

## 你需要自己准备什么

- `WEWE_RSS_BASE_URL`
- `MD2WECHAT_RUN_SH`
- `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL`
- `IMAGE_API_KEY` / `IMAGE_BASE_URL` / `IMAGE_MODEL`
- `md2wechat` 自己的发布配置（公众号 AppID / Secret）

## 第一次没有装好时怎么处理

如果环境里还没有 `wewe-rss` 或 `md2wechat`：

- 先告诉用户缺的是哪一项
- 先问用户是要“连接已有部署”，还是“从官方仓库重新部署”
- 不要静默 clone 和覆盖已有安装

官方仓库：

- `md2wechat`: [https://github.com/geekjourneyx/md2wechat-skill](https://github.com/geekjourneyx/md2wechat-skill)
- `wewe-rss`: [https://github.com/cooderl/wewe-rss](https://github.com/cooderl/wewe-rss)

## 对这套 Skill 来说，什么叫“可用”

### `wewe-rss` 可用

- `WEWE_RSS_BASE_URL` 能访问
- 你已经在 `wewe-rss` 后台订阅了自己的公众号源
- `sync` 能同步出源列表

### `md2wechat` 可用

- `MD2WECHAT_RUN_SH` 指向有效的 `run.sh`
- `md2wechat` 可以读取公众号发布所需的配置
- `run --dry-run` 能完成转换链路

推荐做法：

- 先执行 `bash /path/to/md2wechat/scripts/run.sh config init`
- 在 `md2wechat` 自己的配置里完成公众号发布配置

## 一句话判断

如果这两项还没准备好，就先别直接跑生产链，先补前置条件。

## 第一个命令

第一次进入仓库时，先运行：

```bash
./skill/scripts/run_pipeline.sh prepare
```

这个命令只做检查与引导，不会静默替你安装外部依赖。
