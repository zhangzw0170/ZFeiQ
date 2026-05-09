# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Status

Archived. ZFeiQ was a Linux embedded course project (RK3566) — a LAN instant messenger implementing IPMSG protocol with edge AI (OCR). No longer actively maintained. Serves as a reference for Python/PyQt5 IPMSG + edge AI integration.

## Architecture

Layered design under `NZFeiQ/`:

- **core/** — Pure Python business logic (no UI dependency)
  - `protocol.py` — IPMSG message encoding/decoding, extended fields (`\0` separator), file attachment lists
  - `transport.py` — UDP broadcast/unicast, port & interface detection, platform-specific bind behavior
  - `engine.py` — Event-driven core: node registry, ACK retransmission, encryption integration, file offer dispatch
  - `session.py` — Encrypted session state machine (KX1 → KX2 → ENCREADY → ESTABLISHED)
  - `crypto.py` — X25519 key exchange, HKDF-SHA256 key derivation, ChaCha20-Poly1305 AEAD
  - `filetransfer.py` — TCP file server, IPMSG-style offer/accept/release flow, `_attach_map` semantics
  - `state.py` — NodeRegistry, ChatHistory, PendingAck persistence
  - `ocr.py` — PPOCRv4 interface (NPU/RKNN on device, ONNX Runtime fallback on PC)
  - `events.py` — Event types (EV_NODE_UPD, EV_MSG_SENT, EV_MSG_RECV, EV_FILE_OFFER, EV_FILE_DONE)
  - `screenshot.py` — Screenshot capture utility
- **gui/** — PyQt5 frontend
  - `bridge.py` — Core-to-UI event bridge
  - `window.py`, `chat.py`, `login.py`, `settings.py`, `group_manager.py` — UI pages
  - `emoji_widget.py`, `emote_widget.py` — Emoji/emote panels
  - `styles.py` — Theme/styling, `lang.py` — i18n
- **cli/** — Headless CLI (`shell.py` interactive, `main.py` entry)
- **test/** — Demo/integration scripts (not unit tests)

Data directory: `common/` (auto-created: `config.json`, `groups.json`, `keys/`, `downloads/`, `emotes/`)

## Running

```bash
pip install -r requirements.txt

# GUI
python3 NZFeiQ/gui/main.py

# CLI
python3 NZFeiQ/cli/main.py
```

## Testing

No formal test suite. Integration demos in `NZFeiQ/test/`:

```bash
cd NZFeiQ
python3 test/demo_p2p_secure_loopback.py   # Encrypted P2P handshake
python3 test/demo_filetransfer.py           # File transfer
python3 test/demo_groups_6users.py          # Group messaging (needs loopback aliases)
python3 test/auto_test_requirements.py      # 3-node regression
```

Loopback aliases required for multi-node demos on a single machine:
```bash
sudo ip addr add 127.0.0.2/8 dev lo
sudo ip addr add 127.0.0.3/8 dev lo
# ... up to 127.0.0.6
```

## Key Conventions

- **Default port**: `2425` (IPMSG standard) — do not change in tests
- **Char decoding**: `utf-8` → `gbk` → `cp936` → `latin-1` fallback chain
- **IP priority**: `192.168.x.x` > `172.x.x.x` > `10.x.x.x` for auto-detection
- **Private keys**: Lazy-generated, written to `common/keys/`; never log private key material
- **Broadcast/unicast**: Behavior differs significantly between Linux and Windows — verify on both platforms after any `transport.py` change
- **OCR models**: `resource/PPOCRv4/build_output/` — RKNN for RK3566 NPU, ONNX for PC fallback

## Crypto Stack

X25519 (ephemeral ECDH) → HKDF-SHA256 → ChaCha20-Poly1305 AEAD. Provides forward secrecy. Session nonce derived from `sha256(sid || "zfeiq_nonce" || ascii(ctr))[:12]`. Replay protection via `recv_window` sliding set (max 1024 entries). See `docs/SECURITY.md` for full details.

## Change Guidelines

- Network/transport/crypto changes: write a reproduction script, verify across at least two processes/machines
- Keep `legacy_ZFeiQ/` intact as reference — do not delete historical implementations
- Cross-layer changes (core + gui + tests): split into small PRs with verification scripts per layer
- GUI entry point is `NZFeiQ/gui/main.py`, not `window.py`
