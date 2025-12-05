ZFeiQ — AI 编码助手使用说明

本文件为 AI 编码代理（例如 Copilot 风格 agent）提供在此代码库中高效工作的必要要点。内容聚焦于可被代码、配置与示例直接证实的约定与操作步骤。

**Repository Overview**:
- **Purpose**: 本仓库实现一个无服务器的局域网即时通讯（IPMSG 风格）客户端，现代化改写，重点在于 X25519 密钥协商、ChaCha20-Poly1305 加密与事件驱动的 FSM。
- **Design Partition**: 核心逻辑在 `core/`，交互层在 `cli/`（可替换为 GUI），运行时与可选资源在 `common/` 与 `keys/`。

**How To Run (developer shortcuts)**:
- **启动 CLI**: 在仓库根目录运行 `python3 cli/main.py`。
- **绑定指定地址**: `python3 cli/main.py --bind 127.0.0.1`（用于多网卡或回环测试）。
- **演示/集成测试**: 使用仓库内的 demo 脚本，例如 `python3 test/demo_p2p_secure_loopback.py` 和 `python3/test/demo_filetransfer.py`（在单机上模拟两端）。

**Key Files & What They Contain**:
- **`core/crypto.py`**: 密码学原语（X25519, HKDF, ChaCha20-Poly1305）；所有加密调用应优先复用本模块。
- **`core/session.py`**: 会话与握手有限状态机（KX_SENT -> ESTABLISHED）；处理重传、乱序与握手竞态逻辑。
- **`core/engine.py`**: 引擎入口、事件总线和高层 API，连接 `transport` 与 `session`。
- **`core/transport.py`**: UDP/TCP 抽象、超时与重试策略的实现点。
- **`cli/shell.py`** & **`cli/main.py`**: 基于 `prompt_toolkit` 的交互实现与命令路由（参考命令表在 `README.md`）。

**Project-specific Patterns & Conventions**:
- **Core/CLI 分离**: 不要把协议或加密逻辑写入 `cli/`；所有网络/crypto 变更应在 `core/` 实现并通过 `engine` 暴露接口。
- **事件驱动**: 代码倾向于发布/订阅方式传递消息（事件总线），请搜索 `publish`/`subscribe` / `emit` 等词以定位用法。
- **有限状态机（FSM）**: 会话管理严格遵循 `session.py` 的状态转换，在修改握手流程前先阅读该文件以避免竞态问题。
- **TOFU 身份模型**: 身份通过静态 X25519 公钥的指纹广播；首次见到的新指纹将被接受（Trust On First Use），变更将被记录/警告。

**Helpful Examples (copyable)**:
- 启动本地 CLI：`python3 cli/main.py`
- 回环/双节点演示：`python3 test/demo_p2p_secure_loopback.py`
- 发送文件演示：`python3 test/demo_filetransfer.py`

**Testing & Debugging Tips**:
- **日志级别**: 在 CLI 中执行 `log level debug` 可以看到握手与加密帧（配合 `debug cipher on` 更详细）。
- **快速复现握手问题**: 使用回环演示脚本并开启 `debug cipher`，对比发送前后的密文/明文流（scripts 内已有打印点）。
- **单元/集成脚本位置**: 演示与集成脚本位于 `test/`，优先阅读这些脚本来了解假定的网络拓扑与输入序列。

**Code Change Guidance**:
- 修改加密/会话：先在 `core/crypto.py` 或 `core/session.py` 编写变更并配套修改 `test/` 下的演示脚本以验证。
- 添加 CLI 命令：在 `cli/shell.py` 注册命令回调，尽量调用 `engine` 的高层函数而非直接操作网络/crypto。
- 配置与持久化：`common/config.json` 与 `keys/` 用于运行时配置与密钥，修改格式时更新相应读写逻辑。

**When to Ask for Human Review**:
- 修改握手顺序或密钥派生（HKDF）实现时必须有人审阅（高风险变更）。
- 改动会话状态模型接口或事件总线签名时请先在 PR 描述中包含重现步骤与演示脚本。

如果此文件有遗漏或希望补充更细的例子（例如常见 bug、变量名约定或常用正则匹配），请指出要补充的具体主题或文件，我会立即迭代更新。
