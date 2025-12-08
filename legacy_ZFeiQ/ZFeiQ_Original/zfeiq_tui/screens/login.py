from __future__ import annotations
import os
from typing import List, Tuple
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Center, Middle, Container
from textual.widgets import Label, Input, Select
from textual.screen import Screen
from ..services.client import ClientAdapter

class LoginScreen(Screen):
    BINDINGS=[Binding("enter","login","登录",priority=True), Binding("f1","help","帮助",priority=True), Binding("ctrl+q","quit","退出",priority=True)]
    def __init__(self, client: ClientAdapter):
        super().__init__(); self.client = client
    def compose(self) -> ComposeResult:
        with Horizontal(classes="login-top-bar"):
            yield Label("F1 帮助", classes="login-label")
            yield Label("Ctrl+Q 退出", classes="login-label")
        with Center(id="login_center"):
            with Middle():
                with Container(id="login_box"):
                    yield Label("欢迎使用 ZFeiQ TUI，请先登录", classes="login-title")
                    yield Label("用户名:", classes="login-label")
                    yield Input(placeholder="输入用户名...", id="username")
                    yield Label("选择 IP:", classes="login-label-margin")
                    yield Select([], id="ip_select", prompt="扫描网卡中...")
                    yield Label("Enter 登录 / F1 帮助", classes="key-hint")
    def on_mount(self):
        ips: List[Tuple[str,int]] = []
        try:
            raw = self.client.list_local_ips()
            for ip, pre in raw:
                label = f"{ip} (/{pre})" if pre else ip
                ips.append((label, ip))
        except Exception:
            pass
        if not ips: ips.append(("0.0.0.0 (Auto)", "0.0.0.0"))
        sel = self.query_one('#ip_select', Select)
        sel.set_options(ips)
        sel.value = ips[0][1]
    def action_login(self):
        u = self.query_one('#username').value.strip()
        ip = self.query_one('#ip_select').value
        if u and ip:
            self.app.login(u, ip)
    def action_help(self):
        self.app.show_help()
    def action_quit(self):
        self.app.request_quit()
