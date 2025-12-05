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
            print("ZFeiQ CLI (New Core)")
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
            msg += "\nUse '/file accept <ID>' to receive."
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
        p = text.split()
        cmd = p[0].lower()
        
        if cmd == "/login":
            if len(p)>1: self.core.login(p[1])
            else: print("Usage: /login <name>")
        elif cmd == "/logout": self.core.logout()
        elif cmd == "/send":
            if len(p)<3: print("Usage: /send <ip> <msg>")
            else: self.core.send_text(p[1], " ".join(p[2:]))
        elif cmd == "/discover":
            self.core.discover(p[1] if len(p)>1 else None)
        elif cmd == "/list":
            print("--- Online ---")
            for n in self.core.registry.list_nodes():
                print(f"{n.username}@{n.ip} ({n.hostname}) [{n.status}]")
        elif cmd == "/set":
            if len(p)<3: print("Usage: /set <encrypt|status> <val>")
            else:
                k, v = p[1], p[2]
                if k=="encrypt": 
                    self.core.encrypt_mode = v
                    print(f"Encrypt: {v}")
                elif k=="status":
                    self.core.status = v
                    if self.core.username: self.core._broadcast_presence()
                    print(f"Status: {v}")
        elif cmd == "/ocr":
            if len(p)<2:
                print("Usage: /ocr <path> [--send <ip>]")
                return
            path = p[1].strip('"').strip("'")
            target = None
            if len(p)>=4 and p[2]=="--send": target = p[3]
            self.core.run_ocr(path, target)
        elif cmd == "/file":
            if len(p)<3:
                print("Usage: /file send <ip> <path> | /file accept <id>")
                return
            sub = p[1]
            if sub == "send":
                if len(p)<4: 
                    print("Usage: /file send <ip> <path>")
                    return
                # Handle paths with spaces
                path = " ".join(p[3:]).strip('"')
                self.core.send_file(p[2], path)
            elif sub == "accept":
                self.core.accept_file(p[2])
        elif cmd == "/exit": raise KeyboardInterrupt
        elif cmd == "/help": print("/login, /logout, /send, /discover, /list, /set, /ocr, /file, /exit")
        else: print("Unknown command")
