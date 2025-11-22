# ZFeiQ_Python (Refactor - Python)

This folder contains the refactored core prototype for ZFeiQ. All refactored
code is placed here and the original source files in the repository must not
be modified (per instruction).

Structure:
- `zfeiq_core/` — core facade, event bus, entities, and service stubs.
- `zfeiq_cli/` — small CLI adapter example.
- `zfeiq_gui/` — CoreBridge adapter for GUI integration.
- `run_demo.py` — quick demo to exercise the core.

Quick run (requires `pydantic`):

```pwsh
python -m pip install -r ZFeiQ_Python\requirements.txt
python ZFeiQ_Python\run_demo.py
```
