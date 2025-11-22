from typing import Optional, List
from .events import EventBus, TOPIC_MSG_INCOMING, TOPIC_MSG_SENT, TOPIC_UDP_RECEIVED, TOPIC_FILE_PROGRESS, TOPIC_FILE_COMPLETE, TOPIC_NET_REBIND, TOPIC_USER_OFFLINE
from .entities.message import Message
from .services.history import HistoryService
from .services.crypto import CryptoService
from typing import Optional
from pathlib import Path
import threading
import socket
from .persistence import Persistence
import time


class ZFeiQCore:
    """Facade for core operations. Keeps minimal state and emits events via EventBus.

    This is intentionally small: it's a starting point for the refactor.
    """

    def __init__(self, event_bus: EventBus, db_path: Optional[str] = None):
        self.bus = event_bus
        self.history = HistoryService(db_path or ":memory:")
        self._username: Optional[str] = None
        self.network = None
        self.protocol = None
        self.crypto = CryptoService()
        self._priv_pem: Optional[bytes] = None
        self._pub_pem: Optional[bytes] = None
        self._priv_path: Optional[str] = None
        self._pub_path: Optional[str] = None
        self.persistence = Persistence()
        # node registry: ip -> {username, last_seen}
        self._nodes = {}
        self._keepalive = 0
        self._expire = 0
        self._keepalive_thread = None
        self._expire_thread = None
        # rebind throttle
        self._last_rebind = 0.0
        self._rebind_throttle = 10.0
        # subscribe to online/offline events to maintain registry
        try:
            self.bus.subscribe(TOPIC_USER_ONLINE, self._on_user_online_event)
            # some services publish user.offline; subscribe via centralized constant
            self.bus.subscribe(TOPIC_USER_OFFLINE, self._on_user_offline_event)
        except Exception:
            pass

    def login(self, username: str) -> None:
        self._username = username
        # emit a user.online event (payload: username)
        self.bus.publish("user.online", {"username": username})

    def send_message(self, to: str, text: str) -> Message:
        if not self._username:
            raise RuntimeError("Not logged in")
        msg = Message(from_user=self._username, to=to, text=text)
        # persist
        msg.id = self.history.add_message(msg)
        # emit sent + incoming for local testing
        self.bus.publish(TOPIC_MSG_SENT, msg.dict())
        self.bus.publish(TOPIC_MSG_INCOMING, msg.dict())
        return msg

    def attach_network(self, network_service) -> None:
        """Attach a NetworkService instance so the core can react to incoming
        UDP packets. The network service is expected to publish
        `TOPIC_UDP_RECEIVED` events on the bus; this method subscribes the
        core to that topic and transforms raw packets into `Message` entities
        (best-effort UTF-8 decode).
        """
        self.network = network_service
        # apply persisted bind/port if present
        try:
            cfg_bind = self.get_config('bind', None)
            if cfg_bind:
                try:
                    self.network.bind_ip = cfg_bind
                except Exception:
                    pass
            cfg_port = self.get_config('port', None)
            if cfg_port:
                try:
                    self.network.port = int(cfg_port)
                except Exception:
                    pass
        except Exception:
            pass

        # ensure listener is active
        try:
            self.network.start()
        except Exception:
            pass

        def _on_udp(payload):
            # Consider auto-rebind before parsing
            try:
                addr = payload.get('addr') if isinstance(payload, dict) else None
                if addr and isinstance(addr, (list, tuple)):
                    remote_ip = addr[0]
                    try:
                        self._auto_rebind_consider(remote_ip)
                    except Exception:
                        pass
            except Exception:
                pass

            # If a protocol parser is attached, delegate parsing to it so
            # the protocol can emit richer events (msg/file_offer/user.online).
            if getattr(self, "protocol", None) is not None:
                try:
                    # protocol.handle_raw_packet expects (payload, bus, entities_module)
                    import types
                    from .entities.message import Message as _Message
                    from .entities.file_offer import FileOffer as _FileOffer

                    entities_ns = types.SimpleNamespace(Message=_Message, FileOffer=_FileOffer)
                    self.protocol.handle_raw_packet(payload, self.bus, entities_ns)
                    return
                except Exception:
                    # fall back to raw text handling below
                    pass

            data = payload.get("data")
            addr = payload.get("addr")
            if not data or not addr:
                return
            try:
                text = data.decode("utf-8", errors="replace")
            except Exception:
                text = ""
            # build a minimal Message (from ip, to == all)
            from_user = addr[0] if isinstance(addr, (list, tuple)) else str(addr)
            msg = Message(from_user=from_user, to="all", text=text)
            msg.id = self.history.add_message(msg)
            self.bus.publish(TOPIC_MSG_INCOMING, msg.dict())

        self.bus.subscribe(TOPIC_UDP_RECEIVED, _on_udp)

    def attach_protocol(self, protocol_service) -> None:
        """Attach a ProtocolService instance so the core can convert raw
        UDP payloads into typed entities (Message/FileOffer/user.online).
        """
        self.protocol = protocol_service

    def ensure_keys(self, priv_path: str = "keys/priv.pem", pub_path: str = "keys/pub.pem", bits: int = 2048) -> None:
        """Ensure RSA keypair exists: load if present, otherwise generate and save.

        After successful load/generation, `self._priv_pem` and `self._pub_pem` are set
        and a `keys.ready` event is published with the public key fingerprint.
        """
        self._priv_path = priv_path
        self._pub_path = pub_path
        # try load
        priv = self.crypto.load_private_key(priv_path)
        pub = self.crypto.load_public_key(pub_path)
        if priv and pub:
            self._priv_pem = priv
            self._pub_pem = pub
        else:
            # generate
            priv_pem, pub_pem = self.crypto.generate_keypair(bits)
            # save
            Path(priv_path).parent.mkdir(parents=True, exist_ok=True)
            self.crypto.save_private_key(priv_pem, priv_path)
            self.crypto.save_public_key(pub_pem, pub_path)
            self._priv_pem = priv_pem
            self._pub_pem = pub_pem

        # publish ready event with fingerprint
        try:
            fp = self.crypto.fingerprint(self._pub_pem) if self._pub_pem else ""
        except Exception:
            fp = ""
        self.bus.publish("keys.ready", {"pub_fingerprint": fp, "pub_path": pub_path})

    def get_public_key(self) -> Optional[bytes]:
        return self._pub_pem

    def get_public_fingerprint(self) -> Optional[str]:
        if not self._pub_pem:
            return None
        return self.crypto.fingerprint(self._pub_pem)

    def set_config(self, key: str, value) -> None:
        try:
            data = self.persistence.read()
        except Exception:
            data = {}
        data[key] = value
        try:
            self.persistence.write(data)
        except Exception:
            pass

    def get_config(self, key: str, default=None):
        try:
            data = self.persistence.read()
            return data.get(key, default)
        except Exception:
            return default

    def attach_file_service(self, file_service) -> None:
        """Attach a FileService so core can register file mappings.

        Example: `core.attach_file_service(fs); core.register_file(packet_no, attach_id, path)`
        """
        self.file_service = file_service
        # apply persisted bind/port if present
        try:
            cfg_bind = self.get_config('bind', None)
            if cfg_bind:
                try:
                    self.file_service.bind_ip = cfg_bind
                except Exception:
                    pass
            cfg_port = self.get_config('file_port', None) or self.get_config('port', None)
            if cfg_port:
                try:
                    self.file_service.port = int(cfg_port)
                except Exception:
                    pass
        except Exception:
            pass
        try:
            self.file_service.start()
        except Exception:
            pass

    def register_file(self, packet_no: int, attach_id: int, path: str) -> None:
        if not getattr(self, "file_service", None):
            raise RuntimeError("file service not attached")
        self.file_service.register_file(packet_no, attach_id, path)

    def unregister_file(self, packet_no: int, attach_id: int) -> None:
        if not getattr(self, "file_service", None):
            return
        self.file_service.unregister_file(packet_no, attach_id)

    def get_history(self, limit: int = 100) -> List[Message]:
        rows = self.history.get_messages(limit)
        return [Message(**r) for r in rows]

    # node registry helpers
    def _on_user_online_event(self, payload):
        try:
            ip = payload.get("ip") if isinstance(payload, dict) else None
            username = payload.get("username") if isinstance(payload, dict) else None
            if not ip and isinstance(payload, dict) and payload.get("from_user"):
                ip = payload.get("from_user")
            if not ip:
                return
            self._nodes[ip] = {"username": username or "", "last_seen": time.time()}
        except Exception:
            pass

    def _on_user_offline_event(self, payload):
        try:
            ip = payload.get("ip") if isinstance(payload, dict) else None
            if not ip:
                return
            self._nodes.pop(ip, None)
        except Exception:
            pass

    def _get_bind_locked(self) -> bool:
        try:
            return bool(self.get_config('bind_locked', False))
        except Exception:
            return False

    def _perform_rebind(self, new_bind_ip: str) -> bool:
        """Attempt to rebind network and file services to new_bind_ip.

        Returns True if rebind was attempted, False if skipped (throttled).
        """
        now = time.time()
        if now - self._last_rebind < self._rebind_throttle:
            return False
        self._last_rebind = now
        try:
            if getattr(self, 'network', None):
                try:
                    self.network.stop()
                except Exception:
                    pass
                try:
                    self.network.bind_ip = new_bind_ip
                except Exception:
                    pass
                try:
                    self.network.start()
                except Exception:
                    pass
            if getattr(self, 'file_service', None):
                try:
                    self.file_service.stop()
                except Exception:
                    pass
                try:
                    self.file_service.bind_ip = new_bind_ip
                except Exception:
                    pass
                try:
                    self.file_service.start()
                except Exception:
                    pass
            try:
                self.bus.publish(TOPIC_NET_REBIND, {'bind_ip': new_bind_ip})
            except Exception:
                pass
            return True
        except Exception:
            return False

    def _auto_rebind_consider(self, remote_ip: str) -> None:
        """Consider auto-rebinding to a local interface on the same /24 as remote_ip.

        Heuristics: IPv4 only; match first 3 octets. Respects user lock.
        """
        try:
            if not remote_ip or self._get_bind_locked():
                return
            local_addrs = []
            if getattr(self, 'network', None) and hasattr(self.network, 'get_bind_info'):
                try:
                    info = self.network.get_bind_info() or {}
                    local_addrs = info.get('local_addrs', []) or []
                except Exception:
                    local_addrs = []
            if not local_addrs:
                try:
                    import socket as _socket
                    hn = _socket.gethostname()
                    local_addrs = _socket.gethostbyname_ex(hn)[2]
                except Exception:
                    local_addrs = []

            def prefix3(ip):
                parts = str(ip).split('.')
                if len(parts) >= 3:
                    return '.'.join(parts[:3])
                return None

            r_pref = prefix3(remote_ip)
            if not r_pref:
                return
            for la in local_addrs:
                lp = prefix3(la)
                if lp and lp == r_pref:
                    cur = getattr(self, 'network', None)
                    cur_bind = getattr(cur, 'bind_ip', None) if cur else None
                    if la != cur_bind:
                        self._perform_rebind(la)
                    return
        except Exception:
            pass

    def set_keepalive(self, seconds: int) -> None:
        self._keepalive = int(seconds)
        # persist
        try:
            self.set_config('keepalive', self._keepalive)
        except Exception:
            pass
        if self._keepalive_thread is None and self._keepalive > 0:
            self._keepalive_thread = threading.Thread(target=self._keepalive_worker, daemon=True)
            self._keepalive_thread.start()

    def _keepalive_worker(self):
        while self._keepalive > 0:
            try:
                if self.network:
                    pkt = f"1:0:{self._username or 'node'}:host:1:"
                    try:
                        self.network.broadcast(self.network.port, pkt.encode('utf-8'))
                    except Exception:
                        pass
            except Exception:
                pass
            time.sleep(self._keepalive)

    def set_expire(self, seconds: int) -> None:
        self._expire = int(seconds)
        try:
            self.set_config('expire', self._expire)
        except Exception:
            pass
        if self._expire_thread is None and self._expire > 0:
            self._expire_thread = threading.Thread(target=self._expire_worker, daemon=True)
            self._expire_thread.start()

    def _expire_worker(self):
        while self._expire > 0:
            now = time.time()
            to_remove = []
            for ip, info in list(self._nodes.items()):
                last = info.get('last_seen', 0)
                if now - last > self._expire:
                    to_remove.append((ip, info.get('username')))
            for ip, username in to_remove:
                self._nodes.pop(ip, None)
                try:
                    self.bus.publish("user.offline", {"username": username, "ip": ip})
                except Exception:
                    pass
            time.sleep(1)

    def download_file(self, remote_addr: str, packet_no: int, attach_id: int, dest_path: str, timeout: int = 10, blocking: bool = False) -> Optional[dict]:
        """Download a file via GETFILEDATA-style request from remote_addr:2425.

        - If `blocking` is False (default), returns the Thread object immediately and
          publishes `TOPIC_FILE_PROGRESS`/`TOPIC_FILE_COMPLETE` events.
        - If `blocking` is True, blocks until completion and returns a result dict
          `{"ok": True, "path": ..., "bytes": N}` or `{"ok": False, "error": ...}`.
        """

        result_container = {"result": None}

        def _worker():
            total = 0
            s = None
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(timeout)
                s.connect((remote_addr, 2425))
                req = f"{int(packet_no)}:{int(attach_id)}\n".encode("utf-8")
                s.sendall(req)
                with open(dest_path, "wb") as f:
                    while True:
                        chunk = s.recv(64 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)
                        total += len(chunk)
                        try:
                            self.bus.publish(TOPIC_FILE_PROGRESS, {"remote": remote_addr, "packet_no": packet_no, "attach_id": attach_id, "bytes": total})
                        except Exception:
                            pass
                try:
                    self.bus.publish(TOPIC_FILE_COMPLETE, {"remote": remote_addr, "packet_no": packet_no, "attach_id": attach_id, "path": dest_path, "bytes": total})
                except Exception:
                    pass
                result_container["result"] = {"ok": True, "path": dest_path, "bytes": total}
            except Exception as e:
                try:
                    self.bus.publish(TOPIC_FILE_COMPLETE, {"remote": remote_addr, "packet_no": packet_no, "attach_id": attach_id, "error": str(e)})
                except Exception:
                    pass
                result_container["result"] = {"ok": False, "error": str(e)}
            finally:
                try:
                    if s:
                        s.close()
                except Exception:
                    pass

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        if blocking:
            t.join()
            return result_container.get("result")
        return t
