from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import time
import threading


@dataclass
class Node:
    username: str
    hostname: str
    ip: str
    last_seen: float
    status: str = "online"  # online|busy|away (extension-based; best-effort)
    supports_ack: bool = False  # peer supports SENDCHECK/RECVMSG


class NodeRegistry:
    def __init__(self) -> None:
        self._by_ip: Dict[str, Node] = {}
        self._lock = threading.Lock()

    def upsert(self, ip: str, username: str, hostname: str, status: Optional[str] = None, supports_ack: Optional[bool] = None) -> Node:
        with self._lock:
            n = self._by_ip.get(ip)
            now = time.time()
            if n is None:
                n = Node(username=username, hostname=hostname, ip=ip, last_seen=now, status=(status or "online"), supports_ack=bool(supports_ack))
                self._by_ip[ip] = n
            else:
                n.username = username
                n.hostname = hostname
                n.last_seen = now
                if status:
                    n.status = status
                if supports_ack is not None:
                    n.supports_ack = supports_ack
            return n

    def remove(self, ip: str) -> None:
        with self._lock:
            self._by_ip.pop(ip, None)

    def list_nodes(self) -> List[Node]:
        with self._lock:
            return list(self._by_ip.values())

    def find_by_username(self, username: str) -> List[Node]:
        with self._lock:
            return [n for n in self._by_ip.values() if n.username == username]

    def get_by_ip(self, ip: str) -> Optional[Node]:
        with self._lock:
            return self._by_ip.get(ip)

    def purge(self, older_than_seconds: float) -> List[Node]:
        """Remove nodes not seen within the given seconds. Return removed nodes."""
        removed: List[Node] = []
        now = time.time()
        with self._lock:
            to_del = [ip for ip, n in self._by_ip.items() if (now - n.last_seen) > older_than_seconds]
            for ip in to_del:
                removed.append(self._by_ip.pop(ip))
        return removed


class PendingAck:
    def __init__(self) -> None:
        # packet_no -> (ip, text, attempts, last_ts)
        self._data: Dict[int, Tuple[str, str, int, float]] = {}
        self._lock = threading.Lock()

    def add(self, packet_no: int, ip: str, text: str) -> None:
        with self._lock:
            self._data[packet_no] = (ip, text, 1, time.time())

    def remove(self, packet_no: int) -> None:
        with self._lock:
            self._data.pop(packet_no, None)

    def items(self):
        with self._lock:
            return list(self._data.items())

    def update_attempt(self, packet_no: int) -> None:
        with self._lock:
            ip, text, attempts, _ = self._data.get(packet_no, ("", "", 0, 0.0))
            if attempts > 0:
                self._data[packet_no] = (ip, text, attempts + 1, time.time())


class ChatHistory:
    def __init__(self) -> None:
        # ip -> list[(ts, dir, text)] ; dir in {"in","out"}
        self._data: Dict[str, List[Tuple[float, str, str]]] = {}
        self._lock = threading.Lock()

    def add(self, ip: str, direction: str, text: str) -> None:
        with self._lock:
            self._data.setdefault(ip, []).append((time.time(), direction, text))

    def get(self, ip: str) -> List[Tuple[float, str, str]]:
        with self._lock:
            return list(self._data.get(ip, []))
