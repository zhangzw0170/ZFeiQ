"""Automated parity tests for Core <-> CLI adapter.

Run with:
  powershell> $env:PYTHONPATH='e:\Main\JuniorI\Course_Linux_RK3566\ZFeiQ\ZFeiQ_Python'; python tests\parity_tests.py
"""
import os
import time

from zfeiq_cli.adapter import CLIAdapter


def test_basic_flow():
    print("=== parity test: basic flow ===")
    a = CLIAdapter(username="parity_tester")
    # discover + send
    a.cmd_discover()
    time.sleep(0.1)
    a.cmd_send("all", "parity hello")
    time.sleep(0.1)
    # history should include our message
    hist = a.core.get_history(5)
    assert any("parity hello" in (m.text if hasattr(m, 'text') else str(m)) for m in hist)
    print("history ok")
    # file transfer: register a temp file and download via blocking core API
    import tempfile
    td = tempfile.mkdtemp(prefix="parity_test_")
    src = os.path.join(td, "_tmp_parity.bin")
    dst = os.path.join(td, "_tmp_parity_dl.bin")
    with open(src, "wb") as f:
        f.write(b"PARITY-TEST")
    try:
        a.core.register_file(5555, 1, src)
    except Exception as e:
        print("register failed", e)
        raise
    res = a.core.download_file("127.0.0.1", 5555, 1, dst, blocking=True)
    print("download result:", res)
    assert res and res.get("ok")
    assert os.path.exists(dst) and os.path.getsize(dst) == os.path.getsize(src)
    print("file transfer ok")
    # cleanup
    try:
        a.cmd_logout()
    except Exception:
        pass
    print("=== parity test: PASS ===")


if __name__ == "__main__":
    test_basic_flow()
