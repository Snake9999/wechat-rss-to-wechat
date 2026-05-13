# 发布说明：跨平台入口与 Windows 首次使用支持

这次更新，主要做了两件对普通使用者更友好的事情：

1. 把主入口统一成了 Python 命令，不再要求所有人都先理解 shell 脚本差异
2. 给 Windows 用户补上了更清晰的首次使用路径

## 这次更新了什么

- 新增统一入口：
  `python skill/scripts/run_pipeline.py ...`
- 新增 Windows 启动包装：
  `skill\scripts\run_pipeline.cmd`
- `md2wechat` 的运行脚本现在支持：
  - `run.sh`
  - `run.cmd`
  - `run.ps1`
- README 已补充 Windows 首次使用指南

## 这对你意味着什么

如果你是 `macOS` 或 `Linux` 用户：

- 现在可以直接跟着 README 用 Python 入口跑
- 不需要先关心 `.sh` 里的细节

如果你是 `Windows` 用户：

- 如果你的 `md2wechat` 提供了 `run.cmd` 或 `run.ps1`，可以直接在 Windows 原生环境下使用
- 如果你的 `md2wechat` 只有 `run.sh`，建议改用 `WSL`

## 推荐首次使用顺序

1. 先部署好你自己的 `wewe-rss`
2. 先部署好你自己的 `md2wechat`
3. 运行：
   `python skill/scripts/run_pipeline.py prepare`
4. 按提示补齐 `.env` 和发布配置
5. 继续运行：
   - `python skill/scripts/run_pipeline.py bootstrap`
   - `python skill/scripts/run_pipeline.py sync`
   - `python skill/scripts/run_pipeline.py candidates`
6. 选好题后，先做一次不带改写的 dry-run
7. 确认链路没问题后，再跑改写和真实上传

## 现在仍然需要你自己准备的东西

- 你自己的 `wewe-rss`
- 你自己的 `md2wechat`
- 你自己的公众号订阅源
- 你自己的 API key 和发布配置

这套仓库负责把流程串起来，但不会静默替你安装外部依赖，也不会替你生成订阅源。

## 一句话总结

这次不是新增复杂功能，而是把原来更偏 `macOS / Unix` 的使用方式，整理成了更适合普通用户上手的跨平台入口。
