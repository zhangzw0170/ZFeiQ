import os
import sys
import tempfile
import hashlib

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from zfeiq_cli.filetransfer import IPMsgFileServer, ipmsg_download_file


def sha256(p):
    import hashlib
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(65536), b''):
            h.update(b)
    return h.hexdigest()


def main():
    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, "src.bin")
        dst = os.path.join(td, "dst.bin")
        with open(src, 'wb') as f:
            f.write(os.urandom(1024 * 128))  # 128 KB
        pkt_no = 12345678
        attach_id = 42
        # setup server mapping
        srv = IPMsgFileServer(lambda p, a: src if (p, a) == (pkt_no, attach_id) else None, bind_ip="127.0.0.1")
        srv.start()
        try:
            ipmsg_download_file("127.0.0.1", pkt_no, attach_id, dst, username="tester", hostname="host", encoding="utf-8")
            assert os.path.getsize(dst) == os.path.getsize(src)
            assert sha256(dst) == sha256(src)
            print("[TEST] ipmsg GETFILEDATA loopback PASS")
        finally:
            srv.stop()


if __name__ == "__main__":
    main()
