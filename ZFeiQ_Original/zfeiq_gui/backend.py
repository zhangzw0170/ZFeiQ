from typing import Optional, Dict, Set
import os, json, time
from PyQt5.QtCore import QObject, pyqtSignal, QThread
import hashlib
from zfeiq_cli.cli import ZFeiQCli
from zfeiq_cli.protocol import parse_packet, base_command, IPMSG_SENDMSG, IPMSG_GETFILEDATA, decode_fileattach_lines


class GuiBackend(QObject):
    message_signal = pyqtSignal(str, str, str)  # sender, ip, text
    file_offer_signal = pyqtSignal(str, str, int)  # sender, filename, size
    nodes_updated = pyqtSignal()
    offers_updated = pyqtSignal()
    file_progress = pyqtSignal(str, int)  # offer_id, bytes
    file_saved = pyqtSignal(str, str)     # offer_id, path

    def __init__(self, port: int = 2425, bind_ip: Optional[str] = None):
        super().__init__()
        self.zcli = ZFeiQCli(port=port, bind_ip=bind_ip)
        # GUI 模式：静音用户向控制台的输出，仅保留日志
        try:
            self.zcli.ui_silent = True
        except Exception:
            pass
        # keep original recv handler
        self._orig_on_recv = self.zcli._on_recv
        self._threads = []  # keep background threads
        self._ui_theme = "light"  # light | dark
        self._ui_avatar = ""      # avatar image path (PNG/JPG)
        # Screenshot dir under project root (ZFeiQ_Original)
        PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        self._screenshot_dir = os.path.join(PROJECT_ROOT, "screenshots")  # 截图保存目录
        try:
            os.makedirs(self._screenshot_dir, exist_ok=True)
        except Exception:
            pass

        # persistence paths
        self._state_path = os.path.join(os.getcwd(), "zfeiq_state.json")
        self._history = []  # list of dict records
        self._history_path = os.path.join(os.getcwd(), "zfeiq_history.json")

        def _wrapped_on_recv(data, addr):
            try:
                # call original behavior (updates registry/history)
                self._orig_on_recv(data, addr)
            except Exception:
                pass
            # additional parse to emit signals for GUI
            try:
                header, ext = parse_packet(data)
                cmd = header.get("command", 0)
                base = base_command(cmd)
                user = header.get("username", "?")
                src_ip = addr[0]
                if base == IPMSG_SENDMSG:
                    text = ext.split("\0", 1)[0] if ext else ""
                    # emit message for UI
                    if text and not text.startswith("FILE_OFFER;"):
                        self.message_signal.emit(user, src_ip, text)
                        # record incoming message
                        self._record("in", user=user, ip=src_ip, target="me", text=text)
                    # attachments
                    attaches = []
                    try:
                        # decode only the part after first NUL (IPMSG attachments live there)
                        ext_after = ext.split("\0", 1)[1] if "\0" in (ext or "") else ""
                        attaches = decode_fileattach_lines(ext_after)
                    except Exception:
                        attaches = []
                    for a in attaches:
                        name = a.get("name", "file")
                        size = int(a.get("size", 0))
                        self.file_offer_signal.emit(user, name, size)
                        # augment offer meta with username and timestamp
                        try:
                            pkt_no = int(header.get("packet_no", 0))
                            aid = int(a.get("id", 0))
                            oid = f"ipmsg-{pkt_no}-{aid}"
                            if oid in getattr(self.zcli, "_incoming_offers", {}):
                                self.zcli._incoming_offers[oid]["uname"] = user
                                self.zcli._incoming_offers[oid]["ts"] = time.time()
                        except Exception:
                            pass
                    # on any file offer, notify offers list refresh
                    if text.startswith("FILE_OFFER;") or attaches:
                        # also handle simple FILE_OFFER;id=...
                        if text.startswith("FILE_OFFER;"):
                            try:
                                meta = {}
                                for token in text.split(";"):
                                    if "=" in token:
                                        k, v = token.split("=", 1)
                                        meta[k.strip()] = v.strip()
                                oid = meta.get("id")
                                if oid and oid in getattr(self.zcli, "_incoming_offers", {}):
                                    self.zcli._incoming_offers[oid]["uname"] = user
                                    self.zcli._incoming_offers[oid]["ts"] = time.time()
                            except Exception:
                                pass
                        self.offers_updated.emit()
                elif base == IPMSG_GETFILEDATA:
                    # ignore
                    pass
            except Exception:
                pass

        # monkeypatch
        self.zcli._on_recv = _wrapped_on_recv

    def start(self):
        # load persisted state before start
        self._load_state()
        self.zcli.start()

    def stop(self):
        try:
            self.zcli.stop()
        except Exception:
            pass

    # proxy methods
    def login(self, name: str):
        self.zcli.cmd_login(name)

    def logout(self):
        self.zcli.cmd_logout()

    def discover(self, target_ip: Optional[str] = None):
        self.zcli.cmd_discover(target_ip)

    def send_text(self, target: str, text: str):
        # target can be ip:1.2.3.4 or user:name or group:name
        self.zcli.cmd_send(target, text)
        self._record("out", user=self.zcli.username or "me", ip=self.zcli.local_ip or "local", target=target, text=text)

    def send_file(self, target: str, path: str):
        self.zcli.cmd_file_send(target, path)
        # treat file send as outgoing message (meta)
        self._record("out", user=self.zcli.username or "me", ip=self.zcli.local_ip or "local", target=target, text=f"[FILE]{os.path.basename(path)}")

    def list_incoming_offers(self):
        return dict(self.zcli._incoming_offers)

    def accept_offer(self, oid: str, save_dir: Optional[str] = None):
        # run in thread with progress
        def run():
            def on_prog(total: int):
                try:
                    self.file_progress.emit(oid, int(total))
                except Exception:
                    pass
            path = None
            try:
                path = self.zcli.accept_offer_ex(oid, save_dir, on_progress=on_prog)
            finally:
                try:
                    if path:
                        self.file_saved.emit(oid, path)
                except Exception:
                    pass
                try:
                    self.offers_updated.emit()
                except Exception:
                    pass
        t = QThread()
        def _start():
            run()
            t.quit()
        def _cleanup():
            try:
                self._threads.remove(t)
            except Exception:
                pass
        t.started.connect(_start)
        t.finished.connect(_cleanup)
        t.start()
        self._threads.append(t)

    def cancel_offer(self, oid: str):
        self.zcli.cmd_file_cancel(oid)
        self.offers_updated.emit()

    def get_nodes(self):
        return self.zcli.registry.list_nodes()

    # ---- settings & info ----
    def set_language(self, val: str):
        if val in ("zhCN","enUS"):
            self.zcli.language = val

    def set_status(self, val: str):
        if val in ("online","busy","away"):
            self.zcli.status = val

    def set_debug(self, on: bool):
        self.zcli.debug = bool(on)

    def set_trace(self, on: bool):
        self.zcli.trace = bool(on)

    def set_encoding(self, val: str):
        v = val.lower()
        if v in ("utf8","utf-8"):
            self.zcli.encoding = "utf-8"
        elif v in ("gbk","gb2312"):
            self.zcli.encoding = "gbk"

    def set_keepalive(self, secs: float):
        try:
            if secs > 0:
                self.zcli.keepalive_interval = float(secs)
        except Exception:
            pass

    def set_expire(self, secs: float):
        try:
            if secs >= 10:
                self.zcli.expire_seconds = float(secs)
        except Exception:
            pass

    def bind_ip(self, ip: str):
        try:
            self.zcli._rebind(ip, user_initiated=True)
        except Exception:
            pass

    def set_download_dir(self, path: str):
        try:
            self.zcli.download_dir = path
        except Exception:
            pass

    def get_net_info(self) -> dict:
        info = {
            "local_ip": self.zcli.local_ip,
            "iface_prefix": self.zcli.iface_prefix,
            "broadcast": getattr(self.zcli.transport, "_broadcast_addr", "255.255.255.255"),
        }
        return info

    def get_local_ifaces(self):
        try:
            return list(self.zcli._local_ifaces_with_prefix())
        except Exception:
            return []

    # ---- history helpers ----
    def get_user_history(self, username: str):
        items = []
        try:
            matches = self.zcli.registry.find_by_username(username)
            for n in matches:
                for ts, d, t in self.zcli.history.get(n.ip):
                    items.append((ts, d, t, n.ip))
        except Exception:
            pass
        items.sort(key=lambda x: x[0])
        return items

    def get_group_history(self, group: str):
        items = []
        try:
            members = self.zcli.groups.get(group, set())
            for uname in sorted(members):
                matches = self.zcli.registry.find_by_username(uname)
                for n in matches:
                    for ts, d, t in self.zcli.history.get(n.ip):
                        items.append((ts, d, t, uname, n.ip))
        except Exception:
            pass
        items.sort(key=lambda x: x[0])
        return items

    # -------- groups & broadcast --------
    def list_groups(self) -> Dict[str, Set[str]]:
        try:
            return {k: set(v) for k, v in self.zcli.groups.items()}
        except Exception:
            return {}

    def group_add(self, group: str, username: str):
        # Equivalent to: /group <group> -add <username>
        self.zcli.cmd_group(group, "-add", username)
        try:
            self._flush_state_async()
        except Exception:
            pass

    def group_remove(self, group: str, username: str):
        # Equivalent to: /group <group> -delete <username>
        self.zcli.cmd_group(group, "-delete", username)
        try:
            self._flush_state_async()
        except Exception:
            pass

    def group_send(self, group: str, text: str):
        # Equivalent to: /group <group> -send <text>
        self.zcli.cmd_group(group, "-send", text)
        self._record("out", user=self.zcli.username or "me", ip=self.zcli.local_ip or "local", target=f"group:{group}", text=text)

    def send_all(self, text: str):
        self.zcli.cmd_sendall(text)
        self._record("out", user=self.zcli.username or "me", ip=self.zcli.local_ip or "local", target="all", text=text)

    # -------- persistence helpers --------
    def _record(self, direction: str, **payload):
        try:
            rec = dict(ts=time.time(), direction=direction, **payload)
            self._history.append(rec)
            # lightweight append to file (only last 200 entries kept in memory)
            if len(self._history) > 200:
                self._history = self._history[-200:]
            # history is stored in a separate file to keep state/config small
            self._flush_history_async()
        except Exception:
            pass

    def _flush_history_async(self):
        try:
            tmp = self._history_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._history, f, ensure_ascii=False, indent=0)
            os.replace(tmp, self._history_path)
        except Exception:
            pass

    def _flush_state_async(self):
        try:
            # write JSON state (config + history) atomically via temp
            state = dict(
                config=dict(
                    language=self.zcli.language,
                    status=self.zcli.status,
                    encoding=self.zcli.encoding,
                    encrypt_mode=getattr(self.zcli, 'encrypt_mode', 'off'),
                    keepalive=self.zcli.keepalive_interval,
                    expire=self.zcli.expire_seconds,
                    bind_ip=self.zcli.local_ip if getattr(self.zcli, '_bind_locked', False) else "",
                    download_dir=getattr(self.zcli, 'download_dir', ""),
                    ui_theme=self._ui_theme,
                    ui_avatar=self._ui_avatar,
                    screenshot_dir=self._screenshot_dir,
                ),
                groups={k: sorted(list(v)) for k, v in getattr(self.zcli, 'groups', {}).items()}
            )
            tmp = self._state_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=0)
            os.replace(tmp, self._state_path)
        except Exception:
            pass

    def _load_state(self):
        try:
            if not os.path.isfile(self._state_path):
                return
            with open(self._state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            cfg = data.get("config", {})
            # load history from separate file if present
            try:
                if os.path.isfile(self._history_path):
                    with open(self._history_path, "r", encoding="utf-8") as hf:
                        hist = json.load(hf)
                    if isinstance(hist, list):
                        self._history = hist[-200:]
            except Exception:
                # fallback: if history present in state (old format), read it
                try:
                    self._history = data.get("history", [])[-200:]
                except Exception:
                    self._history = []
            # restore groups if present
            try:
                groups = data.get("groups", {})
                if isinstance(groups, dict):
                    ng = {}
                    for k, v in groups.items():
                        try:
                            if isinstance(v, list):
                                ng[k] = set(v)
                            elif isinstance(v, (set, tuple)):
                                ng[k] = set(v)
                            else:
                                ng[k] = set()
                        except Exception:
                            ng[k] = set()
                    try:
                        self.zcli.groups = ng
                    except Exception:
                        pass
            except Exception:
                pass
            # apply config early
            if cfg.get("language"):
                self.set_language(cfg.get("language"))
            if cfg.get("status"):
                self.set_status(cfg.get("status"))
            if cfg.get("encoding"):
                self.set_encoding(cfg.get("encoding"))
            if isinstance(cfg.get("keepalive"), (int, float)):
                self.set_keepalive(float(cfg.get("keepalive")))
            if isinstance(cfg.get("expire"), (int, float)):
                self.set_expire(float(cfg.get("expire")))
            if cfg.get("encrypt_mode") in ("off","on","strict"):
                try:
                    self.zcli.encrypt_mode = cfg.get("encrypt_mode")
                except Exception:
                    pass
            if cfg.get("download_dir"):
                try:
                    self.zcli.download_dir = cfg.get("download_dir")
                except Exception:
                    pass
            if cfg.get("bind_ip"):
                try:
                    self.zcli._rebind(cfg.get("bind_ip"), user_initiated=True)
                except Exception:
                    pass
            if cfg.get("ui_theme") in ("light","dark"):
                self._ui_theme = cfg.get("ui_theme")
            if isinstance(cfg.get("ui_avatar"), str):
                self._ui_avatar = cfg.get("ui_avatar") or ""
            if isinstance(cfg.get("screenshot_dir"), str) and cfg.get("screenshot_dir"):
                self._screenshot_dir = cfg.get("screenshot_dir")
                try:
                    os.makedirs(self._screenshot_dir, exist_ok=True)
                except Exception:
                    pass
        except Exception:
            pass

    def save_state(self):
        self._flush_state_async()

    # ---- UI config passthrough (for GUI persistence) ----
    def get_ui_theme(self) -> str:
        return self._ui_theme

    def set_ui_theme(self, theme: str):
        if theme in ("light", "dark"):
            self._ui_theme = theme
            self._flush_state_async()

    def get_ui_avatar(self) -> str:
        return self._ui_avatar

    def set_ui_avatar(self, path: str):
        try:
            if not path:
                self._ui_avatar = ""
            else:
                # 统一使用正斜杠分隔，兼容 Win/Linux
                npath = (path or "").replace("\\", "/")
                if os.path.isfile(npath) and os.path.splitext(npath)[1].lower() in (".png",".jpg",".jpeg"):
                    self._ui_avatar = npath
            self._flush_state_async()
        except Exception:
            pass

    # ---- screenshot dir helpers ----
    def get_screenshot_dir(self) -> str:
        return self._screenshot_dir

    def set_screenshot_dir(self, path: str):
        try:
            if path:
                self._screenshot_dir = (path or "").replace("\\", "/")
                os.makedirs(self._screenshot_dir, exist_ok=True)
            self._flush_state_async()
        except Exception:
            pass

    # ---- encryption/key helpers ----
    def get_encrypt_mode(self) -> str:
        try:
            return getattr(self.zcli, 'encrypt_mode', 'off')
        except Exception:
            return 'off'

    def set_encrypt_mode(self, mode: str):
        if mode in ("off","on","strict"):
            try:
                self.zcli.encrypt_mode = mode
                self._flush_state_async()
            except Exception:
                pass

    def get_pubkey_fingerprint(self) -> str:
        try:
            # ensure keys
            if not getattr(self.zcli, '_pub_pem', None):
                try:
                    self.zcli._ensure_keys()
                except Exception:
                    return "(no key)"
            pub = getattr(self.zcli, '_pub_pem', b"") or b""
            if not pub:
                return "(no key)"
            fp = hashlib.sha256(pub).hexdigest()
            # group into pairs for readability
            return ":".join(fp[i:i+2] for i in range(0, len(fp), 2))
        except Exception:
            return "(error)"

    def regenerate_keys(self) -> bool:
        try:
            from zfeiq_cli.crypto import generate_rsa_keypair
            prv, pub = generate_rsa_keypair(3072)
            self.zcli._priv_pem = prv
            self.zcli._pub_pem = pub
            try:
                self.zcli._save_keys()
            except Exception:
                pass
            return True
        except Exception:
            return False

    def export_pubkey(self, path: str) -> Optional[str]:
        try:
            # ensure
            if not getattr(self.zcli, '_pub_pem', None):
                self.zcli._ensure_keys()
            pub = getattr(self.zcli, '_pub_pem', b"") or b""
            if not pub:
                return None
            os.makedirs(os.path.dirname(path) or os.getcwd(), exist_ok=True)
            with open(path, 'wb') as f:
                f.write(pub)
            return path
        except Exception:
            return None
