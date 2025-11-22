import os
import sys
import time
import random

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from zfeiq_cli.cli import ZFeiQCli
from zfeiq_cli.protocol import build_packet, IPMSG_BR_ENTRY


def main():
    app = ZFeiQCli()
    app.start()
    try:
        # set username and announce online
        app.username = f"bot-{random.randint(1000,9999)}"
        pkt = build_packet(app.username, app.hostname, IPMSG_BR_ENTRY)
        app.transport.send_broadcast(pkt)
        print(f"[DEMO] online as {app.username}@{app.local_ip}")

        # simulate a peer for demo (will likely not ack, but okay for demo)
        app.registry.upsert("127.0.0.2", "alice", "demo-host")

        # create group and send
        app.cmd_group("demo", "-add", "alice")
        app.cmd_group("demo", "-send", "hello group!")

        # wait a bit for retrans loop to possibly print
        time.sleep(2.0)
    finally:
        app.stop()


if __name__ == "__main__":
    main()
