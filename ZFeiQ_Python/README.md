# ZFeiQ_Python (Refactor - Python)

This folder contains the refactored core prototype for ZFeiQ. All refactored
code is placed here and the original source files in the repository must not
be modified (per instruction).



# ZFeiQ_Python — refactor workspace

This folder contains the refactored implementation and runnable demos/tests
for the ZFeiQ prototype. The original source in the repository is kept for
reference only; do not modify it. The refactor is self-contained under
`ZFeiQ_Python/`.

**Structure**
- `zfeiq_core/` — core API, services (`network`, `filetransfer`, `crypto`, `history`, `protocol`) and entities.
- `zfeiq_cli/` — CLI adapter, REPL and small demo/test scripts.
- `zfeiq_gui/` — GUI bridge and shared i18n (`zfeiq_gui/lang.py`).
- `demos/` — scripted demos and `run_all.py` (writes logs to `demos/logs/`).
- `tests/` — integration and smoke tests covering rebind, bind persistence, parity, etc.
- `keys/` — demo RSA keys (do not expose private keys in production).

**Quick start (PowerShell)**

1) Install dependencies for this refactor (recommended to use the `rk3566` conda env):

```pwsh
python -m pip install -r ZFeiQ_Python\requirements.txt
```

2) Run the demo runner or single demos:

```pwsh
# run a single demo
python .\ZFeiQ_Python\demos\demo_set_language.py

# run filetransfer/network/protocol/crypto demos
python .\ZFeiQ_Python\demos\run_demo_filetransfer.py
python .\ZFeiQ_Python\demos\run_demo_network.py
python .\ZFeiQ_Python\demos\run_demo_protocol.py
python .\ZFeiQ_Python\demos\run_demo_crypto.py

# run all demos (writes logs into ZFeiQ_Python\demos\logs)
python .\ZFeiQ_Python\demos\run_all.py
```

3) Start the main application (GUI or CLI mode):

```pwsh
# GUI mode (requires PyQt5)
python .\main.py

# headless CLI mode
python .\main.py --cli

# CLI with explicit port / bind
python .\main.py --cli --port 2426 --bind 192.168.1.100
```

**Tests**
- Root tests (quick checks / original tests): `./tests/*.py`
- Refactor tests (integration / parity): `ZFeiQ_Python/tests/*.py`

Run a single test script:

```pwsh
python .\ZFeiQ_Python\tests\parity_tests.py
python .\tests\parity_tests.py
```

**Notes & troubleshooting**
- Demos that exercise networking and file transfer open UDP/TCP sockets on
	default ports (2425/2426). On Windows, ensure your firewall allows
	local traffic for those ports when doing inter-host tests.
- CLI strings and help text are centralized in `zfeiq_gui/lang.py` — change
	translations there and use the CLI `set language <lang>` command to switch.
- Demo logs are written to `ZFeiQ_Python/demos/logs/` by the demo runner.

If you want, I can:
- run `demo_set_language.py` now and capture the output/logs, or
- run `run_all.py` and summarize the demo logs.

--
Minimal readme for working with the refactor. For more details see
`ZFeiQ_Python/docs/` and `ZFeiQ_Python/demos/CLI_COMMANDS.md`.
