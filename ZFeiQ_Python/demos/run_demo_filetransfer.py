"""Demo: start FileService, register a small file, and fetch it via TCP client."""
import time
from zfeiq_core import EventBus, ZFeiQCore
from zfeiq_core.services.filetransfer import FileService
import pathlib


def main():
    bus = EventBus()
    core = ZFeiQCore(bus)
    fs = FileService(bind_ip="127.0.0.1", port=2425)
    core.attach_file_service(fs)

    # create a small temp file
    tmp = pathlib.Path("ZFeiQ_Python/tmp_test_file.bin")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_bytes(b"TEST-DATA-12345")

    packet_no = 99999
    attach_id = 1
    core.register_file(packet_no, attach_id, str(tmp))

    # client: connect and request
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(("127.0.0.1", 2425))
    req = f"{packet_no}:{attach_id}\n".encode("utf-8")
    s.sendall(req)
    data = b""
    while True:
        chunk = s.recv(4096)
        if not chunk:
            break
        data += chunk
    s.close()
    print("received:", data)

    # cleanup
    core.unregister_file(packet_no, attach_id)
    fs.stop()


if __name__ == "__main__":
    main()
