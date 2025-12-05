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