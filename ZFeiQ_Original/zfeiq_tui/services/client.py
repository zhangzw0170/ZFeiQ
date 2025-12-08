from __future__ import annotations
import sys
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any

# Ensure project root on sys.path to import zfeiq_cli
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from zfeiq_cli.cli import ZFeiQCli, _win_list_ipv4_addrs, _linux_list_ipv4_addrs
from zfeiq_cli.protocol import (
    parse_packet,
    base_command,
    IPMSG_SENDMSG,
    decode_fileattach_lines,
    build_packet,
    IPMSG_BR_ENTRY,
    IPMSG_BR_ABSENCE,
    IPMSG_BR_EXIT,
    IPMSG_ANSENTRY,
    IPMSG_ANSLIST,
    IPMSG_GETLIST,
    IPMSG_GETPUBKEY,
)

class ClientAdapter:
    def __init__(self):
        self.zcli: Optional[ZFeiQCli] = None
        self._orig_recv = None
        self._orig_handshake_event = None
        self._persist_path = PROJECT_ROOT / 'ZFeiQ_Original' / 'zfeiq_state.json'
        self._persist: Dict[str, Any] = {}
        self._load_persist()
        # callbacks (assigned by app)
        self.on_message = self._noop_message
        self.on_file_offer = self._noop_file
        self.on_encryption_changed = self._noop
        self.on_offers_updated = self._noop
        self.on_nodes_updated = self._noop

    # default no-op callbacks
    def _noop(self, *args, **kwargs):
        return None

    def _noop_message(self, sender: str, ip: str, text: str, is_system: bool = False):
        return None

    def _noop_file(self, sender: str, name: str, size: int):
        return None

    def _load_persist(self):
        try:
            if self._persist_path.exists():
                import json
                self._persist = json.loads(self._persist_path.read_text(encoding='utf-8') or '{}')
        except Exception:
            self._persist = {}

    def _save_persist(self):
        try:
            import json
            data = json.dumps(self._persist, ensure_ascii=False, indent=2)
            self._persist_path.write_text(data, encoding='utf-8')
        except Exception:
            pass

    def list_local_ips(self) -> List[Tuple[str,int]]:
        raw = _win_list_ipv4_addrs() if sys.platform.startswith('win') else _linux_list_ipv4_addrs()
        return raw

    def start(self, username: str, bind_ip: str):
        self.zcli = ZFeiQCli(port=2425, bind_ip=bind_ip)
        try:
            self.zcli.ui_silent = True
        except Exception:
            pass
        # hook handshake events for system log
        try:
            self._orig_handshake_event = getattr(self.zcli, '_handshake_event', None)
            if self._orig_handshake_event:
                def _wrapped_handshake(ip: str, text: str):
                    try:
                        self._orig_handshake_event(ip, text)
                    finally:
                        try:
                            self.on_message('系统', ip or '-', f"[ENC] {text}", True)
                        except Exception:
                            pass
                self.zcli._handshake_event = _wrapped_handshake  # type: ignore[attr-defined]
        except Exception:
            pass
        self._orig_recv = self.zcli._on_recv
        self.zcli._on_recv = self._recv_hook
        self.zcli.start()
        self.zcli.cmd_login(username)
        try:
            self.on_nodes_updated()
        except Exception:
            pass
        # 应用持久化的加密设置并同步状态
        self._apply_persisted_settings()
        self._sync_encryption_state(initial=True)
        # 主动发现
        self.zcli.cmd_discover()
        try:
            self.on_nodes_updated()
        except Exception:
            pass
        # 系统提示：已登录并开始发现
        try:
            self.on_message('系统', self.zcli.local_ip, '已登录，正在发现用户...', True)
        except Exception:
            pass
        # 若启用了加密，模拟 GUI 的即时握手触发：对当前已知节点尝试 KX
        try:
            mode = getattr(self.zcli, 'encrypt_mode', 'on')
            if mode and mode != 'off':
                nodes = list(self.zcli.registry.list_nodes())
                for n in nodes:
                    try:
                        if n.ip != self.zcli.local_ip:
                            # 清理旧会话并尝试握手
                            if hasattr(self.zcli, 'purge_session'):
                                self.zcli.purge_session(n.ip)
                            if hasattr(self.zcli, 'force_start_kx'):
                                self.zcli.force_start_kx(n.ip)
                                # 系统提示：对节点发起握手
                                try:
                                    self.on_message('系统', n.ip, '已发起加密握手 (KX)', True)
                                except Exception:
                                    pass
                    except Exception:
                        pass
        except Exception:
            pass

    def stop(self):
        try:
            if self.zcli:
                try:
                    if getattr(self, '_orig_handshake_event', None):
                        self.zcli._handshake_event = self._orig_handshake_event  # type: ignore[attr-defined]
                        self._orig_handshake_event = None
                except Exception:
                    pass
                self.zcli.stop()
        except Exception:
            pass

    # --- send helpers ---
    def send_text(self, target: str, text: str):
        if target == 'all':
            self.zcli.cmd_sendall(text)
            try:
                self.on_message(self.zcli.username or '我', 'all', text, False)
            except Exception:
                pass
        elif target.startswith('group:'):
            g = target.split(':',1)[1]
            self.zcli.cmd_group(g, '-send', text)
            try:
                self.on_message(self.zcli.username or '我', f'group:{g}', text, False)
            except Exception:
                pass
        else:
            self.zcli.cmd_send(f'ip:{target}', text)
            try:
                self.on_message(self.zcli.username or '我', target, text, False)
            except Exception:
                pass

    def send_file(self, target: str, path: str):
        self.zcli.cmd_file_send(target if target!='all' else 'all', path)

    def discover(self, ip: Optional[str]=None):
        self.zcli.cmd_discover(ip if ip else None)
        try:
            self.on_message('系统', self.zcli.local_ip, '已发送发现广播', True)
        except Exception:
            pass
        try:
            self.on_nodes_updated()
        except Exception:
            pass
        self._sync_encryption_state()
        # 发现后再尝试对新节点触发握手（加密已启用时）
        try:
            mode = getattr(self.zcli, 'encrypt_mode', 'on')
            if mode and mode != 'off':
                nodes = list(self.zcli.registry.list_nodes())
                for n in nodes:
                    try:
                        if n.ip != self.zcli.local_ip and hasattr(self.zcli, 'force_start_kx'):
                            self.zcli.force_start_kx(n.ip)
                    except Exception:
                        pass
        except Exception:
            pass

    # --- encryption controls ---
    def set_encrypt_mode(self, mode: str):
        try:
            if mode in ('off','on','strict'):
                self.zcli.cmd_set(['encrypt', mode])
                up = dict(self._persist.get('tui', {})); up['encrypt_mode']=mode; self._persist['tui']=up; self._save_persist()
                self._sync_encryption_state()
                self.on_encryption_changed()
        except Exception:
            pass

    def set_encrypt_cipher_print(self, on: bool):
        try:
            self.zcli.cmd_set(['encrypt','cipher','on' if on else 'off'])
            up = dict(self._persist.get('tui', {})); up['encrypt_cipher']=bool(on); self._persist['tui']=up; self._save_persist()
            self.on_encryption_changed()
        except Exception:
            pass

    def set_encrypt_edtag(self, on: bool):
        try:
            self.zcli.cmd_set(['encrypt','EDtag','on' if on else 'off'])
            up = dict(self._persist.get('tui', {})); up['encrypt_edtag']=bool(on); self._persist['tui']=up; self._save_persist()
            self.on_encryption_changed()
        except Exception:
            pass

    def get_encrypt_settings(self) -> Tuple[str, bool, bool]:
        mode = 'on'
        cipher = False
        edtag = False
        try:
            if self.zcli:
                mode = getattr(self.zcli, 'encrypt_mode', 'on') or 'on'
                cipher = bool(getattr(self.zcli, 'encrypt_show_cipher', False))
                edtag = bool(getattr(self.zcli, 'encrypt_edtag', False))
            else:
                tui_cfg = self._persist.get('tui', {})
                mode = tui_cfg.get('encrypt_mode', 'on') or 'on'
                cipher = bool(tui_cfg.get('encrypt_cipher', False))
                edtag = bool(tui_cfg.get('encrypt_edtag', False))
        except Exception:
            pass
        return (mode if mode in ('off','on','strict') else 'on', cipher, edtag)

    # ---- helpers mirroring GUI backend ----
    def _apply_persisted_settings(self):
        try:
            tui_cfg = self._persist.get('tui', {})
            mode = tui_cfg.get('encrypt_mode')
            if mode in ('off','on','strict'):
                self.zcli.cmd_set(['encrypt', mode])
            cipher_on = tui_cfg.get('encrypt_cipher')
            if isinstance(cipher_on, bool):
                self.zcli.cmd_set(['encrypt','cipher','on' if cipher_on else 'off'])
            ed_on = tui_cfg.get('encrypt_edtag')
            if isinstance(ed_on, bool):
                self.zcli.cmd_set(['encrypt','EDtag','on' if ed_on else 'off'])
        except Exception:
            pass

    def _sync_encryption_state(self, initial: bool=False):
        try:
            mode = getattr(self.zcli, 'encrypt_mode', 'off')
            if initial:
                try:
                    if not getattr(self.zcli, '_pub_pem', None):
                        self.zcli._ensure_keys()
                except Exception:
                    pass
            if mode in ('on','strict'):
                self._broadcast_presence()
                self._request_pubkeys_and_kx()
            if initial:
                try:
                    self.on_encryption_changed()
                except Exception:
                    pass
        except Exception:
            pass

    def _broadcast_presence(self):
        try:
            if not getattr(self.zcli, 'username', None):
                return
            cmd = IPMSG_BR_ENTRY if self.zcli.status != 'away' else IPMSG_BR_ABSENCE
            pkt = build_packet(self.zcli.username or '?', self.zcli.hostname, cmd, self.zcli._build_status_ext(), encoding=self.zcli.encoding)
            try:
                self.zcli.transport.send_broadcast(pkt)
            except Exception:
                pass
            try:
                for n in self.zcli.registry.list_nodes():
                    if n.ip and n.ip != self.zcli.local_ip:
                        self.zcli.transport.send_unicast(n.ip, pkt)
            except Exception:
                pass
        except Exception:
            pass

    def _request_pubkeys_and_kx(self):
        try:
            for n in self.zcli.registry.list_nodes():
                ip = getattr(n, 'ip', '')
                if not ip or ip == self.zcli.local_ip:
                    continue
                peer_pub = getattr(self.zcli, '_peer_pubkeys', {}).get(ip)
                if not peer_pub:
                    try:
                        req = build_packet(self.zcli.username or '?', self.zcli.hostname, IPMSG_GETPUBKEY, 'GETPUBKEY', encoding=self.zcli.encoding)
                        self.zcli.transport.send_unicast(ip, req)
                    except Exception:
                        pass
                else:
                    try:
                        if not self.zcli._ensure_session(ip):
                            self.zcli._start_kx(ip)
                    except Exception:
                        pass
        except Exception:
            pass

    def groups(self):
        return self.zcli.groups

    def registry(self):
        return self.zcli.registry

    def _recv_hook(self, data: bytes, addr: tuple):
        if self._orig_recv:
            try: self._orig_recv(data, addr)
            except Exception: pass
        try:
            hdr, ext = parse_packet(data)
            base = base_command(hdr.get('command',0))
            user = hdr.get('username','?')
            src = addr[0]
            if base in (
                IPMSG_BR_ENTRY,
                IPMSG_BR_ABSENCE,
                IPMSG_BR_EXIT,
                IPMSG_ANSENTRY,
                IPMSG_ANSLIST,
                IPMSG_GETLIST,
            ):
                try:
                    self.on_nodes_updated()
                except Exception:
                    pass
            if base == IPMSG_SENDMSG:
                text = ext.split('\0',1)[0] if ext else ''
                ext_after = ext.split('\0',1)[1] if '\0' in (ext or '') else ''
                # 握手帧：通知加密状态刷新，不在聊天区展示原文
                try:
                    if text.startswith('KX1;') or text.startswith('KX2;') or text.startswith('ENCREADY;'):
                        self.on_encryption_changed()
                        text = ''
                except Exception:
                    pass
                # ENC 帧：刷新加密状态，并尝试从历史中取明文
                try:
                    if text.startswith('ENC2;') or text.startswith('ENC;'):
                        self.on_encryption_changed()
                        # 默认不展示原始加密帧；优先替换为已解密明文
                        last_plain = None
                        try:
                            hist = self.zcli.history.get(src)
                            for _, direction, payload in reversed(hist):
                                if direction == 'in' and payload and not payload.startswith('ENC'):
                                    last_plain = payload
                                    break
                        except Exception:
                            last_plain = None
                        if last_plain:
                            text = last_plain
                        else:
                            # 无明文时展示占位提示，避免泄露原始密文
                            text = '[加密消息解密失败]'
                except Exception:
                    pass
                # 文件附件
                attaches = []
                try:
                    attaches = decode_fileattach_lines(ext_after)
                except Exception:
                    attaches = []
                if attaches:
                    finfo = ', '.join([f"{a.get('name') or 'file'}" for a in attaches])
                    try:
                        for a in attaches:
                            name = a.get('name', 'file')
                            size = int(a.get('size', 0) or 0)
                            self.on_file_offer(user, name, size)
                    except Exception:
                        pass
                    try:
                        self.on_offers_updated()
                    except Exception:
                        pass
                    self.on_message(user, src, f"[文件] {finfo}", True)
                # FILE_OFFER 兼容消息
                if text.startswith('FILE_OFFER;'):
                    try:
                        self.on_offers_updated()
                    except Exception:
                        pass
                    return
                if text:
                    # 保证不把 ENC 帧原文写入聊天区
                    if not (text.startswith('ENC2;') or text.startswith('ENC;')):
                        self.on_message(user, src, text, False)
        except Exception:
            pass
