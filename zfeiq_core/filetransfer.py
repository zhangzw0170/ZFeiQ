import os
import socket
import threading
import uuid
from dataclasses import dataclass
from typing import Optional, Callable, Tuple
import time
from .protocol import build_packet_with_no, parse_packet, IPMSG_GETFILEDATA, IPMSG_RELEASEFILES, base_command

BUFFER_SIZE = 64 * 1024


@dataclass
class OutgoingOffer:
    offer_id: str
    filepath: str
    filename: str
    size: int
    port: int
    server: 'SingleFileServer'


class SingleFileServer:
    """Serve a single file once over TCP. Closes after one client finishes.
    Protocol: client connects and reads bytes until EOF.
    """
    def __init__(self, filepath: str, bind_ip: str = "0.0.0.0") -> None:
        self.filepath = filepath
        self.bind_ip = bind_ip
        self._sock: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self.port: int = 0

    def start(self) -> int:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((self.bind_ip, 0))  # ephemeral port
        s.listen(1)
        self.port = s.getsockname()[1]
        self._sock = s
        self._thread = threading.Thread(target=self._serve_once, daemon=True)
        self._thread.start()
        return self.port

    def _serve_once(self) -> None:
        assert self._sock is not None
        try:
            self._sock.settimeout(300)
            conn, _ = self._sock.accept()
        except Exception:
            return
        try:
            with conn:
                with open(self.filepath, 'rb') as f:
                    while not self._stop.is_set():
                        data = f.read(BUFFER_SIZE)
                        if not data:
                            break
                        conn.sendall(data)
        except Exception:
            pass
        finally:
            try:
                self._sock.close()
            except Exception:
                pass

    def stop(self) -> None:
        self._stop.set()
        s = self._sock
        self._sock = None
        if s:
            try:
                s.close()
            except Exception:
                pass
        t = self._thread
        self._thread = None
        if t and t.is_alive():
            try:
                t.join(timeout=1.0)
            except Exception:
                pass


def create_offer(filepath: str, bind_ip: str = "0.0.0.0") -> OutgoingOffer:
    if not os.path.isfile(filepath):
        raise FileNotFoundError(filepath)
    filename = os.path.basename(filepath)
    size = os.path.getsize(filepath)
    offer_id = uuid.uuid4().hex[:8]
    srv = SingleFileServer(filepath, bind_ip=bind_ip)
    port = srv.start()
    return OutgoingOffer(offer_id=offer_id, filepath=filepath, filename=filename, size=size, port=port, server=srv)


def download_file(ip: str, port: int, save_path: str, timeout: float = 300.0, on_progress=None, retries: int = 0, stop_event: Optional[threading.Event] = None) -> None:
    """Download file from TCP server with interruptible loop.

    - Uses socket timeouts and checks `stop_event` between recv attempts.
    - `stop_event` is optional; if set and becomes signalled, function raises `InterruptedError`.
    """
    attempt = 0
    while True:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            # initial connect with total timeout
            s.settimeout(min(10.0, timeout))
            s.connect((ip, port))
            total = 0
            # switch to shorter recv timeout to allow interruption checks
            s.settimeout(5.0)
            with s:
                with open(save_path, 'wb') as f:
                    last_progress_ts = time.time()
                    while True:
                        try:
                            data = s.recv(BUFFER_SIZE)
                        except socket.timeout:
                            # check for cancellation or total timeout
                            if stop_event and stop_event.is_set():
                                raise InterruptedError("download cancelled")
                            # check overall timeout
                            if (time.time() - last_progress_ts) > timeout:
                                raise TimeoutError("download timed out")
                            continue
                        if not data:
                            break
                        f.write(data)
                        total += len(data)
                        last_progress_ts = time.time()
                        if on_progress:
                            try:
                                on_progress(total)
                            except Exception:
                                pass
            return
        except InterruptedError:
            # propagate cancellation
            raise
        except Exception:
            # on failure, retry if allowed
            try:
                s.close()
            except Exception:
                pass
            if attempt >= retries:
                raise
            attempt += 1
            continue


