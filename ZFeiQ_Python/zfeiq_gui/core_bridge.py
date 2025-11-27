"""CoreBridge adapts ZFeiQCore events to GUI callbacks/signals.

This is a minimal, non-Qt shim: the GUI can register callbacks which will be
called when core events occur. The eventual implementation should convert
these to Qt signals in a thread-safe manner.
"""
from typing import Callable, Any
from zfeiq_core import ZFeiQCore, EventBus


class CoreBridge:
    def __init__(self, core: ZFeiQCore):
        self.core = core
        self.bus: EventBus = core.bus
        self._callbacks = {}

    def on(self, topic: str, callback: Callable[[Any], None]):
        self.bus.subscribe(topic, callback)
        self._callbacks.setdefault(topic, []).append(callback)

    def off(self, topic: str, callback: Callable[[Any], None]):
        self.bus.unsubscribe(topic, callback)
        if topic in self._callbacks:
            try:
                self._callbacks[topic].remove(callback)
            except ValueError:
                pass

    # GUI-facing helpers
    def login(self, username: str):
        self.core.login(username)

    def send_message(self, to: str, text: str):
        return self.core.send_message(to, text)
