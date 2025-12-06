# ZFeiQ (Alpha 6.0 Reborn)

ZFeiQ 是一个现代化、高安全性的局域网即时通讯系统。它基于经典的 IPMSG（飞秋/飞鸽传书）协议构建，但在核心层进行了彻底重构与现代化改造。

本项目实现了无服务器通讯，并引入企业级加密协议栈（X25519 + ChaCha20-Poly1305）、事件驱动架构以及边缘 AI（OCR）能力，适用于嵌入式（如 RK3566/RK3588）和桌面（Windows/Linux）环境。

## 项目要求（禁止修改）

在瑞芯微板子麒麟系统实现简单的局域网飞秋功能。

1. 可以建立无需服务器的聊天室,具有群聊天室的功能.
2. 搜索用户功能，可通过输入用户名、组名、IP等来查找我的好友.
3. 分组功能，给所有在线的用户群发消息及分组群发功能.
4. 支持表情包发送(可自定义表情包)、截图功能。
5. 调用RK3569/3566的NPU，实现典型边缘AI智能的加速功能

## 核心特性

### 现代密码学核心 (Modern Crypto Stack)

- **密钥协商**: ECDH-X25519 (Curve25519)，实现完美前向保密 (PFS)。每次会话生成临时密钥，即使长期身份泄露，历史消息依然安全。
- **加密算法**: ChaCha20-Poly1305 (AEAD)。在无 AES 硬件加速的嵌入式设备上性能更优，并自带完整性校验 (MAC)。
- **密钥派生**: HKDF-SHA256（符合 RFC 5869）。
- **身份验证**: 基于静态 X25519 公钥的指纹（Fingerprint）广播与 TOFU（Trust On First Use）模型。

### 工业级架构 (Industrial Architecture)

- **Core/CLI 分离**: `core` 负责纯逻辑与状态机，`cli` 负责交互。模块高度解耦，便于移植到 GUI 或 Web。
- **事件驱动**: 基于发布/订阅模式的消息总线，实现从底层网络到上层 UI 的异步非阻塞通信。
- **有限状态机 (FSM)**: 严谨的加密握手状态机（KX_SENT -> ESTABLISHED），处理 UDP 丢包、乱序与握手竞态问题。

### 极致体验 (Enhanced UX)

- **异步 CLI**: 集成 `prompt_toolkit`，实现类似 IPython 的交互体验，日志输出不会打断当前命令输入。
- **持久化存储**: 自动保存用户配置、身份密钥（`identity.bin`）和聊天历史。
- **边缘 AI**: 集成 OCR 引擎，支持图片文字识别（CPU/NPU 自动切换）。

## 安装与运行

### 环境要求

- Python 3.8+
- 依赖库: `cryptography`, `prompt_toolkit`
- 可选（OCR 支持）: `onnxruntime` 或 `rknn-toolkit2`

### 克隆项目

```bash
git clone https://github.com/your_repo/NZFeiQ.git
cd NZFeiQ
```

### 安装依赖

```bash
pip install prompt_toolkit cryptography
```

> 可选（OCR）:

```bash
pip install onnxruntime
```

### 启动 CLI

```bash
# 默认启动（绑定 0.0.0.0:2425）
python3 cli/main.py

# 指定绑定 IP（适用于多网卡或环回测试）
python3 cli/main.py --bind 127.0.0.1
```

## 命令手册（Commands）

在 CLI 界面中，您可以直接输入以下命令（支持 Tab 补全）：

| 命令 | 参数 | 说明 |
|---|---:|---|
| `login` | `<username>` | 上线并广播存在 |
| `logout` | - | 下线并通知局域网节点 |
| `discover` | `[ip]` | 广播发现所有用户，或单播发现指定 IP |
| `send` | `<ip> <msg>` | 发送文本消息（自动建立加密会话） |
| `file send` | `<ip> <path>` | 发送文件请求 |
| `file accept` | `<offer_id>` | 接受文件并下载 |
| `list` | - | 列出当前在线用户及状态 |
| `ocr` | `<path> [--send <ip>]` | 识别图片文字，可选直接发送结果 |
| `debug cipher` | `<on/off>` | 开启/关闭显示原始密文（调试） |
| `log level` | `<info/debug...>` | 设置日志级别 |
| `set status` | `<online/busy>` | 切换在线状态 |
| `set encrypt` | `<on/off/strict>` | 设置加密模式（strict 模式拒绝明文） |
| `clear` | - | 清屏 |
| `exit` | - | 退出程序 |

## 自动化测试与演示

项目包含一个自动化集成测试脚本，用于在单机环境下模拟双节点（Alice 和 Bob）的完整通讯流程，包括自动握手与加密验证。

运行演示：

```bash
# 确保您在项目根目录下
python3 tests/demo_p2p_secure_loopback.py
```

演示内容示例：

- 启动两个独立进程绑定 `127.0.0.1` 和 `127.0.0.2`。
- 模拟用户登录与服务发现。
- 自动捕获并打印 `[明文] -> [ChaCha20 密文] -> [解密明文]` 的全过程，验证传输与加密流程。

## 目录结构

```text
NZFeiQ/
├── cli/                # 命令行交互层
│   ├── main.py         # 程序入口
│   └── shell.py        # 基于 prompt_toolkit 的交互 Shell
├── core/               # 核心逻辑层 (无 UI)
│   ├── engine.py       # 核心引擎 (API, 调度)
│   ├── session.py      # 加密会话状态机
│   ├── crypto.py       # 密码学原语 (X25519, ChaCha20, HKDF)
│   ├── protocol.py     # IPMSG 协议解析
│   ├── transport.py    # UDP/TCP 网络传输
│   └── ...
├── common/             # 运行时数据 (配置, 密钥, 下载)
├── tests/              # 测试脚本
└── README.md           # 本文档
```

