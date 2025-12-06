# NZFeiQ/cli/shell.py
# -*- coding: utf-8 -*-
import sys
import os
import time
import ipaddress
from typing import Optional
import html

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

        elif ev.type == EV_OCR_DONE:
            txt = ev.data['text']
            path = ev.data['image_path']
            header = "========== OCR Result =========="
            # Header: bright green (same as username color)
            if _HAS_PT and HTML:
                try:
                    _print(HTML(f"<user>{header}</user>"))
                    # Escape the body to avoid HTML parse issues, but keep original formatting
                    safe = html.escape(txt)
                    # Print body as plain info block
                    _print(HTML(f"<info>{safe}</info>"))
                except Exception:
                    print(header)
                    print(txt)
            else:
                # ANSI bright green for header
                print(f"\033[1;32m{header}\033[0m")
                print(txt)

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
            if len(parts) < 3:
                print("Usage: send <ip|all|user:<name>|group:<name>> <msg>")
            else:
                target = parts[1]
                msg = " ".join(parts[2:])

                # broadcast
                if target == 'all':
                    self.core.send_text('all', msg)

                # send by username (may map to multiple IPs)
                elif target.lower().startswith('user:'):
                    name = target.split(':', 1)[1]
                    nodes = self.core.registry.find_by_username(name)
                    if not nodes:
                        print(f"No online node for user: {name}")
                    else:
                        sent = 0
                        for n in nodes:
                            self.core.send_text(n.ip, msg)
                            sent += 1
                        print(f"Sent to {sent} node(s) for user: {name}")

                # send to group (use group send helper)
                elif target.lower().startswith('group:'):
                    g = target.split(':', 1)[1]
                    if g not in self.core.groups:
                        print(f"Group not found: {g}")
                    else:
                        self.core.send_group_msg(g, msg)
                        print(f"Group message queued to group: {g}")

                # If target looks like an IP address, send directly
                else:
                    def _looks_like_ip(s: str) -> bool:
                        try:
                            ipaddress.ip_address(s)
                            return True
                        except Exception:
                            return False

                    # If user supplied a bare username (no colon and no dot), try to resolve
                    if (':' not in target) and (not _looks_like_ip(target)) and ('.' not in target):
                        nodes = self.core.registry.find_by_username(target)
                        if not nodes:
                            print(f"No online node for user: {target}")
                        else:
                            sent = 0
                            for n in nodes:
                                self.core.send_text(n.ip, msg)
                                sent += 1
                            print(f"Sent to {sent} node(s) for user: {target}")
                    else:
                        # treat as IP/hostname and send
                        self.core.send_text(target, msg)
            
        elif cmd == "discover":
            self.core.discover(parts[1] if len(parts) > 1 else None)

        elif cmd == "info":
            # info
            # info                => show local info + online list
            # info net            => network / bind details
            # info user:<name>    => show recent history with user
            # info group:<name>   => show group members + recent history
            if len(parts) == 1:
                print(f"Local: {self.core.username or '?(not logged in)'}@{self.core.local_ip} ({self.core.hostname})")
                print(f"Bound: {getattr(self.core.transport, 'bind_ip', 'N/A')}  Port: {getattr(self.core.transport, 'port', 'N/A')}")
                print("--- Online ---")
                for n in self.core.registry.list_nodes():
                    print(f"{n.username}@{n.ip} ({n.hostname}) [{n.status}]")
            else:
                sub = parts[1]
                if sub == "net":
                    bcast = getattr(self.core.transport, '_broadcast_addr', 'unknown')
                    print("Network:")
                    print(f"  Local IP: {self.core.local_ip}")
                    print(f"  Bind IP: {getattr(self.core.transport, 'bind_ip', 'N/A')}")
                    print(f"  Iface IP: {getattr(self.core.transport, 'iface_ip', 'N/A')}")
                    print(f"  Broadcast: {bcast}")
                    print(f"  UDP Port: {getattr(self.core.transport, 'port', 'N/A')}")
                elif sub.startswith("user:"):
                    name = sub.split(":", 1)[1]
                    nodes = self.core.registry.find_by_username(name)
                    if not nodes:
                        print(f"No online node for user: {name}")
                    for node in nodes:
                        msgs = self.core.history.get(node.ip)
                        print(f"History with {name}@{node.ip} (last {min(10, len(msgs))}):")
                        for ts, direction, text in msgs[-10:]:
                            t = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))
                            print(f"  [{t}] {direction} {text}")
                elif sub.startswith("group:"):
                    g = sub.split(":", 1)[1]
                    members = self.core.groups.get(g)
                    if not members:
                        print(f"Group not found: {g}")
                    else:
                        print(f"Group {g}: {len(members)} members")
                        for m in members:
                            print(f"  - {m}")
                        print("--- Recent per-member history (last 5 each) ---")
                        for m in members:
                            # find nodes for username
                            nds = self.core.registry.find_by_username(m)
                            for nd in nds:
                                msgs = self.core.history.get(nd.ip)
                                if msgs:
                                    print(f"{m}@{nd.ip}:")
                                    for ts, direction, text in msgs[-5:]:
                                        t = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))
                                        print(f"  [{t}] {direction} {text}")
                else:
                    print("Usage: info | info net | info user:<name> | info group:<name>")
            
        elif cmd == "list":
            print("--- Known Nodes ---")
            # Build map of current registry nodes
            reg_map = {n.ip: n for n in self.core.registry.list_nodes()}
            printed = set()

            # First print nodes currently in registry (online/busy/away)
            for ip, n in reg_map.items():
                print(f"{n.username}@{n.ip} ({n.hostname}) [{n.status}]")
                printed.add(ip)

            # Also include any IPs we have history for but which are not in registry (treat as offline)
            hist_ips = []
            try:
                # ChatHistory stores messages in _data: ip -> list
                hist_data = getattr(self.core.history, '_data', {})
                hist_ips = [ip for ip in hist_data.keys() if ip not in printed]
            except Exception:
                hist_ips = []

            for ip in hist_ips:
                # we may not have username/hostname for offline entries
                msgs = []
                try:
                    msgs = self.core.history.get(ip)
                except Exception:
                    msgs = []
                last = msgs[-1][0] if msgs else 0
                ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(last)) if last else "-"
                print(f"?(unknown)@{ip} (unknown) [offline]  last_msg={ts}")
                
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

        # 常用语命令
        elif cmd == "quick":
            # quick [list]
            # quick send <target> <index>
            sub = parts[1].lower() if len(parts) > 1 else "list"
            
            texts = self.core.get_quick_texts()
            
            if sub == "list":
                print("--- Quick Texts ---")
                # 3 items per line, 1-based index
                row = []
                for i, t in enumerate(texts, 1):
                    row.append(f"{i}: {t}")
                    if len(row) == 3:
                        print("\t".join(row))
                        row = []
                if row:
                    print("\t".join(row))
                    
            elif sub == "send":
                if len(parts) < 4:
                    print("Usage: quick send <target> <index>")
                    return
                target = parts[2]
                try:
                    idx = int(parts[3])
                    real_idx = idx - 1 # Convert 1-based to 0-based
                    if 0 <= real_idx < len(texts):
                        msg = texts[real_idx]
                        if target.startswith("group:"):
                            self.core.send_group_msg(target[6:], msg)
                        else:
                            self.core.send_text(target, msg)
                        print(f"Sent quick text #{idx} to {target}")
                    else:
                        print(f"Invalid index: {idx}")
                except ValueError:
                    print("Index must be an integer")
            else:
                print("Usage: quick [list] | quick send <target> <index>")
            
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
        
        elif cmd == "ls":
            # 展示当前工作目录文件，支持可选路径参数
            target_dir = os.getcwd()
            if len(parts) > 1:
                p = parts[1]
                if os.path.isabs(p):
                    target_dir = p
                else:
                    target_dir = os.path.abspath(os.path.join(os.getcwd(), p))
            try:
                entries = os.listdir(target_dir)
                print(f"Directory: {target_dir}")
                for name in sorted(entries):
                    full = os.path.join(target_dir, name)
                    typ = "<DIR>" if os.path.isdir(full) else "     "
                    try:
                        sz = os.path.getsize(full) if os.path.isfile(full) else 0
                    except Exception:
                        sz = 0
                    print(f"{typ} {str(sz).rjust(8)}  {name}")
            except Exception as e:
                print(f"ls error: {e}")
            
        elif cmd == "exit": 
            raise KeyboardInterrupt
            
        elif cmd == "help": 
            # 完整命令列表（包括用法和描述）
            all_commands = [
                ("login <name>", "上线并广播存在"),
                ("logout", "下线但保持程序运行"),
                ("discover [ip]", "广播或单播发现节点"),
                ("info", "显示本机与在线节点摘要"),
                ("info net", "显示绑定/广播/端口等网络信息"),
                ("info user:<name>", "查看与某用户的最近聊天历史（若在线）"),
                ("info group:<name>", "查看群组成员与最近历史"),
                ("list", "列出当前在线用户及状态"),
                ("send <ip> <msg>", "发送文本消息；若 target 为 'all' 则广播"),
                ("send user:<name> <msg>", "按用户名发送（如有多个 IP，会逐个发送） [可用]"),
                ("file send <ip> <path>", "发送文件要约"),
                ("file list", "列出待接收/待处理的文件要约 [未完全实现]"),
                ("file accept <id>", "接受文件要约并下载"),
                ("file cancel <id>", "取消/放弃文件要约 [未实现]"),
                ("group list", "列出本地群组"),
                ("group create <name>", "创建群组"),
                ("group add <name> <user>", "将用户添加到群组"),
                ("group msg <name> <text>", "向群组在线成员逐个发送消息"),
                ("group delete <name>", "删除群组或移除成员（未实现）"),
                ("search <query>", "按用户名/组名/IP 搜索"),
                ("ocr <path> [--send <ip>]", "识别图片文字，可选发送结果"),
                ("quick [list]", "列出常用语"),
                ("quick send <target> <idx>", "发送常用语 (索引从1开始)"),
                ("debug cipher <on|off>", "显示/隐藏原始密文（调试）"),
                ("log level <DEBUG|INFO|WARN|ERROR>", "设置日志等级"),
                ("set status <online|busy|away>", "设置在线状态并广播"),
                ("set encrypt <off|on|strict>", "设置加密策略；strict 则在握手完成前拒绝明文"),
                ("set encoding <utf8|gbk>", "设置发送编码（未暴露全部选项）"),
                ("set bind <ip>", "切换绑定地址（运行时需重启 transport，慎用）"),
                ("screenshot", "本地截图并保存（可选发送）"),
                ("ls [path]", "列出当前或指定目录文件"),
                ("clear", "清屏"),
                ("exit", "退出程序"),
            ]

            # 提取根命令用于展示简表
            root_commands = sorted(list(set(r[0].split(' ')[0] for r in all_commands)))

            # --- 逻辑判断：有无参数 ---
            if len(parts) == 1:
                print("Command:")
                # 自适应宽度计算：每行 5 个
                col_count = 5
                # 计算最大命令长度用于对齐
                max_len = max(len(c) for c in root_commands) + 4 
                
                for i in range(0, len(root_commands), col_count):
                    chunk = root_commands[i:i+col_count]
                    # 使用 ljust 进行填充对齐
                    line = "".join(c.ljust(max_len) for c in chunk)
                    print(line)
                    
            else:
                # 2. 有参数时：展示该命令的详细用法
                sub_cmd = parts[1].lower()
                
                # --- 标题高亮逻辑 ---
                title_content = f"{sub_cmd}"
                if _HAS_PT and print_formatted_text and HTML:
                    # 使用 prompt_toolkit 的 HTML 格式 (绿色粗体)
                    print_formatted_text(HTML(f"Command <ansigreen><bold>{title_content}</bold></ansigreen>:"))
                else:
                    # 使用 ANSI 转义码 (绿色粗体)
                    print(f"Command \033[1;32m{title_content}\033[0m:")
                
                # 过滤出与子命令相关的行
                filtered_rows = []
                
                # 1. 尝试作为顶级命令匹配 (如 help file)
                # 获取以该词开头的命令描述
                filtered_rows.extend([r for r in all_commands if r[0].split(' ')[0] == sub_cmd])
                
                # 2. 尝试作为子命令匹配 (如 help user -> info user:...)
                if not filtered_rows:
                     for r in all_commands:
                        # 简单的包含检查，实际可能需要更严谨的解析
                        if sub_cmd in r[0] and not r[0].startswith(sub_cmd):
                             filtered_rows.append(r)

                # 格式化并打印详细用法
                if filtered_rows:
                    filtered_rows.sort(key=lambda x: (len(x[0]), x[0]))
                    max_cmd_len = max(len(r[0]) for r in filtered_rows)
                    leftw = max(max_cmd_len, 10) + 2
                    for left, desc in filtered_rows:
                        print(left.ljust(leftw) + "  " + desc)
                else:
                    print(f"No help found for '{sub_cmd}'.")
        else: 
            print(f"Unknown command '{cmd}'. Type 'help' for list.")
