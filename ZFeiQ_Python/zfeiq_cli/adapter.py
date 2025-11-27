import threading
import socket
import os
from zfeiq_common.fsutils import ensure_dir
import sys
from typing import Dict, Any, Optional

from zfeiq_core.events import EventBus, TOPIC_MSG_INCOMING, TOPIC_MSG_SENT, TOPIC_USER_ONLINE, TOPIC_FILE_OFFER, TOPIC_FILE_PROGRESS, TOPIC_FILE_COMPLETE, TOPIC_NET_REBIND
from zfeiq_core.api import ZFeiQCore
from zfeiq_core.services.network import NetworkService
from zfeiq_core.services.protocol import ProtocolService
from zfeiq_core.services.filetransfer import FileService
try:
    # reuse GUI translations when available so CLI and GUI share the same keys
    from zfeiq_gui.lang import t as _t_global, set_language, get_current_language
except Exception:
    _t_global = None
    set_language = None
    get_current_language = None


class CLIAdapter:
    """Minimal CLI adapter that maps commands to ZFeiQCore calls.

    Responsibilities:
    - parse a small set of commands
    - maintain CLI-local structures (groups, pending file offers)
    - subscribe to core events and print user-friendly messages
    """

    def __init__(self, username: str = "cli_user", core=None):
        global t
        t = _t_global
        self.bus = EventBus()
        # allow injecting an existing core for testing/embedding
        self.core = core or ZFeiQCore(self.bus)
        # attach services
        # respect persisted bind if present
        cfg_bind = self.core.get_config('bind', None)
        bind_ip = cfg_bind or "0.0.0.0"
        cfg_port = self.core.get_config('port', None)
        port = int(cfg_port) if cfg_port else 2425
        self.net = NetworkService(self.bus, bind_ip=bind_ip, port=port)
        self.core.attach_network(self.net)
        self.proto = ProtocolService()
        self.core.attach_protocol(self.proto)
        # file service should follow bind/port settings where applicable
        file_bind = cfg_bind or "0.0.0.0"
        file_port_cfg = self.core.get_config('file_port', None) or cfg_port
        file_port = int(file_port_cfg) if file_port_cfg else 2425
        self.fs = FileService(bind_ip=file_bind, port=file_port)
        self.core.attach_file_service(self.fs)

        self.groups: Dict[str, list] = {}
        # pending file offers: id -> dict (from, name, size, meta)
        self._file_offers: Dict[int, Dict[str, Any]] = {}
        self._next_offer_id = 1

        # subscribe events
        self.bus.subscribe(TOPIC_MSG_INCOMING, self._on_msg_incoming)
        self.bus.subscribe(TOPIC_MSG_SENT, self._on_msg_sent)
        self.bus.subscribe(TOPIC_USER_ONLINE, self._on_user_online)
        self.bus.subscribe(TOPIC_FILE_OFFER, self._on_file_offer)
        self.bus.subscribe(TOPIC_FILE_PROGRESS, self._on_file_progress)
        self.bus.subscribe(TOPIC_FILE_COMPLETE, self._on_file_complete)
        # show rebind events
        try:
            self.bus.subscribe(TOPIC_NET_REBIND, self._on_net_rebind)
        except Exception:
            pass

        self.core.login(username)
        self.core.ensure_keys()  # ensure keys exist
        # initialize download_dir from persisted config or default to ./downloads
        import os
        dd = self.core.get_config('download_dir', None)
        if not dd:
            try:
                self.download_dir = ensure_dir('downloads')
            except Exception:
                self.download_dir = os.path.join(os.getcwd(), 'downloads')
        else:
            try:
                # normalize persisted path into commons
                self.download_dir = ensure_dir(dd)
            except Exception:
                self.download_dir = dd

        self._running = False

    def cmd_help(self) -> None:
        """Print help text for available CLI commands."""
        # Prefer translations from zfeiq_gui.lang when available
        def _t(key, default):
            try:
                if t is not None:
                    return t[key]
            except Exception:
                pass
            return default

        help_lines = [
            _t('help', '可用命令：'),
            f"  {_t('discover','discover')}                    - {_t('discover','Broadcast a discovery packet (like /discover)')}",
            f"  {_t('send','send')} <target> <text>        - {_t('send','Send a message to target (use \'all\' for broadcast)')}",
            f"  {_t('groups','group')} <name> -add <user>    - {_t('group_new','Add member to group')}",
            f"  {_t('group_send','group send')} <name> -send <text>   - {_t('group_send','Send message to group members')}",
            f"  {_t('files','file send')} <target> <path>   - {_t('file_offer_label','Send a file offer to target')}",
            f"  {_t('file_offer_label','file list')}                   - {_t('file_offer_label','List pending file offers')}",
            f"  {_t('file_done_label','file accept')} <id> [ip] [dst] - {_t('file_done_label','Accept offer id, optionally specify remote IP and dest path')}",
            f"  {_t('cancel','file cancel')} <id>            - {_t('cancel','Cancel/unregister a file mapping')}",
            f"  {_t('download_dir','set download_dir')} <path>     - {_t('download_dir','Set default download directory')}",
            f"  {_t('lang','set language')} <lang>         - {_t('lang','Switch CLI language (e.g. zhCN, enUS)')}",
            f"  {_t('status','set status')} <token>          - {_t('status','Set and broadcast status (online|away|busy)')}",
            f"  {_t('set_bind','set bind')} <ip>               - {_t('set_bind','Bind IP and lock auto-rebind')}",
            f"  {_t('set_bind_unlocked','set bind unlock')}             - {_t('set_bind_unlocked','Unlock auto-rebind (allow automatic interface switching)')}",
            f"  {_t('keepalive','set keepalive')} <sec>         - {_t('keepalive','Set keepalive interval (seconds)')}",
            f"  {_t('expire','set expire')} <sec>            - {_t('expire','Set node expire time (seconds)')}",
            f"  {_t('info','info')}                        - {_t('info','Show recent history')}",
            f"  {_t('info','info net')}                    - {_t('info','Show network bind info')}",
            f"  {_t('search','search')} user:<name>|ip:<ip>  - {_t('search','Search history by user or ip')}",
            f"  {_t('clear','clear')}                       - {_t('clear','Simple clear (print blank lines)')}",
            f"  {_t('logout','logout')} | {_t('logout_long','exit')}               - {_t('logout_long','Send exit & stop services')}",
            f"  {_t('help','help')}                        - {_t('help','Show this help text')}",
        ]
        for l in help_lines:
            print(l)

    def cmd_set_language(self, lang: str) -> None:
        """Set CLI language using shared GUI language map when available."""
        if not lang:
            print(t['set_language_usage'])
            return
        # attempt runtime switch
        try:
            if set_language:
                set_language(lang)
                print(t['set_language_success'] + str(lang))
            else:
                print(t['set_language_module_na'])
        except Exception as e:
            print(t['set_language_failed'] + str(e))
        # persist in core.persistence under 'config.language' to be compatible with gui.lang loader
        try:
            data = self.core.persistence.read()
        except Exception:
            data = {}
        cfg = data.get('config') or {}
        cfg['language'] = lang
        data['config'] = cfg
        try:
            self.core.persistence.write(data)
        except Exception:
            pass

    def _refresh_print(self, text: str) -> None:
        """Print an external event with blank line before/after and redraw prompt when in REPL.

        This helps avoid mixing prompt and incoming messages. It's best-effort: prints
        an empty line, the text, another empty line, and then (if REPL active) writes
        a fresh prompt without consuming input.
        """
        try:
            # ensure we start on a fresh line
            sys.stdout.write("\n")
            sys.stdout.write(str(text) + "\n")
            sys.stdout.write("\n")
            sys.stdout.flush()
            # Do not print a prompt here — input() prints its own prompt and
            # writing a prompt from an asynchronous event leads to duplicate
            # prompts like "manual => manual =>". We leave the prompt to input().
        except Exception:
            try:
                print(text)
            except Exception:
                pass

    # Event handlers
    def _on_msg_incoming(self, payload: Any) -> None:
        try:
            if isinstance(payload, dict):
                from_user = payload.get("from_user") or payload.get("from") or payload.get("from_user")
                text = payload.get("text")
                self._refresh_print((t['msg_incoming'] if t is not None else '[IN] ') + f"{from_user}: {text}")
            else:
                self._refresh_print((t['msg_incoming'] if t is not None else '[IN] ') + str(payload))
        except Exception:
            pass

    def _on_msg_sent(self, payload: Any) -> None:
        try:
            if isinstance(payload, dict):
                to = payload.get("to")
                text = payload.get("text")
                self._refresh_print((t['msg_sent'] if t is not None else '[SENT] ') + f"to {to}: {text}")
            else:
                self._refresh_print((t['msg_sent'] if t is not None else '[SENT] ') + str(payload))
        except Exception:
            pass

    def _on_user_online(self, payload: Any) -> None:
        try:
            try:
                label = _t_global['online'] if _t_global is not None else '在线'
            except Exception:
                label = '在线'
            self._refresh_print(f"[{label}] {payload}")
        except Exception:
            pass

    def _on_file_offer(self, payload: Any) -> None:
        # store a simple local offer id and present to user
        oid = self._next_offer_id
        self._next_offer_id += 1
        self._file_offers[oid] = payload
        from_user = payload.get("from_user") if isinstance(payload, dict) else str(payload)
        name = payload.get("filename") if isinstance(payload, dict) else "<file>"
        size = payload.get("size") if isinstance(payload, dict) else 0
        try:
            self._refresh_print((t['file_offer_cli'] if t is not None else '[FILE OFFER #') + f"{oid}] {from_user}: {name} ({size} bytes)")
        except Exception:
            pass

    def _on_file_progress(self, payload: Any) -> None:
        try:
            remote = payload.get("remote")
            pno = payload.get("packet_no")
            aid = payload.get("attach_id")
            b = payload.get("bytes")
            self._refresh_print((t['file_progress_cli'] if t is not None else '[FILE PROGRESS] ') + f"{remote} {pno}:{aid} - {b} bytes")
        except Exception:
            pass

    def _on_file_complete(self, payload: Any) -> None:
        try:
            if payload.get("error"):
                self._refresh_print((t['file_complete_error'] if t is not None else '[FILE COMPLETE] error: ') + str(payload.get('error')))
            else:
                self._refresh_print((t['file_complete_saved'] if t is not None else '[FILE COMPLETE] saved ') + f"{payload.get('path')} ({payload.get('bytes')} bytes)")
        except Exception:
            pass

    def _on_net_rebind(self, payload: Any) -> None:
        try:
            bind_ip = payload.get('bind_ip') if isinstance(payload, dict) else str(payload)
            try:
                self._refresh_print((t['net_rebind'] if t is not None else '[NET] rebind -> ') + str(bind_ip))
            except Exception:
                pass
        except Exception:
            pass

    # Command implementations
    def cmd_discover(self) -> None:
        # send a simple broadcast packet compatible with IPMSG BR_ENTRY (basic)
        text = b"1:0:cli:host:1:"  # minimal packet
        try:
            self.net.broadcast(2425, text)
            print(t['discover_sent'])
        except Exception as e:
            print(t['discover_failed'] + str(e))

    def cmd_send(self, target: str, text: str) -> None:
        try:
            self.core.send_message(target, text)
        except Exception as e:
            print(t['send_error'] + str(e))

    def cmd_group_add(self, group: str, username: str) -> None:
        self.groups.setdefault(group, [])
        if username not in self.groups[group]:
            self.groups[group].append(username)
        print(t['group_members'] + f"{group} members: {self.groups[group]}")

    def cmd_group_send(self, group: str, text: str) -> None:
        members = self.groups.get(group, [])
        if not members:
            print(t['group_no_members'] + str(group))
            return
        for m in members:
            if m == self.core._username:
                continue
            self.cmd_send(m, text)

    def cmd_file_send(self, target: str, path: str) -> None:
        if not os.path.exists(path):
            print(t['file_path_not_found'])
            return
        # register file mapping: use packet_no=1 attach_id incremental per file for demo
        pno = int(1)
        aid = int(len(self._file_offers) + 1)
        try:
            self.core.register_file(pno, aid, path)
        except Exception as e:
            print(t['file_register_failed'] + str(e))
            return
        # build a FILEATTACH-like message body; real clients expect specific format
        meta = f"{aid}:{os.path.basename(path)}:{os.path.getsize(path)}:0:0"
        # send message with extension carrying fileattach
        # For simplicity send as plain text to target
        self.core.send_message(target, f"FILE_OFFER;{meta}")
        print(t['file_offer_sent'] + f"{target} (offer id local={aid})")

    def cmd_file_list(self) -> None:
        try:
            print(_t_global['file_pending_offers'])
        except Exception:
            print(t['file_pending_offers'])
        for oid, meta in self._file_offers.items():
            print(str(oid) + ' ' + str(meta))

    def cmd_file_accept(self, oid: int, remote_ip: Optional[str] = None, save_to: Optional[str] = None) -> None:
        offer = self._file_offers.get(int(oid))
        if not offer:
            try:
                print(_t_global['file_unknown_offer'])
            except Exception:
                print(t['file_unknown_offer'])
            return
        # For simplicity require remote_ip and packet:attach info in offer payload or ask user
        # Offer payload may not contain packet_no/attach_id; we'll prompt if missing
        try:
            print(_t_global['file_accepting_offer'] + str(oid))
        except Exception:
            print(t['file_accepting_offer'] + str(oid))
        # Determine remote and request format
        if remote_ip is None:
            try:
                print(_t_global['file_missing_remote_ip'])
            except Exception:
                print(t['file_missing_remote_ip'])
            return
        # require request string like 'packet:attach'
        if "packet_no" in offer and "attach_id" in offer:
            pno = int(offer["packet_no"])
            aid = int(offer["attach_id"])
        else:
            # for demo, ask user to input request on CLI level; here we default to 1:1
            pno = 1
            aid = list(self._file_offers.keys())[0]
        # determine destination: explicit save_to > adapter download_dir > cwd
        if save_to:
            dest = save_to
        else:
            import os
            filename = offer.get("filename", f"download_{oid}")
            dest = os.path.join(self.download_dir or os.getcwd(), filename)
        try:
            # use core-level download helper (async). Adapter listens for progress/complete events.
            self.core.download_file(remote_ip, pno, aid, dest)
            print(t['file_download_started'] + str(dest))
        except Exception as e:
            print(t['file_download_failed'] + str(e))

    def cmd_file_cancel(self, oid: int) -> None:
        # no-op for received offers; if we created registered mapping, unregister it
        print(t['file_cancel'] + str(oid))
        # attempt to remove mapping if present
        try:
            # mapping was registered with pno=1 aid=oid in cmd_file_send above
            self.core.unregister_file(1, oid)
            print(t['file_mapping_unregistered'])
        except Exception:
            pass

    def cmd_set_download_dir(self, path: str) -> None:
        if not os.path.exists(path):
            try:
                ensure_dir(path)
            except Exception as e:
                print(t['set_create_dir_failed'] + str(e))
                return
        # persist in core via persistence API
        try:
            self.core.set_config('download_dir', os.path.abspath(path))
            print(t['set_download_dir'] + str(os.path.abspath(path)))
        except Exception as e:
            print(t['set_persist_failed'] + str(e))

    def cmd_set_status(self, token: str) -> None:
        # publish a BR_ENTRY-like effect via sending a message or using network directly
        print(t['set_status'] + str(token))
        # broadcast a simple packet indicating status (demo)
        pkt = f"1:0:{self.core._username}:host:1:status={token}".encode("utf-8")
        self.net.broadcast(2425, pkt)

    def cmd_set_keepalive(self, seconds: int) -> None:
        try:
            self.core.set_keepalive(int(seconds))
            print(t['set_keepalive'] + str(seconds) + 's')
        except Exception as e:
            print(t['set_keepalive_failed'] + str(e))

    def cmd_set_expire(self, seconds: int) -> None:
        try:
            self.core.set_expire(int(seconds))
            print(t['set_expire'] + str(seconds) + 's')
        except Exception as e:
            print(t['set_expire_failed'] + str(e))

    def cmd_set_bind(self, bind_ip: str) -> None:
        # restart network service bound to bind_ip
        try:
            self.net.stop()
        except Exception:
            pass
        # persist the bind selection and mark as user-locked so auto-rebind won't override
        try:
            self.core.set_config('bind', bind_ip)
            self.core.set_config('bind_locked', True)
        except Exception:
            pass
        self.net = NetworkService(self.bus, bind_ip=bind_ip, port=self.net.port)
        self.core.attach_network(self.net)
        try:
            bind_label = t['bind_ip'] if t is not None else 'bind'
        except Exception:
            bind_label = 'bind'
        print(t['set_bind'] + str(bind_label) + ' -> ' + str(bind_ip))

    def cmd_unset_bind(self) -> None:
        """Remove user bind and allow auto-rebind again."""
        try:
            # clear persisted bind and unlock
            self.core.set_config('bind', None)
            self.core.set_config('bind_locked', False)
        except Exception:
            pass
        # restart network with default any-bind
        try:
            self.net.stop()
        except Exception:
            pass
        self.net = NetworkService(self.bus, bind_ip='0.0.0.0', port=self.net.port)
        self.core.attach_network(self.net)
        try:
            bind_label = t['bind_ip'] if t is not None else 'bind'
        except Exception:
            bind_label = 'bind'
        print(t['set_bind_unlocked'] + str(bind_label))

    def cmd_logout(self) -> None:
        # send BR_EXIT broadcast and stop services
        pkt = b"1:0:cli:host:2:"
        try:
            self.net.broadcast(2425, pkt)
        except Exception:
            pass
        try:
            self.fs.stop()
        except Exception:
            pass
        try:
            self.net.stop()
        except Exception:
            pass
        self._running = False
        print(t['logout_done'])

    # helper: simple GETFILEDATA implementation
    def _download_file(self, remote_ip: str, packet_no: int, attach_id: int, dest_path: str) -> None:
        # legacy; downloads are now handled by core.download_file
        raise RuntimeError("use core.download_file instead")

    # REPL
    def repl(self):
        self._running = True
        print(t['cli_running_as'] + str(self.core._username))
        while self._running:
            try:
                line = input(f"{self.core._username} => ")
            except EOFError:
                break
            if not line:
                continue
            parts = line.strip().split()
            cmd = parts[0]
            args = parts[1:]
            try:
                if cmd in ("discover",):
                    self.cmd_discover()
                elif cmd == "send":
                    if len(args) < 2:
                        print(t['usage_send'])
                    else:
                        self.cmd_send(args[0], " ".join(args[1:]))
                elif cmd == "group":
                    if len(args) >= 3 and args[1] == "-add":
                        self.cmd_group_add(args[0], args[2])
                    elif len(args) >= 3 and args[1] == "-send":
                        self.cmd_group_send(args[0], " ".join(args[2:]))
                    else:
                        print(t['usage_group'])
                elif cmd == "file":
                    if len(args) >= 2 and args[0] in ("send",):
                        # file send user|ip <path>
                        self.cmd_file_send(args[1], args[2] if len(args) > 2 else "")
                    elif len(args) >= 1 and args[0] == "list":
                        self.cmd_file_list()
                    elif len(args) >= 2 and args[0] == "accept":
                        self.cmd_file_accept(int(args[1]), remote_ip=(args[2] if len(args) > 2 else None), save_to=(args[3] if len(args) > 3 else None))
                    elif len(args) >= 2 and args[0] == "cancel":
                        self.cmd_file_cancel(int(args[1]))
                    else:
                        print(t['usage_file'])
                elif cmd == "set":
                    if len(args) >= 2 and args[0] == "download_dir":
                        self.cmd_set_download_dir(args[1])
                    elif len(args) >= 2 and args[0] == "status":
                        self.cmd_set_status(args[1])
                    elif len(args) >= 2 and args[0] == "bind":
                        # support: set bind <ip> OR set bind unlock|none
                        if args[1] in ("unlock", "none"):
                            self.cmd_unset_bind()
                        else:
                            self.cmd_set_bind(args[1])
                    elif len(args) >= 2 and args[0] == "language":
                        # set language <lang>
                        self.cmd_set_language(args[1])
                    elif len(args) >= 2 and args[0] == "keepalive":
                        self.cmd_set_keepalive(int(args[1]))
                    elif len(args) >= 2 and args[0] == "expire":
                        self.cmd_set_expire(int(args[1]))
                    else:
                        print(t['usage_set'])
                elif cmd in ("logout", "exit"):
                    self.cmd_logout()
                elif cmd == "info":
                    if len(args) >= 1 and args[0].startswith("net"):
                        try:
                            info = self.net.get_bind_info()
                            print(t['info_net'])
                            for k, v in info.items():
                                print(t['info_net_item'] + str(k) + ': ' + str(v))
                        except Exception:
                            print(t['info_net_fallback'] + str(self.net.bind_ip) + ' port=' + str(self.net.port))
                    else:
                        hist = self.core.get_history(10)
                        print(t['history_last_10'])
                        for m in hist:
                            print(str(m))
                elif cmd == "search":
                    # search user:<name>|ip:<addr>|group:<name>
                    if not args:
                        print(t['usage_search'])
                    else:
                        q = args[0]
                        if q.startswith("user:"):
                            name = q.split(":", 1)[1]
                            # best-effort search in history/online list
                            results = []
                            for row in self.core.history.get_messages(200):
                                if name in str(row.get('from_user', '')):
                                    results.append(row)
                            print(t['search_user_results'] + str(name) + '] ' + str(len(results)) + ' results')
                            for r in results[:20]:
                                print(str(r))
                        elif q.startswith("ip:"):
                            ip = q.split(":", 1)[1]
                            # check online event registry not stored; best-effort: check history source
                            results = []
                            for row in self.core.history.get_messages(200):
                                if ip in str(row.get('from_user', '')) or ip in str(row.get('to', '')):
                                    results.append(row)
                            print(t['search_ip_results'] + str(ip) + '] ' + str(len(results)) + ' results')
                            for r in results[:20]:
                                print(str(r))
                        else:
                            print(t['search_type_not_supported'])
                elif cmd == "search":
                    print(t['search_not_implemented'])
                elif cmd == "help":
                    self.cmd_help()
                elif cmd == "clear":
                    # simple clear: print newline
                    print("\n" * 2)
                else:
                    print(t['unknown_command'] + str(cmd))
            except Exception as e:
                print(t['command_error'] + str(e))


if __name__ == "__main__":
    a = CLIAdapter(username="cli_demo")
    # run a short automated demo in a background thread then drop to repl
    def demo_actions():
        import time
        time.sleep(0.5)
        a.cmd_discover()
        time.sleep(0.5)
        a.cmd_send("all", "hello from adapter demo")

    demo_thread = threading.Thread(target=demo_actions, daemon=True)
    demo_thread.start()
    a.repl()
