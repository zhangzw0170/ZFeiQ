import os
import sys

# ensure project root on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from zfeiq_cli.protocol import build_packet, parse_packet, IPMSG_SENDMSG


def main():
    pkt = build_packet("alice", "hostA", IPMSG_SENDMSG, "hello")
    header, ext = parse_packet(pkt)
    assert header["ver"] == "1"
    assert header["username"] == "alice"
    assert header["hostname"] == "hostA"
    assert header["command"] == IPMSG_SENDMSG
    assert ext == "hello"
    print("protocol roundtrip PASS")


if __name__ == "__main__":
    main()
