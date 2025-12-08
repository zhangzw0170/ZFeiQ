.github/copilot-instructions.md — ZFeiQ AI agent quick start

目的
- 为 AI 编码代理提供可直接执行的、仓库特定的开发启动说明：可运行命令、关键阅读顺序、以及对高风险区域的约束（尤其是协议/加密/持久化）。

快速命令（最有用）
- 启动 GUI：`python3 NZFeiQ/gui/main.py`
- 启动 CLI：`python3 NZFeiQ/cli/main.py [--bind 127.0.0.X] [--port 2425]`
- 回归 / 演示脚本（在仓库根目录运行）：
  - `python3 test/demo_p2p_secure_loopback.py` — 握手 / 加密回归（首选）
  - `python3 test/demo_filetransfer.py` — 文件传输演示
  - `python3 test/auto_test_requirements.py` — 多节点环境检查

概要架构（快速上手）
- `NZFeiQ/core/` 是系统核心：`engine.py` 负责节点发现、事件分发与持久化，是把 CLI/GUI 与网络、存储连接起来的单一编排点。
- `session.py` + `crypto.py` 实现握手状态机及加密流：此处改动风险高，须附回归脚本与日志。
- `protocol.py` 负责报文编解码（注意 `ext` 字段使用 `\\0` 分隔符，勿破坏线序兼容）。
- `transport.py` 处理 UDP 广播/单播与网卡选择；文件传输使用独立端口/重试逻辑。

优先阅读的文件（按顺序）
- `NZFeiQ/core/engine.py` — 系统编排与事件总线。
- `NZFeiQ/core/session.py`、`NZFeiQ/core/crypto.py` — 握手/密钥/流加密实现（高风险）。
- `NZFeiQ/core/protocol.py` — 报文格式与 `ext` 分隔约定。
- `NZFeiQ/core/transport.py` — UDP 与接口选择逻辑。
- `NZFeiQ/core/state.py` — 节点/会话序列化与并发注意点。
- `NZFeiQ/core/events.py` — 事件名与载荷契约（CLI/GUI 依赖此处接口）。

项目特有约定
- 密钥与密文：`common/keys/` 与 `NZFeiQ/common/keys/` 存放示例密钥；切勿提交真实私钥。修改密钥格式必须附示例与回归脚本（放在 `test/`）。
- 配置模式：`common/config.json` 与 `common/groups.json` 是 schema 源，改变 schema 时必须同步修改 `engine.py` 的 `_load_*` / `_save_*`。
- 事件驱动集成：使用 `ZFeiQCore.set_event_handler(handler)` 注册回调，事件由 `Event(type, data)` 表示；变更事件需同时更新 `NZFeiQ/cli/shell.py` 与 `NZFeiQ/gui/bridge.py`。
- 兼容性：线下有 `legacy/` 目录包含旧实现，仅在对比或迁移时参考，主线代码在 `NZFeiQ/`。

高风险变更清单（必须遵守）
1. 任何对 `session.py`、`crypto.py`、或 `protocol.py` 的修改都必须：
   - 提交回归脚本（优先使用 `test/demo_p2p_secure_loopback.py`）
   - 附上握手成功的日志片段（能证明互通）
2. 持久化/配置 schema 变化需同步更新 `common/*.json` 与 `engine.py` 的加载/保存函数。
3. 在 PR 描述中列出受影响模块、向后兼容策略与回滚计划。

调试与常见故障定位
- 搜索日志关键字：`[DEBUG] send_broadcast`、`cipher`、`handshake` 来追踪网络/加密流程。
- 文件传输问题：检查 `NZFeiQ/core/filetransfer.py` 的端口分配、`_attach_map` 与重试逻辑。
- 并发/状态问题：优先查看 `NZFeiQ/core/state.py` 与 `engine.py` 的锁与调用路径。

集成点示例
- CLI ↔ 引擎：`NZFeiQ/cli/shell.py` 通过 `ZFeiQCore` API 发起操作并接收事件。
- GUI ↔ 引擎：`NZFeiQ/gui/bridge.py` 与 `NZFeiQ/gui/main.py` 把 UI 事件映射为 `ZFeiQCore` 事件，修改事件契约时两端必须同步。

测试建议
- 优先添加小而专注的 demo 脚本到 `test/`（比大型集成测试更易回归与审查）。
- 使用 `test/demo_p2p_secure_loopback.py` 作为握手/加密回归的 canonical 测试，并在 PR 中附上运行命令与关键日志片段。

需要更多或更具体的说明？
- 告诉我你要修改的模块（如 `session`、`protocol`、`filetransfer`），我会补充：受影响事件列表、示例日志片段与回归脚本模版。

---
(保留简洁风格：专注于可发现的仓库模式与可运行命令，避免空泛建议)