## 免责声明

本项目基于 IPMSG 协议进行了非标准扩展：在加密模式下，ZFeiQ 仅能与相同版本的 ZFeiQ 客户端互通（因使用自定义 X25519 握手帧）。

该项目旨在用于学术研究与嵌入式系统课程设计，请勿用于非法用途。

---

NZFeiQ Team | 2025

## Legacy 版本功能迁移状态
**已实现**
- 事件驱动核心与加密握手：`core/engine.py`、`core/session.py` 延续了 X25519 + HKDF + ChaCha20-Poly1305 的会话流程，并通过事件回调覆盖 `legacy/zfeiq_cli` 的主要业务场景。
- 基础 CLI 流程：`cli/shell.py` 提供登录、节点发现、群组消息、搜索、文件发送/接收、截图与 OCR 命令，与 `legacy/zfeiq_cli/cli.py` 的基础功能对齐。
- 文件传输栈：`core/filetransfer.py` 与 `core/engine.py` 复用 TCP offer/下载逻辑，`gui/chat.py` 通过 `Bridge` 自动接收文件，能力上接续了旧版的核心文件流。
- OCR 与截图：`core/ocr.py` 与 `core/engine.capture_screen` 仍支持 NPU/CPU 自动切换和命令行截图，`test/auto_test_requirements.py` 用于回归这些能力。

**尚未实现**

**尚未实现（详细清单与实现提示）**
- CLI: 额外命令集合（推荐优先级与实现要点）
	- `info` 系列：`/info`、`/info net`、`/info user:<name>`、`/info group:<name>`。
		- 用途：调试网络/显示历史消息与本机绑定信息。
		- 实现提示：`ZFeiQCore` 已有 `registry`、`history` 与 `_detect_best_ip` 可供查询；在 `cli/shell.py` 添加 `/info` 子命令即可。
	- `send user:<name>` / `send all <text>`：按用户名或广播发送。
		- 实现提示：使用 `core.state.NodeRegistry.find_by_username` 映射到 IP；广播映射到 `send_text('all', ...)`。
	- 文件管理：`file list`（列出 `_incoming_offers`）、`file cancel <id>`（取消本地待接收/发送项）。
		- 实现提示：`ZFeiQCore._incoming_offers` 与 `_attach_map` 已存在，暴露安全的只读/修改方法给 CLI。
	- 群组管理扩展：`group delete`、`group rename`、按用户名批量添加/删除成员。
		- 实现提示：`ZFeiQCore.groups` 已持久化到 `common/groups.json`，在 CLI 中实现 CRUD 并调用 `_save_groups()`。
	- 高级 `/set`：`/set encoding <utf8|gbk>`、`/set language <zhCN|enUS>`、`/set bind <ip>`、`/set debug/trace`。
		- 风险/注意：`/set bind` 需要重启或重建 `UdpTransport`（慎重）；语言切换需要移植或加载 `legacy/zfeiq_gui/lang.py` 中的字典。

- GUI：欠缺的页面与 UX 功能
	- 完整设置页（高级网络、下载/截图目录、编码自测）——`legacy/zfeiq_gui/pages/settings_page.py` 提供参考实现。
	- 群组管理页（创建/重命名/成员管理）、文件列表页与 KeyPage（查看/导出 X25519 指纹）——均可复用 `legacy` 中的 UI 逻辑并通过 `Bridge` 调用 `ZFeiQCore`。
	- 表情包/表情挑选器（`emotes_page.py`）与聊天面板的表情按钮绑定（`gui/chat.py` 按钮目前无实现）。

- OCR / NPU / 模型资源
	- `core/ocr.py` 已实现 CPU/ONNX 与 RKNN 分支，但仓库内并不保证包含 `PPOCRv4` 的模型文件（`build_output`）或 `ZFeiQ_Original/PPOCRv4` 目录。
	- 实现提示：要启用 OCR，需要在仓库或部署环境中放置 ONNX/RKNN 模型文件并安装对应运行时（`onnxruntime` 或 `rknn-toolkit2`/`rknnlite`）。

- 互操作/兼容性细节
	- E‑D 标记、旧版 ENC2 语法与一些兼容性标签在 `legacy/zfeiq_cli/cli.py` 中有更多开关（如 `encrypt_edtag`），这些细粒度兼容选项尚未迁移。
	- 运行时动态换绑定（`/set bind`）和多网卡治理（`iface_prefix` 设定）在新实现中未暴露运行时接口。

- 测试与脚本
	- 自动化/回归脚本（如更复杂的场景脚本、encoding 自测）多数集中在 `legacy` 或 `test/` 中的老脚本。部分旧版测试/自测脚本需要适配新命令与路径。

**下一步建议**
- 优先实现（CLI）: `info` 系列、`file list`/`file cancel`、`send user`、`send all`、`group delete/rename`。
- 中期：迁移 GUI 页（`emotes`, `groups`, `files`, `key`）并把 `Bridge` 扩展为控制接口；补入语言字典以支持多语言切换。
- OCR：确认模型文件与运行时后再开启完整 OCR 流（否则在运行时会报模型缺失）。

若你同意优先级，我可以立即在 `cli/shell.py` 开始实现首批高优先级命令（会逐项提交变更并运行 smoke tests）。