# ZFeiQ (Public Archive)

> **⚠️ archive notice**  
> 本项目原为 Linux 嵌入式课程设计（RK3566 平台）作品，现已完成其历史使命。  
> 代码已停止积极维护。可以作为一个基于 Python/PyQt5 实现 IPMSG 协议与边缘 AI 结合的参考案例公开存档。  
> **This project is no longer maintained.**

---

ZFeiQ 是一个现代化、高安全性的局域网即时通讯系统。它致敬了经典的 IPMSG（飞秋/飞鸽传书）协议，针对嵌入式设备（如 Rockchip RK3566）进行了优化，并集成了边缘 AI 能力。

本项目在核心层进行了彻底重构，引入了无服务器通讯、企业级加密协议栈、事件驱动架构以及基于 NPU 加速的 OCR 功能。

## 🎯 项目背景与目标

本项目旨在使用 Python 在 Linux (RK3566/KylinOS) 环境下实现一个功能完备的局域网通讯软件。

**核心要求与达成情况：**
- ✅ **无服务器通讯**：基于 UDP 广播/组播实现节点发现与通信。
- ✅ **聊天室/群组**：支持 P2P 私聊及多人群组聊天。
- ✅ **即时搜索**：支持按用户、IP 等关键词搜索在线好友。
- ✅ **文件传输**：支持大文件传输（TCP 通道）。
- ✅ **多媒体功能**：支持发送表情包、截图以及 Emoji。
- ✅ **边缘 AI 加速**：集成 PPOCRv4，调用 RK3566 NPU 实现本地图片文字识别（OCR）。

## 🏗️ 架构概览

项目采用分层架构设计，实现了核心逻辑与界面的解耦 (`NZFeiQ` 目录)：

- **Core (`NZFeiQ/core`)**: 纯 Python 实现的协议核心，包含协议编解码、网络传输、加密会话、文件传输引擎、OCR 接口等。
- **GUI (`NZFeiQ/gui`)**: 基于 PyQt5 的现代化图形界面。
- **CLI (`NZFeiQ/cli`)**: 命令行交互界面，用于无头模式运行或调试。
- **Legacy (`legacy_*`)**: 保留了早期的开发迭代版本作为参考。

## 🚀 快速开始

虽然本项目不再维护，但您仍可以运行它进行学习或测试。需要 Python 3.8+ 环境。

### 1. 安装依赖

```bash
python3 -m pip install -r requirements.txt
# 或者手动安装核心依赖
python3 -m pip install PyQt5 pycryptodome numpy
```

### 2. 运行

**图形界面 (GUI)**:
```bash
python3 NZFeiQ/gui/main.py
```

**命令行界面 (CLI)**:
```bash
python3 NZFeiQ/cli/main.py
```

### 3. OCR 说明
OCR 功能依赖于 `resource/` 目录下的模型文件。在 RK3566 设备上，会自动尝试加载 `rknn_toolkit_lite2` 进行 NPU 推理；在 PC 上则回退至 CPU/ONNX Runtime 推理。

## 🛡️ 安全特性

不同于传统的明文 IPMSG，ZFeiQ 实现了一套可选的安全传输层：
- **密钥交换**: X25519
- **流加密**: ChaCha20-Poly1305
- **身份验证**: 基于公钥的身份标识

## 📁 目录结构

```plaintext
root/
├── NZFeiQ/               # 重构后的主代码库 (New ZFeiQ)
│   ├── core/             # 业务逻辑核心
│   ├── gui/              # PyQt5 界面
│   └── cli/              # 命令行工具
├── legacy_*/             # 历史遗留代码 (参考用)
├── resource/             # 静态资源与模型 (OCR等)
├── docs/                 # 开发文档与设计说明
└── test/                 # 测试脚本与演示
```

## 📝 声明

本项目仅供学习交流使用。
由于不再维护，对于 Issues 和 PR 可能不会进行响应，建议 Fork 后自行修改。

**License**: MIT 
