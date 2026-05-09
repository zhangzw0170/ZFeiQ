# ZFeiQ

A modern, secure LAN instant messenger inspired by IPMSG (Feige/Feiqiu), optimized for embedded Linux (RK3566) with edge AI capabilities.

ZFeiQ 是一个现代化、高安全性的局域网即时通讯系统。致敬经典 IPMSG 协议，针对 RK3566 嵌入式平台优化，并集成了边缘 AI（OCR）能力。

## Features

- **Serverless P2P** — UDP broadcast/multicast node discovery, no central server required
- **Encrypted sessions** — X25519 + HKDF + ChaCha20-Poly1305 (AEAD) with forward secrecy
- **Group chat** — Multi-user group messaging with persistent membership
- **File transfer** — TCP-based large file transfer with IPMSG-style offer/accept flow
- **Edge OCR** — PPOCRv4 with NPU (RKNN) acceleration on RK3566, ONNX Runtime fallback on PC
- **Rich media** — Emoji panel, custom emotes, screenshot capture

## Architecture

```
NZFeiQ/
├── core/           # Protocol, transport, crypto, sessions, file transfer, OCR
├── gui/            # PyQt5 frontend with core-to-UI event bridge
├── cli/            # Headless interactive shell
└── test/           # Integration demo scripts
```

**Tech stack**: Python 3.8+, PyQt5, `cryptography` (X25519/ChaCha20-Poly1305), ONNX Runtime / RKNN Toolkit Lite2

**Dependencies**: PyQt5>=5.14, cryptography>=46.0, Pillow>=10.0, numpy>=1.24, opencv-python>=4.5, requests>=2.22, netifaces>=0.10, psutil>=5.8, PyYAML>=5.3, python-dotenv>=0.21, pytest>=7.0

## Quick Start

```bash
pip install -r requirements.txt

# GUI
python3 NZFeiQ/gui/main.py

# CLI
python3 NZFeiQ/cli/main.py
```

### Testing

```bash
cd NZFeiQ
python3 test/demo_p2p_secure_loopback.py   # Encrypted P2P handshake
python3 test/demo_filetransfer.py           # File transfer
python3 test/demo_groups_6users.py          # Group messaging
python3 test/auto_test_requirements.py      # 3-node regression
```

Multi-node demos on a single machine require loopback aliases:

```bash
sudo ip addr add 127.0.0.2/8 dev lo
sudo ip addr add 127.0.0.3/8 dev lo
```

## Documentation

| Document | Content |
|----------|---------|
| `docs/SECURITY.md` | Crypto design, handshake flow, key derivation, known trade-offs |
| `docs/TEST.md` | Test procedures, CLI commands, OCR verification, debug tips |
| `docs/HANDSHAKE_AUTH.md` | Handshake authentication design and CI test examples |

## AI Usage Disclosure

This project was developed with the assistance of AI tools: **GPT**, **Gemini**, and **GLM**. AI was used for code generation, debugging, and documentation throughout the development process.

本项目在开发过程中使用了 AI 辅助工具：**GPT**、**Gemini** 和 **GLM**。AI 参与了代码生成、调试和文档编写等环节。

## Project Status

Archived — originally a Linux embedded systems course project (RK3566 / KylinOS). No longer actively maintained. Issues and PRs may not receive responses; fork and modify as needed.

Last functional update: 2026-01-08

## License

[MIT](LICENSE)
