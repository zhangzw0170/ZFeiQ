<!-- Copilot instructions for the ZFeiQ codebase -->
# ZFeiQ — AI coding agent quick guide

This file explains the important, repository-specific facts an AI coding agent needs to be productive in ZFeiQ.

- Project modes: `GUI` and `CLI`.
  - Start GUI: `python main.py` (requires `PyQt5==5.15.0`).
  - Start CLI: `python main.py --cli`.
  - Network port: default `2425`; can pass `--port 2426` or set `ZFEIQ_PORT` env var. Bind interface: `--bind 192.168.x.x`.

- Architecture (big picture):
  - `main.py`: entry point — chooses CLI or GUI.
  - `zfeiq_cli/`: core networking, protocol and headless UI for tests and automation.
    - `protocol.py`: IPMSG constants, packet build/parse and file-attach encoders.
    - `transport.py`: `UdpTransport` — broadcast/unicast, bind behavior (Windows binds specific iface; Linux binds `0.0.0.0`).
    - `cli.py`: `ZFeiQCli` — app state, registry, keepalive/purge loops, auto-rebind heuristics, encryption flow and file-transfer hooks.
    - `crypto.py`: RSA/AES helpers and base64 helpers used for pubkey exchange.
    - `filetransfer.py`: TCP-based file serve/download helpers and IPMsg interop.
    - `state.py`: in-memory registries and persistence related helpers.
  - `zfeiq_gui/`: PyQt5 UI layer.
    - `app.py`: `launch_gui()` (font, plugin and soft-OpenGL handling for RK3566).
    - `backend.py`, `main_window.py`, `pages/`: UI backend bindings and page components. `lang.py` centralizes translations.

- Important runtime behaviors & gotchas:
  - Default network behavior: on Linux the UDP socket binds `0.0.0.0` to reliably receive broadcasts; the code computes an outgoing iface via `iface_ip` and `iface_prefix`.
  - Auto-rebind: `ZFeiQCli` may automatically switch local binding to a same-subnet interface when receiving traffic (unless user locked bind via `--bind` or `/set bind`). See `_auto_rebind_consider` in `zfeiq_cli/cli.py`.
  - Keys: RSA keys stored under `./keys/priv.pem` and `./keys/pub.pem`. Key generation is lazy (`_ensure_keys`).
  - File transfer: IPMSG file attachments use `filetransfer.py` and a small TCP server on port 2425 when needed; attachments mapping kept in `_attach_map`.
  - Encoding heuristics: CLI attempts `utf-8`, `gbk`, `cp936`, `latin-1` when decoding bytes (`_decode_bytes_auto`).
  - RK3566 / aarch64: UI forces software OpenGL when `ZFEIQ_FORCE_SOFTGL` is set or detected platform.

- Tests and examples:
  - Quick demo/test scripts live under `tests/` (e.g. `discover_and_sendall.py`, `group_send_demo.py`). Use these as small integration examples rather than unit tests.

- Common edit patterns for contributors/agents:
  - Adding a new IPMSG command:
    1. Add constant and encode/decode helpers in `zfeiq_cli/protocol.py`.
    2. Update CLI handlers in `zfeiq_cli/cli.py` to react to the new `base_command` value.
    3. If UI-visible, add frontend/backend plumbing in `zfeiq_gui/backend.py` and appropriate `pages/` widgets.
  - When changing transport behavior, update `zfeiq_cli/transport.py` and validate broadcast/unicast on both Windows and Linux.

- Useful code locations to inspect when debugging:
  - `main.py` — startup options and error messages for missing GUI.
  - `zfeiq_cli/cli.py` — lifecycle, keepalive, retransmit and maintain loops.
  - `zfeiq_cli/transport.py` — socket creation and send/receive semantics.
  - `zfeiq_gui/app.py` and `zfeiq_gui/backend.py` — UI launch and bridging to the CLI-like backend.
  - `zfeiq_gui/lang.py` — translations and where all UI strings are defined.

- Best assumptions for code changes by AI agents:
  - Preserve cross-platform behavior: Windows vs Linux have different binding logic.
  - Avoid changing default port or encoding without explicit tests; many tests and demos assume port 2425.
  - Keep key storage in `./keys/` and avoid exposing private PEM in logs.

If anything above is unclear or you want the instructions expanded (e.g. more examples, workflow for adding GUI pages, or a quick test harness), tell me which section to expand.
