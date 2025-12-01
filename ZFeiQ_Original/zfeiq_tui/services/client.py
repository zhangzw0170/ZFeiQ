from __future__ import annotations
import sys
from pathlib import Path
from typing import Optional, List, Tuple

# Ensure project root on sys.path to import zfeiq_cli
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from zfeiq_cli.cli import ZFeiQCli, _win_list_ipv4_addrs, _linux_list_ipv4_addrs
from zfeiq_cli.protocol import parse_packet, base_command, IPMSG_SENDMSG, decode_fileattach_lines

class ClientAdapter:
    def __init__(self):
        self.zcli: Optional[ZFeiQCli] = None
        self._orig_recv = None

    def list_local_ips(self) -> List[Tuple[str,int]]:
        raw = _win_list_ipv4_addrs() if sys.platform.startswith('win') else _linux_list_ipv4_addrs()
        return raw

    def start(self, username: str, bind_ip: str):
        self.zcli = ZFeiQCli(port=2425, bind_ip=bind_ip)
        self._orig_recv = self.zcli._on_recv
        self.zcli._on_recv = self._recv_hook
        self.zcli.start()
        self.zcli.cmd_login(username)
        self.zcli.cmd_discover()

    def stop(self):
        try:
            if self.zcli:
                self.zcli.stop()
        except Exception:
            pass

    # --- send helpers ---
    def send_text(self, target: str, text: str):
        if target == 'all':
            self.zcli.cmd_sendall(text)
        elif target.startswith('group:'):
            g = target.split(':',1)[1]
            self.zcli.cmd_group(g, '-send', text)
        else:
            self.zcli.cmd_send(f'ip:{target}', text)

    def send_file(self, target: str, path: str):
        self.zcli.cmd_file_send(target if target!='all' else 'all', path)

    def discover(self, ip: Optional[str]=None):
        self.zcli.cmd_discover(ip if ip else None)

    def groups(self):
        return self.zcli.groups

    def registry(self):
        return self.zcli.registry

    # hook for app to override
    def on_message(self, sender: str, ip: str, text: str, is_system: bool=False):
        pass

    def _recv_hook(self, data: bytes, addr: tuple):
        if self._orig_recv:
            try: self._orig_recv(data, addr)
            except Exception: pass
        try:
            hdr, ext = parse_packet(data)
            base = base_command(hdr.get('command',0))
            user = hdr.get('username','?')
            src = addr[0]
            if base == IPMSG_SENDMSG:
                txt = ext.split('\0',1)[0] if ext else ''
                ext_after = ext.split('\0',1)[1] if '\0' in (ext or '') else ''
                try:
                    attaches = decode_fileattach_lines(ext_after)
                except Exception:
                    attaches = []
                if attaches:
                    finfo = ', '.join([f"{a.get('name')}" for a in attaches])
                    self.on_message(user, src, f"[文件] {finfo}", True)
                if txt and not txt.startswith('FILE_OFFER;'):
                    self.on_message(user, src, txt, False)
        except Exception:
            pass
