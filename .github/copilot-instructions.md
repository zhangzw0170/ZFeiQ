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

# ZFeiQ — AI 代码代理快速指南

目的：为进入仓库的自动化/交互式 AI 代理提供最少且高价值的定位信息，帮助快速做出安全、可审的修改。

**一行快照**：事件驱动的 P2P 引擎 + 会话加密（core/*），上层接口分别为 `NZFeiQ/cli`（CLI）和 `NZFeiQ/gui`（GUI），常用测试脚本在 `test/`。

**关键区域（优先阅读）**
- 引擎：`core/engine.py`（`ZFeiQCore`）——事件分发、节点注册、持久化入口。
- 会话/加密：`core/session.py`、`core/crypto.py` —— 握手状态机（KX1/KX2）、密钥派生（HKDF）、ChaCha20-Poly1305。
- 报文协议：`core/protocol.py` —— IPMSG 报文格式与 `ext` 字段位置约定。
- 传输：`core/transport.py` —— UDP 广播/单播及 iface 推断（查看 `[DEBUG] send_broadcast` 日志标识）。

**常用命令（在仓库根目录运行）**
- 启动 CLI: `python3 NZFeiQ/cli/main.py [--bind 127.0.0.X] [--port 2425]`
- 启动 GUI: `python3 NZFeiQ/gui/main.py`
- 快速运行示例/回归: `python3 test/demo_p2p_secure_loopback.py`, `python3/test/demo_filetransfer.py`, `python3/test/auto_test_requirements.py`

**项目约定（必须遵守的可发现规则）**
- 事件中心化：所有事件名在 `core/events.py`，订阅通过 `ZFeiQCore.set_event_handler(handler)`。
- 配置文件：`common/config.json` 与 `common/groups.json` 由引擎读写，改动 schema 时同步 `_load_*`/`_save_*`。
- 密钥与敏感数据：`common/keys/` 存放密钥材料，避免在提交中泄露实际私钥。

**敏感/高风险区域（改动前请附回归步骤）**
- 握手 & 密钥派生：`core/session.py`（更改必须包含握手日志示例和回归脚本）。
- 报文与兼容性：`core/protocol.py`（任何格式变动可能破坏兼容节点）。
- 跨线程共享/序列化：`core/state.py`（`NodeRegistry`）、`core/transport.py`（线程/iface 逻辑）。

**常见变更模式（示例操作流程）**
- 新增事件：编辑 `core/events.py` -> 在 `core/engine.py` 广播 -> 更新 `NZFeiQ/cli/shell.py` 与 `NZFeiQ/gui/bridge.py` 的处理函数。
- 新增 CLI 命令：在 `NZFeiQ/cli/shell.py` 添加解析与 handler，尽量复用 `ZFeiQCore` 的方法。

**测试/验证要点**
- 调试握手：在 `core/session.py` 打开详细日志（KX1/KX2），用 `test/demo_p2p_secure_loopback.py` 验证两节点成功建立会话并能互相加密通信。
- 文件传输：查 `core/filetransfer.py` 中 `_attach_map` 与端口保留逻辑，使用 `test/demo_filetransfer.py` 复核。

如需更多细节（例如示例代码片段、具体事件名清单或回归脚本），请告诉我想要的深度，我会把对应片段添加进来。
