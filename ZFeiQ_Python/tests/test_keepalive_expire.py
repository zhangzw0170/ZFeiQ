import time
from zfeiq_cli.adapter import CLIAdapter


def test_keepalive_expire():
    a = CLIAdapter(username="keepalive_test")
    # set short keepalive and expire
    a.cmd_set_keepalive(1)
    a.cmd_set_expire(2)
    # trigger a discover (will populate nodes)
    a.cmd_discover()
    time.sleep(0.5)
    # snapshot nodes
    nodes_before = dict(a.core._nodes)
    print("nodes before:", nodes_before)
    # wait longer than expire
    time.sleep(3)
    nodes_after = dict(a.core._nodes)
    print("nodes after:", nodes_after)
    # nodes_after should be empty or missing previously seen entries
    assert len(nodes_after) <= len(nodes_before)
    a.cmd_logout()


if __name__ == "__main__":
    test_keepalive_expire()
