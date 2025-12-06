ZFeiQ — AI Coding Agent 操作手册（简版）

目标：让进入本仓库的 AI 编码代理在首小时即可高效、可审地修改代码，避免破坏握手/加密与跨组件约定。

## 架构速览（为什么与边界）
- 引擎核心：`NZFeiQ/core/engine.py`（类 `ZFeiQCore`）负责节点发现、事件分发、持久化；上层 CLI/GUI 通过事件与其交互。
- 会话与加密：`NZFeiQ/core/session.py`（`Session`）握手 FSM（`KX1`→`KX2`→`ENCREADY`），密钥派生用 X25519+HKDF，报文加密用 ChaCha20-Poly1305；密文/扩展字段规则在 `session.py` 与 `protocol.py`。
- 传输：`NZFeiQ/core/transport.py`（`UdpTransport`）管理 UDP 广播/单播线程，接口选择与广播日志以 `[DEBUG] send_broadcast` 标记。
- 状态/节点：`NZFeiQ/core/state.py`（`NodeRegistry`）集中管理节点信息与序列化。

## 关键开发工作流（命令与验证）
- 启动 CLI：`python3 NZFeiQ/cli/main.py [--bind 127.0.0.X] [--port 2425]`
- 启动 GUI：`python3 NZFeiQ/gui/main.py`
- 加密会话回归：`python3 test/demo_p2p_secure_loopback.py`
- 文件传输演示：`python3 test/demo_filetransfer.py`
- 三节点自动校验：`python3 test/auto_test_requirements.py`

## 事件驱动约定（跨层通信）
- 事件常量集中在 `NZFeiQ/core/events.py`；通过 `ZFeiQCore.set_event_handler(handler)` 订阅，事件形态为 `Event(type, data)`。
- CLI 事件处理示例：`NZFeiQ/cli/shell.py`（`ZFeiQShell.on_core_event`）。
- GUI 桥接：`NZFeiQ/gui/bridge.py` 映射引擎事件到 UI。

## 报文/协议与扩展字段
- IPMSG 报文构建/解析在 `NZFeiQ/core/protocol.py`；扩展区 `ext` 用 `\0` 分隔，兼容要求高，修改前需审查对旧节点影响。

## 配置/持久化与密钥
- 配置：`common/config.json`、`common/groups.json` 由引擎读写；如改 schema，需同步引擎的 `_load_*`/`_save_*`。
- 密钥材料：位于 `common/keys/`；避免提交真实私钥与敏感数据。

## 高风险改动前置要求
- 握手/密钥派生（`core/session.py`、`core/crypto.py`）：提交需附握手调试日志与回归脚本（优先 `demo_p2p_secure_loopback.py`）。
- 报文格式（`core/protocol.py`）：任何格式变动都需说明兼容策略与验证步骤。
- 跨线程/网络（`core/transport.py`、`core/state.py`）：注意线程安全与 iface 推断逻辑。

## 常见改动模式（示例）
- 新增事件：`core/events.py` 增加常量 → 在 `core/engine.py` 广播 → 更新 `NZFeiQ/cli/shell.py` 与 `NZFeiQ/gui/bridge.py` 的处理。
- 新增 CLI 命令：在 `NZFeiQ/cli/shell.py` 添加解析与 handler，复用 `ZFeiQCore` 方法与事件回传。

## 调试提示（可快速定位）
- 开启密文相关日志：在 `core/session.py`/调试命令启用“debug cipher on”，结合 `[DEBUG] send_broadcast` 观察握手与广播行为。
- 文件传输：参考 `core/filetransfer.py` 的 `_attach_map` 与端口保留逻辑。

如需更细的事件清单、握手日志示例或脚本说明，请反馈要点，我会补充对应片段与验证步骤。
