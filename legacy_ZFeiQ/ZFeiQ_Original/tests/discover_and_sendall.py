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
        print(f"[TEST] online as {app.username}@{app.local_ip}")

        # wait for discovery
        time.sleep(2.0)
        nodes = app.registry.list_nodes()
        print(f"[TEST] discovered {len(nodes)} node(s):")
        for n in nodes:
            print(f" - {n.username}@{n.ip} ({n.hostname})")

        # try sendall
        app.cmd_sendall("hello from auto test")
        time.sleep(1.5)
        print("[TEST] sendall attempted; exiting")
    finally:
        app.stop()


if __name__ == "__main__":
    main()
