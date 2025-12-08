import socket
import threading
import time
from typing import Optional, Tuple
import os
import subprocess
from zfeiq_common.fsutils import ensure_dir
import re
import ipaddress
from zfeiq_version import APP_VERSION, APP_LAST_UPDATE
import hashlib

from .protocol import (
    IPMSG_BR_ENTRY,
    IPMSG_BR_EXIT,
    IPMSG_ANSENTRY,
    IPMSG_BR_ABSENCE,
    IPMSG_SENDMSG,
    IPMSG_RECVMSG,
    IPMSG_SENDCHECKOPT,
    IPMSG_GETLIST,
    IPMSG_ANSLIST,
    IPMSG_GETPUBKEY,
    IPMSG_ANSPUBKEY,
    build_packet,
    build_packet_with_no,
    parse_packet,
    base_command,
    gen_packet_no,
    encode_list_entries,
    decode_list_entries,
    IPMSG_GETFILEDATA,
    IPMSG_RELEASEFILES,
    IPMSG_FILEATTACHOPT,
    encode_fileattach_lines,
    decode_fileattach_lines,
)
from .crypto import generate_rsa_keypair, aes_gcm_encrypt, aes_gcm_decrypt, b64e, b64d, hkdf_sha256
from .transport import UdpTransport, DEFAULT_PORT
from .filetransfer import create_offer, download_file, IPMsgFileServer, ipmsg_download_file
from .state import NodeRegistry, PendingAck, ChatHistory


def _decode_bytes_auto(b: bytes) -> str:
    for enc in ("utf-8", "gbk", "cp936", "latin-1"):
        try:
            return b.decode(enc)
        except Exception:
            continue
    return b.decode("latin-1", errors="ignore")


def _win_list_ipv4_addrs() -> list:
    addrs = []  # list of (ip, prefixlen or None)
    try:
        out = subprocess.check_output(["ipconfig"], stderr=subprocess.STDOUT)
        text = _decode_bytes_auto(out)
        lines = [l.strip() for l in text.splitlines()]
        pending_ip = None
        for ln in lines:
            m = re.search(r"IPv4[^:]*:\s*([0-9.]+)", ln, re.IGNORECASE)
            if not m:
                m = re.search(r"IPv4\s*地址[^:]*:\s*([0-9.]+)", ln)
            if m:
                pending_ip = m.group(1)
                continue
            if pending_ip:
                m2 = re.search(r"(Subnet\s*Mask|子网掩码)[^:]*:\s*([0-9.]+)", ln, re.IGNORECASE)
                if m2:
                    mask = m2.group(2)
                    try:
                        prefix = ipaddress.IPv4Network(f"0.0.0.0/{mask}").prefixlen
                    except Exception:
                        prefix = None
                    addrs.append((pending_ip, prefix))
                    pending_ip = None
            if not ln:
                pending_ip = None
    except Exception:
        pass
    return addrs


def _linux_list_ipv4_addrs() -> list:
    addrs = []  # list of (ip, prefixlen)
    try:
        out = subprocess.check_output(["ip", "-4", "addr"], stderr=subprocess.STDOUT)
        text = out.decode("utf-8", errors="ignore")
        for ln in text.splitlines():
            ln = ln.strip()
            m = re.search(r"inet\s+([0-9.]+)/([0-9]+)\b", ln)
            if m and " lo" not in ln and "scope host" not in ln:
                ip = m.group(1)
                prefix = int(m.group(2))
                addrs.append((ip, prefix))
    except Exception:
        pass
    return addrs


def get_best_local_ip() -> str:
    """自动选择最合适的本地 IPv4 地址。

    优先级：
    1) 192.168.137.0/24（Windows ICS/直连常见网段）
    2) 192.168.0.0/16
    3) 172.16.0.0/12
    4) 10.0.0.0/8
    5) 其他私有地址
    否则回退到系统默认出站 IP（8.8.8.8 trick）；失败则 0.0.0.0
    """
    candidates = []  # list of (priority, ip)

    try:
        addrs = _win_list_ipv4_addrs() if os.name == "nt" else _linux_list_ipv4_addrs()
        for ip, prefix in addrs:
            try:
                ipa = ipaddress.IPv4Address(ip)
                if not ipa.is_private or ipa.is_loopback:
                    continue
                prio = 100
                if prefix is None:
                    if ip.startswith("192.168.137."):
                        prio = 0
                    elif ip.startswith("192.168."):
                        prio = 10
                    elif ip.startswith("172."):
                        prio = 20
                    elif ip.startswith("10."):
                        prio = 30
                else:
                    net = ipaddress.IPv4Interface(f"{ip}/{prefix}").network
                    if ipaddress.IPv4Network("192.168.137.0/24").supernet_of(net) or str(net) == "192.168.137.0/24":
                        prio = 0
                    elif ipaddress.IPv4Network("192.168.0.0/16").supernet_of(net) or (str(net).startswith("192.168.") and net.prefixlen >= 16):
                        prio = 10
                    elif ipaddress.IPv4Network("172.16.0.0/12").supernet_of(net):
                        prio = 20
                    elif ipaddress.IPv4Network("10.0.0.0/8").supernet_of(net):
                        prio = 30
                    else:
                        prio = 90
                candidates.append((prio, ip))
            except Exception:
                continue
    except Exception:
        pass

    if candidates:
        candidates.sort(key=lambda x: x[0])
        return candidates[0][1]

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.1)
        try:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        finally:
            s.close()
        return ip
    except Exception:
        return "0.0.0.0"


def get_prefix_for_ip(ip: str) -> Optional[int]:
    try:
        addrs = _win_list_ipv4_addrs() if os.name == "nt" else _linux_list_ipv4_addrs()
        for a, prefix in addrs:
            if a == ip and prefix:
                return int(prefix)
    except Exception:
        return None
    return None


def ts_str(ts: float) -> str:
    return time.strftime("%H:%M:%S", time.localtime(ts))

def ts_str_full(ts: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))


