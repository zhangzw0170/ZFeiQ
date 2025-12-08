# .github/copilot-instructions.md — ZFeiQ AI agent quick start

Purpose: give an AI coding agent the exact, actionable knowledge to be productive quickly
without breaking protocol/cryptography or shipping secrets.

Quick commands
- Start GUI: `python3 NZFeiQ/gui/main.py`
- Start CLI: `python3 NZFeiQ/cli/main.py [--bind 127.0.0.X] [--port 2425]`
- Key demos / regression scripts:
  - `python3 test/demo_p2p_secure_loopback.py` (handshake / crypto regression)
  - `python3 test/demo_filetransfer.py` (file transfer)
  - `python3 test/auto_test_requirements.py` (multi-node checks)

Core files to read first
- `NZFeiQ/core/engine.py` — ZFeiQCore: node discovery, event dispatch, persistence (system hub).
- `NZFeiQ/core/session.py` & `NZFeiQ/core/crypto.py` — handshake FSM, key derivation, encryption streams. HIGH RISK: any change requires regression artifacts.
- `NZFeiQ/core/protocol.py` — packet build/parse. Note: `ext` field uses `\\0` separators; keep wire-format compatible.
- `NZFeiQ/core/transport.py` — UDP broadcast/unicast and interface selection.
- `NZFeiQ/core/state.py` — node/state serialization; watch for concurrent access.
- `NZFeiQ/core/events.py` — event constants and payload formats used across CLI/GUI.

Project-specific conventions and important patterns
- Keys and secrets: `common/keys/` — NEVER commit real private keys. If you change key format, include example keys and regression scripts.
- Config schema: `common/config.json` and `common/groups.json`. If you change schema, also update engine load/save helpers (search for `_load_` / `_save_`).
- Wire compatibility: `protocol.py` changes must include compatibility plan and regression tests; `ext` separators are `\\0`.
- Event-driven flow: ZFeiQ uses events as the integration surface — `ZFeiQCore.set_event_handler(handler)` and `Event(type, data)` are central. When adding an event, update `events.py`, `engine.py` (broadcaster), and CLI/GUI handlers (e.g., `NZFeiQ/cli/shell.py`, `NZFeiQ/gui/bridge.py`).

High-risk change checklist (must follow)
1. For changes in `session.py`, `crypto.py`, or `protocol.py`: include a regression script (prefer reusing `test/demo_p2p_secure_loopback.py`) and attach sample logs demonstrating correct handshake.
2. For schema or persistence changes: update `common/config.json`/`common/groups.json` and corresponding `_load_*` / `_save_*` functions in `engine.py`.
3. Document affected modules and compatibility strategy in the PR description.

Common developer tasks and examples
- Add an event: modify `NZFeiQ/core/events.py` → broadcast in `NZFeiQ/core/engine.py` → handle in `NZFeiQ/cli/shell.py` or `NZFeiQ/gui/bridge.py`.
- Add CLI command: edit `NZFeiQ/cli/shell.py` to parse and call `ZFeiQCore` APIs (follow existing handlers as examples).

Debugging and quick triage
- Run the handshake demo: `python3 test/demo_p2p_secure_loopback.py` and inspect logs.
- Search logs for: `[DEBUG] send_broadcast`, `cipher`, `handshake` to track network and crypto flows.
- File transfer issues: inspect `NZFeiQ/core/filetransfer.py` and `_attach_map` logic, port allocation, and retry behaviour.

Where to look for integration points
- CLI ↔ Engine: `NZFeiQ/cli/shell.py` uses `ZFeiQCore` for commands and receives events.
- GUI ↔ Engine: `NZFeiQ/gui/bridge.py` and `NZFeiQ/gui/main.py` bridge UI events to `ZFeiQCore`.

Testing guidance
- Reuse existing demos for regression: tests are mostly script-based; prefer adding new demo scripts for new protocol or crypto changes.
- If you need to add automated tests, place them under `test/` and keep them runnable without real private keys (use sample or ephemeral keys).

If you are unsure or making risky changes
- Stop and ask: provide a short summary of the intended change, files to touch, and the plan to keep wire compatibility.
- Provide regression steps and example logs with the PR.

Need help expanding this file?
- Tell me which module you want deeper guidance for (e.g., `session`, `protocol`, `filetransfer`) and I will add event lists, sample handshake logs, and a regression script template.

---
(This file is intentionally short — it focuses on discoverable, project-specific patterns and commands. Preserve its brevity when editing.)