class IPMsgFileServer:
    """Minimal TCP/2425 server to serve files for IPMSG_GETFILEDATA requests.

    resolver(pid:int, aid:int) -> filepath or None
    """

    def __init__(self, resolver: Callable[[int, int], Optional[str]], bind_ip: str = "0.0.0.0", releaser: Optional[Callable[[int, int], None]] = None) -> None:
        self.resolver = resolver
        self.releaser = releaser
        self.bind_ip = bind_ip
        self._sock: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((self.bind_ip, 2425))
        s.listen(5)
        self._sock = s
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        s = self._sock
        self._sock = None
        if s:
            try:
                s.close()
            except Exception:
                pass
        t = self._thread
        self._thread = None
        if t and t.is_alive():
            try:
                t.join(timeout=1.0)
            except Exception:
                pass

    def _serve(self) -> None:
        assert self._sock is not None
        self._sock.settimeout(1.0)
        while not self._stop.is_set():
            try:
                conn, addr = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(target=self._handle, args=(conn, addr), daemon=True).start()

    def _handle(self, conn: socket.socket, addr: Tuple[str, int]) -> None:
        try:
            conn.settimeout(5.0)
            # Read some bytes for header (IPMSG packet over TCP)
            raw = b""
            try:
                while len(raw) < 4096:
                    chunk = conn.recv(1024)
                    if not chunk:
                        break
                    raw += chunk
                    if b":" in raw:
                        # heuristic: enough for parse_packet to split 6 parts
                        if raw.count(b":") >= 5:
                            break
            except Exception:
                pass
            hdr, ext = parse_packet(raw)
            base = base_command(hdr.get("command", 0))
            if base not in (IPMSG_GETFILEDATA, IPMSG_RELEASEFILES):
                conn.close()
                return
            pid = 0
            aid = 0
            try:
                parts = (ext or "").split(":")
                if len(parts) >= 2:
                    pid = int(parts[0])
                    aid = int(parts[1])
            except Exception:
                pass
            if base == IPMSG_RELEASEFILES:
                if (pid and aid) and self.releaser:
                    try:
                        self.releaser(pid, aid)
                    except Exception:
                        pass
                # nothing to send back; close
                return
            # GETFILEDATA
            path = self.resolver(pid, aid) if (pid and aid) else None
            if not path or not os.path.isfile(path):
                conn.close()
                return
            with open(path, "rb") as f:
                while True:
                    data = f.read(BUFFER_SIZE)
                    if not data:
                        break
                    conn.sendall(data)
        except Exception:
            pass
        finally:
            try:
                conn.close()
            except Exception:
                pass


def ipmsg_download_file(ip: str, packet_no: int, attach_id: int, save_path: str, username: str, hostname: str, encoding: str = "utf-8", timeout: float = 300.0, on_progress=None, send_release: bool = True, stop_event: Optional[threading.Event] = None) -> None:
    """Download file via IPMSG_GETFILEDATA from peer's TCP/2425.

    This implementation is interruptible via `stop_event` and uses short recv timeouts
    to periodically check for cancellation and timeouts.
    """
    total = 0
    # create initial connection
    s = socket.create_connection((ip, 2425), timeout=min(10.0, timeout))
    try:
        s.settimeout(5.0)
        pkt = build_packet_with_no(packet_no, username, hostname, IPMSG_GETFILEDATA, f"{packet_no}:{attach_id}", encoding=encoding)
        s.sendall(pkt)
        with open(save_path, 'wb') as f:
            last_progress_ts = time.time()
            while True:
                try:
                    data = s.recv(BUFFER_SIZE)
                except socket.timeout:
                    if stop_event and stop_event.is_set():
                        raise InterruptedError("download cancelled")
                    if (time.time() - last_progress_ts) > timeout:
                        raise TimeoutError("download timed out")
                    continue
                if not data:
                    break
                f.write(data)
                total += len(data)
                last_progress_ts = time.time()
                if on_progress:
                    try:
                        on_progress(total)
                    except Exception:
                        pass
    finally:
        try:
            s.close()
        except Exception:
            pass
    # 下载完成后，按规范发送 RELEASEFILES 通知对端（可选）
    if send_release:
        try:
            with socket.create_connection((ip, 2425), timeout=min(10.0, timeout)) as s2:
                s2.settimeout(5.0)
                rel = build_packet_with_no(packet_no, username, hostname, IPMSG_RELEASEFILES, f"{packet_no}:{attach_id}", encoding=encoding)
                s2.sendall(rel)
        except Exception:
            pass
