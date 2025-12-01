from __future__ import annotations
import os, time
from textual import work
from textual.app import App
from textual.widgets import Header, Footer, RichLog, Label
from textual.binding import Binding

from .screens.login import LoginScreen
from .screens.main import MainScreen
from .widgets.common import MessageModal
from .services.client import ClientAdapter

class ZFeiQTuiApp(App):
    CSS_PATH = 'styles/theme.tcss'
    ENABLE_COMMAND_PALETTE = False  # avoid Ctrl+P conflict
    BINDINGS=[Binding('ctrl+q','quit_app','退出',priority=True)]

    def __init__(self):
        super().__init__()
        self.client = ClientAdapter()
        self._main: MainScreen | None = None

    def on_mount(self):
        self.push_screen(LoginScreen(self.client))

    # high-level API used by screens
    def login(self, username: str, bind_ip: str):
        self.client.on_message = self._on_backend_message
        self.client.start(username, bind_ip)
        self._main = MainScreen(self.client)
        self.switch_screen(self._main)
        self.notify(f"登录成功: {username}")
        # 登录后立即刷新一次，避免等待定时器才看到用户/组
        try:
            self._main.refresh_ui()
        except Exception:
            pass

    def request_quit(self):
        self.action_quit_app()

    def action_quit_app(self):
        self.client.stop()
        self.exit()

    def show_help(self):
        help_text = (
            "1) 左侧选择聊天对象，右侧输入区 Enter 发送\n"
            "2) 全局快捷键: Ctrl+D 发现、Ctrl+P 常用语、Ctrl+E 表情、Ctrl+F 发文件、Ctrl+O OCR、Ctrl+Q 退出\n"
            "3) 组管理: F3 新建、F4 删除、F5 重命名、F6 加成员、F7 删成员"
        )
        self.push_screen(MessageModal('帮助 / Help', help_text))

    def show_settings(self):
        self.push_screen(MessageModal('设置', '设置页尚未实现'))

    def _on_backend_message(self, sender: str, ip: str, text: str, is_system: bool=False):
        if self._main:
            self.call_from_thread(self._main.post_backend_message, sender, ip, text, is_system)

    @work(thread=True)
    def run_ocr_worker(self, path: str):
        try:
            from zfeiq_cli.ocr import ZFeiQOcr
            engine = ZFeiQOcr.get_instance()
            if not engine.ready:
                if self._main:
                    self.call_from_thread(lambda: self._main.query_one('#chat_log', RichLog).write('[red]OCR 初始化失败[/]'))
                return
            res = engine.run(path)
            if self._main:
                def _fill():
                    ta = self._main.query_one('#msg_input')
                    from textual.widgets import TextArea
                    assert isinstance(ta, TextArea)
                    ta.insert(f"{res}"); ta.focus()
                    self._main.query_one('#chat_log', RichLog).write('[dim]OCR 完成[/]')
                self.call_from_thread(_fill)
        except Exception as e:
            if self._main:
                self.call_from_thread(lambda: self._main.query_one('#chat_log', RichLog).write(f'[red]OCR 错误: {e}[/]'))