class ZFeiQCli:
    def __init__(self, port: int = DEFAULT_PORT, bind_ip: Optional[str] = None) -> None:
        self.username: Optional[str] = None
        self.hostname: str = socket.gethostname()
        self.local_ip: str = bind_ip if bind_ip else get_best_local_ip()
        # settings
        self.status: str = "online"  # online|busy|away
        self.language: str = "zhCN"   # zhCN|enUS
        self.debug: bool = False
        self.trace: bool = False
        self.time_format: str = "hms"  # hms|full
        self.download_dir: Optional[str] = None
        # GUI 静音模式：抑制面向用户的控制台输出，仅保留日志
        self.ui_silent: bool = False
        # timers (configurable)
        self.keepalive_interval: float = 30.0  # seconds
        self.expire_seconds: float = 90.0      # seconds
        self.purge_interval: float = 10.0      # seconds
        # whether user explicitly bound (via --bind or /set bind); disables auto-rebind
        self._user_bound: bool = bool(bind_ip)
        self.registry = NodeRegistry()
        self.pending = PendingAck()
        self.history = ChatHistory()
        # sessions: ip -> {key: bytes, sid: bytes(8), send_ctr: int, recv_ctr: int, recv_window: set[int], last_ts: float,
        #                     local_seed?: bytes, local_ready: bool, peer_ready: bool, ready_sent: bool,
        #                     ready_announced: bool, await_peer_notice: bool, _first_enc2_sent?: bool}
        self._sessions = {}
        # encryption settings
        # 默认改为 on，便于用户无需手动开启即可进行公钥交换与加密通讯
        self.encrypt_mode: str = "on"  # off|on|strict
        # 显示原始密文与 E-D OK 标签的开关（CLI）
        self.encrypt_show_cipher: bool = False
        self.encrypt_edtag: bool = False
        self._priv_pem: Optional[bytes] = None
        self._pub_pem: Optional[bytes] = None
        self._peer_pubkeys: dict = {}  # ip -> pub_pem bytes
        self._peer_fps: dict = {}  # ip -> fingerprint hex (actual, from pubkey)
        self._peer_fp_announced: dict = {}  # ip -> fingerprint hex (from BR_ENTRY/ANSENTRY)
        # nonce 基字符串（只影响 ENC2 会话 nonce 生成），可在高级设置中覆盖
        self.nonce_base: str = os.environ.get("ZFEIQ_NONCE_BASE", "zfeiq_msg")
        # 简单的握手去抖：记录最近一次收到 KX1/KX2 的时间，避免短时重复处理
        self._kx_recent: dict = {}
        # Linux 上绑定 0.0.0.0 以可靠接收广播，同时通过 iface_ip 指定发送所依据的网卡地址
        listen_ip = self.local_ip if os.name == "nt" else "0.0.0.0"
        self.encoding: str = "utf-8"  # utf-8 | gbk
        self.iface_prefix: Optional[int] = get_prefix_for_ip(self.local_ip)
        self.transport = UdpTransport(
            bind_ip=listen_ip,
            port=port,
            recv_callback=self._on_recv,
            iface_ip=self.local_ip,
            iface_prefix=self.iface_prefix,
            on_debug_log=self._on_debug,
        )

        self._retrans_stop = threading.Event()
        self._retrans_thread: Optional[threading.Thread] = None
        # group name -> set of usernames
        self.groups = {}
        # maintenance: keepalive & purge
        self._maint_stop = threading.Event()
        self._maint_thread = None
        # 当有外部信息刷新时，丢弃当前输入行，重新给提示符
        self._invalidate_input = False
        # 控制下一次 input 是否抑制自带提示（避免我们已经手动打印了一次）
        self._suppress_next_prompt = False
        # file transfer (simple TCP offers)
        self._incoming_offers = {}  # offer_id -> {ip, port, name, size}
        self._outgoing_offers = {}  # offer_id -> {port, name, size, path}
        # IPMSG file-attach interop
        self._attach_map = {}       # (packet_no, attach_id) -> {path, ts}
        self._ipmsg_srv = None      # lazy-start TCP/2425 server
        # auto-bind heuristics
        self._last_auto_rebind_ts: float = 0.0
        # emotes support (CLI): default directory
        try:
            PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            self.emotes_dir = ensure_dir('emotes')
        except Exception:
            self.emotes_dir = os.getcwd()
        # load keys if present
        try:
            self._load_keys()
        except Exception:
            pass

    def _send_text(self, ip: str, text: str) -> None:
        """发送纯文本或 ENC2 加密文本到指定 IP。

        - 优先使用已建立的 ENC2 会话；
        - 若未建会话：触发 HKDF-only 握手；strict 模式下不发送；
        - 始终请求回执（SENDCHECKOPT）。
        """
        if not ip or not isinstance(text, str):
            return
        cmd = IPMSG_SENDMSG | IPMSG_SENDCHECKOPT
        pkt_no = gen_packet_no()
        ext = text
        try:
            if self.encrypt_mode in ("on", "strict"):
                if self._session_can_encrypt(ip):
                    s = self._sessions.get(ip) or {}
                    ctr = int(s.get("send_ctr") or 0) + 1
                    s["send_ctr"] = ctr
                    self._sessions[ip] = s
                    nonce = self._sess_nonce(s.get("sid"), ctr, direction="out")
                    _, ct, tag = aes_gcm_encrypt(s.get("key"), text.encode(self.encoding, errors="ignore"), aad=(s.get("sid") or b""), nonce=nonce)
                    # 简化：统一使用 ENC 前缀承载会话加密帧（原 ENC2 语义）
                    ext = f"ENC;sid={b64e(s.get('sid'))};ctr={ctr};tag={b64e(tag)};b64=" + b64e(ct)
                    try:
                        if not s.get("_first_enc2_sent"):
                            s["_first_enc2_sent"] = True
                            self._handshake_event(ip, f"与 {ip} 的会话已建立，首次通过 ENC 发送加密消息")
                    except Exception:
                        pass
                else:
                    if self._ensure_session(ip):
                        # 我们已有密钥但对端尚未确认，确保发送 ready 帧并提示等待
                        self._send_enc_ready(ip, notify=False, force=True)
                        self._session_mark_waiting(ip)
                    else:
                        # 触发 HKDF-only 握手；严格模式下暂不发送
                        self._start_kx(ip)
                        if self.encrypt_mode == "strict":
                            try:
                                self._handshake_event(ip, f"尚无 ENC2 会话，已发起与 {ip} 的 HKDF 握手；严格模式下不发送")
                            except Exception:
                                pass
                            return
                    if self.encrypt_mode == "strict":
                        try:
                            self._handshake_event(ip, f"等待 {ip} 确认 ENC 会话，严格模式下暂不发送")
                        except Exception:
                            pass
                        return
        except Exception as e:
            print(f"[ENC] 加密失败，退回明文: {e}")
        packet = build_packet_with_no(pkt_no, self.username or "?", self.hostname, cmd, ext, encoding=self.encoding)
        self.transport.send_unicast(ip, packet)
        self.pending.add(pkt_no, ip, text)
        self.history.add(ip, "out", text)

    # ---- handshake / encryption system events ----
    def _handshake_event(self, ip: str, text: str) -> None:
        """Record a human-readable handshake/encryption step.

        - Stored in ChatHistory with direction 'sys' for GUI to render
          as居中系统行；
        - Printed in CLI unless ui_silent.
        """
        try:
            msg = f"[ENC] {text}"
            self.history.add(ip or "*", "sys", msg)
        except Exception:
            pass
        try:
            if not getattr(self, "ui_silent", False):
                ts = ts_str_full(time.time()) if self.time_format == "full" else ts_str(time.time())
                print(f"[{ts}] {msg}")
        except Exception:
            pass

    # ======== session helpers (ENC2) ========
    def _sess_nonce(self, sid: bytes, ctr: int, direction: str) -> bytes:
        # derive 12-byte nonce: SHA256(sid||nonce_base||ctr)[0:12]
        # direction 仅用于内部逻辑，不再参与 nonce 派生，避免双方实现差异导致解密失败
        import hashlib
        h = hashlib.sha256()
        h.update(sid)
        try:
            base = (self.nonce_base or "zfeiq_msg").encode("utf-8", errors="ignore")
        except Exception:
            base = b"zfeiq_msg"
        h.update(base)
        h.update(str(ctr).encode('ascii'))
        return h.digest()[:12]

    def _derive_ikm_ip_order(self, local_ip: str, peer_ip: str, local_seed: bytes, peer_seed: bytes) -> bytes:
        """按 IP 字典序决定 seed 拼接；IP 相同则按 seed 字节序 small+large。

        - 保证 KX1/KX2 两端对同一对 (local_ip, peer_ip) 得到完全一致的 IKM。
        """
        if not isinstance(local_seed, (bytes, bytearray)) or not isinstance(peer_seed, (bytes, bytearray)):
            raise ValueError("seeds must be bytes")
        li = local_ip or ""; pi = peer_ip or ""
        ls = bytes(local_seed); ps = bytes(peer_seed)
        if li == pi:
            return (ls + ps) if ls <= ps else (ps + ls)
        return (ls + ps) if li < pi else (ps + ls)

    def _ensure_session(self, ip: str) -> bool:
        s = self._sessions.get(ip)
        return bool(s and isinstance(s.get('key'), (bytes, bytearray)))

    def _has_active_session(self, ip: str) -> bool:
        """Return True if we have a fully usable ENC2 session for this peer."""
        s = self._sessions.get(ip) or {}
        return bool(isinstance(s.get('key'), (bytes, bytearray)) and isinstance(s.get('sid'), (bytes, bytearray)))

    def _session_can_encrypt(self, ip: str) -> bool:
        s = self._sessions.get(ip) or {}
        return bool(
            isinstance(s.get('key'), (bytes, bytearray))
            and isinstance(s.get('sid'), (bytes, bytearray))
            and bool(s.get('local_ready'))
            and bool(s.get('peer_ready'))
        )

    def _session_mark_waiting(self, ip: str, session: Optional[dict] = None) -> None:
        try:
            s = session if session is not None else self._sessions.get(ip)
            if not s:
                return
            if not s.get('local_ready'):
                return
            if s.get('await_peer_notice'):
                return
            s['await_peer_notice'] = True
            self._sessions[ip] = s
            self._handshake_event(ip, f"已派生 ENC 会话，等待 {ip} 确认加密就绪")
        except Exception:
            pass

    def _send_enc_ready(self, ip: str, session: Optional[dict] = None, *, notify: bool = True, force: bool = False) -> None:
        try:
            s = session if session is not None else self._sessions.get(ip)
            if not s:
                return
            sid = s.get('sid')
            if not isinstance(sid, (bytes, bytearray)):
                return
            if s.get('ready_sent') and not force:
                # 已发送过确认帧，除非显式 force，否则无需重复发送
                return
            text = f"ENCREADY;sid={b64e(sid)}"
            pkt = build_packet(self.username or "?", self.hostname, IPMSG_SENDMSG, text, encoding=self.encoding)
            self.transport.send_unicast(ip, pkt)
            s['ready_sent'] = True
            s.setdefault('local_ready', True)
            # 若对端尚未确认，继续等待；否则关闭等待标记以避免误导日志
            if s.get('peer_ready'):
                s['await_peer_notice'] = False
            else:
                s['await_peer_notice'] = True
                if notify:
                    self._handshake_event(ip, f"已通知 {ip} 会话就绪，等待对端确认")
            self._sessions[ip] = s
            self._session_announce_ready(ip, s)
        except Exception:
            pass

    def _session_announce_ready(self, ip: str, session: Optional[dict] = None) -> None:
        """Emit a single log once双方已确认 ENC 会话可用。"""
        try:
            s = session if session is not None else self._sessions.get(ip)
            if not isinstance(s, dict):
                return
            if s.get('ready_announced'):
                return
            if bool(s.get('local_ready')) and bool(s.get('peer_ready')):
                s['ready_announced'] = True
                s['await_peer_notice'] = False
                self._sessions[ip] = s
                self._handshake_event(ip, f"与 {ip} 的加密通讯已启用")
        except Exception:
            pass

    def _start_kx(self, ip: str, port_override: Optional[int] = None) -> None:
        """Send KX1 (HKDF-only): exchange random seeds in clear text.

        不再依赖 RSA 公钥；双方通过随机种子 + IP 顺序规则派生 IKM 与会话密钥。
        """
        try:
            if not ip:
                return
            # 避免对自身 IP/本机其它网卡地址发起握手
            try:
                allow_local = port_override is not None
                if not allow_local:
                    if ip == self.local_ip:
                        return
                    local_ips = {a for a, _ in (_win_list_ipv4_addrs() if os.name == "nt" else _linux_list_ipv4_addrs())}
                    if ip in local_ips:
                        return
            except Exception:
                pass
            # HKDF-only：不需要本地或对端 RSA 密钥
            if self._ensure_session(ip):
                # 已有会话，无需重复发起
                if self.debug:
                    self._handshake_event(ip, f"与 {ip} 的会话已存在，跳过 KX1")
                return
            import os
            seed = os.urandom(32)
            # 直接携带种子（A）明文；fp 字段留空以兼容旧解析
            fp = ""
            text = f"KX1;ver=1;fp={fp};seedA={b64e(seed)}"
            pkt = build_packet(self.username or "?", self.hostname, IPMSG_SENDMSG, text, encoding=self.encoding)
            try:
                if port_override is not None:
                    self.transport.send_unicast_port(ip, int(port_override), pkt)
                else:
                    self.transport.send_unicast(ip, pkt)
            except Exception:
                self.transport.send_unicast(ip, pkt)
            # cache local seed until peer responds
            self._sessions[ip] = {
                "local_seed": seed,
                "last_ts": time.time(),
                "local_ready": False,
                "peer_ready": False,
                "ready_sent": False,
                "ready_announced": False,
                "await_peer_notice": False,
            }
            self._handshake_event(ip, f"发送 KX1 到 {ip}")
        except Exception as e:
            try:
                self._handshake_event(ip, f"发起 KX1 到 {ip} 失败: {e}")
            except Exception:
                pass

    def force_start_kx(self, ip: str) -> None:
        """Force start a KX1 handshake with peer `ip`.

        - 与 `_start_kx` 不同：不检查 `encrypt_mode`，仅依赖本地/对端公钥与会话状态；
        - 供 GUI 或 CLI 在需要时显式触发单个节点的密钥交换；
        - 若本就已存在会话，则为 no-op。
        """
        try:
            if not ip:
                return
            # 仅在尚未建立会话时尝试发起；具体前置条件由 _start_kx 给出详细提示
            port_override: Optional[int] = None
            ip_only = ip
            try:
                if ":" in ip:
                    host, port_s = ip.split(":", 1)
                    if host.strip():
                        ip_only = host.strip()
                    ps = port_s.strip()
                    if ps.isdigit():
                        port_override = int(ps)
            except Exception:
                ip_only = ip; port_override = None
            if not self._ensure_session(ip_only):
                self._start_kx(ip_only, port_override=port_override)
        except Exception as e:
            try:
                self._handshake_event(ip, f"发起 KX1 到 {ip} 的请求异常: {e}")
            except Exception:
                pass

    def purge_session(self, ip: str) -> None:
        """Clear session and recent KX debounce for a specific peer to allow a clean retry."""
        try:
            if ip in self._sessions:
                try:
                    del self._sessions[ip]
                except Exception:
                    self._sessions.pop(ip, None)
            try:
                # 清除最近的 KX1/KX2 记录，允许立即重试
                self._kx_recent.pop((ip, "KX1"), None)
                self._kx_recent.pop((ip, "KX2"), None)
            except Exception:
                pass
            self._handshake_event(ip, f"已清理与 {ip} 的会话状态，准备重新握手")
        except Exception:
            pass

    # ============ lifecycle ============
    def start(self) -> None:
        try:
            self.transport.start()
        except PermissionError as e:
            print("[FATAL] 无法绑定 UDP 端口，可能被占用或权限受限。")
            print("        解决方案：")
            print("        1) 关闭占用 2425 的程序（如其他飞秋/FeiQ/IPMSG 客户端），或")
            print("        2) 使用 --port 指定其他端口（例如 2426），或")
            print("        3) 在 WSL 中运行一端，Windows 运行另一端（推荐单机双端测试）。")
            print(f"        原始错误：{e}")
            raise
        self._start_retrans()
        self._start_maint()
        self._user_print(self._t("app.started"))
        # 列出本机可用 IP
        try:
            addrs = _win_list_ipv4_addrs() if os.name == "nt" else _linux_list_ipv4_addrs()
            ips = [a for a, _ in addrs]
            if ips:
                self._user_print("本机 IP：")
                for ip in ips:
                    self._user_print(ip)
            # 显示默认下载目录（绝对路径）
            try:
                default_dir = self.download_dir or os.getcwd()
                self._user_print("下载目录：", os.path.abspath(default_dir))
            except Exception:
                pass
        except Exception:
            pass

    def stop(self) -> None:
        self._stop_retrans()
        self._stop_maint()
        self.transport.stop()
        try:
            if self._ipmsg_srv:
                self._ipmsg_srv.stop()
        except Exception:
            pass

    # ---- crypto helpers ----
    def _keys_dir(self) -> str:
        PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        try:
            return ensure_dir('keys')
        except Exception:
            return os.path.join(PROJECT_ROOT, "keys")

    def _load_keys(self) -> None:
        d = self._keys_dir()
        prv = os.path.join(d, "priv.pem"); pub = os.path.join(d, "pub.pem")
        if os.path.isfile(prv) and os.path.isfile(pub):
            try:
                with open(prv, "rb") as f:
                    self._priv_pem = f.read()
                with open(pub, "rb") as f:
                    self._pub_pem = f.read()
            except Exception:
                self._priv_pem = None; self._pub_pem = None

    def _save_keys(self) -> None:
        if not self._priv_pem or not self._pub_pem:
            return
        d = self._keys_dir()
        try:
            with open(os.path.join(d, "priv.pem"), "wb") as f:
                f.write(self._priv_pem)
            with open(os.path.join(d, "pub.pem"), "wb") as f:
                f.write(self._pub_pem)
        except Exception:
            pass

    def _ensure_keys(self) -> bool:
        if self._priv_pem and self._pub_pem:
            return True
        try:
            prv, pub = generate_rsa_keypair(3072)
            self._priv_pem, self._pub_pem = prv, pub
            self._save_keys()
            # 新密钥对生成后，清空会话与对端公钥缓存，触发重新握手
            try:
                self._sessions.clear()
            except Exception:
                self._sessions = {}
            self._peer_pubkeys.clear()
            self._peer_fps.clear()
            self._peer_fp_announced.clear()
            # 若已登录，则广播一次上线信息，携带新的指纹，促使对端重新获取公钥
            try:
                if self.username:
                    ext = self._build_status_ext()
                    cmd = IPMSG_BR_ENTRY if self.status != "away" else IPMSG_BR_ABSENCE
                    pkt = build_packet(self.username, self.hostname, cmd, ext, encoding=self.encoding)
                    self.transport.send_broadcast(pkt)
            except Exception:
                pass
            return True
        except Exception as e:
            print(f"[ERR] keygen: {e}")
            return False

    def _rebind(self, new_ip: str, user_initiated: bool = False) -> None:
        """在运行时切换绑定网卡/IP。

        - Windows: 绑定到 new_ip；
        - Linux: 继续绑定 0.0.0.0 但基于 new_ip 计算广播地址；
        - 若已登录，切换后广播一次 BR_ENTRY/BR_ABSENCE。
        """
        try:
            # 验证 new_ip 是否为本机 IP
            addrs = _win_list_ipv4_addrs() if os.name == "nt" else _linux_list_ipv4_addrs()
            local_ips = {a for a, _ in addrs}
            if new_ip not in local_ips:
                print(self._t("set.bind_bad"))
                return
            # 在切换前，若已登录，则使用旧 IP 广播一次 BR_EXIT，通知对端下线
            try:
                old_ip = self.local_ip
                if self.username and old_ip:
                    try:
                        pkt = build_packet(self.username or "?", self.hostname, IPMSG_BR_EXIT, encoding=self.encoding)
                        # 尽量使用旧传输对象发出：广播 + 向所有已知节点单播
                        try:
                            self.transport.send_broadcast(pkt)
                        except Exception:
                            pass
                        try:
                            for n in self.registry.list_nodes():
                                if n.ip and n.ip != old_ip:
                                    self.transport.send_unicast(n.ip, pkt)
                        except Exception:
                            pass
                    except Exception:
                        pass
            except Exception:
                pass
            # 停止旧传输
            try:
                self.transport.stop()
            except Exception:
                pass
            # 更新本地配置并重建传输
            old_ip = self.local_ip
            self.local_ip = new_ip
            self.iface_prefix = get_prefix_for_ip(self.local_ip)
            listen_ip = self.local_ip if os.name == "nt" else "0.0.0.0"
            port = self.transport.port if hasattr(self.transport, "port") else DEFAULT_PORT
            self.transport = UdpTransport(
                bind_ip=listen_ip,
                port=port,
                recv_callback=self._on_recv,
                iface_ip=self.local_ip,
                iface_prefix=self.iface_prefix,
                on_debug_log=self._on_debug,
            )
            self.transport.start()
            print(self._t("set.bind_done", val=new_ip))
            # 仅当用户显式触发时，锁定当前绑定，禁止自动重绑
            if user_initiated:
                self._user_bound = True
            # 如已登录，切换后立即广播一次
            if self.username:
                try:
                    cmd = IPMSG_BR_ENTRY if self.status != "away" else IPMSG_BR_ABSENCE
                    pkt = build_packet(self.username or "?", self.hostname, cmd, self._build_status_ext(), encoding=self.encoding)
                    self.transport.send_broadcast(pkt)
                    # 更新在线表：移除旧 IP 的自我条目，加入新 IP
                    try:
                        if old_ip and old_ip != self.local_ip:
                            self.registry.remove(old_ip)
                    except Exception:
                        pass
                    try:
                        self.registry.upsert(self.local_ip, self.username, self.hostname, self.status, supports_ack=True)
                    except Exception:
                        pass
                except Exception:
                    pass
        except Exception as e:
            print(f"[ERROR] rebind failed: {e}")

    def _start_retrans(self) -> None:
        self._retrans_stop.clear()
        self._retrans_thread = threading.Thread(target=self._retrans_loop, daemon=True)
        self._retrans_thread.start()

    def _stop_retrans(self) -> None:
        self._retrans_stop.set()
        t = self._retrans_thread
        self._retrans_thread = None
        if t and t.is_alive():
            try:
                t.join(timeout=1.0)
            except Exception:
                pass

    # maintenance: periodic BR_ENTRY keepalive and node purge
    def _start_maint(self) -> None:
        self._maint_stop.clear()
        self._maint_thread = threading.Thread(target=self._maint_loop, daemon=True)
        self._maint_thread.start()

    def _stop_maint(self) -> None:
        self._maint_stop.set()
        t = self._maint_thread
        self._maint_thread = None
        if t and t.is_alive():
            try:
                t.join(timeout=1.0)
            except Exception:
                pass

    # ======== auto NIC selection helpers ========
    def _local_ifaces_with_prefix(self):
        try:
            addrs = _win_list_ipv4_addrs() if os.name == "nt" else _linux_list_ipv4_addrs()
        except Exception:
            addrs = []
        # filter out missing prefixes
        return [(ip, int(pre)) for ip, pre in addrs if pre is not None]

    def _find_ip_same_subnet(self, peer_ip: str) -> Optional[str]:
        best = None
        best_pl = -1
        try:
            pip = ipaddress.IPv4Address(peer_ip)
        except Exception:
            return None
        for ip, pre in self._local_ifaces_with_prefix():
            try:
                net = ipaddress.IPv4Interface(f"{ip}/{pre}").network
                if pip in net:
                    if pre > best_pl:
                        best = ip
                        best_pl = pre
            except Exception:
                continue
        return best

    def _auto_rebind_consider(self, peer_ip: str) -> None:
        """Auto-rebind was originally used to follow peer subnets.

        当前版本取消自动切换行为：登录后本端 IP 仅在显式 /set bind 或 GUI 绑定时变更，
        以避免多网卡环境下频繁在 192.168.x.x / 172.x.x.x 间跳动，导致会话与加密状态混乱。
        """
        return

    def _ingest_peer_pubkey(self, src_ip: str, payload: Optional[str]) -> bool:
        """Parse and store peer public key from GET/ANSPUBKEY payload."""
        try:
            txt = (payload or "").split("\0", 1)[0].strip()
            if not txt:
                return False
            pem_bytes: Optional[bytes]
            if "-----BEGIN PUBLIC KEY-----" in txt:
                pem_bytes = txt.encode("utf-8", errors="ignore")
            else:
                if txt.upper().startswith("PEM:"):
                    b64 = txt.split(":", 1)[1].strip()
                else:
                    b64 = txt
                try:
                    pem_bytes = b64d(b64)
                except Exception:
                    pem_bytes = None
            if not pem_bytes:
                return False
            fp = hashlib.sha256(pem_bytes).hexdigest()
            prev_ann = self._peer_fp_announced.get(src_ip)
            prev_actual = self._peer_fps.get(src_ip)
            # 仅在首次发现 announced 与 actual 不一致时告警一次，避免刷屏
            if prev_ann and prev_ann != fp and not getattr(self, "_fp_warned", {}).get(src_ip, False):
                print(f"[WARN] fingerprint mismatch for {src_ip}: announced={prev_ann} actual={fp}")
                try:
                    warned = getattr(self, "_fp_warned", {})
                    warned[src_ip] = True
                    self._fp_warned = warned
                except Exception:
                    pass
            self._peer_pubkeys[src_ip] = pem_bytes
            self._peer_fps[src_ip] = fp
            # 覆盖旧的 announced 指纹为实际指纹，便于后续 /debug encinfo 收敛一致
            try:
                self._peer_fp_announced[src_ip] = fp
            except Exception:
                pass
            if self.debug:
                print(f"[DBG] learned pubkey from {src_ip} ({len(pem_bytes)} bytes) fp={fp}")
                self._print_prompt(suppress_next=False)
            return True
        except Exception:
            return False

    def _maint_loop(self) -> None:
        last_keepalive = 0.0
        t0 = time.time()
        while not self._maint_stop.is_set():
            now = time.time()
            # keepalive
            if self.username and (now - last_keepalive >= self.keepalive_interval):
                try:
                    # 扩展字段第1段作为昵称（兼容 FeiQ 展示），第2段留空（避免被当作组名），第3段起为自定义键值
                    # 广播在线或缺席（away -> BR_ABSENCE）并声明能力 cap=ack
                    ext = self._build_status_ext()
                    cmd = IPMSG_BR_ENTRY if self.status != "away" else IPMSG_BR_ABSENCE
                    pkt = build_packet(self.username, self.hostname, cmd, ext, encoding=self.encoding)
                    self.transport.send_broadcast(pkt)
                    # 额外：对当前已知节点逐个单播 keepalive（跨子网/广播受限时生效）
                    try:
                        for n in self.registry.list_nodes():
                            if n.ip == self.local_ip:
                                continue
                            self.transport.send_unicast(n.ip, pkt)
                    except Exception:
                        pass
                except Exception:
                    pass
                last_keepalive = now
            # purge stale nodes periodically
            if (now - t0) >= self.purge_interval:
                removed = self.registry.purge(self.expire_seconds)
                for n in removed:
                    if n.ip != self.local_ip:
                        ts = ts_str_full(time.time()) if self.time_format == "full" else ts_str(time.time())
                        print(f"\n[{ts}] - {n.username}@{n.ip} 超时下线")
                        self._print_prompt(suppress_next=False)
                # 清理过期的附件映射，默认保留 10 分钟
                try:
                    ttl = 600.0
                    for key, val in list(self._attach_map.items()):
                        ts0 = val.get("ts", 0.0) if isinstance(val, dict) else 0.0
                        if ts0 and (now - ts0) >= ttl:
                            self._attach_map.pop(key, None)
                    # 映射空时主动停止 2425 服务以节省资源
                    if not self._attach_map and self._ipmsg_srv:
                        try:
                            self._ipmsg_srv.stop()
                        finally:
                            self._ipmsg_srv = None
                except Exception:
                    pass
                t0 = now
            try:
                time.sleep(1.0)
            except Exception:
                break

    def _retrans_loop(self) -> None:
        while not self._retrans_stop.is_set():
            time.sleep(1.0)
            now = time.time()
            for pkt, (ip, text, attempts, last_ts) in list(self.pending.items()):
                if now - last_ts >= 3.0:
                    if attempts >= 3:
                        print(f"[WARN] send to {ip} not acked after {attempts} tries: '{text}'")
                        self.pending.remove(pkt)
                        continue
                    # resend
                    cmd = IPMSG_SENDMSG | IPMSG_SENDCHECKOPT
                    packet = build_packet_with_no(pkt, self.username or "?", self.hostname, cmd, text, encoding=self.encoding)
                    try:
                        self.transport.send_unicast(ip, packet)
                        self.pending.update_attempt(pkt)
                        print(f"[INFO] retransmit #{attempts+1} to {ip}")
                    except Exception as e:
                        print(f"[ERROR] retransmit failed: {e}")

    # ============ networking ============
    def _on_recv(self, data: bytes, addr: Tuple[str, int]) -> None:
        src_ip, _ = addr
        try:
            header, ext = parse_packet(data)
        except Exception:
            return
        cmd = header["command"]
        base = base_command(cmd)
        user = header.get("username", "?")
        host = header.get("hostname", "?")
        pkt_no = header.get("packet_no", 0)

        # （已禁用）自动选网卡逻辑已移除，避免多网卡环境频繁切换

        if self.debug:
            try:
                ts = ts_str_full(time.time()) if self.time_format == "full" else ts_str(time.time())
                print(f"\n[{ts}] [DBG] RECV base={base:#x} from {src_ip} user={user}")
                self._print_prompt(suppress_next=False)
            except Exception:
                pass

        # 公钥握手：GETPUBKEY -> 回复 ANSPUBKEY；接收 ANSPUBKEY 存档
        if base == IPMSG_GETPUBKEY:
            try:
                if self._ensure_keys():
                    # 发送 ANSPUBKEY，扩展放入 PEM 文本；尽量走通用格式
                    pem_txt = (self._pub_pem or b"").decode("utf-8", errors="ignore")
                    pkt = build_packet(self.username or "?", self.hostname, IPMSG_ANSPUBKEY, pem_txt, encoding=self.encoding)
                    self.transport.send_unicast(src_ip, pkt)
            except Exception:
                pass
            try:
                stored = self._ingest_peer_pubkey(src_ip, ext)
                if stored and self.encrypt_mode in ("on","strict") and (not self._ensure_session(src_ip)):
                    self._start_kx(src_ip)
            except Exception:
                pass
            return
        elif base == IPMSG_ANSPUBKEY:
            try:
                stored = self._ingest_peer_pubkey(src_ip, ext)
                if not stored:
                    self._handshake_event(src_ip, f"收到 {src_ip} 的公钥响应但内容为空或无法解析，已忽略")
                else:
                    try:
                        if self.encrypt_mode in ("on", "strict") and (not self._ensure_session(src_ip)):
                            self._start_kx(src_ip)
                    except Exception:
                        pass
            except Exception:
                pass
            # 不进一步处理为在线/消息
            return

        # 会话握手：KX1/KX2（级别B）
        if base == IPMSG_SENDMSG and (ext or "").startswith("KX1;"):
            # 【新增】若本机加密已关闭，直接无视握手请求，阻断会话建立
            if self.encrypt_mode == "off":
                return
            # 忽略来自本机任一 IP 的握手包
            try:
                local_ips = {ip for ip, _ in (_win_list_ipv4_addrs() if os.name == "nt" else _linux_list_ipv4_addrs())}
                if src_ip in local_ips:
                    return
            except Exception:
                pass
            # 若 KX1 中携带的指纹与本机公钥指纹一致，也视为自发自收，直接忽略
            try:
                fp_self = hashlib.sha256((self._pub_pem or b"")).hexdigest() if self._pub_pem else ""
                fields_probe = dict(x.split("=",1) for x in (seg.strip() for seg in (ext or "").split(";") ) if "=" in x)
                if fields_probe.get("fp","") and fp_self and fields_probe.get("fp") == fp_self:
                    return
            except Exception:
                pass
            # 若已存在有效会话，视为重发，直接忽略
            try:
                if self._ensure_session(src_ip):
                    return
            except Exception:
                pass
            # 去抖：3 秒内重复的 KX1 只处理一次
            try:
                now_ts = time.time()
                if now_ts - (self._kx_recent.get((src_ip, "KX1"), 0.0)) < 3.0:
                    return
                self._kx_recent[(src_ip, "KX1")] = now_ts
            except Exception:
                pass
            try:
                # parse seedA (plain)
                fields = dict(x.split("=",1) for x in (seg.strip() for seg in ext.split(";") ) if "=" in x)
                seedA = b64d(fields.get("seedA",""))
                # prepare our seedB and reply KX2 (plain)
                import os
                seedB = os.urandom(32)
                fpB = ""
                text2 = f"KX2;ver=1;fp={fpB};seedB={b64e(seedB)}"
                pkt2 = build_packet(self.username or "?", self.hostname, IPMSG_SENDMSG, text2, encoding=self.encoding)
                self.transport.send_unicast(src_ip, pkt2)
                self._handshake_event(src_ip, f"收到 KX1 来自 {src_ip}，已发送 KX2")
                # derive session via deterministic IP-order rule
                ikm = self._derive_ikm_ip_order(self.local_ip, src_ip, local_seed=seedB, peer_seed=seedA)
                key = hkdf_sha256(ikm, info=b"zfeiq-aes256gcm", length=32)
                import hashlib
                sid = hashlib.sha256(ikm).digest()[:8]
                self._sessions[src_ip] = {
                    "key": key,
                    "sid": sid,
                    "send_ctr": 0,
                    "recv_ctr": 0,
                    "recv_window": set(),
                    "last_ts": time.time(),
                    "local_seed": seedB,
                    "local_ready": True,
                    "peer_ready": False,
                    "ready_sent": False,
                    "ready_announced": False,
                    "await_peer_notice": False,
                }
                if self.debug:
                    print(f"[DBG] session established with {src_ip} sid={b64e(sid)}")
                    self._print_prompt(suppress_next=False)
                self._send_enc_ready(src_ip)
            except Exception:
                pass
            return
        if base == IPMSG_SENDMSG and (ext or "").startswith("ENCREADY;"):
            try:
                fields = dict(x.split("=",1) for x in (seg.strip() for seg in ext.split(";") ) if "=" in x)
                sid_bytes = b64d(fields.get("sid","")) if fields.get("sid") else None
            except Exception:
                sid_bytes = None
            sess = self._sessions.get(src_ip)
            if sess and isinstance(sid_bytes, (bytes, bytearray)) and isinstance(sess.get("sid"), (bytes, bytearray)):
                try:
                    if sess.get("sid") == sid_bytes:
                        if not sess.get("peer_ready"):
                            sess["peer_ready"] = True
                            sess["await_peer_notice"] = False
                            self._handshake_event(src_ip, f"{src_ip} 已确认 ENC 会话就绪")
                        if sess.get("local_ready"):
                            self._send_enc_ready(src_ip, sess, notify=False)
                        self._session_announce_ready(src_ip, sess)
                        self._sessions[src_ip] = sess
                    else:
                        if self.debug:
                            print(f"[DBG] ENCREADY sid mismatch from {src_ip}")
                            self._print_prompt(suppress_next=False)
                except Exception:
                    pass
            else:
                if self.debug:
                    print(f"[DBG] ENCREADY from {src_ip} ignored: no matching session")
                    self._print_prompt(suppress_next=False)
            return
        if base == IPMSG_SENDMSG and (ext or "").startswith("KX2;"):
            # 忽略来自本机任一 IP 的握手包
            try:
                local_ips = {ip for ip, _ in (_win_list_ipv4_addrs() if os.name == "nt" else _linux_list_ipv4_addrs())}
                if src_ip in local_ips:
                    return
            except Exception:
                pass
            # 若 KX2 中携带的指纹与本机公钥指纹一致，也视为自发自收，直接忽略
            try:
                fp_self = hashlib.sha256((self._pub_pem or b"")).hexdigest() if self._pub_pem else ""
                fields_probe = dict(x.split("=",1) for x in (seg.strip() for seg in (ext or "").split(";") ) if "=" in x)
                if fields_probe.get("fp","") and fp_self and fields_probe.get("fp") == fp_self:
                    return
            except Exception:
                pass
            # 若已存在有效会话，视为重发，直接忽略
            try:
                if self._ensure_session(src_ip):
                    return
            except Exception:
                pass
            # 去抖：3 秒内重复的 KX2 只处理一次
            try:
                now_ts = time.time()
                if now_ts - (self._kx_recent.get((src_ip, "KX2"), 0.0)) < 3.0:
                    return
                self._kx_recent[(src_ip, "KX2")] = now_ts
            except Exception:
                pass
            try:
                fields = dict(x.split("=",1) for x in (seg.strip() for seg in ext.split(";") ) if "=" in x)
                seedB = b64d(fields.get("seedB",""))
                # fetch cached seedA；若因历史状态缺失未找到，则无法建立对称会话
                sess_entry = self._sessions.get(src_ip) or {}
                seedA = sess_entry.get("local_seed")
                if not isinstance(seedA, (bytes, bytearray)):
                    # 为了避免留下一个“空壳”会话，这里确保不存在残缺条目
                    try:
                        if src_ip in self._sessions:
                            del self._sessions[src_ip]
                    except Exception:
                        pass
                    if self.debug:
                        print(f"[DBG] KX2 from {src_ip} but no cached seedA; cannot derive session")
                        self._print_prompt(suppress_next=False)
                    return
                # derive session via deterministic IP-order rule
                ikm = self._derive_ikm_ip_order(self.local_ip, src_ip, local_seed=seedA, peer_seed=seedB)
                key = hkdf_sha256(ikm, info=b"zfeiq-aes256gcm", length=32)
                import hashlib
                sid = hashlib.sha256(ikm).digest()[:8]
                self._sessions[src_ip] = {
                    "key": key,
                    "sid": sid,
                    "send_ctr": 0,
                    "recv_ctr": 0,
                    "recv_window": set(),
                    "last_ts": time.time(),
                    "local_ready": True,
                    "peer_ready": False,
                    "ready_sent": False,
                    "ready_announced": False,
                    "await_peer_notice": False,
                }
                if self.debug:
                    print(f"[DBG] session established with {src_ip} sid={b64e(sid)}")
                    self._print_prompt(suppress_next=False)
                self._send_enc_ready(src_ip)
            except Exception as e:
                if self.debug:
                    print(f"[DBG] failed to process KX2 from {src_ip}: {e}")
                    self._print_prompt(suppress_next=False)
            return

        # BR_ENTRY / BR_ABSENCE: 更新在线并回复 ANSENTRY
        if base == IPMSG_BR_ENTRY or base == IPMSG_BR_ABSENCE:
            # 忽略任何来源 IP 属于本机网卡的上线报文，避免多网卡环境下“看到自己”
            try:
                local_ips = {ip for ip, _ in (_win_list_ipv4_addrs() if os.name == "nt" else _linux_list_ipv4_addrs())}
                if src_ip in local_ips:
                    return
            except Exception:
                pass
            # update and reply ANSENTRY；首次发现时提示上线
            was = self.registry.get_by_ip(src_ip)
            st = self._parse_status_from_ext(ext) or ("away" if base == IPMSG_BR_ABSENCE else None)
            cap_ack = self._parse_cap_ack_from_ext(ext)
            # parse announced fingerprint if present
            try:
                fp = self._parse_fp_from_ext(ext)
                if fp:
                    self._peer_fp_announced[src_ip] = fp
            except Exception:
                pass
            old_status = was.status if was else None
            self.registry.upsert(src_ip, user, host, st, supports_ack=cap_ack)
            if was is None and src_ip != self.local_ip:
                ts = ts_str_full(time.time()) if self.time_format == "full" else ts_str(time.time())
                self._user_print(f"\n[{ts}] + {user}@{src_ip} 上线")
                self._print_prompt(suppress_next=False)
            elif st and old_status and st != old_status and src_ip != self.local_ip:
                ts = ts_str_full(time.time()) if self.time_format == "full" else ts_str(time.time())
                self._user_print(f"\n[{ts}] * {user}@{src_ip} 状态: {old_status} -> {st}")
                self._print_prompt(suppress_next=False)
            # 若启用加密且未知对端公钥，主动请求（不影响上面的 if/elif 链）
            try:
                # 若对端声明支持加密能力且我们拥有本地公钥，则主动推送公钥；否则在需要发送时再请求
                peer_cap_enc = self._parse_cap_enc_from_ext(ext)
                if peer_cap_enc and (self._pub_pem and len(self._pub_pem) > 0):
                    try:
                        pem_txt = (self._pub_pem or b"").decode("utf-8", errors="ignore")
                        pkt_pub = build_packet(self.username or "?", self.hostname, IPMSG_ANSPUBKEY, pem_txt, encoding=self.encoding)
                        self.transport.send_unicast(src_ip, pkt_pub)
                    except Exception:
                        pass
                elif self.encrypt_mode in ("on", "strict") and src_ip not in self._peer_pubkeys:
                    req = build_packet(self.username or "?", self.hostname, IPMSG_GETPUBKEY, "GETPUBKEY", encoding=self.encoding)
                    self.transport.send_unicast(src_ip, req)
            except Exception:
                pass
            if self.username:
                try:
                    pkt = build_packet(self.username, self.hostname, IPMSG_ANSENTRY, self._build_status_ext(), encoding=self.encoding)
                    self.transport.send_unicast(src_ip, pkt)
                except Exception:
                    # transport may not be started in tests or headless modes
                    pass
            # 若启用加密，自动尝试会话握手（拥有对端公钥且尚未建链）
            try:
                if self.encrypt_mode in ("on", "strict") and (src_ip in self._peer_pubkeys) and (not self._ensure_session(src_ip)):
                    self._start_kx(src_ip)
            except Exception:
                pass
        elif base == IPMSG_ANSENTRY:
            # 同样忽略来自本机任一 IP 的 ANSENTRY
            try:
                local_ips = {ip for ip, _ in (_win_list_ipv4_addrs() if os.name == "nt" else _linux_list_ipv4_addrs())}
                if src_ip in local_ips:
                    return
            except Exception:
                pass
            was = self.registry.get_by_ip(src_ip)
            st = self._parse_status_from_ext(ext)
            cap_ack = self._parse_cap_ack_from_ext(ext)
            # parse announced fingerprint if present
            try:
                fp = self._parse_fp_from_ext(ext)
                if fp:
                    self._peer_fp_announced[src_ip] = fp
            except Exception:
                pass
            old_status = was.status if was else None
            self.registry.upsert(src_ip, user, host, st, supports_ack=cap_ack)
            if was is None and src_ip != self.local_ip:
                ts = ts_str_full(time.time()) if self.time_format == "full" else ts_str(time.time())
                self._user_print(f"\n[{ts}] + {user}@{src_ip} 上线")
                self._print_prompt(suppress_next=False)
            elif st and old_status and st != old_status and src_ip != self.local_ip:
                ts = ts_str_full(time.time()) if self.time_format == "full" else ts_str(time.time())
                self._user_print(f"\n[{ts}] * {user}@{src_ip} 状态: {old_status} -> {st}")
                self._print_prompt(suppress_next=False)
            # 若启用加密且未知对端公钥，主动请求（不影响上面的 if/elif 链）
            try:
                if self.encrypt_mode in ("on","strict") and src_ip not in self._peer_pubkeys:
                    req = build_packet(self.username or "?", self.hostname, IPMSG_GETPUBKEY, "GETPUBKEY", encoding=self.encoding)
                    self.transport.send_unicast(src_ip, req)
            except Exception:
                pass
            # 若启用加密，且已有对端公钥但未建链，主动发起KX
            try:
                if self.encrypt_mode in ("on","strict") and (src_ip in self._peer_pubkeys) and (not self._ensure_session(src_ip)):
                    self._start_kx(src_ip)
            except Exception:
                pass
        elif base == IPMSG_BR_EXIT:
            # 忽略自己发出的下线广播以及重复下线事件
            if src_ip == self.local_ip:
                return
            existed = self.registry.get_by_ip(src_ip)
            if existed is not None:
                ts = ts_str_full(time.time()) if self.time_format == "full" else ts_str(time.time())
                print(f"\n[{ts}] - {user}@{src_ip} 下线")
                self.registry.remove(src_ip)
                self._print_prompt(suppress_next=False)
        elif base == IPMSG_GETLIST:
            # 对方请求主机列表，回 ANSLIST
            entries = [
                {"username": n.username, "ip": n.ip, "hostname": n.hostname}
                for n in self.registry.list_nodes()
            ]
            ext_text = encode_list_entries(entries)
            pkt = build_packet(self.username or "?", self.hostname, IPMSG_ANSLIST, ext_text, encoding=self.encoding)
            self.transport.send_unicast(src_ip, pkt)
        elif base == IPMSG_ANSLIST:
            # 合并对方提供的列表，同时过滤掉本机所有 IP
            try:
                items = decode_list_entries(ext)
                try:
                    local_ips = {ip for ip, _ in (_win_list_ipv4_addrs() if os.name == "nt" else _linux_list_ipv4_addrs())}
                except Exception:
                    local_ips = set()
                for it in items:
                    ip = it["ip"]
                    if ip in local_ips:
                        continue
                    self.registry.upsert(ip, it["username"], it["hostname"])
            except Exception:
                pass
        elif base == IPMSG_SENDMSG:
            text = ext.split("\0", 1)[0] if ext else ""
            enc_success = False
            enc_ctx = None  # {'sid':str,'ctr':int,'b64':str,'tag':str}
            # ENC2 会话加密
            # 会话加密：统一解析 ENC;sid=...（原 ENC2 语义）
            if text.startswith("ENC;"):
                try:
                    # 【修改】注释掉下面 3 行，允许被动解密（只要手里有密钥）
                    # if self.encrypt_mode == "off":
                    #    text = ""
                    #    raise RuntimeError("enc-off-ignore")
                    fields = dict(x.split("=",1) for x in (seg.strip() for seg in text.split(";") ) if "=" in x)
                    sid = b64d(fields.get("sid",""))
                    ctr = int(fields.get("ctr","0"))
                    s = self._sessions.get(src_ip)
                    if not s or s.get("sid") != sid:
                        # 兼容：若按 IP 未命中，尝试在所有会话中按 sid 匹配（解决同一 IP 多实例/端口的冲突）
                        s = next((v for v in self._sessions.values() if isinstance(v, dict) and v.get("sid") == sid), None)
                        if not s or s.get("sid") != sid:
                            raise ValueError("unknown session")
                    # simple replay protection
                    rw = s.get("recv_window") or set()
                    if ctr in rw:
                        raise ValueError("replayed")
                    # 使用与加密端一致的方向标记，确保 nonce 生成匹配
                    # 原实现使用 direction="out" 加密，direction="in" 解密会导致 nonce 不一致从而解密失败
                    nonce = self._sess_nonce(sid, ctr, direction="out")
                    cipher_b64 = fields.get("b64","")
                    tag_b64 = fields.get("tag","")
                    # 需传入与加密端相同的 AAD (sid)，否则 GCM 验证失败
                    pt = aes_gcm_decrypt(s.get("key"), nonce, b64d(cipher_b64), b64d(tag_b64) if tag_b64 else b"\x00"*16, aad=s.get("sid"))
                    if self.debug:
                        try:
                            print(f"[ENC] DEC ok from {src_ip}: sid={b64e(s.get('sid'))} ctr={ctr}")
                        except Exception:
                            pass
                    text = pt.decode(self.encoding, errors="ignore")
                    enc_success = True
                    try:
                        enc_ctx = {"sid": b64e(s.get("sid")), "ctr": ctr, "b64": cipher_b64, "tag": tag_b64}
                    except Exception:
                        enc_ctx = None
                    # update window
                    rw.add(ctr)
                    if len(rw) > 512:
                        # keep set small
                        for _ in range(len(rw) - 512):
                            try:
                                rw.remove(min(rw))
                            except Exception:
                                break
                    s["recv_window"] = rw
                except Exception as _e:
                    if str(_e) == "enc-off-ignore":
                        # 已在上方置空 text，这里不产生“解密失败”噪声
                        pass
                    else:
                        text = "[加密消息解密失败]"
                        # 若开启 debug，输出更详细的错误原因，便于排查会话/nonce/AAD 问题
                        try:
                            if self.debug:
                                print(f"[ENC] ENC decrypt error from {src_ip}: {_e}")
                        except Exception:
                            pass
            # 兼容旧 ENC 一次性密钥的解密路径已移除（开发阶段不再保留）
            # 若是握手文本（KX1/KX2），避免作为普通消息显示（但仍然按下方流程 ACK）
            try:
                if text.startswith("KX1;") or text.startswith("KX2;"):
                    # 已在专用分支处理过（或我们将忽略展示），清空文本避免入历史
                    text = ""
            except Exception:
                pass

            # 收到消息时也刷新能力位与状态（若有）并更新在线表
            cap_ack = self._parse_cap_ack_from_ext(ext)
            st = self._parse_status_from_ext(ext)
            self.registry.upsert(src_ip, user, host, status=st, supports_ack=cap_ack)
            has_attach_opt = bool(cmd & IPMSG_FILEATTACHOPT)
            # 简易文件要约: "FILE_OFFER;id=..;name=..;size=..;port=.."
            if text.startswith("FILE_OFFER;"):
                meta = {}
                for token in text.split(";"):
                    if "=" in token:
                        k, v = token.split("=", 1)
                        meta[k.strip()] = v.strip()
                oid = meta.get("id")
                try:
                    size_i = int(meta.get("size", "0"))
                except Exception:
                    size_i = 0
                if oid and meta.get("port"):
                    try:
                        port_i = int(meta.get("port", "0"))
                    except Exception:
                        port_i = 0
                    if port_i > 0:
                        self._incoming_offers[oid] = {
                            "ip": src_ip,
                            "port": port_i,
                            "name": meta.get("name", "file"),
                            "size": size_i,
                        }
                        ts = ts_str_full(time.time()) if self.time_format == "full" else ts_str(time.time())
                        print(f"\n[{ts}] <{user}@{src_ip}> 提供文件: {meta.get('name','file')} ({size_i} bytes), offer={oid}")
                        print("使用: /file accept "+oid+" 以接收；或 /file list 查看所有待接收；或 /file cancel "+oid+" 放弃")
                        self._print_prompt(suppress_next=False)
                        # 仍按常规消息路径 ack
            # 解析 IPMSG 附件（与飞秋互通）：仅解析首个 NUL 之后的部分
            try:
                ext_after = ext.split("\0", 1)[1] if "\0" in (ext or "") else ""
                attaches = decode_fileattach_lines(ext_after)
            except Exception:
                attaches = []
            if attaches:
                for a in attaches:
                    oid = f"ipmsg-{pkt_no}-{a.get('id',0)}"
                    self._incoming_offers[oid] = {
                        "ip": src_ip,
                        "port": 2425,
                        "name": a.get("name", "file"),
                        "size": int(a.get("size", 0)),
                        "method": "ipmsg",
                        "pkt_no": pkt_no,
                        "attach_id": int(a.get("id", 0)),
                    }
                    ts = ts_str_full(time.time()) if self.time_format == "full" else ts_str(time.time())
                    print(f"\n[{ts}] <{user}@{src_ip}> 附件: {a.get('name','file')} ({int(a.get('size',0))} bytes), offer={oid}")
                    print("使用: /file accept "+oid+" 以接收；或 /file list 查看所有待接收；或 /file cancel "+oid+" 放弃")
                self._print_prompt(suppress_next=False)
            # 判定是否仅为附件（无文本）或为 FILE_OFFER 元数据，如果是则不打印原始文本
            only_attach_no_text = has_attach_opt and attaches and (text == "")
            is_file_offer = text.startswith("FILE_OFFER;")
            if text and not (only_attach_no_text or is_file_offer):
                self.history.add(src_ip, "in", text)
                ts = ts_str_full(time.time()) if self.time_format == "full" else ts_str(time.time())
                # 可选打印原始密文
                if enc_success and self.encrypt_show_cipher and enc_ctx:
                    print(f"\n[{ts}] [cipher] ENC sid={enc_ctx.get('sid','')} ctr={enc_ctx.get('ctr','')} tag={enc_ctx.get('tag','')} b64={enc_ctx.get('b64','')}")
                tag = " [E-D OK]" if (enc_success and self.encrypt_edtag) else ""
                print(f"\n[{ts}] <{user}@{src_ip}>{tag} {text}")
            # ack
            ack = build_packet(self.username or "?", self.hostname, IPMSG_RECVMSG, str(pkt_no), encoding=self.encoding)
            self.transport.send_unicast(src_ip, ack)
            self._print_prompt(suppress_next=False)
        elif base == IPMSG_RELEASEFILES:
            # 释放对端请求的附件映射：格式可能为 多行 或 BEL 分隔 的 packetNo:attachId
            try:
                lines = []
                for seg in (ext or "").split("\a"):
                    lines.extend(seg.splitlines())
                for ln in lines:
                    parts = [p for p in ln.split(":") if p]
                    if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
                        pno = int(parts[0]); aid = int(parts[1])
                        self._attach_map.pop((pno, aid), None)
            except Exception:
                pass
        elif base == IPMSG_RECVMSG:
            try:
                ack_no = int(ext.strip() or "0")
            except Exception:
                ack_no = 0
            if ack_no:
                self.pending.remove(ack_no)
        else:
            # ignore others
            pass

    # ============ commands ============
    def cmd_login(self, name_param: Optional[str] = None) -> None:
        if self.username:
            self._user_print(self._t("login.already", user=self.username))
            return
        name = (name_param or "").strip()
        if not name:
            name = input(self._t("login.prompt")).strip()
        if not name:
            self._user_print(self._t("login.empty"))
            return
        self.username = name
        ext = self._build_status_ext()
        cmd = IPMSG_BR_ENTRY if self.status != "away" else IPMSG_BR_ABSENCE
        pkt = build_packet(self.username, self.hostname, cmd, ext, encoding=self.encoding)
        self.transport.send_broadcast(pkt)
        # 将自己加入在线表，避免依赖系统是否回环接收广播（部分 Linux 不回环）
        self.registry.upsert(self.local_ip, self.username, self.hostname, self.status, supports_ack=True)
        self._user_print(self._t("login.online", user=self.username, ip=self.local_ip))

    def cmd_logout(self) -> bool:
        # 仅下线，不退出程序
        if not self.username:
            self._user_print(self._t("logout.notlogged"))
            return False
        try:
            pkt = build_packet(self.username or "?", self.hostname, IPMSG_BR_EXIT, encoding=self.encoding)
            # 广播 + 向所有已知节点单播（兼容广播受限网络）
            try:
                self.transport.send_broadcast(pkt)
            except Exception:
                pass
            try:
                for n in self.registry.list_nodes():
                    if n.ip and n.ip != self.local_ip:
                        self.transport.send_unicast(n.ip, pkt)
            except Exception:
                pass
        finally:
            # 从在线表移除自己
            self.registry.remove(self.local_ip)
            self._user_print(self._t("logout.done", user=self.username))
            self.username = None
        return False

    def _print_online(self) -> None:
        nodes = sorted(self.registry.list_nodes(), key=lambda n: (n.username, n.ip))
        self._user_print(f"user: {self.username or '-'}  ip: {self.local_ip}  online: {len(nodes)}")
        for n in nodes:
            st = f" [{n.status}]" if getattr(n, 'status', 'online') != 'online' else ""
            self._user_print(f" - {n.username}@{n.ip} ({n.hostname}){st}")

    def cmd_discover(self, target_ip: Optional[str] = None) -> None:
        if not self.username:
            self._user_print(self._t("common.login_first"))
            return
        ext = self._build_status_ext()
        cmd = IPMSG_BR_ENTRY if self.status != "away" else IPMSG_BR_ABSENCE
        pkt = build_packet(self.username, self.hostname, cmd, ext, encoding=self.encoding)
        if target_ip:
            # 向指定 IP 单播探测，适用于不同子网/广播受限场景
            try:
                self.transport.send_unicast(target_ip, pkt)
                pkt2 = build_packet(self.username or "?", self.hostname, IPMSG_GETLIST, encoding=self.encoding)
                self.transport.send_unicast(target_ip, pkt2)
                if self.debug:
                    print(f"[DBG] unicast GETLIST to {target_ip}")
            except Exception:
                pass
        else:
            self.transport.send_broadcast(pkt)
            # 紧接着请求列表
            try:
                pkt2 = build_packet(self.username or "?", self.hostname, IPMSG_GETLIST, encoding=self.encoding)
                self.transport.send_broadcast(pkt2)
                if self.debug:
                    print("[DBG] broadcast GETLIST")
            except Exception:
                pass
        ts = ts_str_full(time.time()) if self.time_format == "full" else ts_str(time.time())
        if target_ip:
            self._user_print(f"[{ts}] 向 {target_ip} 发送单播发现")
        else:
            self._user_print(f"[{ts}] {self._t('discover.sent')}")
        # 聚合等待一段时间以收集 ANSENTRY/ANSLIST，再统一打印
        try:
            time.sleep(1.2)
        except Exception:
            pass
        self._print_online()

    # status parsing from ext
    def _parse_status_from_ext(self, ext: str) -> Optional[str]:
        try:
            segments = (ext or "").split("\0")
            for seg in segments:
                for token in seg.split(";"):
                    token = token.strip()
                    if token.startswith("status="):
                        val = token.split("=", 1)[1].strip().lower()
                        if val in ("online","busy","away"):
                            return val
        except Exception:
            pass
        return None

    def _parse_cap_ack_from_ext(self, ext: str) -> Optional[bool]:
        try:
            segments = (ext or "").split("\0")
            for seg in segments:
                for token in seg.split(";"):
                    token = token.strip().lower()
                    if token == "cap=ack":
                        return True
        except Exception:
            pass
        return None

    def _parse_cap_enc_from_ext(self, ext: str) -> Optional[bool]:
        """解析扩展字段中是否声明了 cap=enc（表示支持公钥交换/加密）。"""
        try:
            segments = (ext or "").split("\0")
            for seg in segments:
                for token in seg.split(";"):
                    token = token.strip().lower()
                    if token == "cap=enc":
                        return True
        except Exception:
            pass
        return None

    def _build_status_ext(self) -> str:
        """构造 BR_ENTRY/ANSENTRY 使用的扩展字段，包含用户名、状态与能力位。"""
        caps = ["cap=ack"]
        # 仅在 encrypt=on|strict 时声明支持加密能力
        try:
            if self.encrypt_mode in ("on", "strict"):
                caps.append("cap=enc")
        except Exception:
            pass
        # 若存在本地公钥，计算并广播其指纹（SHA256 hex）以供指纹比对
        fp_token = None
        try:
            if self._pub_pem and len(self._pub_pem) > 0:
                fp = hashlib.sha256(self._pub_pem).hexdigest()
                fp_token = f"fp={fp}"
        except Exception:
            fp_token = None
        cap_parts = caps[:]  # copy
        if fp_token:
            cap_parts.append(fp_token)
        cap_str = ";".join(cap_parts)
        return f"{self.username}\0\0status={self.status};{cap_str}"

    def _parse_fp_from_ext(self, ext: str) -> Optional[str]:
        """从扩展字段解析 fp=<hex> 指纹（返回小写 hex 字符串）。"""
        try:
            segments = (ext or "").split("\0")
            for seg in segments:
                for token in seg.split(";"):
                    token = token.strip()
                    if token.lower().startswith("fp="):
                        return token.split("=", 1)[1].strip().lower()
        except Exception:
            pass
        return None

    # 用户输出（GUI 模式可静音）
    def _user_print(self, *args, **kwargs) -> None:
        if not getattr(self, "ui_silent", False):
            try:
                print(*args, **kwargs)
            except Exception:
                pass

    # prompt helpers
    def _on_debug(self, msg: str) -> None:
        try:
            if not self.debug:
                return
            # 独立一行输出调试信息，并随后重绘提示符
            self._user_print("\n" + msg)
            # 调试输出不丢弃用户当前输入，且不压制下一次 input 的提示
            self._print_prompt(invalidate=False, suppress_next=False)
        except Exception:
            pass

    def _prompt_header(self) -> str:
        # 未登录：形如 [ZFeiQ] [Debug ON] [Trace ON]
        # 已登录：形如 <username> [Debug ON] [Trace ON]
        dbg = []
        if self.debug:
            dbg.append("[Debug ON]")
        if self.trace:
            dbg.append("[Trace ON]")
        if not self.username:
            base = "[ZFeiQ]"
        else:
            base = f"<{self.username}>"
        return (base + (" " + " ".join(dbg) if dbg else ""))

    def _make_prompt(self) -> str:
        # 单行提示符：<username> =>
        return f"{self._prompt_header()} => "

    def _print_prompt(self, invalidate: bool = True, suppress_next: bool = True) -> None:
        try:
            if getattr(self, "ui_silent", False):
                return
            # 异步事件后，丢弃当前输入，并立即打印一行新提示
            # 若已经打印过提示且尚未进入下一次 input，则避免重复打印
            if getattr(self, "_suppress_next_prompt", False):
                if invalidate:
                    self._invalidate_input = True
                return
            if invalidate:
                self._invalidate_input = True
            if suppress_next:
                self._suppress_next_prompt = True
            # 兼容终端：直接换行并重绘提示
            print("\n" + self._make_prompt(), end="", flush=True)
        except Exception:
            pass

    def cmd_info_group(self, group_name: str) -> None:
        members = self.groups.get(group_name)
        if members is None:
            print(f"group '{group_name}' not found")
            return
        # 聚合组内成员的会话历史（按时间排序）
        entries = []  # (ts, dir, text, uname, ip)
        print(f"-- group '{group_name}' chat history --")
        for uname in sorted(members):
            matches = self.registry.find_by_username(uname)
            if not matches:
                continue
            # 多重名时，遍历每个 ip 的历史
            for n in matches:
                ip = n.ip
                msgs = self.history.get(ip)
                for ts, d, t in msgs:
                    entries.append((ts, d, t, uname, ip))
        if target_ip:
            # 向指定 IP 单播探测，支持 ip:port
            try:
                host = target_ip
                port_override: Optional[int] = None
                if target_ip and ":" in target_ip:
                    h, p = target_ip.split(":", 1)
                    if h.strip():
                        host = h.strip()
                    ps = p.strip()
                    if ps.isdigit():
                        port_override = int(ps)
                if port_override is not None:
                    self.transport.send_unicast_port(host, port_override, pkt)
                else:
                    self.transport.send_unicast(host, pkt)
                pkt2 = build_packet(self.username or "?", self.hostname, IPMSG_GETLIST, encoding=self.encoding)
                if port_override is not None:
                    self.transport.send_unicast_port(host, port_override, pkt2)
                else:
                    self.transport.send_unicast(host, pkt2)
                if self.debug:
                    print(f"[DBG] unicast GETLIST to {host}{(':'+str(port_override)) if port_override is not None else ''}")
            except Exception:
                pass
        # 扩展字段：默认仅为文本；不再附加非标准的 cap=ack，避免对端显示为文本
        ext = text
        # 加密：优先使用会话 ENC2；否则尝试发起 HKDF-only 握手
        try:
            if self.encrypt_mode in ("on","strict"):
                if self._ensure_session(ip):
                    s = self._sessions.get(ip)
                    ctr = (s.get("send_ctr") or 0) + 1
                    s["send_ctr"] = ctr
                    nonce = self._sess_nonce(s.get("sid"), ctr, direction="out")
                    _, ct, tag = aes_gcm_encrypt(s.get("key"), text.encode(self.encoding, errors="ignore"), aad=(s.get("sid") or b""), nonce=nonce)
                    ext = f"ENC;sid={b64e(s.get('sid'))};ctr={ctr};tag={b64e(tag)};b64=" + b64e(ct)
                    # 若这是本会话首次使用 ENC2 发送消息，可记录一条握手事件
                    try:
                        if not s.get("_first_enc2_sent"):
                            s["_first_enc2_sent"] = True
                            # 更明确的提示：仅表示“本端首次通过现有会话发送 ENC2 消息”，不会重新建会话
                            self._handshake_event(ip, f"与 {ip} 的会话已建立，首次通过 ENC 发送加密消息")
                    except Exception:
                        pass
                else:
                    # 无会话：直接触发 HKDF-only 握手；严格模式下暂不发送
                    self._start_kx(ip)
                    if self.encrypt_mode == "strict":
                        try:
                            self._handshake_event(ip, f"尚无 ENC2 会话，已发起与 {ip} 的 HKDF 握手；严格模式下不发送")
                        except Exception:
                            pass
                        return
        except Exception as e:
            print(f"[ENC] 加密失败，退回明文: {e}")
        # 注意：不在 SENDMSG 中拼接自定义扩展键值，避免互通客户端将其当作文本显示
        packet = build_packet_with_no(pkt_no, self.username or "?", self.hostname, cmd, ext, encoding=self.encoding)
        self.transport.send_unicast(ip, packet)
        if need_ack:
            self.pending.add(pkt_no, ip, text)
        self.history.add(ip, "out", text)

    def cmd_send(self, target: str, text: str) -> None:
        if not self.username:
            print(self._t("common.login_first"))
            return
        if target.startswith("user:"):
            name = target[5:]
            matches = self.registry.find_by_username(name)
            if not matches:
                print(self._t("user.notfound", name=name))
                return
            if len(matches) > 1:
                print(self._t("user.ambiguous"))
                for n in matches:
                    print(f" - {n.username}@{n.ip}")
                print(self._t("user.ambiguous_hint"))
                return
            ip = matches[0].ip
            self._send_text(ip, text)
        elif target.startswith("group:"):
            gname = target[6:]
            members = self.groups.get(gname, set())
            if not members:
                print(self._t("group.empty_or_missing", group=gname))
                return
            sent = 0
            for uname in list(members):
                matches = self.registry.find_by_username(uname)
                if not matches:
                    print(self._t("group.member_offline", user=uname))
                    continue
                if len(matches) > 1:
                    print(self._t("group.member_ambiguous", user=uname))
                    continue
                ip = matches[0].ip
                if ip == self.local_ip and uname == (self.username or ""):
                    continue
                self._send_text(ip, text)
                sent += 1
            print(self._t("group.sent_count", group=gname, count=sent))
        elif target == "all":
            self.cmd_sendall(text)
        elif target.startswith("ip:"):
            ip = target[3:]
            self._send_text(ip, text)
        else:
            print(self._t("send.target_usage"))

    def cmd_search(self, query: str) -> None:
        q = query.strip()
        if q.startswith("user:"):
            name = q[5:].strip().lower()
            matches = [n for n in self.registry.list_nodes() if name in n.username.lower()]
            if not matches:
                print(self._t("user.notfound", name=name))
                return
            print(self._t("search.user_matches", name=name))
            for n in matches:
                print(f" - {n.username}@{n.ip} ({n.hostname}) [{n.status}]")
        elif q.startswith("group:"):
            g = q[6:].strip().lower()
            found = False
            for group, members in self.groups.items():
                if g in group.lower():
                    found = True
                    print(self._t("search.group_header", group=group))
                    for uname in sorted(members):
                        ms = [n for n in self.registry.list_nodes() if n.username == uname]
                        if not ms:
                            print(f" - {uname} (offline)")
                        elif len(ms) > 1:
                            ips = ", ".join(n.ip for n in ms)
                            print(f" - {uname} (ambiguous: {ips})")
                        else:
                            n = ms[0]
                            print(f" - {uname}@{n.ip} ({n.hostname}) [{n.status}]")
            if not found:
                print(self._t("search.group_notfound", group=g))
        elif q.startswith("ip:"):
            ip = q[3:].strip().lower()
            matches = [n for n in self.registry.list_nodes() if ip in n.ip.lower()]
            if not matches:
                print(self._t("search.ip_notfound", ip=ip))
            else:
                for n in matches:
                    print(f"{n.username}@{n.ip} ({n.hostname}) [{n.status}]")
        else:
            print(self._t("search.usage"))

    # ======== file commands ========
    def cmd_file_send(self, target: str, path: str) -> None:
        if not os.path.isfile(path):
            print(self._t("file.path_bad", p=path))
            return
        if target.startswith("ip:"):
            ip = target[3:]
            self._send_file_ip(ip, path)
        elif target.startswith("user:"):
            name = target[5:]
            matches = self.registry.find_by_username(name)
            if not matches:
                print(self._t("user.notfound", name=name))
                return
            if len(matches) > 1:
                print(self._t("user.ambiguous"))
                for n in matches:
                    print(f" - {n.username}@{n.ip}")
                print(self._t("user.ambiguous_hint"))
                return
            ip = matches[0].ip
            self._send_file_ip(ip, path)
        elif target.startswith("group:"):
            gname = target[6:]
            members = self.groups.get(gname, set())
            if not members:
                print(self._t("group.empty_or_missing", group=gname))
                return
            sent = 0
            for uname in sorted(members):
                ms = self.registry.find_by_username(uname)
                if not ms or len(ms) != 1:
                    continue
                ip = ms[0].ip
                if ip == self.local_ip and uname == (self.username or ""):
                    continue
                self._send_file_ip(ip, path)
                sent += 1
            print(self._t("group.sent_count", group=gname, count=sent))
        elif target == "all":
            for n in self.registry.list_nodes():
                if n.ip == self.local_ip and (n.username == (self.username or "")):
                    continue
                self._send_file_ip(n.ip, path)
        else:
            print(self._t("file.send_usage"))

    def _send_file_ip(self, ip: str, path: str) -> None:
        try:
            filename = os.path.basename(path)
            size = os.path.getsize(path)
            attach_id = int(time.time() * 1000) & 0x7fffffff
            mtime = int(os.path.getmtime(path))
            # IPMSG 约定：附件行需位于首个 NUL 之后；即使无文本，也要以 NUL 开头
            faext_body = encode_fileattach_lines([
                {"id": attach_id, "name": filename, "size": size, "mtime": mtime, "attr": 0}
            ])
            faext = "\0" + faext_body + "\0"
            pkt_no = gen_packet_no()
            pkt = build_packet_with_no(
                pkt_no,
                self.username or "?",
                self.hostname,
                IPMSG_SENDMSG | IPMSG_FILEATTACHOPT,
                faext,
                encoding=self.encoding,
            )
            self.transport.send_unicast(ip, pkt)
            # 登记以供 GETFILEDATA 请求
            self._attach_map[(pkt_no, attach_id)] = {"path": path, "ts": time.time()}
            # 懒启动 2425 服务
            if not self._ipmsg_srv:
                self._ipmsg_srv = IPMsgFileServer(
                    resolver=lambda p, a: (self._attach_map.get((p, a)) or {}).get("path"),
                    bind_ip=self.local_ip if os.name == "nt" else "0.0.0.0",
                    releaser=lambda p, a: self._attach_map.pop((p, a), None),
                )
                try:
                    self._ipmsg_srv.start()
                except Exception as e:
                    print(f"[WARN] 无法启动 2425/TCP GETFILEDATA 服务：{e}")
                    self._ipmsg_srv = None
            # 记录一个可取消项，便于 /file cancel
            offer_id = f"ipmsg-{pkt_no}-{attach_id}"
            self._outgoing_offers[offer_id] = {
                "method": "ipmsg",
                "name": filename,
                "size": size,
                "path": path,
                "pkt_no": pkt_no,
                "attach_id": attach_id,
                "server": None,
            }
            print(self._t("file.offered", name=filename, size=size, id=offer_id, ip=ip))
        except Exception as e:
            print(self._t("file.offer_fail", e=str(e)))

    # ======== CLI emotes ========
    def cmd_emote_list(self) -> None:
        try:
            names = []
            for n in sorted(os.listdir(self.emotes_dir)):
                p = os.path.join(self.emotes_dir, n)
                if os.path.isfile(p) and os.path.splitext(n)[1].lower() in (".png", ".jpg", ".jpeg", ".gif", ".bmp"):
                    names.append(n)
            if not names:
                print("(no emotes)")
                return
            print("emotes:")
            for n in names:
                print(" -", n)
        except Exception as e:
            print(f"[ERR] list emotes: {e}")

    def cmd_emote_send(self, target: str, name: str) -> None:
        path = os.path.join(self.emotes_dir, name)
        if not os.path.isfile(path):
            print(f"emote not found: {name}")
            return
        self.cmd_file_send(target, path)

    # ======== CLI screenshot (cross-platform with scrot on Linux) ========
    def _capture_fullscreen_bmp(self) -> Optional[str]:
        """Capture the screen via scrot/gnome-screenshot on Linux or Win32 APIs."""
        import subprocess
        import tempfile

        if os.name != "nt":
            try:
                fd, path = tempfile.mkstemp(suffix=".png", prefix="zfeiq_ss_")
                os.close(fd)
                print("正在启动截图... (请使用鼠标框选区域，或点击屏幕截取全屏)")
                try:
                    subprocess.run(["scrot", "-s", path], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    if os.path.exists(path) and os.path.getsize(path) > 0:
                        return path
                except (FileNotFoundError, subprocess.CalledProcessError):
                    try:
                        subprocess.run(["gnome-screenshot", "-a", "-f", path], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        if os.path.exists(path) and os.path.getsize(path) > 0:
                            return path
                    except Exception:
                        print("[ERR] 截图失败: 请安装 scrot (sudo apt install scrot)")
                        return None
            except Exception as e:
                print(f"[ERR] screenshot error: {e}")
                return None
            return None
        try:
            print("[INFO] Windows CLI 截图逻辑执行中...")
            # 首选：Pillow 的 ImageGrab（更稳健）
            try:
                from PIL import ImageGrab  # type: ignore
                img = ImageGrab.grab(all_screens=True)
                fd, path = tempfile.mkstemp(suffix=".bmp", prefix="zfeiq_ss_")
                os.close(fd)
                img.save(path, format="BMP")
                return path
            except Exception:
                pass
            # 退路：ctypes + GDI，导出为 BMP（24bpp）
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.WinDLL('user32', use_last_error=True)
            gdi32 = ctypes.WinDLL('gdi32', use_last_error=True)
            GetDC = user32.GetDC; ReleaseDC = user32.ReleaseDC
            CreateCompatibleDC = gdi32.CreateCompatibleDC
            CreateCompatibleBitmap = gdi32.CreateCompatibleBitmap
            SelectObject = gdi32.SelectObject
            BitBlt = gdi32.BitBlt
            DeleteObject = gdi32.DeleteObject
            DeleteDC = gdi32.DeleteDC
            SRCCOPY = 0x00CC0020
            cx = user32.GetSystemMetrics(0); cy = user32.GetSystemMetrics(1)
            hdc_screen = GetDC(None)
            hdc_mem = CreateCompatibleDC(hdc_screen)
            hbmp = CreateCompatibleBitmap(hdc_screen, cx, cy)
            SelectObject(hdc_mem, hbmp)
            BitBlt(hdc_mem, 0, 0, cx, cy, hdc_screen, 0, 0, SRCCOPY)
            class BITMAPFILEHEADER(ctypes.Structure):
                _fields_ = [
                    ("bfType", wintypes.WORD),
                    ("bfSize", wintypes.DWORD),
                    ("bfReserved1", wintypes.WORD),
                    ("bfReserved2", wintypes.WORD),
                    ("bfOffBits", wintypes.DWORD),
                ]
            class BITMAPINFOHEADER(ctypes.Structure):
                _fields_ = [
                    ("biSize", wintypes.DWORD),
                    ("biWidth", wintypes.LONG),
                    ("biHeight", wintypes.LONG),
                    ("biPlanes", wintypes.WORD),
                    ("biBitCount", wintypes.WORD),
                    ("biCompression", wintypes.DWORD),
                    ("biSizeImage", wintypes.DWORD),
                    ("biXPelsPerMeter", wintypes.LONG),
                    ("biYPelsPerMeter", wintypes.LONG),
                    ("biClrUsed", wintypes.DWORD),
                    ("biClrImportant", wintypes.DWORD),
                ]
            BI_RGB = 0
            bmi = BITMAPINFOHEADER()
            bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            bmi.biWidth = cx
            bmi.biHeight = -cy
            bmi.biPlanes = 1
            bmi.biBitCount = 24
            bmi.biCompression = BI_RGB
            rowbytes = ((cx * 3 + 3) // 4) * 4
            imgsize = rowbytes * cy
            buf = (ctypes.c_byte * imgsize)()
            GetDIBits = gdi32.GetDIBits
            GetDIBits.argtypes = [wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT, ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT]
            GetDIBits(hdc_mem, hbmp, 0, cy, ctypes.byref(buf), ctypes.byref(bmi), 0)
            fd, path = tempfile.mkstemp(suffix=".bmp", prefix="zfeiq_ss_")
            os.close(fd)
            bfh = BITMAPFILEHEADER()
            bfh.bfType = 0x4D42
            bfh.bfOffBits = ctypes.sizeof(BITMAPFILEHEADER) + ctypes.sizeof(BITMAPINFOHEADER)
            bfh.bfSize = bfh.bfOffBits + imgsize
            bfh.bfReserved1 = 0
            bfh.bfReserved2 = 0
            with open(path, 'wb') as f:
                f.write(bytes(bfh))
                f.write(bytes(bmi))
                f.write(bytes(buf))
            DeleteObject(hbmp)
            DeleteDC(hdc_mem)
            ReleaseDC(None, hdc_screen)
            return path
        except Exception as e:
            print(f"[ERR] screenshot: {e}")
            return None

    def cmd_screenshot_send(self, target: str) -> None:
        p = self._capture_fullscreen_bmp()
        if not p:
            return
        try:
            self.cmd_file_send(target, p)
        finally:
            try:
                os.remove(p)
            except Exception:
                pass

    def cmd_file_list(self) -> None:
        if not self._incoming_offers:
            print(self._t("file.none"))
            return
        print(self._t("file.pending"))
        for oid, m in self._incoming_offers.items():
            method = m.get("method", "tcp")
            if method == "ipmsg":
                src = f"{m['ip']}:2425/ipmsg"
            else:
                src = f"{m['ip']}:{m.get('port','-')}"
            print(f" - {oid}: {m['name']} ({m['size']} bytes) from {src}")

    def cmd_file_accept(self, oid: str, save_dir: Optional[str] = None) -> None:
        meta = self._incoming_offers.get(oid)
        if not meta:
            print(self._t("file.unknown", id=oid))
            return
        ip = meta["ip"]
        name = meta["name"]
        save_dir = save_dir or self.download_dir or os.getcwd()
        ensure_dir(save_dir)
        save_path = os.path.join(save_dir, name)
        try:
            last = 0
            def on_prog(total):
                nonlocal last
                now = time.time()
                # 简单节流打印
                if now - last >= 0.5:
                    last = now
                    print(f"... {total} bytes", end="\r")
            if meta.get("method") == "ipmsg":
                pkt_no = int(meta.get("pkt_no", 0))
                aid = int(meta.get("attach_id", 0))
                ipmsg_download_file(ip, pkt_no, aid, save_path, self.username or "?", self.hostname, encoding=self.encoding, on_progress=on_prog)
                # 按 IPMSG 规范发送 RELEASEFILES 通知释放
                try:
                    rel = f"{pkt_no}:{aid}"
                    pkt = build_packet(self.username or "?", self.hostname, IPMSG_RELEASEFILES, rel, encoding=self.encoding)
                    self.transport.send_unicast(ip, pkt)
                except Exception:
                    pass
            else:
                port = meta["port"]
                download_file(ip, port, save_path, on_progress=on_prog, retries=1)
            print("\n" + self._t("file.saved", path=save_path))
            self._incoming_offers.pop(oid, None)
        except Exception as e:
            print(self._t("file.download_fail", e=str(e)))

    # GUI 专用：接受文件并回调进度（不直接打印进度）
    def accept_offer_ex(self, oid: str, save_dir: Optional[str] = None, on_progress=None, stop_event: Optional[threading.Event] = None) -> Optional[str]:
        meta = self._incoming_offers.get(oid)
        if not meta:
            return None
        ip = meta["ip"]
        name = meta["name"]
        save_dir = save_dir or self.download_dir or os.getcwd()
        ensure_dir(save_dir)
        save_path = os.path.join(save_dir, name)
        try:
            cb = on_progress if callable(on_progress) else None
            if meta.get("method") == "ipmsg":
                pkt_no = int(meta.get("pkt_no", 0))
                aid = int(meta.get("attach_id", 0))
                ipmsg_download_file(ip, pkt_no, aid, save_path, self.username or "?", self.hostname, encoding=self.encoding, on_progress=cb, stop_event=stop_event)
                # 发送 RELEASEFILES
                try:
                    rel = f"{pkt_no}:{aid}"
                    pkt = build_packet(self.username or "?", self.hostname, IPMSG_RELEASEFILES, rel, encoding=self.encoding)
                    self.transport.send_unicast(ip, pkt)
                except Exception:
                    pass
            else:
                port = meta["port"]
                download_file(ip, port, save_path, on_progress=cb, retries=1, stop_event=stop_event)
            self._incoming_offers.pop(oid, None)
            return save_path
        except Exception:
            return None

    def cmd_file_cancel(self, oid: str) -> None:
        # 取消入站要约
        if oid in self._incoming_offers:
            self._incoming_offers.pop(oid, None)
            self._user_print(self._t("file.canceled_in", id=oid))
            return
        # 取消出站要约：尝试关闭一次性服务器
        out = self._outgoing_offers.get(oid)
        if out:
            srv = out.get("server")
            try:
                if srv:
                    srv.stop()
            except Exception:
                pass
            self._outgoing_offers.pop(oid, None)
            # 清理映射
            try:
                if out.get("method") == "ipmsg":
                    pkt_no = out.get("pkt_no")
                    aid = out.get("attach_id")
                    if pkt_no and aid:
                        self._attach_map.pop((pkt_no, aid), None)
                else:
                    path = out.get("path")
                    if path:
                        for k, v in list(self._attach_map.items()):
                            p = v.get("path") if isinstance(v, dict) else v
                            if p == path:
                                self._attach_map.pop(k, None)
            except Exception:
                pass
            self._user_print(self._t("file.canceled_out", id=oid))
        else:
            self._user_print(self._t("file.unknown", id=oid))

    def cmd_sendall(self, text: str) -> None:
        if not self.username:
            self._user_print(self._t("common.login_first"))
            return
        nodes = self.registry.list_nodes()
        if not nodes:
            self._user_print(self._t("sendall.nopeers"))
            return
        for n in nodes:
            # avoid sending to self if discovered
            if n.ip == self.local_ip and (n.username == self.username):
                continue
            self._send_text(n.ip, text)

    def _send_plain(self, ip: str, text: str) -> None:
        """直接以明文发送到指定 IP，不走会话加密路径。

        用于课程作业场景下的群组消息明文收发。
        """
        if not ip or not isinstance(text, str):
            return
        cmd = IPMSG_SENDMSG | IPMSG_SENDCHECKOPT
        pkt_no = gen_packet_no()
        packet = build_packet_with_no(pkt_no, self.username or "?", self.hostname, cmd, text, encoding=self.encoding)
        self.transport.send_unicast(ip, packet)
        self.pending.add(pkt_no, ip, text)
        self.history.add(ip, "out", text)

    def cmd_group(self, group_name: str, subcmd: str, arg: Optional[str]) -> None:
        # subcmd starts with '-' per spec
        sub = subcmd.lstrip('-').lower()
        members = self.groups.setdefault(group_name, set())
        if sub == "add":
            if arg:
                members.add(arg)
                self._user_print(f"group '{group_name}': added user '{arg}'")
            else:
                # create group (no-op if exists)
                self.groups.setdefault(group_name, members)
                self._user_print(f"group '{group_name}' created (or already exists)")
        elif sub == "delete":
            if arg:
                if arg in members:
                    members.remove(arg)
                    self._user_print(f"group '{group_name}': removed user '{arg}'")
                else:
                    self._user_print(f"group '{group_name}': user '{arg}' not in group")
            else:
                # delete group
                if group_name in self.groups:
                    del self.groups[group_name]
                    self._user_print(f"group '{group_name}' deleted")
                else:
                    self._user_print(f"group '{group_name}' not found")
        elif sub == "send":
            # 课程作业约定：群组消息统一按明文逐个成员发送，不在群组中发起握手
            text = arg or ""
            if not text:
                self._user_print(self._t("group.send_usage_legacy"))
                return
            ms = sorted(self.groups.get(group_name, set()))
            if not ms:
                self._user_print(self._t("group.empty_or_missing", group=group_name))
                return
            sent = 0
            for uname in ms:
                matches = self.registry.find_by_username(uname)
                if not matches:
                    self._user_print(self._t("group.member_offline", user=uname))
                    continue
                if len(matches) > 1:
                    self._user_print(self._t("group.member_ambiguous", user=uname))
                    continue
                ip = matches[0].ip
                if ip == self.local_ip and uname == (self.username or ""):
                    continue
                # 强制明文发送
                self._send_plain(ip, text)
                sent += 1
            self._user_print(self._t("group.sent_count", group=group_name, count=sent))
        elif sub == "rename":
            # Rename group atomically: move members to new name, fail if target exists
            new_name = arg or ""
            if not new_name:
                self._user_print(self._t("group.rename_usage", old=group_name))
                return
            if group_name == new_name:
                self._user_print(self._t("group.rename_same", name=group_name))
                return
            if new_name in self.groups:
                self._user_print(self._t("group.rename_exists", name=new_name))
                return
            # perform rename
            members = self.groups.get(group_name, set())
            self.groups[new_name] = members
            if group_name in self.groups:
                try:
                    del self.groups[group_name]
                except Exception:
                    pass
            self._user_print(f"group '{group_name}' renamed to '{new_name}'")
        else:
            self._user_print(self._t("group.unsupported"))

    def cmd_info_user(self, name: str) -> None:
        matches = self.registry.find_by_username(name)
        if not matches:
            self._user_print(self._t("user.notfound", name=name))
            return
        ips = [n.ip for n in matches]
        for ip in ips:
            msgs = self.history.get(ip)
            self._user_print(f"-- chat with {name}@{ip} --")
            for ts, d, t in msgs:
                arrow = ">>" if d == "out" else "<<"
                fmt_ts = ts_str_full(ts) if self.time_format == "full" else ts_str(ts)
                self._user_print(f"[{fmt_ts}] {arrow} {t}")

    def loop(self) -> None:
        try:
            while True:
                # 主循环，支持系统消息刷新时自动丢弃输入，避免多次按Enter
                while True:
                    prompt = "" if getattr(self, "_suppress_next_prompt", False) else self._make_prompt()
                    self._suppress_next_prompt = False
                    try:
                        cmdline = input(prompt).strip()
                    except EOFError:
                        # Ctrl-D/EOF 退出
                        return
                    # 若在输入期间有外部信息刷新，直接丢弃本次输入并给新提示符
                    if self._invalidate_input:
                        self._invalidate_input = False
                        continue
                    break
                if not cmdline:
                    continue
                if cmdline == "/help":
                    rows = self._help_rows()
                    w = max(len(r[0]) for r in rows)
                    print(self._t("help.head_cmd").ljust(w), "  ", self._t("help.head_desc"))
                    print("-" * w, "  ", "-" * 30)
                    for a, b in rows:
                        print(a.ljust(w), "  ", b)
                elif cmdline.startswith("/login"):
                    parts = cmdline.split(" ", 1)
                    if len(parts) == 2 and parts[1].strip():
                        self.cmd_login(parts[1].strip())
                    else:
                        self.cmd_login()
                elif cmdline == "/logout":
                    self.cmd_logout()
                elif cmdline == "/exit":
                    if self.username:
                        try:
                            pkt = build_packet(self.username or "?", self.hostname, IPMSG_BR_EXIT, encoding=self.encoding)
                            try:
                                self.transport.send_broadcast(pkt)
                            except Exception:
                                pass
                            try:
                                for n in self.registry.list_nodes():
                                    if n.ip and n.ip != self.local_ip:
                                        self.transport.send_unicast(n.ip, pkt)
                            except Exception:
                                pass
                        finally:
                            pass
                    break
                elif cmdline == "/discover":
                    self.cmd_discover()
                elif cmdline.startswith("/discover "):
                    arg = cmdline.split(" ", 1)[1].strip()
                    if arg.startswith("ip:"):
                        self.cmd_discover(arg[3:])
                    else:
                        print("usage: /discover ip:<addr[:port]>")
                elif cmdline == "/info" or cmdline == "/info sys":
                    self._print_online()
                elif cmdline == "/info net":
                    try:
                        addrs = _win_list_ipv4_addrs() if os.name == "nt" else _linux_list_ipv4_addrs()
                        print(f"bind(local_ip) = {self.local_ip}")
                        print(f"iface_prefix = {self.iface_prefix}")
                        try:
                            bcast = getattr(self.transport, "_broadcast_addr", "255.255.255.255")
                            print(f"broadcast_addr = {bcast}")
                        except Exception:
                            pass
                        print("local ifaces:")
                        for ip, pre in addrs:
                            print(f" - {ip}/{pre if pre is not None else '-'}")
                    except Exception as e:
                        print(f"[ERR] info net: {e}")
                elif cmdline == "/clear":
                    try:
                        os.system("cls" if os.name == "nt" else "clear")
                    finally:
                        # 不主动打印提示，由下一轮 input() 绘制，避免重复
                        pass
                elif cmdline.startswith("/send "):
                    rest = cmdline[6:]
                    if " " not in rest:
                        print(self._t("send.usage"))
                        continue
                    target, text = rest.split(" ", 1)
                    self.cmd_send(target, text)
                # 兼容性移除：/sendall 废弃，改为 /send all <text>
                elif cmdline == "/group":
                    # 无参数：列出所有群组
                    self._info_all_groups()
                elif cmdline.startswith("/group "):
                    # /group <group_name> -<subcommand> [username]
                    tokens = cmdline.split()
                    if len(tokens) < 3:
                        print(self._t("group.usage"))
                    else:
                        group_name = tokens[1]
                        subcmd = tokens[2]
                        # -send 需要后续整行文本；其他子命令只取下一个参数
                        if subcmd.lower() == "-send":
                            # 计算文本起始位置
                            # 找到第三个空格后的剩余部分
                            try:
                                first = cmdline.index(" ")
                                second = cmdline.index(" ", first + 1)
                                third = cmdline.index(" ", second + 1)
                                text = cmdline[third + 1 :].strip()
                            except ValueError:
                                text = ""
                            self.cmd_group(group_name, subcmd, text)
                        else:
                            arg = tokens[3] if len(tokens) > 3 else None
                            self.cmd_group(group_name, subcmd, arg)
                elif cmdline.startswith("/info user:"):
                    name = cmdline[len("/info user:"):].strip()
                    if name:
                        self.cmd_info_user(name)
                    else:
                        print(self._t("info.user_usage"))
                elif cmdline.startswith("/info group:"):
                    name = cmdline[len("/info group:"):].strip()
                    if name:
                        self.cmd_info_group(name)
                    else:
                        # 语义变更：/info group: 已废弃列出功能，请使用 /group
                        self._info_all_groups()
                elif cmdline == "/search":
                    print(self._t("search.usage"))
                elif cmdline.startswith("/search "):
                    q = cmdline[len("/search "):]
                    self.cmd_search(q)
                elif cmdline.startswith("/set "):
                    # /set language zhCN|enUS; /set status online|busy|away; /set debug on|off; /set trace on|off
                    tokens = cmdline.split()
                    if len(tokens) < 3:
                        print(self._t("set.usage"))
                    else:
                        key = tokens[1].lower()
                        val = tokens[2]
                        if key == "language":
                            if val in ("zhCN","enUS"):
                                self.language = val
                                print(self._t("set.language", val=val))
                            else:
                                print(self._t("set.language_bad"))
                        elif key == "status":
                            v = val.lower()
                            if v in ("online","busy","away"):
                                self.status = v
                                print(self._t("set.status", val=v))
                                # 立即广播一次状态变更
                                try:
                                    cmd = IPMSG_BR_ENTRY if self.status != "away" else IPMSG_BR_ABSENCE
                                    pkt = build_packet(self.username or "?", self.hostname, cmd, self._build_status_ext(), encoding=self.encoding)
                                    self.transport.send_broadcast(pkt)
                                except Exception:
                                    pass
                            else:
                                print(self._t("set.status_bad"))
                        elif key == "debug":
                            self.debug = val.lower() in ("1","on","true","yes")
                            print(self._t("set.debug", val=("on" if self.debug else "off")))
                        elif key == "trace":
                            self.trace = val.lower() in ("1","on","true","yes")
                            print(self._t("set.trace", val=("on" if self.trace else "off")))
                        elif key == "encoding":
                            v = val.lower()
                            if v in ("utf8","utf-8"):
                                self.encoding = "utf-8"
                                print(self._t("set.encoding", val="utf-8"))
                            elif v in ("gbk","gb2312"):
                                self.encoding = "gbk"
                                print(self._t("set.encoding", val="gbk"))
                            else:
                                print(self._t("set.encoding_bad"))
                        elif key == "keepalive":
                            try:
                                secs = float(val)
                                if secs <= 0:
                                    raise ValueError()
                                self.keepalive_interval = secs
                                print(self._t("set.keepalive", val=str(secs)))
                            except Exception:
                                print(self._t("set.keepalive_bad"))
                        elif key == "expire":
                            try:
                                secs = float(val)
                                if secs < 10:
                                    raise ValueError()
                                self.expire_seconds = secs
                                print(self._t("set.expire", val=str(secs)))
                            except Exception:
                                print(self._t("set.expire_bad"))
                        elif key == "bind":
                            # 运行时切换绑定 IP（多网卡环境）
                            v = val
                            if v.startswith("ip:"):
                                v = v[3:]
                            self._rebind(v, user_initiated=True)
                        elif key == "encrypt":
                            # 允许子项与参数包含空格，例如：/set encrypt cipher on
                            try:
                                v = cmdline.split(" ", 2)[2].strip().lower()
                            except Exception:
                                v = val.lower()
                            # 子项：cipher/EDtag
                            if v.startswith("cipher "):
                                onoff = v.split(" ", 1)[1].strip()
                                self.encrypt_show_cipher = (onoff == "on")
                                print(f"encrypt.cipher={'on' if self.encrypt_show_cipher else 'off'}")
                            elif v.startswith("edtag ") or v.startswith("edtag"):
                                onoff = v.split(" ", 1)[1].strip() if " " in v else "on"
                                self.encrypt_edtag = (onoff == "on")
                                print(f"encrypt.edtag={'on' if self.encrypt_edtag else 'off'}")
                            elif v in ("off","on","strict"):
                                if v in ("on","strict") and not self._ensure_keys():
                                    print("[ENC] 生成或加载密钥失败，仍切换为 off")
                                    self.encrypt_mode = "off"
                                else:
                                    self.encrypt_mode = v
                                print(f"encrypt={self.encrypt_mode}")
                                # 切换加密模式后的配套行为：
                                try:
                                    # 1) 清理或启用会话
                                    if self.encrypt_mode == "off":
                                        try:
                                            self._sessions.clear()
                                        except Exception:
                                            self._sessions = {}
                                    # 2) 广播一次在线状态，更新 cap=enc 与指纹
                                    if self.username:
                                        ext2 = self._build_status_ext()
                                        cmd2 = IPMSG_BR_ENTRY if self.status != "away" else IPMSG_BR_ABSENCE
                                        pkt2 = build_packet(self.username or "?", self.hostname, cmd2, ext2, encoding=self.encoding)
                                        self.transport.send_broadcast(pkt2)
                                        # 3) 若切到 on/strict，立即触发发现与握手，以便登录后也能建立加密
                                        if self.encrypt_mode in ("on", "strict"):
                                            # 3.1 主动向已知节点请求公钥（若尚未缓存）
                                            try:
                                                for n in self.registry.list_nodes():
                                                    if n.ip == self.local_ip:
                                                        continue
                                                    if n.ip not in self._peer_pubkeys:
                                                        req = build_packet(self.username or "?", self.hostname, IPMSG_GETPUBKEY, "GETPUBKEY", encoding=self.encoding)
                                                        self.transport.send_unicast(n.ip, req)
                                            except Exception:
                                                pass
                                            # 3.2 对已有公钥但未建会话的节点，立即发起 KX
                                            try:
                                                for ip, pem in list(self._peer_pubkeys.items()):
                                                    if ip == self.local_ip:
                                                        continue
                                                    if not self._ensure_session(ip):
                                                        self._start_kx(ip)
                                            except Exception:
                                                pass
                                            # 3.3 发送一次单播/广播发现，促使对端回复 ANSENTRY 并携带能力位
                                            try:
                                                # 广播 BR_ENTRY + GETLIST（与 cmd_discover 的行为一致）
                                                pkt3 = build_packet(self.username or "?", self.hostname, IPMSG_GETLIST, encoding=self.encoding)
                                                self.transport.send_broadcast(pkt3)
                                            except Exception:
                                                pass
                                except Exception:
                                    pass
                            else:
                                print("usage: /set encrypt <off|on|strict> | encrypt cipher <on|off> | encrypt EDtag <on|off>")
                        else:
                            print(self._t("set.unknown"))
                elif cmdline.startswith("/file "):
                    # /file send user:<name>|ip:<addr> <path>
                    # /file list
                    # /file accept <offer_id>
                    # /file cancel <offer_id>
                    tokens = cmdline.split()
                    if len(tokens) >= 2 and tokens[1] == "list":
                        self.cmd_file_list()
                    elif len(tokens) >= 4 and tokens[1] == "send":
                        target = tokens[2]
                        # get the rest of the line as path (allow spaces)
                        try:
                            first = cmdline.index(" ")
                            second = cmdline.index(" ", first + 1)
                            third = cmdline.index(" ", second + 1)
                            path = cmdline[third + 1 :].strip().strip('"')
                        except ValueError:
                            path = ""
                        if not path:
                            print(self._t("file.send_usage"))
                        else:
                            self.cmd_file_send(target, path)
                    elif len(tokens) >= 3 and tokens[1] == "accept":
                        self.cmd_file_accept(tokens[2])
                    elif len(tokens) >= 3 and tokens[1] == "cancel":
                        self.cmd_file_cancel(tokens[2])
                    else:
                        print(self._t("file.usage"))
                elif cmdline == "/emote":
                    self.cmd_emote_list()
                elif cmdline.startswith("/emote list"):
                    self.cmd_emote_list()
                elif cmdline.startswith("/emote send "):
                    # /emote send user:<name>|ip:<addr>|group:<name>|all <emote_name>
                    rest = cmdline[len("/emote send "):].strip()
                    if " " not in rest:
                        print("usage: /emote send user|ip|group|all <emote_name>")
                    else:
                        tgt, name = rest.split(" ", 1)
                        self.cmd_emote_send(tgt, name.strip())
                elif cmdline.startswith("/screenshot send "):
                    tgt = cmdline[len("/screenshot send "):].strip()
                    if tgt:
                        self.cmd_screenshot_send(tgt)
                    else:
                        print("usage: /screenshot send user|ip|group|all")

                elif cmdline.startswith("/kx "):
                    # 调试命令：/kx <ip>，强制对指定 IP 发起一次 KX1 握手
                    ip = cmdline[len("/kx "):].strip()
                    if ip:
                        try:
                            self.force_start_kx(ip)
                        except Exception as e:
                            print(f"[ENC] /kx failed for {ip}: {e}")
                    else:
                        print("usage: /kx <ip>")
                elif cmdline.startswith("/debug encinfo"):
                    # 调试：打印当前加密会话与公钥信息
                    try:
                        print("-- ENC INFO --")
                        print(f"encrypt_mode = {self.encrypt_mode}")
                        print(f"nonce_base = {getattr(self, 'nonce_base', 'zfeiq_msg')}")
                        print("\nSessions:")
                        if not self._sessions:
                            print(" (no sessions)")
                        for ip, s in list(self._sessions.items()):
                            try:
                                sid = b64e(s.get('sid')) if s.get('sid') else ''
                            except Exception:
                                sid = str(s.get('sid'))
                            send_ctr = s.get('send_ctr', 0)
                            recv_ctr = s.get('recv_ctr', 0)
                            last_ts = s.get('last_ts')
                            last = ts_str_full(last_ts) if last_ts else 'N/A'
                            key_len = len(s.get('key')) if isinstance(s.get('key'), (bytes, bytearray)) else 'N/A'
                            print(f" - {ip}: sid={sid} send_ctr={send_ctr} recv_ctr={recv_ctr} last={last} key_len={key_len}")
                        print("\nPeer announced fingerprints:")
                        for ip, fp in self._peer_fp_announced.items():
                            print(f" - {ip}: announced={fp}")
                        print("\nPeer actual fingerprints (from pubkeys):")
                        for ip, fp in self._peer_fps.items():
                            print(f" - {ip}: actual={fp}")
                        print("\nKnown peer pubkey sizes:")
                        for ip, pem in self._peer_pubkeys.items():
                            try:
                                plen = len(pem)
                            except Exception:
                                plen = 'unknown'
                            print(f" - {ip}: pubkey_bytes={plen}")
                    except Exception as e:
                        print(f"[DBG] encinfo failed: {e}")
                elif cmdline == "/admin reset-keys":
                    # 删除 common/keys 下的密钥并重建，然后广播一次携带新指纹
                    try:
                        d = self._keys_dir()
                        try:
                            for fn in ("priv.pem", "pub.pem"):
                                p = os.path.join(d, fn)
                                if os.path.exists(p):
                                    os.remove(p)
                        except Exception:
                            pass
                        self._priv_pem = None; self._pub_pem = None
                        ok = self._ensure_keys()
                        if ok:
                            print("[ENC] keys regenerated")
                            if self.username:
                                ext = self._build_status_ext()
                                cmd2 = IPMSG_BR_ENTRY if self.status != "away" else IPMSG_BR_ABSENCE
                                pkt2 = build_packet(self.username or "?", self.hostname, cmd2, ext, encoding=self.encoding)
                                self.transport.send_broadcast(pkt2)
                        else:
                            print("[ENC] key regeneration failed")
                    except Exception as e:
                        print(f"[ENC] reset-keys failed: {e}")
                elif cmdline == "/admin purge-sessions":
                    try:
                        self._sessions.clear()
                    except Exception:
                        self._sessions = {}
                    print("[ENC] sessions cleared")
                elif cmdline == "/admin refresh-fp":
                    try:
                        # 清空 announced，强制后续以实际 pubkey 回写
                        self._peer_fp_announced.clear()
                    except Exception:
                        self._peer_fp_announced = {}
                    try:
                        if self.username:
                            ext = self._build_status_ext()
                            cmd2 = IPMSG_BR_ENTRY if self.status != "away" else IPMSG_BR_ABSENCE
                            pkt2 = build_packet(self.username or "?", self.hostname, cmd2, ext, encoding=self.encoding)
                            self.transport.send_broadcast(pkt2)
                        print("[ENC] announced fingerprints will refresh on next discovery")
                    except Exception as e:
                        print(f"[ENC] refresh-fp failed: {e}")
              
                elif cmdline.startswith("/ocr "):
                    # 用法: /ocr <image_path> [--send [target]]
                    args = cmdline.split()
                    if len(args) < 2:
                        print("usage: /ocr <image_path> [--send target]")
                        continue
                        
                    path = args[1]
                    do_send = False
                    target = None
                    
                    if len(args) > 2 and args[2] == "--send":
                        do_send = True
                        if len(args) > 3:
                            target = args[3]
                    
                    try:
                        from .ocr import ZFeiQOcr
                        # 获取单例，触发懒加载
                        engine = ZFeiQOcr.get_instance()
                        
                        if not engine.ready:
                            print("OCR engine initialization failed. Check logs/dependencies.")
                            continue
                            
                        # 【调试信息】显式指出当前使用的硬件后端
                        backend_type = "NPU (RK3566/RKNN)" if engine.use_npu else "CPU (ONNX Runtime)"
                        print(f"[OCR Info] Engine: {backend_type}")
                        
                        print(f"Recognizing {path} ...")
                        start_t = time.time()
                        text = engine.run(path)
                        cost_t = time.time() - start_t
                        
                        print(f"\n------------ Result ({cost_t:.2f}s) -----------")
                        print(text)
                        print("---------------------------------------")
                        
                        if do_send and text and "Error" not in text:
                            if not target:
                                target = "all" 
                            print(f"Sending result to {target}...")
                            self.cmd_send(target, f"[OCR Result]\n{text}")
                            
                    except ImportError:
                        print("Error: zfeiq_cli.ocr module not found. Please install requirements.")
                    except Exception as e:
                        print(f"OCR Execution Error: {e}")
        except KeyboardInterrupt:
            print()
        except EOFError:
            # Ctrl+D / 管道结束：直接退出（若在线先广播下线）
            if self.username:
                try:
                    pkt = build_packet(self.username or "?", self.hostname, IPMSG_BR_EXIT, encoding=self.encoding)
                    try:
                        self.transport.send_broadcast(pkt)
                    except Exception:
                        pass
                    try:
                        for n in self.registry.list_nodes():
                            if n.ip and n.ip != self.local_ip:
                                self.transport.send_unicast(n.ip, pkt)
                    except Exception:
                        pass
                finally:
                    pass
        finally:
            self.stop()

    # ======== i18n ========
    def _t(self, key: str, **kwargs) -> str:
        zh = {
            "app.started": f"ZFeiQ - {APP_VERSION} - CLI\n最近更新：{APP_LAST_UPDATE}\n- /login <用户名>: 上线\n- /help: 查看命令帮助",
            "login.already": "已在线：{user}",
            "login.prompt": "用户名: ",
            "login.empty": "用户名不能为空",
            "login.online": "已上线 {user}@{ip}",
            "logout.notlogged": "尚未登录",
            "logout.done": "已下线：{user}",
            "discover.sent": "已发送发现广播",
            "common.login_first": "请先 /login",
            "common.unknown": "未知命令；试试 /help",
            "send.usage": "用法: /send user:<name>|ip:<addr>|group:<group>|all <text>",
            "send.target_usage": "目标参数必须是 user:<name>、ip:<addr>、group:<group> 或 all",
            "send.empty": "消息内容不能为空",
            "sendall.usage": "用法: /sendall <text>",
            "sendall.nopeers": "暂无在线用户可群发",
            "group.usage": "用法: /group <group_name> -add [username] | /group <group_name> -delete [username]",
            "group.empty_or_missing": "群组 '{group}' 不存在或无成员",
            "group.member_offline": "[警告] 成员 '{user}' 离线或未知，已跳过",
            "group.member_ambiguous": "[警告] 成员 '{user}' 存在重名，已跳过",
            "group.sent_count": "群组 '{group}': 已发送给 {count} 名成员",
            "group.send_usage_legacy": "用法: /group <group_name> -send <text>（已兼容，推荐 /send group:<group> <text>）",
            "group.unsupported": "不支持的子命令；请使用 -add 或 -delete",
            "info.user_usage": "用法: /info user:<name>",
            "help.head_cmd": "命令",
            "help.head_desc": "说明",
            "set.usage": "用法: /set <language|status|debug|trace|encoding|keepalive|expire|bind|encrypt> <value>",
            "set.encoding": "编码已设置为 {val}",
            "set.encoding_bad": "encoding 必须是 utf8|gbk",
            "set.language": "语言已切换为 {val}",
            "set.language_bad": "language 必须是 zhCN 或 enUS",
            "set.status": "状态已设置为 {val}",
            "set.status_bad": "status 必须是 online|busy|away",
            "set.debug": "debug={val}",
            "set.trace": "trace={val}",
            "set.unknown": "未知设置项；可选: language|status|debug|trace|encoding|keepalive|expire|bind|encrypt",
            "set.keepalive": "keepalive 间隔已设置为 {val} 秒",
            "set.keepalive_bad": "keepalive 需为正数（单位秒）",
            "set.expire": "超时下线阈值已设置为 {val} 秒",
            "set.expire_bad": "expire 需为 >= 10 的秒数",
            "set.bind_done": "已切换绑定到 {val}",
            "set.bind_bad": "bind 失败：指定 IP 不是本机地址",
            "user.notfound": "未找到用户: {name}",
            "user.ambiguous": "用户名不唯一，候选：",
            "user.ambiguous_hint": "请改用 /send ip:<ip> ...",
            "groups.header": "所有群组：",
            "groups.one": "- {name}: {count} 人 -> {members}",
            # file transfer
            "file.usage": "用法: /file send user:<name>|ip:<addr> <path> | /file list | /file accept <offer_id> | /file cancel <offer_id>",
            "file.send_usage": "用法: /file send user:<name>|ip:<addr> <path>",
            "file.path_bad": "文件不存在: {p}",
            "file.offer_fail": "创建文件要约失败: {e}",
            "file.offered": "已向 {ip} 提供文件 {name} ({size} 字节)，编号 {id}",
            "file.none": "暂无可接收文件",
            "file.pending": "待接收文件:",
            "file.unknown": "未知要约: {id}",
            "file.saved": "已保存至 {path}",
            "file.download_fail": "下载失败: {e}",
            "file.canceled_in": "已放弃接收要约 {id}",
            "file.canceled_out": "已取消发送要约 {id}",
        }
        en = {
            "app.started": f"ZFeiQ - {APP_VERSION} - CLI\nLast update: {APP_LAST_UPDATE}\n- /login <username>: go online\n- /help: show command help",
            "login.already": "Already logged in as {user}",
            # search
            "search.usage": "用法: /search user:<name>|group:<name>|ip:<addr>",
            "search.user_matches": "按用户名匹配到: {name}",
            "search.group_notfound": "未找到群组: {group}",
            "search.group_header": "群组 {group} 的成员：",
            "search.ip_notfound": "未找到 IP: {ip}",
            "login.prompt": "username: ",
            "login.empty": "username cannot be empty",
            "login.online": "online as {user}@{ip}",
            "logout.notlogged": "not logged in",
            # search
            "search.usage": "usage: /search user:<name>|group:<name>|ip:<addr>",
            "search.user_matches": "user matches for: {name}",
            "search.group_notfound": "no such group: {group}",
            "search.group_header": "members in group {group}:",
            "search.ip_notfound": "no such ip: {ip}",
            "logout.done": "logged out: {user}",
            "discover.sent": "discover broadcast sent",
            "common.login_first": "Please /login first",
            "common.unknown": "unknown command; try /help",
            "send.usage": "usage: /send user:<name>|ip:<addr>|group:<group>|all <text>",
            "send.target_usage": "target must be user:<name>, ip:<addr>, group:<group> or all",
            "send.empty": "text cannot be empty",
            "sendall.usage": "usage: /sendall <text>",
            "sendall.nopeers": "no online peers to send",
            "group.usage": "usage: /group <group_name> -add [username] | /group <group_name> -delete [username]",
            "group.empty_or_missing": "group '{group}' not found or has no members",
            "group.member_offline": "[WARN] user '{user}' offline or unknown; skip",
            "group.member_ambiguous": "[WARN] user '{user}' ambiguous; skip",
            "group.sent_count": "group '{group}': sent to {count} member(s)",
            "group.send_usage_legacy": "usage: /group <group_name> -send <text> (deprecated; use /send group:<group> <text>)",
            "group.unsupported": "unsupported subcommand; use -add or -delete",
            "info.user_usage": "usage: /info user:<name>",
            "help.head_cmd": "COMMAND",
            "help.head_desc": "DESCRIPTION",
            "set.usage": "usage: /set <language|status|debug|trace|encoding|keepalive|expire|bind|encrypt> <value>",
            "set.encoding": "encoding set to {val}",
            "set.encoding_bad": "encoding must be utf8|gbk",
            "set.language": "language set to {val}",
            "set.language_bad": "language must be zhCN or enUS",
            "set.status": "status set to {val}",
            "set.status_bad": "status must be online|busy|away",
            "set.debug": "debug={val}",
            "set.trace": "trace={val}",
            "set.unknown": "unknown setting; keys: language|status|debug|trace|encoding|keepalive|expire|bind|encrypt",
            "set.keepalive": "keepalive interval set to {val} seconds",
            "set.keepalive_bad": "keepalive must be positive seconds",
            "set.expire": "expire threshold set to {val} seconds",
            "set.expire_bad": "expire must be >= 10 seconds",
            "set.bind_done": "re-bound to {val}",
            "set.bind_bad": "bind failed: ip is not a local address",
            "user.notfound": "no such user: {name}",
            "user.ambiguous": "ambiguous username; candidates:",
            "user.ambiguous_hint": "use /send ip:<ip> ... instead",
            "groups.header": "Groups:",
            "groups.one": "- {name}: {count} member(s) -> {members}",
            # file transfer
            "file.usage": "usage: /file send user:<name>|ip:<addr> <path> | /file list | /file accept <offer_id> | /file cancel <offer_id>",
            "file.send_usage": "usage: /file send user:<name>|ip:<addr> <path>",
            "file.path_bad": "file not found: {p}",
            "file.offer_fail": "failed to create file offer: {e}",
            "file.offered": "offered {name} ({size} bytes) to {ip}, id {id}",
            "file.none": "no pending file offers",
            "file.pending": "pending file offers:",
            "file.unknown": "unknown offer: {id}",
            "file.saved": "saved to {path}",
            "file.download_fail": "download failed: {e}",
            "file.canceled_in": "canceled incoming offer {id}",
            "file.canceled_out": "canceled outgoing offer {id}",
        }
        lang = zh if self.language == "zhCN" else en
        s = lang.get(key, key)
        try:
            return s.format(**kwargs)
        except Exception:
            return s

    def _help_rows(self):
        # 按前缀归类
        rows = [
            ("/login [username]", self._t("登录（可带用户名参数）") if self.language=="zhCN" else "login (optionally with username)"),
            ("/logout", self._t("下线但不退出程序") if self.language=="zhCN" else "logout but keep app running"),
            ("/exit", self._t("退出程序（若在线先下线广播）") if self.language=="zhCN" else "exit app (broadcast offline if online)"),
            ("/discover", self._t("主动广播并显示在线列表") if self.language=="zhCN" else "broadcast and show online list"),
            ("/discover ip:<addr>", self._t("向指定 IP 单播发现（跨子网可用）") if self.language=="zhCN" else "unicast discovery to specific ip (cross-subnet)"),
            ("/clear", self._t("清屏") if self.language=="zhCN" else "clear screen"),
            ("/info", self._t("显示本机与当前在线列表") if self.language=="zhCN" else "show local and online list"),
            ("/info net", self._t("显示绑定 IP、广播地址和本机网卡列表") if self.language=="zhCN" else "show binding, broadcast and local ifaces"),
            ("/info user:<name>", self._t("查看与该用户的历史消息") if self.language=="zhCN" else "show chat history with user"),
            ("/info group:<name>", self._t("查看该群组的会话历史") if self.language=="zhCN" else "show group chat history"),
            ("/group", self._t("展示所有的组及其成员和人数") if self.language=="zhCN" else "list all groups and member counts"),
            ("/search user|group|ip", self._t("按用户名/组名/IP 搜索") if self.language=="zhCN" else "search by user/group/ip"),
            ("/set language <zhCN|enUS>", self._t("切换语言包") if self.language=="zhCN" else "switch language"),
            ("/set status <online|busy|away>", self._t("设置在线状态") if self.language=="zhCN" else "set presence status"),
            ("/set debug <on|off>", self._t("调试开关（打印收发摘要）") if self.language=="zhCN" else "debug logging on/off"),
            ("/set trace <on|off>", self._t("诊断开关（更详细日志）") if self.language=="zhCN" else "trace logging on/off"),
            ("/set encoding <utf8|gbk>", self._t("设置发送编码（与飞秋兼容可用 gbk）") if self.language=="zhCN" else "set outgoing encoding"),
            ("/set encrypt <off|on|strict>", self._t("设置加密模式（off|on|strict）") if self.language=="zhCN" else "set encryption mode"),
            ("/set encrypt cipher <on|off>", self._t("启用/关闭显示原始密文") if self.language=="zhCN" else "toggle showing raw cipher"),
            ("/set encrypt EDtag <on|off>", self._t("启用/关闭明文旁 [E-D OK] 标记") if self.language=="zhCN" else "toggle E-D OK tag on plaintext"),
            ("/set bind <ip>", self._t("切换绑定网卡/IP（多网卡环境）") if self.language=="zhCN" else "switch bound NIC/IP (multi-NIC)"),
            ("/send user:<name> <text>", self._t("按用户名发送消息") if self.language=="zhCN" else "send to username"),
            ("/send ip:<ip> <text>", self._t("按 IP 发送消息") if self.language=="zhCN" else "send to ip"),
            ("/send group:<group> <text>", self._t("向群组内在线成员逐个发送") if self.language=="zhCN" else "send to members of group"),
            ("/send all <text>", self._t("给所有在线用户群发") if self.language=="zhCN" else "broadcast to all online"),
            ("/file send user|ip <path>", self._t("发送文件（实验版，先在本实现之间互传）") if self.language=="zhCN" else "send file (experimental; intra-app first)"),
            ("/file list", self._t("查看待接收文件要约") if self.language=="zhCN" else "list pending file offers"),
            ("/file accept <id>", self._t("接受文件并保存到当前目录") if self.language=="zhCN" else "accept file and save to cwd"),
            ("/file cancel <id>", self._t("放弃/取消文件要约") if self.language=="zhCN" else "cancel an incoming/outgoing file offer"),
            ("/group <group> -add [username]", self._t("创建群组或添加成员") if self.language=="zhCN" else "create group or add member"),
            ("/group <group> -delete [username]", self._t("删除群组或移除成员") if self.language=="zhCN" else "delete group or remove member"),
            ("/ocr <path> [--send]", self._t("识别图片文字(支持NPU/CPU)") if self.language=="zhCN" else "OCR image text (NPU/CPU auto)"),
        ]
        return rows

    def _info_all_groups(self):
        print(self._t("groups.header"))
        if not self.groups:
            print(" - (none)")
            return
        for name, members in sorted(self.groups.items()):
            mems = ",".join(sorted(members)) if members else "-"
            print(self._t("groups.one", name=name, count=len(members), members=mems))
        
    def _info_all_groups(self):
        print(self._t("groups.header"))
        if not self.groups:
            print(" - (none)")
            return
        for name, members in sorted(self.groups.items()):
            mems = ",".join(sorted(members)) if members else "-"
            print(self._t("groups.one", name=name, count=len(members), members=mems))
