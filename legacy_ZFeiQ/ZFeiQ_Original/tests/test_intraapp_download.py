import os
import sys
import tempfile
import hashlib

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from zfeiq_cli.filetransfer import SingleFileServer, download_file


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        while True:
            b = f.read(65536)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def main():
    # prepare a temp file
    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, "src.bin")
        dst = os.path.join(td, "dst.bin")
        with open(src, 'wb') as f:
            f.write(os.urandom(1024 * 256))  # 256 KB
        s = SingleFileServer(src, bind_ip="127.0.0.1")
        port = s.start()
        try:
            download_file("127.0.0.1", port, dst)
            assert os.path.getsize(dst) == os.path.getsize(src)
            assert sha256(dst) == sha256(src)
            print("[TEST] intra-app download PASS")
        finally:
            s.stop()


if __name__ == "__main__":
    main()
