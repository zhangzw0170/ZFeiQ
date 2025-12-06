ZFeiQ — AI Coding Agent 操作手册
# ZFeiQ — AI 代码助手 快速指南

目的：让新进 AI 编码代理快速上手本仓库，理解架构边界、关键文件、运行/测试命令与常见改动注意点。

## 快速架构与边界
- 引擎（核心）：`core/engine.py`（类 `ZFeiQCore`）负责节点发现、会话管理、事件分发与持久化；上层 `cli/` 与 `gui/` 通过事件回调与其交互。
- 会话与加密：`core/session.py` （类 `Session`）实现握手 FSM（例如 `KX1/KX2/ENCREADY` 流程），使用 X25519 + HKDF + ChaCha20-Poly1305，密文格式约定在 `core/session.py` 与 `core/protocol.py` 中。
- 传输层：`core/transport.py`（`UdpTransport`）封装 UDP 广播/单播线程；IP/iface 推断逻辑在此处，广播相关调试日志以 `[DEBUG] send_broadcast` 标记。

## 关键文件与职责（先看这些）
- `core/engine.py` — 引擎主逻辑与事件队列。
- `core/session.py` — 握手、密钥派生、加解密规则。
- `core/protocol.py` — IPMSG 报文构建/解析与扩展字段位置（`ext` 区域，`\0` 分割）。
- `core/events.py` — 事件常量；所有事件名在此统一管理。
- `core/state.py` — `NodeRegistry`、节点信息持久化与查找逻辑。
- `cli/shell.py` — CLI 命令实现与 `ZFeiQShell.on_core_event` 的事件处理示例。
- `gui/bridge.py` — GUI 与引擎的事件桥接，查看如何把事件映射到 UI。

## 常用运行与调试命令
```
python3 cli/main.py [--bind 127.0.0.X] [--port 2425]   # 启动 CLI
python3 gui/main.py                                   # 启动 GUI
python3 test/demo_p2p_secure_loopback.py               # 验证加密会话
python3 test/demo_filetransfer.py                      # 文件传输演示
python3 test/auto_test_requirements.py                 # 三节点自动校验脚本
```

## 项目约定与模式（请遵守）
- 事件驱动：使用 `ZFeiQCore.set_event_handler(handler)` 订阅事件，事件形态为 `Event(type, data)`。
- 配置与持久化：`common/config.json` 与 `common/groups.json` 由引擎自动读写，修改 schema 时需同步引擎的 `_load_*`/`_save_*` 实现。
- 日志/调试：`EV_LOG_INFO` 用于事件日志；开启 `debug cipher on`（代码内或调试命令）会把密文相关日志输出，便于握手/加密调试。

## 修改敏感区域（需要额外审查）
- 握手流程、密钥派生函数（例如 `hkdf_sha256`）、密文格式或会话状态机改动必须附带示例日志与回归步骤。
- 改动事件签名、`NodeRegistry` 数据模型或跨线程共享结构时，请提供 CLI/GUI 验证步骤及影响范围（尤其参考 `test/auto_test_requirements.py`）。

## 常见小任务示例（查这些文件做对应改动）
- 新增事件：修改 `core/events.py` -> 在 `core/engine.py` 广播 -> 更新 `cli/shell.py` 与 `gui/bridge.py` 的处理。
- 新增 CLI 命令：在 `cli/shell.py` 添加解析与 handler，重用 `ZFeiQCore` 提供的 API。
- 调试握手问题：在 `core/session.py` 增加详细日志（KX1/KX2），用 `test/demo_p2p_secure_loopback.py` 验证。

## 其它注意点与资源
- 文件传输映射：查看 `core/filetransfer.py` 中 `_attach_map` 的使用与端口保留逻辑。
- OCR：懒加载实现位于 `core/ocr.py`，运行 OCR 需 `onnxruntime` 或相应运行时。

---
请检查这份精简版：我已保留原有重要警告与运行示例，并把可操作要点提炼为“看哪几个文件、跑哪些命令、在哪些改动要审查”。如果你希望我把某部分扩展为具体示例（例如“如何新增事件”的代码片段或一组验证步骤），告诉我想要的深度，我会继续更新。
