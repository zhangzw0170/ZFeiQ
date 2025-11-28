#!/usr/bin/env python3
"""Smoke test: simulate two ZFeiQCli instances exchanging pubkeys and fingerprints.

This test runs without opening UDP sockets by directly invoking the
`_on_recv(data, addr)` handler to simulate received packets.

Run from repository root:
  python3 ZFeiQ_Original/tests/test_key_exchange_smoke.py

Exit codes:
  0 - success
  1 - failure
"""
from __future__ import annotations

import sys
import os
import time
import hashlib

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)

from zfeiq_cli.cli import ZFeiQCli
from zfeiq_cli.protocol import build_packet, IPMSG_BR_ENTRY, IPMSG_ANSPUBKEY, IPMSG_GETPUBKEY


def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def simulate_handshake():
    # Create two CLI instances (no transports started)
    a = ZFeiQCli(port=2426)
    b = ZFeiQCli(port=2426)
    a.username = 'alice'
    b.username = 'bob'

    # Ensure both have keypairs
    assert a._ensure_keys(), "A key gen failed"
    assert b._ensure_keys(), "B key gen failed"

    # Build A's BR_ENTRY packet (contains fp via _build_status_ext)
    a_ext = a._build_status_ext()
    a_pkt = build_packet(a.username, a.hostname, IPMSG_BR_ENTRY, a_ext, encoding='utf-8')
    a_ip = '10.0.0.1'

    # Simulate B receiving A's BR_ENTRY
    b._on_recv(a_pkt, (a_ip, 2425))

    # B should have recorded announced fingerprint for A
    announced_fp = b._peer_fps.get(a_ip)
    expected_a_fp = sha256_hex(a._pub_pem or b'')
    if announced_fp != expected_a_fp:
        print(f"FAIL: B did not record A announced fp correctly: got={announced_fp} expect={expected_a_fp}")
        return 1
    print(f"OK: B recorded A announced fp={announced_fp}")

    # Now simulate B proactively sending ANSPUBKEY back to A (what real code would do)
    b_pem_txt = (b._pub_pem or b"").decode('utf-8', errors='ignore')
    b_pkt = build_packet(b.username, b.hostname, IPMSG_ANSPUBKEY, b_pem_txt, encoding='utf-8')
    b_ip = '10.0.0.2'

    # Simulate A receiving B's ANSPUBKEY
    a._on_recv(b_pkt, (b_ip, 2425))

    # A should have stored B's pubkey and fingerprint
    stored_pub = a._peer_pubkeys.get(b_ip)
    if not stored_pub:
        print("FAIL: A did not store B's pubkey")
        return 1
    stored_fp = a._peer_fps.get(b_ip)
    expected_b_fp = sha256_hex(b._pub_pem or b'')
    if stored_fp != expected_b_fp:
        print(f"FAIL: A stored fp mismatch: got={stored_fp} expect={expected_b_fp}")
        return 1
    print(f"OK: A stored B pubkey and fp={stored_fp}")

    # Also verify B still has A's fp recorded
    if b._peer_fps.get(a_ip) != expected_a_fp:
        print("FAIL: B lost A announced fp")
        return 1

    # Test GETPUBKEY -> ANSPUBKEY flow simulation: C requests A's pubkey
    c = ZFeiQCli(port=2426)
    c.username = 'charlie'
    # Simulate C sending GETPUBKEY to A
    req = build_packet(c.username, c.hostname, IPMSG_GETPUBKEY, 'GETPUBKEY', encoding='utf-8')
    a._on_recv(req, ('10.0.0.3', 2425))
    # A would reply ANSPUBKEY; simulate reply and ensure receiver parses it
    # Build explicit ANSPUBKEY from A and deliver to C
    a_pem_txt = (a._pub_pem or b"").decode('utf-8', errors='ignore')
    resp = build_packet(a.username, a.hostname, IPMSG_ANSPUBKEY, a_pem_txt, encoding='utf-8')
    c._on_recv(resp, ('10.0.0.1', 2425))
    # c should now have A's pubkey recorded
    if not c._peer_pubkeys.get('10.0.0.1'):
        print("FAIL: C did not record A's pubkey via ANSPUBKEY")
        return 1
    print("OK: GETPUBKEY/ANSPUBKEY simulated flow works")

    return 0


if __name__ == '__main__':
    rc = simulate_handshake()
    if rc == 0:
        print("SMOKE TEST PASSED")
    else:
        print("SMOKE TEST FAILED")
    sys.exit(rc)
