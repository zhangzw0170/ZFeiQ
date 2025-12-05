# NZFeiQ/cli/shell.py
# -*- coding: utf-8 -*-
import sys
import os
import time
from typing import Optional

try:
    from prompt_toolkit import PromptSession, print_formatted_text
    from prompt_toolkit.patch_stdout import patch_stdout
    from prompt_toolkit.formatted_text import HTML
    from prompt_toolkit.styles import Style
    _HAS_PT = True
except ImportError:
    _HAS_PT = False
    PromptSession = None
    print_formatted_text = None
    patch_stdout = None
    HTML = None
    Style = None

from core.engine import ZFeiQCore
from core.events import *

class ZFeiQShell:
    def __init__(self, port: int, bind_ip: Optional[str]):
        self.core = ZFeiQCore(port=port, bind_ip=bind_ip)
        self.core.set_event_handler(self.on_core_event)
        self.session = PromptSession() if _HAS_PT and PromptSession else None
        
        self.style = None
        if _HAS_PT and Style:
            self.style = Style.from_dict({
                'user': 'ansigreen bold',
                'peer': 'ansicyan',
                'debug': 'ansiyellow',
                'error': 'ansired bold',
                'info': 'gray',
            })

    def run(self):
        try:
            self.core.start()
            
            # Banner
            try:
                from core import __version__, __last_update__
                banner = f"ZFeiQ CLI - {__version__} ({__last_update__})"
            except ImportError:
                banner = "ZFeiQ CLI - Dev Build"

            if _HAS_PT and print_formatted_text and HTML:
                print_formatted_text(HTML(f"<ansigreen><bold>{banner}</bold></ansigreen>"))
            else:
                print(f"\033[1;32m{banner}\033[0m")

            print("Type 'help' for commands.")
            
            if _HAS_PT: self._loop_pt()
            else: self._loop_basic()
        except KeyboardInterrupt:
            pass
        finally:
            print("\nStopping...")
            self.core.stop()

    def on_core_event(self, ev: Event):
        def _print(c):
            if _HAS_PT and print_formatted_text: print_formatted_text(c, style=self.style)
            else: 
                t = c.value if hasattr(c, "value") else str(c)
                print(t.replace("<","[").replace(">","]"))

        ts = time.strftime("%H:%M:%S", time.localtime(ev.timestamp))
        
        if ev.type == EV_MSG_RECV:
            s, i, t = ev.data['sender'], ev.data['ip'], ev.data['text']
            if _HAS_PT and HTML: _print(HTML(f"[{ts}] <peer>{s}@{i}</peer>: {t}"))
            else: print(f"[{ts}] <{s}@{i}>: {t}")
            
        elif ev.type == EV_MSG_SENT:
            t, txt = ev.data['target'], ev.data['text']
            enc = "[ENC]" if ev.data.get('encrypted') else ""
            if _HAS_PT and HTML: _print(HTML(f"[{ts}] <user>Me</user> -> {t} {enc}: {txt}"))
            else: print(f"[{ts}] Me -> {t} {enc}: {txt}")
            
        elif ev.type == EV_LOG_INFO:
            if _HAS_PT and HTML: _print(HTML(f"<info>[INFO] {ev.data['msg']}</info>"))
            else: print(f"[INFO] {ev.data['msg']}")
            
        elif ev.type == EV_LOG_ERR:
            if _HAS_PT and HTML: _print(HTML(f"<error>[ERR] {ev.data['msg']}</error>"))
            else: print(f"[ERR] {ev.data['msg']}")

        elif ev.type == EV_FILE_OFFER:
            sender = ev.data['sender']
            fname = ev.data['filename']
            size = ev.data['size']
            oid = ev.data['offer_id']
            msg = f"File Offer from {sender}: {fname} ({size} bytes). ID: {oid}"
            msg += "\nUse 'file accept <ID>' to receive."
            if _HAS_PT and HTML: _print(HTML(f"<peer>{msg}</peer>"))
            else: print(msg)

        elif ev.type == EV_FILE_PROG:
            curr = ev.data['current']
            total = ev.data['total']
            pct = int(curr * 100 / total) if total > 0 else 0
            if pct % 20 == 0 and curr > 0: 
                 if _HAS_PT and HTML: _print(HTML(f"<info>Downloading... {pct}%</info>"))
                 else: print(f"Downloading... {pct}%")

        elif ev.type == EV_FILE_DONE:
            path = ev.data['path']
            if _HAS_PT and HTML: _print(HTML(f"<info>File saved: {path}</info>"))
            else: print(f"File saved: {path}")

        elif ev.type == EV_ENC_STATE:
            p, s = ev.data['peer'], ev.data['state']
            if _HAS_PT and HTML: _print(HTML(f"<debug>[ENC] {p} -> {s}</debug>"))

        # [新增] 处理节点更新事件，输出日志供测试脚本捕获 (Step 1 修复)
        elif ev.type == EV_NODE_UPD:
            count = len(self.core.registry.list_nodes())
            msg = f"Node list updated: {count} peers online."
            if _HAS_PT and HTML: _print(HTML(f"<info>[INFO] {msg}</info>"))
            else: print(f"[INFO] {msg}")

    def _get_prompt(self):
        if not (_HAS_PT and HTML): return "> "
        u = self.core.username or "ZFeiQ"
        c = "user"
        if self.core.status == "busy": c = "error"
        elif self.core.status == "away": c = "debug"
        return HTML(f"<{c}>{u}</{c}> => ")

    def _loop_pt(self):
        if not (patch_stdout and self.session): return self._loop_basic()
        with patch_stdout():
            while True:
                try:
                    t = self.session.prompt(self._get_prompt(), style=self.style)
                    self._handle(t.strip())
                except (EOFError, KeyboardInterrupt): break

    def _loop_basic(self):
        while True:
            try:
                t = input(f"{self.core.username or 'ZFeiQ'}> ")
                self._handle(t.strip())
            except (EOFError, KeyboardInterrupt): break

    def _handle(self, text: str):
        if not text: return
        
        # 移除前缀并分割
        clean_text = text.lstrip('/')
        parts = clean_text.split()
        cmd = parts[0].lower()
        
        if cmd == "login":
            if len(parts) > 1: self.core.login(parts[1])
            else: print("Usage: login <name>")
        
        elif cmd == "logout": self.core.logout()
        
        elif cmd == "send":
            if len(parts) < 3: print("Usage: send <ip> <msg>")
            else: self.core.send_text(parts[1], " ".join(parts[2:]))
            
        elif cmd == "discover":
            self.core.discover(parts[1] if len(parts) > 1 else None)
            
        elif cmd == "list":
            print("--- Online ---")
            for n in self.core.registry.list_nodes():
                print(f"{n.username}@{n.ip} ({n.hostname}) [{n.status}]")
                
        elif cmd == "set":
            if len(parts) < 3: print("Usage: set <encrypt|status> <val>")
            else:
                k, v = parts[1], parts[2]
                if k == "encrypt": 
                    self.core.encrypt_mode = v
                    print(f"Encrypt: {v}")
                elif k == "status":
                    self.core.status = v
                    if self.core.username: self.core._broadcast_presence()
                    print(f"Status: {v}")

        # [新增] debug 命令
        elif cmd == "debug":
            if len(parts) < 3:
                print("Usage: debug cipher <on|off>")
            else:
                key, val = parts[1].lower(), parts[2].lower()
                if key == "cipher":
                    self.core.show_cipher = (val in ("on", "true", "1"))
                    print(f"Show Ciphertext: {self.core.show_cipher}")
                else:
                    print(f"Unknown debug key: {key}")

        # [新增] log 命令
        elif cmd == "log":
            if len(parts) < 3:
                print("Usage: log level <debug|info|warn|error>")
            else:
                key, val = parts[1].lower(), parts[2].upper()
                if key == "level":
                    if val in ("DEBUG", "INFO", "WARN", "ERROR"):
                        self.core.log_level = val
                        print(f"Log Level set to: {val}")
                    else:
                        print("Invalid level. Use DEBUG, INFO, WARN, ERROR")

        elif cmd == "ocr":
            if len(parts) < 2:
                print("Usage: ocr <path> [--send <ip>]")
                return
            path = parts[1].strip('"').strip("'")
            target = None
            if len(parts) >= 4 and parts[2] == "--send": target = parts[3]
            self.core.run_ocr(path, target)
            
        elif cmd == "file":
            if len(parts) < 3:
                print("Usage: file send <ip> <path> | file accept <id>")
                return
            sub = parts[1]
            if sub == "send":
                if len(parts) < 4: 
                    print("Usage: file send <ip> <path>")
                    return
                path = " ".join(parts[3:]).strip('"')
                self.core.send_file(parts[2], path)
            elif sub == "accept":
                self.core.accept_file(parts[2])

        # 分组命令
        # [新增] 分组命令逻辑优化
        elif cmd == "group":
            # group list
            # group create <name>
            # group add <name> <user>
            # group msg <name> <text>
            
            # [修改] 允许 group list (长度为2)
            if len(parts) < 2:
                print("Usage: group <list|create|add|msg> <args...>")
                return
            
            sub = parts[1].lower()
            
            if sub == "list":
                print("--- Groups ---")
                if not self.core.groups:
                    print("(no groups)")
                for name, members in self.core.groups.items():
                    print(f"{name}: {', '.join(members)}")
                return

            if sub == "create":
                self.core.create_group(parts[2])
            elif sub == "add":
                if len(parts) < 4: print("Usage: group add <name> <user>"); return
                self.core.add_to_group(parts[2], parts[3])
            elif sub == "msg":
                if len(parts) < 4: print("Usage: group msg <name> <text>"); return
                self.core.send_group_msg(parts[2], " ".join(parts[3:]))
            elif sub == "list":
                print("--- Groups ---")
                for name, members in self.core.groups.items():
                    print(f"{name}: {', '.join(members)}")

        # [新增] 搜索命令
        elif cmd == "search":
            if len(parts) < 2:
                print("Usage: search <query>")
                return
            res = self.core.search_nodes(parts[1])
            print("--- Search Result ---")
            for item in res:
                if item['type'] == 'user':
                    print(f"[User] {item['name']}@{item['ip']}")
                else:
                    print(f"[Group] {item['name']} ({item['count']} members)")

        # [新增] 截图命令
        elif cmd == "screenshot":
            path = self.core.capture_screen()
            if path:
                print(f"Screenshot saved: {path}")
                if len(parts) >= 3 and parts[1] == "send":
                    target = parts[2]
                    self.core.send_file(target, path)
            else:
                print("Screenshot failed.")
                
        elif cmd == "clear":
            os.system('cls' if os.name == 'nt' else 'clear')
            
        elif cmd == "exit": 
            raise KeyboardInterrupt
            
        elif cmd == "help": 
            print("Commands: login, logout, send, discover, list, set, debug, log, ocr, file, group, search, screenshot, clear, exit")
            
        else: 
            print(f"Unknown command '{cmd}'. Type 'help' for list.")
