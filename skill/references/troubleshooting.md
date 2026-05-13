# Troubleshooting

## 使用顺序总提醒

先按这个顺序排查，不要跳步：

1. 自己的 `wewe-rss` 里是否已经订阅公众号
2. `.env` 和环境变量里的 key 是否已经填好
3. `prepare` 是否已经指出缺什么
4. `doctor` 是否通过
5. `sync` 是否能拿到源
6. `candidates` 是否能生成候选
7. `run --dry-run` 是否能走完

## 常见失败与含义

### `sync` 返回空列表

常见原因：

- 自己的 `wewe-rss` 里还没有订阅任何公众号
- `WEWE_RSS_BASE_URL` 指向了错误地址

先做什么：

- 先去 `wewe-rss` 后台订阅自己的源
- 再重新运行 `sync`

### `candidates` 没有候选

常见原因：

- 没有已启用的源
- 所有文章都超出了新鲜度窗口
- `sync` 还没有成功执行

先做什么：

- 看 `output/candidates/latest.json` 里的 `skipped`
- 检查 `config/sources.yaml` 是否有 `enabled: true`
- 检查 `freshness.max_age_hours`

### `failed_rewrite_required`

含义：

- 改写阶段执行了
- 但改写结果没有通过质量门禁
- 因为 `rewrite.required=true`，流程被主动中止

这不一定代表项目坏了。

先做什么：

- 查看 `data/state/run_history.jsonl` 里的 `rewrite_quality`
- 先用不带 `--rewrite` 的 `--dry-run` 验证传输链
- 再决定是否放宽数字一致性或长度约束

### `failed_invalid_ip_whitelist`

含义：

- 微信接口拒绝了当前出口 IP
- 草稿上传链路本身未必有问题

先做什么：

- 把当前出口 IP 加入微信白名单
- 然后重新运行真实上传命令

### `all image models failed`

含义：

- 封面图阶段已经触发
- 但当前图片 provider 或模型不可用

先做什么：

- 检查 `IMAGE_API_KEY` / `IMAGE_BASE_URL` / `IMAGE_MODEL`
- 看 `run_history.jsonl` 里的 `cover.tried_models`
- 必要时先关闭改写或改用原文封面回退路径

### `MD2WECHAT_RUN_SCRIPT` 不可用

常见原因：

- 路径写错
- `md2wechat` 没有安装完成

先做什么：

- 检查 `.env` 里的 `MD2WECHAT_RUN_SCRIPT`
- 手动执行一次：
  `bash /path/to/md2wechat/scripts/run.sh --help`
- 如果你是 Windows 原生环境，也可以改成测试 `run.cmd` 或 `run.ps1`

## 先看哪里

- 首次使用问题：先看 `python skill/scripts/run_pipeline.py prepare`
- 环境问题：先看 `python skill/scripts/run_pipeline.py doctor`
- 候选问题：先看 `output/candidates/latest.md` 和 `latest.json`
- 改写问题：先看 `data/state/run_history.jsonl` 的 `rewrite` / `rewrite_quality`
- 配图问题：先看 `run_history.jsonl` 的 `cover`
- 发布问题：先看 `run_history.jsonl` 的 `status` 和微信白名单
