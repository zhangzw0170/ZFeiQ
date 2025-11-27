# zfeiq_cli — 文档

目标：轻量 CLI 前端，负责参数解析、控制台渲染、并调用 `zfeiq_core` API。

当前状态

- `zfeiq_cli/cli_core.py`：示例适配器，展示如何订阅 `EventBus` 事件并调用 `ZFeiQCore`。
- CLI 的老实现（位于上层 `zfeiq_cli/`）仍可作为参考，不要直接修改；我们将逐步把调用点替换为 `ZFeiQCore`。

下一步

- 在 CLI 启动路径调用 `core.ensure_keys(...)`。
- 将现有命令（/file send、/file accept 等）逐步重定向到 `zfeiq_core` 的 FileService API（未来实现）。
