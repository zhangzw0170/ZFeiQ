"""Run a minimal GUI for manual testing.
This demo launches the refactored GUI and connects it to a CoreBridge instance.
"""
from zfeiq_gui import launch_gui
from zfeiq_core import ZFeiQCore, EventBus
from zfeiq_gui.core_bridge import CoreBridge
from zfeiq_gui.core_adapter import CoreAdapter


def main():
    # Create an in-process EventBus and pass it to the core facade.
    bus = EventBus()
    core = ZFeiQCore(event_bus=bus)
    bridge = CoreBridge(core)
    adapter = CoreAdapter(bridge)
    # Pass the adapter into the GUI; the GUI will either accept it as a
    # backend (original full MainWindow) or as core_bridge for the refactored lightweight window.
    launch_gui(core_bridge=adapter)


if __name__ == "__main__":
    main()
