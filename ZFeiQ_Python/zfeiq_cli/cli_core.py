"""A tiny CLI adapter that talks to the new core facade.

This is a reference example showing how the CLI front-end can use the new
`ZFeiQCore` API and subscribe to events.
"""
from typing import Any
from zfeiq_core import ZFeiQCore, EventBus


class ZFeiQCli:
    def __init__(self, core: ZFeiQCore):
        self.core = core
        self.bus: EventBus = core.bus
        self.bus.subscribe("msg.incoming", self._on_incoming)
        self.bus.subscribe("msg.sent", self._on_sent)

    def _on_incoming(self, payload: Any):
        print(f"[INCOMING] {payload}")

    def _on_sent(self, payload: Any):
        print(f"[SENT] {payload}")

    def run_demo(self, username: str = "cli_user"):
        self.core.login(username)
        self.core.send_message("all", "Hello from CLI bridge")
