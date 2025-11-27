import socket
import threading
from typing import Optional
from ..events import TOPIC_UDP_RECEIVED


class NetworkService:
    """Basic UDP network service.

    - Binds a UDP socket and listens for incoming datagrams on a background
      thread, publishing received packets via `EventBus` topic
      `net.udp.recv` (payload: dict with keys `data`, `addr`).
    - Provides `send_udp` and `broadcast` helpers.

    Note: this implementation is intentionally small and blocking-safe for
    a single-threaded core that wants to receive network events.
    """

    def __init__(self, event_bus, bind_ip: str = "0.0.0.0", port: int = 2425):
        self._bus = event_bus
        self.bind_ip = bind_ip
        self.port = port
        self._sock: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def start(self):
        if self._running:
            return
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # allow reuse
        try:
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except Exception:
            pass
        # bind
        self._sock.bind((self.bind_ip, self.port))
        self._running = True
        self._thread = threading.Thread(target=self._recv_loop, daemon=True)
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

    def _recv_loop(self):
        sock = self._sock
        if not sock:
            return
        while self._running:
            try:
                data, addr = sock.recvfrom(65536)
            except OSError:
                break
            except Exception:
                continue
            # publish raw packet payload to event bus
            try:
                self._bus.publish(TOPIC_UDP_RECEIVED, {"data": data, "addr": addr})
            except Exception:
                pass

    def send_udp(self, ip: str, port: int, data: bytes) -> None:
        if not self._sock:
            # create ephemeral socket for send
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.sendto(data, (ip, port))
            finally:
                s.close()
            return
        try:
            self._sock.sendto(data, (ip, port))
        except Exception:
            # best-effort
            pass

    def broadcast(self, port: int, data: bytes, broadcast_ip: str = "255.255.255.255") -> None:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            s.sendto(data, (broadcast_ip, port))
        finally:
            s.close()

    def get_bind_info(self) -> dict:
        """Return simple diagnostic info: bind ip, port, local hostnames and addresses."""
        info = {
            "bind_ip": self.bind_ip,
            "port": self.port,
            "broadcast_ip": "255.255.255.255",
            "local_addrs": [],
        }
        try:
            import socket as _socket
            hn = _socket.gethostname()
            info["hostname"] = hn
            # best-effort local addresses
            try:
                addrs = _socket.gethostbyname_ex(hn)[2]
            except Exception:
                addrs = []
            info["local_addrs"] = addrs
        except Exception:
            pass
        return info
