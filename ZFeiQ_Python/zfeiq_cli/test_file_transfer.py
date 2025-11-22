import os
import time
from adapter import CLIAdapter


def run_test():
    a = CLIAdapter(username="file_test")
    # create a small temp file to serve
    src = os.path.join(os.getcwd(), "ZFeiQ_Python", "zfeiq_cli", "_tmp_test_file.bin")
    with open(src, "wb") as f:
        f.write(b"TEST-DATA-12345")
    pno = 12345
    aid = 1
    # register mapping on local FileService
    a.core.register_file(pno, aid, src)
    dest = os.path.join(os.getcwd(), "ZFeiQ_Python", "zfeiq_cli", "_downloaded.bin")
    try:
        if os.path.exists(dest):
            os.remove(dest)
    except Exception:
        pass
    t = a.core.download_file("127.0.0.1", pno, aid, dest)
    # wait for completion (threaded)
    t.join(timeout=5)
    time.sleep(0.2)
    ok = os.path.exists(dest)
    size = os.path.getsize(dest) if ok else 0
    print("download exists:", ok, "size:", size)
    # cleanup
    try:
        a.cmd_logout()
    except Exception:
        pass

if __name__ == "__main__":
    run_test()
