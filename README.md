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

ZFeiQ 是基于 IPMSG 协议的点对点局域网即时通讯项目，主要特点：

- 事件驱动的引擎与轻量消息队列（快速节点发现、广播/单播消息）
- 会话加密：基于 X25519 的密钥交换与 ChaCha20-Poly1305 加密通道
- 文件传输（TCP offer / progress / 完成回调）
- OCR 支持（CPU/ONNX/NPU）与可选的本地模型加速

## 简短迁移状态（Legacy -> NZFeiQ）

**已实现**
- 事件驱动核心（节点发现、消息收发、加密会话）
- 基本 CLI 与 GUI 功能（登录、发现、搜索、发送文本/文件、OCR 调用）
- 文件传输基础（offer/progress/done 报告）
- OCR 支持（CPU/ONNX/NPU 路径，`EV_OCR_DONE` 返回 `engine_type`/`elapsed`）

**未实现 / 待补齐**
- 若干 GUI 页面（表情、文件列表、Key、群组管理）
- 高级 CLI 管理命令与运行时动态 `bind` / 多网卡策略
- 完整本地化字典与语言切换支持
- 部分自动化回归脚本与模型资源（例如 PPOCRv4 模型）

## 快速上手

1. 安装依赖（示例）

```bash
python3 -m pip install -r requirements.txt  # 如果你维护 requirements.txt
# 或至少安装 PyQt5
python3 -m pip install PyQt5
```

2. 启动 GUI

```bash
python3 NZFeiQ/gui/main.py
```

3. 启动 CLI（可选）

```bash
python3 NZFeiQ/cli/main.py
```

4. 常见测试（手动）

- 在两台机器或两个进程间登录并相互发现
- 发送文本/文件、测试 OCR 功能（`test/demo_*` 脚本可作参考）

## 测试要点（要覆盖的核心流程）

- 节点发现与状态同步（`sig_nodes_changed` / `EV_NODE_UPD`）
- 文本消息收发（私聊与广播）、加密握手与会话加密
- 文件传输（offer / 进度 / 完成）与本地打开回退（`xdg-open`）
- OCR 调用与 `EV_OCR_DONE` 返回值校验（`engine_type` 和 `elapsed`）

## Legacy 管理建议（简要）

建议将 `legacy/` 作为参考归档（`archive/legacy_v1`），把 `NZFeiQ/` 作为后续开发主线；迁移时逐条核对功能并用小 PR 分步验证。

如需，我可以生成 `legacy ↔ new` 的文件对照清单并按优先级输出迁移计划。

## 贡献与联系

欢迎提 PR 或 issue。提交变更时请保持小而明确的改动（每个 PR 对应一个小目标，例如 OCR 延迟加载、节点刷新事件驱动、历史保留上限）。

---

NZFeiQ Team | 2025
