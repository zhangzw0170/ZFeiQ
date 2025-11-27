import socket
import threading
from typing import Dict, Tuple, Optional
from pathlib import Path


class FileService:
    """Simple TCP file serve mapping compatible with IPMSG GETFILEDATA.

    Behavior:
    - Start a TCP server (default port 2425). Call `register_file(packet_no, attach_id, path)`
      to expose a file for download.
    - Clients connect and send a request in the format `<packet_no>:<attach_id>` (UTF-8),
      server responds by sending raw file bytes and closes the connection.

    This is intentionally minimal for compatibility testing and local LAN use.
    """

    def __init__(self, bind_ip: str = "0.0.0.0", port: int = 2425):
        self.bind_ip = bind_ip
        self.port = port
        self._sock: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        # mapping: (packet_no, attach_id) -> file path
        self._mapping: Dict[Tuple[int, int], str] = {}
        self._lock = threading.Lock()

    def start(self):
        if self._running:
            return
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self.bind_ip, self.port))
        self._sock.listen(5)
        self._running = True
        self._thread = threading.Thread(target=self._serve_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None

    def register_file(self, packet_no: int, attach_id: int, path: str) -> None:
        p = Path(path)
        if not p.exists() or not p.is_file():
            raise FileNotFoundError(path)
        with self._lock:
            self._mapping[(int(packet_no), int(attach_id))] = str(p)

    def unregister_file(self, packet_no: int, attach_id: int) -> None:
        with self._lock:
            self._mapping.pop((int(packet_no), int(attach_id)), None)

    def _serve_loop(self):
        sock = self._sock
        if not sock:
            return
        while self._running:
            try:
                conn, addr = sock.accept()
            except OSError:
                break
            except Exception:
                continue
            t = threading.Thread(target=self._handle_client, args=(conn, addr), daemon=True)
            t.start()

    def _handle_client(self, conn: socket.socket, addr):
        try:
            # read small request (up to 1024 bytes)
            req = b""
            conn.settimeout(5.0)
            while True:
                chunk = conn.recv(1024)
                if not chunk:
                    break
                req += chunk
                # if newline found, stop reading
                if b"\n" in req:
                    break
            text = req.decode("utf-8", errors="replace").strip()
            # expected format: packet_no:attach_id
            if ":" not in text:
                conn.close()
                return
            parts = text.split(":", 1)
            try:
                pno = int(parts[0])
                aid = int(parts[1])
            except Exception:
                conn.close()
                return
            with self._lock:
                fp = self._mapping.get((pno, aid))
            if not fp:
                conn.close()
                return
            # stream file
            with open(fp, "rb") as f:
                while True:
                    data = f.read(64 * 1024)
                    if not data:
                        break
                    try:
                        conn.sendall(data)
                    except Exception:
                        break
        finally:
            try:
                conn.close()
            except Exception:
                pass
