"""Demo: show REPL-safe printing behavior for incoming events.

This script creates a CLIAdapter, simulates that the REPL is active, and
fires several event handlers to show the blank-line-before/after + prompt redraw.
"""
import time
import sys

sys.path.insert(0, r'e:\Main\JuniorI\Course_Linux_RK3566\ZFeiQ\ZFeiQ_Python')
from zfeiq_cli.adapter import CLIAdapter


def main():
    a = CLIAdapter(username='demo')
    # simulate REPL active
    a._running = True
    # Simulate some events
    a._on_msg_incoming({'from_user': 'alice', 'text': 'hello demo'})
    time.sleep(0.2)
    a._on_msg_sent({'to': 'all', 'text': 'broadcast test'})
    time.sleep(0.2)
    a._on_file_offer({'from_user': 'bob', 'filename': 'example.txt', 'size': 123})
    time.sleep(0.2)
    a._on_file_progress({'remote': '127.0.0.1', 'packet_no': 1, 'attach_id': 1, 'bytes': 64})
    time.sleep(0.2)
    a._on_file_complete({'path': 'example.txt', 'bytes': 123})


if __name__ == '__main__':
    main()
