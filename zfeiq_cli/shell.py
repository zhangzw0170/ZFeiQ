# NZFeiQ/zfeiq_cli/shell.py
# -*- coding: utf-8 -*-
import sys
import os
import time
from typing import Optional

# 尝试引入 prompt_toolkit，并为 Pylance 提供类型占位符
try:
    from prompt_toolkit import PromptSession, print_formatted_text
    from prompt_toolkit.patch_stdout import patch_stdout
    from prompt_toolkit.formatted_text import HTML
    from prompt_toolkit.styles import Style
    _HAS_PT = True
except ImportError:
    _HAS_PT = False
    # 为静态分析定义占位符，防止 "PossiblyUnboundVariable"
    PromptSession = None
    print_formatted_text = None
    patch_stdout = None
    HTML = None
    Style = None

# 引入核心层
from zfeiq_core.engine import ZFeiQCore
from zfeiq_core.events import *

class ZFeiQShell:
    def __init__(self, port: int, bind_ip: Optional[str]):
        self.core = ZFeiQCore(port=port, bind_ip=bind_ip)
        # 订阅 Core 的事件
        self.core.set_event_handler(self.on_core_event)
        
        # 交互会话状态
        self.session = PromptSession() if _HAS_PT and PromptSession else None
        
        # 样式定义 (HTML 风格)
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
        """启动 CLI"""
        try:
            self.core.start()
            print("ZFeiQ Refactored CLI (Core + Shell)")
            print("Type /help for commands.")
            
            if _HAS_PT and self.session:
                self._loop_pt()
            else:
                self._loop_basic()
        except KeyboardInterrupt:
            pass
        finally:
            print("\nShutting down...")
            self.core.stop()

    # --- 事件处理 (Output) ---

    def on_core_event(self, ev: Event):
        """处理来自 Core 的事件，格式化并打印"""
        
        # 辅助打印函数 (兼容 prompt_toolkit 的防冲刷)
        def _print(content):
            if _HAS_PT and print_formatted_text:
                print_formatted_text(content, style=self.style)
            else:
                # 降级模式：直接 print (可能会冲走输入)
                # 简单去除 HTML 标签
                text = str(content)
                # 如果是 prompt_toolkit 的 HTML 对象，取其 value
                if hasattr(content, "value"): 
                    text = content.value 
                
                # 极简去标签 (仅用于 fallback)
                import re
                clean = re.sub(r'<[^>]+>', '', text)
                print(clean)

        ts = time.strftime("%H:%M:%S", time.localtime(ev.timestamp))
        
        if ev.type == EV_MSG_RECV:
            sender = ev.data['sender']
            ip = ev.data['ip']
            text = ev.data['text']
            if _HAS_PT and HTML:
                _print(HTML(f"[{ts}] <peer>{sender}@{ip}</peer>: {text}"))
            else:
                print(f"[{ts}] <{sender}@{ip}>: {text}")

        elif ev.type == EV_MSG_SENT:
            target = ev.data['target']
            text = ev.data['text']
            enc_mark = "[ENC]" if ev.data.get('encrypted') else ""
            if _HAS_PT and HTML:
                _print(HTML(f"[{ts}] <user>Me</user> -> {target} {enc_mark}: {text}"))
            else:
                print(f"[{ts}] Me -> {target} {enc_mark}: {text}")

        elif ev.type == EV_LOG_INFO:
            msg = ev.data['msg']
            if _HAS_PT and HTML:
                _print(HTML(f"<info>[INFO] {msg}</info>"))
            else:
                print(f"[INFO] {msg}")

        elif ev.type == EV_LOG_ERR:
            msg = ev.data['msg']
            if _HAS_PT and HTML:
                _print(HTML(f"<error>[ERR] {msg}</error>"))
            else:
                print(f"[ERR] {msg}")

        elif ev.type == EV_FILE_OFFER:
            sender = ev.data['sender']
            fname = ev.data['filename']
            size = ev.data['size']
            oid = ev.data['offer_id']
            msg = f"File Offer from {sender}: {fname} ({size} bytes). ID: {oid}"
            msg += "\nUse '/file accept <ID>' to receive."
            if _HAS_PT and HTML:
                _print(HTML(f"<peer>{msg}</peer>"))
            else:
                print(msg)

        elif ev.type == EV_FILE_PROG:
            # 简化：仅打印进度条，防止刷屏。实际可优化为单行刷新
            # 这里简单处理：每 20% 打印一次
            curr = ev.data['current']
            total = ev.data['total']
            pct = int(curr * 100 / total) if total > 0 else 0
            # 简单限流
            if pct % 20 == 0 and curr > 0: 
                 pass 

        elif ev.type == EV_FILE_DONE:
            path = ev.data['path']
            if _HAS_PT and HTML:
                _print(HTML(f"<info>File saved: {path}</info>"))
            else:
                print(f"File saved: {path}")

        elif ev.type == EV_ENC_STATE:
            peer = ev.data['peer']
            state = ev.data['state']
            if _HAS_PT and HTML:
                _print(HTML(f"<debug>[ENC] Session {peer} -> {state}</debug>"))

    # --- 交互循环 (Input) ---

    def _get_prompt(self):
        if not (_HAS_PT and HTML): return "> "
        
        user = self.core.username or "ZFeiQ"
        status_color = "user"
        if self.core.status == "busy": status_color = "error"
        elif self.core.status == "away": status_color = "debug"
        
        return HTML(f"<{status_color}>{user}</{status_color}> => ")

    def _loop_pt(self):
        """Prompt Toolkit 循环 (推荐)"""
        # Pylance 检查：确保 patch_stdout 和 self.session 不为 None
        if not (patch_stdout and self.session):
            return self._loop_basic()

        with patch_stdout():
            while True:
                try:
                    text = self.session.prompt(self._get_prompt(), style=self.style)
                    self._handle_command(text.strip())
                except (EOFError, KeyboardInterrupt):
                    break

    def _loop_basic(self):
        """Fallback 循环"""
        while True:
            try:
                text = input(f"{self.core.username or 'ZFeiQ'}> ")
                self._handle_command(text.strip())
            except (EOFError, KeyboardInterrupt):
                break

    # --- 命令解析 ---

    def _handle_command(self, text: str):
        if not text: return
        parts = text.split()
        cmd = parts[0].lower()

        if cmd == "/login":
            if len(parts) > 1:
                self.core.login(parts[1])
            else:
                print("Usage: /login <username>")
        
        elif cmd == "/logout":
            self.core.logout()

        elif cmd == "/send":
            # /send ip msg...
            if len(parts) < 3:
                print("Usage: /send <ip> <message>")
                return
            target_ip = parts[1]
            msg = " ".join(parts[2:])
            self.core.send_text(target_ip, msg)

        elif cmd == "/discover":
            target = parts[1] if len(parts) > 1 else None
            self.core.discover(target)

        elif cmd == "/file":
            # /file send ip path
            # /file accept id
            if len(parts) < 3:
                print("Usage: /file send <ip> <path> | /file accept <offer_id>")
                return
            sub = parts[1]
            if sub == "send":
                # /file send ip path... (path may have spaces)
                if len(parts) < 4:
                    print("Usage: /file send <ip> <path>")
                    return
                ip = parts[2]
                path = " ".join(parts[3:]).strip('"')
                self.core.send_file(ip, path)
            elif sub == "accept":
                oid = parts[2]
                self.core.accept_file(oid, os.getcwd()) # 默认存当前目录
            else:
                print("Unknown file command")

        elif cmd == "/set":
            # /set encrypt off|on|strict
            # /set status online|busy
            if len(parts) < 3:
                print("Usage: /set <encrypt|status> <val>")
                return
            key = parts[1]
            val = parts[2]
            if key == "encrypt":
                self.core.encrypt_mode = val
                print(f"Encryption set to {val}")
            elif key == "status":
                self.core.status = val
                # 广播状态变更
                if self.core.username:
                    self.core._broadcast_presence() # 调用 core 内部方法重新广播
                print(f"Status set to {val}")

        elif cmd == "/list":
            # 简单打印一下在线列表
            print("--- Online Nodes ---")
            for n in self.core.registry.list_nodes():
                print(f"{n.username}@{n.ip} ({n.hostname}) [{n.status}]")
        
        elif cmd == "/help":
            print("Commands: /login, /logout, /send, /file, /discover, /set, /list")

        elif cmd == "/exit":
            raise KeyboardInterrupt

        else:
            print("Unknown command. Try /help")
