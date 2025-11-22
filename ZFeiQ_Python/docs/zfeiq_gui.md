# zfeiq_gui — 文档

目标：GUI 前端通过 `CoreBridge` 与 `zfeiq_core` 交互，负责把 core 事件映射为 Qt Signals 并把 UI 操作转为 core API 调用。

当前状态

- `zfeiq_gui/core_bridge.py`：最小的回调适配器示例；日后应改为跨线程安全的 Qt Signal 适配。
- UI 仍保留旧代码（`zfeiq_gui/`），后续步骤为把界面事件替换为对 `CoreBridge` 的调用。

下一步

- 把 `CoreBridge.on(topic, callback)` 转为 Qt Signals 并确保线程安全（使用 `QMetaObject.invokeMethod` 或 `pyqtSignal`）。
- 在 GUI 启动时调用 `core.ensure_keys(...)` 并在设置页展示公钥指纹。
