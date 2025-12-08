import os
import sys
from zfeiq_cli.cli import ZFeiQCli

# Minimal unit checks for ikm ordering helper

def main() -> int:
    cli = ZFeiQCli(bind_ip="127.0.0.1", port=2425)
    # Different IPs
    a = b"A"*32
    b = b"B"*32
    ikm1 = cli._derive_ikm_ip_order("10.0.0.1", "10.0.0.2", a, b)
    ikm2 = cli._derive_ikm_ip_order("10.0.0.2", "10.0.0.1", b, a)
    assert ikm1 == ikm2 and len(ikm1) == 64
    # Equal IPs fallback
    a2 = os.urandom(32)
    b2 = os.urandom(32)
    ikm3 = cli._derive_ikm_ip_order("10.0.0.1", "10.0.0.1", a2, b2)
    ikm4 = cli._derive_ikm_ip_order("10.0.0.1", "10.0.0.1", b2, a2)
    assert ikm3 == ikm4 and len(ikm3) == 64
    print("[OK] ikm helper symmetry holds")
    return 0

if __name__ == "__main__":
    sys.exit(main())
