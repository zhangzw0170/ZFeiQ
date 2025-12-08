`.github/copilot-instructions.md` — ZFeiQ AI 代理快速上手

目的：让 AI 代理能在最短时间内安全、可审地修改仓库，重点提示高风险区域、常用命令、以及项目特有约定。

**快速命令**
- **启动 GUI**: `python3 NZFeiQ/gui/main.py`
- **启动 CLI**: `python3 NZFeiQ/cli/main.py [--bind 127.0.0.X] [--port 2425]`
- **关键演示/回归**: `python3 test/demo_p2p_secure_loopback.py`, `python3 test/demo_filetransfer.py`, `python3 test/auto_test_requirements.py`

**必须阅读的核心文件（快速理解系统）**
- `NZFeiQ/core/engine.py` — `ZFeiQCore`：节点发现、事件分发与持久化（系统中枢）。
- `NZFeiQ/core/session.py`, `NZFeiQ/core/crypto.py` — 会话与加密（握手 FSM、密钥派生、加密流），改动属高风险。
- `NZFeiQ/core/transport.py` — UDP 广播/单播与接口选择（网络层实现）。
- `NZFeiQ/core/protocol.py` — 报文构建/解析；扩展字段 `ext` 使用 `\0` 分隔，任何格式改动需兼容说明。
- `NZFeiQ/core/state.py` — 节点与状态序列化，注意并发访问。
- `NZFeiQ/core/events.py` — 事件常量与载荷格式。

**项目约定与限制（务必遵守）**
- **私钥/密钥**：`common/keys/` 下不要提交真实密钥。如需修改密钥格式，必须附示例密钥与回归脚本。
- **配置 schema**：`common/config.json` 与 `common/groups.json` 的 schema 变更需同时更新引擎的 `_load_*` / `_save_*` 实现。
- **报文兼容性优先**：修改 `protocol.py` 或任何会影响线上兼容性的改动，需提供兼容策略、回归脚本并在 PR 中列明影响范围。

**常见开发模式（示例）**
- 增加事件：编辑 `NZFeiQ/core/events.py` → 在 `NZFeiQ/core/engine.py` 广播 → 在 `NZFeiQ/cli/shell.py` 或 `NZFeiQ/gui/bridge.py` 添加处理器。
- 新 CLI：在 `NZFeiQ/cli/shell.py` 增加解析与 handler，调用 `ZFeiQCore` API。

**调试/回归要点**
- 验证握手/加密：运行 `python3 test/demo_p2p_secure_loopback.py` 并保存握手日志供审查。
- 跟踪日志关键词：`[DEBUG] send_broadcast`, `cipher`, `handshake`。
- 文件传输问题：阅读 `NZFeiQ/core/filetransfer.py` 的 `_attach_map`、端口与重试实现。

**PR 要求（高风险改动）**
- 对 `session.py` / `crypto.py` / `protocol.py` 的改动必须同时包含：回归脚本、示例运行日志、兼容说明与受影响模块清单。

如需我把某个模块（例如 `session`、`protocol` 或 `filetransfer`）的事件清单、握手日志样例或回归脚本模版加入本文件，请指出要补充的模块。
ZFeiQ — AI Coding Agent 操作手册（简版）
```instructions
ZFeiQ — AI 编码代理 使用指南（精简）

目标：让 AI 代理在首小时内可安全、可审地修改仓库，避免破坏握手/协议或跨组件不兼容的改动。

**架构速览**
- **引擎核心：** `NZFeiQ/core/engine.py`（`ZFeiQCore`）负责节点发现、事件分发与持久化；CLI/GUI 通过事件与其交互。
- **会话/加密：** `NZFeiQ/core/session.py` 与 `NZFeiQ/core/crypto.py`，实现握手 FSM（KX1→KX2→ENCREADY）、X25519+HKDF、ChaCha20-Poly1305。此处改动属高风险，必须附回归脚本与握手日志。
- **传输：** `NZFeiQ/core/transport.py`（`UdpTransport`）管理 UDP 广播/单播与接口选择；日志关键字包括 `[DEBUG] send_broadcast`。
- **状态/节点：** `NZFeiQ/core/state.py`（`NodeRegistry`）集中节点信息与序列化；并发访问请注意线程安全。

**关键工作流 / 常用命令**
- 启动 CLI（交互）： `python3 NZFeiQ/cli/main.py [--bind 127.0.0.X] [--port 2425]`
- 启动 GUI： `python3 NZFeiQ/gui/main.py`
- 回归/演示脚本：
	- 加密回归： `python3 test/demo_p2p_secure_loopback.py`
	- 文件传输 demo： `python3 test/demo_filetransfer.py`
	- 多节点自动校验： `python3 test/auto_test_requirements.py`

**项目约定与注意事项（针对 AI 代理）**
- 配置/持久化：`common/config.json`、`common/groups.json`。若变更 schema，务必同步引擎的 `_load_*` / `_save_*` 实现。
- 密钥：`common/keys/`，禁止提交真实密钥；变更格式需提供示例密钥与回归脚本。
- 报文兼容性：报文构建/解析在 `NZFeiQ/core/protocol.py`，扩展区 `ext` 用 `\0` 分隔。任何格式变更需附兼容策略与测试。
- 事件驱动：事件常量在 `NZFeiQ/core/events.py`，引擎通过 `ZFeiQCore.set_event_handler(handler)` 广播 `Event(type, data)`；查看 `NZFeiQ/cli/shell.py` 与 `NZFeiQ/gui/bridge.py`。

**高风险改动流程（必遵）**
1. 在本地运行 `python3 test/demo_p2p_secure_loopback.py` 验证握手/加密改动。
2. 如改报文格式，提交兼容说明与回归脚本（示例：复用 `test/demo_*`）。
3. 在 PR 描述中列出受影响模块和回归测试步骤。

**代码模式与示例**
- 增加事件：编辑 `core/events.py` → 在 `core/engine.py` 广播 → 更新 `NZFeiQ/cli/shell.py` 与 `NZFeiQ/gui/bridge.py` 的处理。
- 新 CLI 命令：在 `NZFeiQ/cli/shell.py` 增加解析与 handler，使用 `ZFeiQCore` 的 API 发起操作（参见已实现命令）。

**调试/快速定位技巧**
- 搜日志关键字：`[DEBUG] send_broadcast`、`cipher` 相关条目用于追踪广播与握手。
- 文件传输：参考 `NZFeiQ/core/filetransfer.py` 的 `_attach_map`、端口保留与重试逻辑。

如需更详细事件清单、握手日志样例或具体回归指导，请指出希望补充的模块或 demo（例如：`session`、`protocol`、`filetransfer`）。

```
如需更细的事件清单、握手日志示例或脚本说明，请反馈要点，我会补充对应片段与验证步骤。
