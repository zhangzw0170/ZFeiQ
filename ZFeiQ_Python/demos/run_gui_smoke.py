"""Headless smoke test for GUI refactor: verifies imports and core construction.
This does NOT start a QApplication or show windows — safe for CI / headless runs.
"""
from zfeiq_core import ZFeiQCore, EventBus
from zfeiq_gui.core_bridge import CoreBridge


def main():
    print("Creating EventBus...")
    bus = EventBus()
    print("Instantiating ZFeiQCore with EventBus...")
    core = ZFeiQCore(event_bus=bus)
    print("Creating CoreBridge...")
    bridge = CoreBridge(core)
    print("Smoke test OK: core and bridge constructed")


if __name__ == '__main__':
    main()
