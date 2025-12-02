import socket
import ipaddress
import threading
from typing import Callable, Optional

DEFAULT_PORT = 2425


class UdpTransport:
    def __init__(self, bind_ip: str = "0.0.0.0", port: int = DEFAULT_PORT,
                 recv_callback: Optional[Callable[[bytes, tuple], None]] = None,
                 iface_ip: Optional[str] = None,
                 iface_prefix: Optional[int] = None,
                 on_debug_log: Optional[Callable[[str], None]] = None) -> None:
        """UDP 传输层

        bind_ip: 用于 socket.bind 的地址，建议在 Linux 绑定 0.0.0.0 以可靠接收广播
        iface_ip: 用于推断定向广播地址（如果未提供，则使用 bind_ip 推断）
        """
        self.bind_ip = bind_ip
        self.iface_ip = iface_ip or bind_ip
        self.port = port
        self.recv_callback = recv_callback
        self.sock: Optional[socket.socket] = None
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        # 单一子网广播地址（如 192.168.1.255）；若无法推断，则回退到 255.255.255.255
        self._broadcast_addr = "255.255.255.255"
        self._iface_prefix = iface_prefix
        self._on_debug = on_debug_log

    def _log(self, msg: str) -> None:
        cb = getattr(self, "_on_debug", None)
        if cb:
            try:
                cb(msg)
                return
            except Exception:
                pass
        # fallback
        print(msg)

    def start(self) -> None:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            # Not available on all platforms, ignore if fails
            s.setsockopt(socket.SOL_SOCKET, getattr(socket, "SO_REUSEPORT", 15), 1)
        except Exception:
            pass
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.bind((self.bind_ip, self.port))
        # 动态根据 iface_ip 推断广播地址：
        # - 若 iface_ip 为 0.0.0.0/127.0.0.1：使用 255.255.255.255；
        # - 否则基于 iface_ip/iface_prefix 推断子网定向广播地址（如 192.168.1.255）。
        if self.iface_ip not in ("0.0.0.0", "127.0.0.1"):
            try:
                if self._iface_prefix and 0 < self._iface_prefix <= 32:
                    net = ipaddress.IPv4Interface(f"{self.iface_ip}/{self._iface_prefix}").network
                    self._broadcast_addr = str(net.broadcast_address)
                else:
                    ip_parts = self.iface_ip.split(".")
                    if len(ip_parts) == 4:
                        self._broadcast_addr = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.255"
            except Exception:
                self._broadcast_addr = "255.255.255.255"
        self.sock = s
        self._stop.clear()
        self._thread = threading.Thread(target=self._recv_loop, name="zfeiq-recv", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        # signal stop and close socket so recv loop unblocks
        self._stop.set()
        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass
        self.sock = None
        # ensure background recv thread exits before interpreter shutdown
        t = self._thread
        self._thread = None
        if t and t.is_alive():
            try:
                t.join(timeout=1.0)
            except Exception:
                pass

    def _recv_loop(self) -> None:
        assert self.sock is not None
        while not self._stop.is_set():
            try:
                data, addr = self.sock.recvfrom(65535)
            except OSError:
                break
            except Exception:
                continue
            if self.recv_callback:
                try:
                    self.recv_callback(data, addr)
                except Exception:
                    # swallow exceptions from callback to keep loop alive
                    pass

    def send_broadcast(self, data: bytes) -> None:
        if not self.sock:
            raise RuntimeError("transport not started")
        # 调试输出：仅显示当前计算出的单一广播地址
        self._log(f"[DEBUG] send_broadcast: local_ip={self.iface_ip}, bcast={self._broadcast_addr}, port={self.port}")
        try:
            self.sock.sendto(data, (self._broadcast_addr, self.port))
        except Exception as e:
            self._log(f"[DEBUG] send_broadcast to {self._broadcast_addr} failed: {e}")

    def send_unicast(self, ip: str, data: bytes) -> None:
        if not self.sock:
            raise RuntimeError("transport not started")
        self.sock.sendto(data, (ip, self.port))
    
    def send_unicast_port(self, ip: str, port: int, data: bytes) -> None:
        """Send a UDP datagram to a specific ip:port, bypassing default port.

        Useful for testing or multi-instance setups on the same host.
        """
        if not self.sock:
            raise RuntimeError("transport not started")
        try:
            self._sock.sendto(data, (ip, int(port)))
        except Exception:
            # fallback to default port
            self._sock.sendto(data, (ip, self.port))
