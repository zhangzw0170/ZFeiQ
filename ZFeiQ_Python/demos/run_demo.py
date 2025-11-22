"""Small demo runner showing core usage from `ZFeiQ_Python` refactor.

Run:
    python run_demo.py

It will print events emitted by the core.
"""
from zfeiq_core import EventBus, ZFeiQCore
from zfeiq_core import events


def main():
    bus = EventBus()

    def on_incoming(payload):
        print("[demo] incoming:", payload)

    def on_sent(payload):
        print("[demo] sent:", payload)

    bus.subscribe(events.TOPIC_MSG_INCOMING, on_incoming)
    bus.subscribe(events.TOPIC_MSG_SENT, on_sent)

    core = ZFeiQCore(bus)
    core.login("demo_user")
    core.send_message("all", "Hello from refactored core demo")


if __name__ == "__main__":
    main()
