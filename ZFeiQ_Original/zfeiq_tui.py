import os
import time
import platform
from typing import List, Tuple, Optional, Callable

from textual import work, on, events
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, Container, Center, Middle
from textual.widgets import (
    Header, Footer, Input, RichLog, ListView, ListItem, Label, Button, 
    Select, TabbedContent, TabPane, DirectoryTree, TextArea, Static
)
from textual.message import Message
from textual.screen import Screen, ModalScreen
from textual.reactive import reactive
from textual.binding import Binding

# 导入 ZFeiQ 核心
from zfeiq_cli.cli import ZFeiQCli, _win_list_ipv4_addrs, _linux_list_ipv4_addrs
from zfeiq_cli.protocol import parse_packet, base_command, IPMSG_SENDMSG, decode_fileattach_lines

# --- 样式定义 (CSS) ---
GLOBAL_CSS = """
/* 全局设定 */
Screen { background: $surface; }
.sub-text { color: $text-muted; text-style: italic; }
.bold { text-style: bold; }

/* === 布局框架 === */

/* 左侧侧边栏 */
#sidebar {
    width: 40;
    dock: left;
    border-right: solid $secondary;
    height: 100%;
    layout: vertical;
}

/* 列表区域 */
TabbedContent {
    height: 1fr;
}
TabPane {
    height: 100%;
    padding: 0;
    layout: vertical;
}
ListView {
    height: 1fr; /* 占据剩余空间 */
    border: none;
    scrollbar-gutter: stable;
}

/* === 底部面板 === */

/* 左侧底部面板 (网络信息) */
#net_info_box {
    height: 10; /* 固定高度 */
    border-top: solid $secondary;
    background: $surface-darken-1;
    padding: 1;
    layout: vertical;
}

/* 右侧底部面板 (输入区) */
#chat_input_container {
    height: 10; /* 与左侧保持高度一致 */
    border-top: solid $secondary;
    background: $surface-darken-1;
    padding: 0 1 1 1;
}

/* === 组件样式 === */

/* 用户页底部内容 */
#net_info_box Label {
    margin-bottom: 1;
    color: $text-muted;
}

/* 组页底部提示信息 */
.group-hint {
    color: $accent;
    text-align: center;
    width: 100%;
}

/* 聊天区域 */
#chat_container {
    height: 100%;
    layout: vertical;
}
/* 蓝色条占满右侧顶部 */
#chat_header {
    height: 3;
    background: $accent;
    color: $surface;     
    content-align: left middle;
    padding-left: 2;
    text-style: bold;
    width: 100%;
}
#chat_log {
    height: 1fr; /* 占据中间空间 */
    padding: 0 1;
    overflow-y: scroll;
}

/* 输入框 */
ChatTextArea {
    height: 100%;
    border: solid $secondary;
    background: $surface;
}
ChatTextArea:focus {
    border: double $accent;
}

/* 弹窗通用 */
ModalScreen { align: center middle; background: rgba(0,0,0,0.7); }
.modal-box {
    background: $surface;
    border: panel $primary;
    padding: 1;
    layout: vertical;
}
.modal-title {
    text-align: center;
    text-style: bold;
    border-bottom: solid $secondary;
    padding-bottom: 1;
    margin-bottom: 1;
}
.modal-message {
    text-align: center; 
    margin: 1 0;
}
.modal-sm { width: 50; height: auto; }
.modal-md { width: 60; height: 60%; }
#file_tree { height: 1fr; }
#sel_list { height: 1fr; }
.btn-row { 
    height: auto; 
    align: right middle; 
    margin-top: 1; 
}
.btn-row Button { margin-left: 1; }

/* 登录页样式 */
.login-top-bar { dock: top; height: 3; align-horizontal: right; padding: 0 1; }
.login-title { text-align: center; color: $accent; margin-bottom: 1; text-style: bold; }
.login-label { color: $text-muted; }
.login-label-margin { color: $text-muted; margin-top: 1; }
.login-btn-full { width: 100%; margin-top: 2; }
#login_center { align: center middle; height: 100%; }
#login_box { width: 50; height: auto; border: heavy $accent; padding: 1 2; }

/* 设置页样式 */
.settings-box { border: panel $accent; padding: 2; width: auto; height: auto; }
.settings-text { text-align: center; margin-bottom: 2; }
"""

# --- 辅助类 ---

class BackendMessage(Message):
    def __init__(self, sender: str, ip: str, text: str, is_system: bool = False):
        self.sender = sender
        self.ip = ip
        self.text = text
        self.is_system = is_system
        super().__init__()

class ChatTextArea(TextArea):
    """自定义输入框：手动处理按键以支持 Enter 发送"""
    
    class Submitted(Message):
        def __init__(self, value: str):
            self.value = value
            super().__init__()

    async def _on_key(self, event: events.Key) -> None:
        if event.key == "enter":
            if "shift" in event.modifiers:
                # Shift+Enter -> 换行
                self.insert("\n")
            else:
                # Enter -> 发送
                event.prevent_default()
                event.stop()
                self.post_message(self.Submitted(self.text))
                self.text = ""
        else:
            await super()._on_key(event)

# --- 弹窗组件 ---

class MessageModal(ModalScreen):
    """通用消息提示弹窗"""
    def __init__(self, title: str, message: str):
        super().__init__()
        self.box_title = title
        self.message = message

    def compose(self) -> ComposeResult:
        with Container(classes="modal-box modal-sm"):
            yield Label(self.box_title, classes="modal-title")
            # 修复：移除 inline style，使用 CSS class
            yield Label(self.message, classes="modal-message")
            with Horizontal(classes="btn-row"):
                yield Button("确定", variant="primary", id="btn_ok")

    @on(Button.Pressed, "#btn_ok")
    def ok(self):
        self.dismiss()

class HelpModal(ModalScreen):
    def compose(self) -> ComposeResult:
        help_text = (
            "1) 登录后在左侧列表选择聊天对象\n"
            "2) 输入文字按 Enter 发送，Shift+Enter 换行\n"
            "3) 全局快捷键:\n"
            "   Ctrl+D: 发现/刷新用户\n"
            "   Ctrl+P: 常用语\n"
            "   Ctrl+E: 表情\n"
            "   Ctrl+F: 发送文件\n"
            "   Ctrl+S: 截图 (仅Windows)\n"
            "   Ctrl+O: OCR文字识别\n"
            "   Ctrl+Q: 退出\n"
            "4) 组管理快捷键:\n"
            "   F3: 新建组  F4: 删除组  F5: 重命名\n"
            "   F6: 添加成员 F7: 删除成员"
        )
        with Container(classes="modal-box modal-md"):
            yield Label("帮助 / Help", classes="modal-title")
            yield Label(help_text)
            with Horizontal(classes="btn-row"):
                yield Button("关闭", id="btn_close")

    @on(Button.Pressed, "#btn_close")
    def close(self):
        self.dismiss()

class FilePickerModal(ModalScreen):
    def __init__(self, title: str, select_callback: Callable[[str], None]):
        super().__init__()
        self.picker_title = title
        self.callback = select_callback

    def compose(self) -> ComposeResult:
        with Container(classes="modal-box modal-md"):
            yield Label(self.picker_title, classes="modal-title")
            yield DirectoryTree(os.getcwd(), id="file_tree")
            with Horizontal(classes="btn-row"):
                yield Button("取消", id="btn_cancel")

    @on(DirectoryTree.FileSelected)
    def on_file_selected(self, event: DirectoryTree.FileSelected):
        self.callback(event.path)
        self.dismiss()

    @on(Button.Pressed, "#btn_cancel")
    def cancel(self):
        self.dismiss()

class InputModal(ModalScreen):
    def __init__(self, title: str, placeholder: str, callback: Callable[[str], None]):
        super().__init__()
        self.title_text = title
        self.ph = placeholder
        self.callback = callback

    def compose(self) -> ComposeResult:
        with Container(classes="modal-box modal-sm"):
            yield Label(self.title_text, classes="modal-title")
            yield Input(placeholder=self.ph, id="modal_input")
            with Horizontal(classes="btn-row"):
                yield Button("确定", variant="primary", id="btn_ok")
                yield Button("取消", id="btn_cancel")

    def on_mount(self):
        self.query_one("#modal_input").focus()

    @on(Button.Pressed, "#btn_ok")
    def ok(self):
        self.callback(self.query_one("#modal_input").value)
        self.dismiss()
    
    @on(Input.Submitted)
    def submit(self):
        self.ok()

    @on(Button.Pressed, "#btn_cancel")
    def cancel(self):
        self.dismiss()

class SelectionModal(ModalScreen):
    def __init__(self, title: str, items: List[str], callback: Callable[[str], None]):
        super().__init__()
        self.title_text = title
        self.items = items
        self.callback = callback

    def compose(self) -> ComposeResult:
        with Container(classes="modal-box modal-md"):
            yield Label(self.title_text, classes="modal-title")
            yield ListView(*[ListItem(Label(i)) for i in self.items], id="sel_list")
            with Horizontal(classes="btn-row"):
                yield Button("关闭", id="btn_close")

    @on(ListView.Selected)
    def on_selected(self, event: ListView.Selected):
        label = event.item.query_one(Label)
        if label: self.callback(str(label.renderable))
        self.dismiss()

    @on(Button.Pressed, "#btn_close")
    def close(self):
        self.dismiss()

class SettingsScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header()
        with Center():
            with Middle():
                with Container(classes="settings-box"):
                    yield Label("设置页面 (暂未实现)", classes="settings-text")
                    yield Button("返回", variant="primary", id="btn_back")
        yield Footer()

    @on(Button.Pressed, "#btn_back")
    def back(self):
        self.dismiss()

# --- 列表项组件 ---

class UserItem(ListItem):
    def __init__(self, username: str, ip: str, hostname: str, status: str, is_local: bool = False):
        self.username = username
        self.ip = ip
        self.status = status
        self.is_local = is_local
        super().__init__()

    def compose(self) -> ComposeResult:
        if self.ip == "all":
            icon = "📡"
            display_name = f"{icon} 所有在线 (广播)"
        else:
            icon = "🟢" if self.status == "online" else "🟠" if self.status == "busy" else "⚫"
            local_tag = "[LOCAL] " if self.is_local else ""
            display_name = f"{icon} {local_tag}{self.username}"
            
        yield Label(display_name)
        if self.ip != "all":
            yield Label(f"   {self.ip}", classes="sub-text")

class GroupItem(ListItem):
    def __init__(self, name: str, count: int):
        self.group_name = name
        self.count = count
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Label(f"👥 {self.group_name}")
        yield Label(f"   ({self.count} 成员)", classes="sub-text")

# --- 屏幕 ---

class LoginScreen(Screen):
    def compose(self) -> ComposeResult:
        with Horizontal(classes="login-top-bar"):
            yield Button("帮助 / Help", id="btn_help")
        with Center(id="login_center"):
            with Middle():
                with Container(id="login_box"):
                    yield Label("欢迎使用 ZFeiQ TUI，请先登录", classes="login-title")
                    yield Label("用户名:", classes="login-label")
                    yield Input(placeholder="输入用户名...", id="username")
                    yield Label("选择 IP:", classes="login-label-margin")
                    yield Select([], id="ip_select", prompt="扫描网卡中...")
                    yield Button("登录 / Login", id="btn_login", variant="primary", classes="login-btn-full")

    def on_mount(self):
        ips = []
        try:
            raw = _win_list_ipv4_addrs() if os.name == "nt" else _linux_list_ipv4_addrs()
            for ip, pre in raw:
                label = f"{ip} (/{pre})" if pre else ip
                ips.append((label, ip))
        except: pass
        if not ips: ips.append(("0.0.0.0 (Auto)", "0.0.0.0"))
        sel = self.query_one("#ip_select", Select)
        sel.set_options(ips)
        sel.value = ips[0][1]

    @on(Button.Pressed, "#btn_login")
    def login(self):
        u = self.query_one("#username").value.strip()
        ip = self.query_one("#ip_select").value
        if u and ip: self.app.do_login(u, ip)

    @on(Button.Pressed, "#btn_help")
    def help(self):
        self.app.push_screen(HelpModal())

class MainScreen(Screen):
    """主界面"""
    BINDINGS = [
        # 系统
        Binding("ctrl+q", "quit", "退出", priority=True),
        Binding("f1", "show_help", "帮助", priority=True),
        Binding("f2", "settings", "设置", priority=True),
        # 聊天
        Binding("ctrl+d", "discover", "发现", priority=True),
        Binding("ctrl+p", "phrase", "常用语", priority=True),
        Binding("ctrl+e", "emote", "表情", priority=True),
        Binding("ctrl+f", "file", "发文件", priority=True),
        Binding("ctrl+s", "screenshot", "截图", priority=True),
        Binding("ctrl+o", "ocr", "OCR", priority=True),
        # 组管理 (Footer 显示)
        Binding("f3", "grp_new", "新建组"),
        Binding("f4", "grp_del", "删除组"),
        Binding("f5", "grp_ren", "重命名"),
        Binding("f6", "grp_add", "加成员"),
        Binding("f7", "grp_rem", "删成员"),
    ]

    target_id = reactive("")
    target_display = reactive("未选择")
    target_status = reactive("-")
    target_ip = reactive("-.-.-.-")

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        
        with Horizontal():
            # === 左侧边栏 ===
            with Container(id="sidebar"):
                with TabbedContent(initial="tab_users"):
                    
                    # 用户页
                    with TabPane("用户", id="tab_users"):
                        yield ListView(id="user_list")
                        # 左侧底部面板 - 网络信息
                        with Vertical(id="net_info_box"):
                            yield Label("本机: -", id="lbl_local_ip")
                            yield Label("广播: -", id="lbl_bcast")
                            yield Label("在线: 0", id="lbl_online_count")

                    # 组页
                    with TabPane("组", id="tab_groups"):
                        yield ListView(id="group_list")
                        # 组页面板
                        with Vertical(id="net_info_box"): 
                            # 修复：移除 inline style，使用 CSS class
                            yield Label("请使用下方 F3-F7 快捷键", classes="group-hint")
                            yield Label("管理选中的群组", classes="group-hint")

            # === 右侧聊天区 ===
            with Container(id="chat_container"):
                yield Label("未选择", id="chat_header")
                yield RichLog(id="chat_log", markup=True, wrap=True)
                
                # 右侧底部面板 - 输入区
                with Container(id="chat_input_container"):
                    yield ChatTextArea(id="msg_input")

        yield Footer()

    def on_mount(self):
        self.set_interval(2.0, self.refresh_ui)
        # 初始聚焦输入框
        self.query_one("#msg_input").focus()

    # --- UI 刷新 ---
    def refresh_ui(self):
        zcli = self.app.zcli
        if not zcli: return

        # 刷新用户列表
        ulist = self.query_one("#user_list", ListView)
        idx = ulist.index
        
        # 1. 广播选项
        new_items = []
        new_items.append(UserItem("所有在线 (广播)", "all", "Broadcast", "online"))
        
        # 2. 本机 + 其他在线用户
        nodes = zcli.registry.list_nodes()
        
        # 更新底部信息
        self.query_one("#lbl_local_ip", Label).update(f"本机: {zcli.local_ip}")
        bcast = getattr(zcli.transport, "_broadcast_addr", "-")
        self.query_one("#lbl_bcast", Label).update(f"广播: {bcast}")
        self.query_one("#lbl_online_count", Label).update(f"在线: {len(nodes)}")

        # 显示自己
        local_node = zcli.registry.get_by_ip(zcli.local_ip)
        if local_node:
            new_items.append(UserItem(local_node.username, local_node.ip, local_node.hostname, "online", is_local=True))
        else:
            # 如果还没刷出来自己，手动造一个
            new_items.append(UserItem(zcli.username or "Me", zcli.local_ip, zcli.hostname, "online", is_local=True))

        for n in sorted(nodes, key=lambda x: x.ip):
            if n.ip == zcli.local_ip: continue
            new_items.append(UserItem(n.username, n.ip, n.hostname, getattr(n, 'status', 'online')))
        
        ulist.clear()
        ulist.extend(new_items)
        if idx is not None and idx < len(ulist.children): ulist.index = idx

        # 刷新组列表
        glist = self.query_one("#group_list", ListView)
        gidx = glist.index
        glist.clear()
        for gname, mems in sorted(zcli.groups.items()):
            glist.append(GroupItem(gname, len(mems)))
        if gidx is not None and gidx < len(glist.children): glist.index = gidx

    # --- 交互 ---
    def on_list_view_selected(self, event: ListView.Selected):
        item = event.item
        if isinstance(item, UserItem):
            self.target_id = item.ip
            self.target_display = item.username if item.ip != "all" else "所有在线"
            self.target_status = item.status
            self.target_ip = item.ip
        elif isinstance(item, GroupItem):
            self.target_id = f"group:{item.group_name}"
            self.target_display = f"群组:{item.group_name}"
            self.target_status = "-"
            self.target_ip = "-"
        
        self.update_header()
        self.query_one("#msg_input").focus()

    def update_header(self):
        if not self.target_id:
            txt = "未选择"
        else:
            txt = f"{self.target_display} [{self.target_status}] ({self.target_ip})"
        self.query_one("#chat_header", Label).update(txt)

    # --- 消息发送 ---
    def on_chat_text_area_submitted(self, event: ChatTextArea.Submitted):
        text = event.value.strip()
        if not text: return
        if not self.target_id:
            self.write_log("[bold red]请先选择发送目标！[/]")
            return
        
        if text.startswith("/"):
            self.app.handle_cli_command(text)
            return
        
        self.app.do_send(self.target_id, text)

    def write_log(self, text: str):
        self.query_one("#chat_log", RichLog).write(text)

    # --- 快捷键动作 ---
    
    def action_quit(self): self.app.action_quit()
    def action_settings(self): self.app.push_screen(SettingsScreen())
    def action_show_help(self): self.app.push_screen(HelpModal())

    # 1. 发现
    def action_discover(self):
        def _do(ip):
            self.app.zcli.cmd_discover(ip if ip else None)
            self.write_log(f"[dim]已发送发现广播...[/]")
        self.app.push_screen(InputModal("发现用户", "输入IP (留空则广播)", _do))

    # 2. 常用语
    def action_phrase(self):
        phrases = ["在吗？", "收到。", "稍等一下", "方便发个文件吗？", "谢谢！"]
        try:
            if os.path.exists("quick_texts.txt"):
                with open("quick_texts.txt", "r", encoding="utf-8") as f:
                    lines = [l.strip() for l in f if l.strip()]
                    if lines: phrases = lines
        except: pass
        
        def _pick(s):
            ta = self.query_one("#msg_input", TextArea)
            ta.insert(s)
            ta.focus()
        self.app.push_screen(SelectionModal("选择常用语", phrases, _pick))

    # 3. 表情
    def action_emote(self):
        edir = self.app.zcli.emotes_dir if self.app.zcli else "emotes"
        if not os.path.exists(edir): os.makedirs(edir)
        def _send(path):
            if not self.target_id: return
            self.app.zcli.cmd_file_send(self.target_id, path)
            self.write_log(f"[dim]已发送表情: {os.path.basename(path)}[/]")
        try:
            files = [f for f in os.listdir(edir) if f.lower().endswith(('.png','.jpg','.gif'))]
            if not files:
                self.write_log("[yellow]emotes 目录下无图片[/]")
                return
            self.app.push_screen(SelectionModal("选择表情", files, lambda f: _send(os.path.join(edir, f))))
        except: pass

    # 4. 文件
    def action_file(self):
        def _pick(path):
            if not self.target_id: 
                self.write_log("[red]未选择目标[/]")
                return
            if os.path.isdir(path): return
            self.app.zcli.cmd_file_send(self.target_id, path)
            self.write_log(f"[dim]正在发送文件: {path}[/]")
        self.app.push_screen(FilePickerModal("选择文件发送", _pick))

    # 5. 截图
    def action_screenshot(self):
        if not self.target_id: return
        if os.name != "nt": 
            self.write_log("[yellow]全屏截图仅支持 Windows[/]")
            return
        try:
            path = self.app.zcli._capture_fullscreen_bmp()
            if path:
                self.app.zcli.cmd_file_send(self.target_id, path)
                self.app.push_screen(MessageModal("截图成功", f"已发送全屏截图:\n{path}"))
                self.write_log(f"[dim]已发送全屏截图[/]")
        except Exception as e:
            self.write_log(f"[red]截图失败: {e}[/]")

    # 6. OCR
    def action_ocr(self):
        def _run(path):
            if not os.path.isfile(path): return
            self.write_log(f"[dim]识别中: {os.path.basename(path)}...[/]")
            self.app.run_ocr_worker(path)
        self.app.push_screen(FilePickerModal("选择图片识别", _run))

    # --- 组管理快捷键 (F3-F7) ---
    def action_grp_new(self): 
        self.app.push_screen(InputModal("新建群组", "输入组名", lambda n: self.app.zcli.cmd_group(n, "-add", None) if n else None))
    
    def action_grp_del(self): 
        if self.target_id.startswith("group:"):
            gname = self.target_id.split(":",1)[1]
            self.app.zcli.cmd_group(gname, "-delete", None)
            self.target_id=""
            self.update_header()
        else:
            self.app.push_screen(MessageModal("提示", "请先在列表中选中一个群组"))

    def action_grp_ren(self):
        if self.target_id.startswith("group:"):
            old = self.target_id.split(":",1)[1]
            self.app.push_screen(InputModal("重命名", "新名称", lambda n: self.app.zcli.cmd_group(old, "-rename", n) if n else None))
        else:
            self.app.push_screen(MessageModal("提示", "请先在列表中选中一个群组"))

    def action_grp_add(self):
        if self.target_id.startswith("group:"):
            gname = self.target_id.split(":",1)[1]
            self.app.push_screen(InputModal(f"添加到 {gname}", "用户名或IP", lambda m: self.app.zcli.cmd_group(gname, "-add", m) if m else None))
        else:
            self.app.push_screen(MessageModal("提示", "请先在列表中选中一个群组"))

    def action_grp_rem(self):
        if self.target_id.startswith("group:"):
            gname = self.target_id.split(":",1)[1]
            self.app.push_screen(InputModal(f"从 {gname} 移除", "用户名或IP", lambda m: self.app.zcli.cmd_group(gname, "-delete", m) if m else None))
        else:
            self.app.push_screen(MessageModal("提示", "请先在列表中选中一个群组"))


class ZFeiQApp(App):
    CSS = GLOBAL_CSS
    SCREENS = {"login": LoginScreen, "main": MainScreen}

    def __init__(self):
        super().__init__()
        self.zcli: Optional[ZFeiQCli] = None
        self._orig_recv = None

    def on_mount(self):
        self.push_screen("login")

    def do_login(self, username: str, bind_ip: str):
        try:
            self.zcli = ZFeiQCli(port=2425, bind_ip=bind_ip)
            self._orig_recv = self.zcli._on_recv
            self.zcli._on_recv = self._recv_hook
            self.zcli.start()
            self.zcli.cmd_login(username)
            self.switch_screen("main")
            self.notify(f"登录成功: {username}")
            self.zcli.cmd_discover()
        except Exception as e:
            self.notify(f"登录失败: {e}", severity="error")

    def action_quit(self):
        if self.zcli: self.zcli.stop()
        self.exit()

    def _recv_hook(self, data: bytes, addr: tuple):
        if self._orig_recv:
            try: self._orig_recv(data, addr)
            except: pass
        try:
            hdr, ext = parse_packet(data)
            base = base_command(hdr.get("command", 0))
            user = hdr.get("username", "?")
            src = addr[0]
            if base == IPMSG_SENDMSG:
                txt = ext.split("\0", 1)[0] if ext else ""
                ext_after = ext.split("\0", 1)[1] if "\0" in (ext or "") else ""
                try: attaches = decode_fileattach_lines(ext_after)
                except: attaches = []
                if attaches:
                    finfo = ", ".join([f"{a.get('name')}" for a in attaches])
                    self.call_from_thread(self.post_msg, BackendMessage(user, src, f"[文件] {finfo}", True))
                if txt and not txt.startswith("FILE_OFFER;"):
                    self.call_from_thread(self.post_msg, BackendMessage(user, src, txt))
        except: pass

    def post_msg(self, msg: BackendMessage):
        try:
            scr = self.get_screen("main")
            if isinstance(scr, MainScreen):
                ts = time.strftime("%H:%M:%S")
                style = "bold yellow" if msg.is_system else "bold green"
                pre = "系统" if msg.is_system else f"{msg.sender}@{msg.ip}"
                scr.write_log(f"[dim]{ts}[/] [{style}]{pre}[/]: {msg.text}")
        except: pass

    def do_send(self, target: str, text: str):
        if not self.zcli: return
        try:
            scr = self.get_screen("main")
            ts = time.strftime("%H:%M:%S")
            if target == "all":
                self.zcli.cmd_sendall(text)
                scr.write_log(f"[dim]{ts}[/] [bold cyan]我 -> 所有人[/]: {text}")
            elif target.startswith("group:"):
                gname = target.split(":", 1)[1]
                self.zcli.cmd_group(gname, "-send", text)
                scr.write_log(f"[dim]{ts}[/] [bold cyan]我 -> 群:{gname}[/]: {text}")
            else:
                self.zcli.cmd_send(f"ip:{target}", text)
                scr.write_log(f"[dim]{ts}[/] [bold cyan]我 -> {target}[/]: {text}")
        except Exception as e:
            self.notify(f"发送失败: {e}", severity="error")

    def handle_cli_command(self, text: str):
        scr = self.get_screen("main")
        cmd = text.split()[0]
        if cmd == "/discover":
            self.zcli.cmd_discover()
            scr.write_log("[dim]已广播发现...[/]")
        elif cmd == "/clear":
            scr.query_one("#chat_log", RichLog).clear()
        else:
            scr.write_log(f"[red]暂不支持命令 {cmd}[/]")

    @work(thread=True)
    def run_ocr_worker(self, path: str):
        try:
            from zfeiq_cli.ocr import ZFeiQOcr
            engine = ZFeiQOcr.get_instance()
            if not engine.ready:
                self.call_from_thread(lambda: self.get_screen("main").write_log("[red]OCR 初始化失败[/]"))
                return
            res = engine.run(path)
            def _fill():
                scr = self.get_screen("main")
                ta = scr.query_one("#msg_input", TextArea)
                ta.insert(f"{res}") # 已移除 [OCR] 前缀
                ta.focus()
                scr.write_log(f"[dim]OCR 完成[/]")
            self.call_from_thread(_fill)
        except Exception as e:
            self.call_from_thread(lambda: self.get_screen("main").write_log(f"[red]OCR 错误: {e}[/]"))

if __name__ == "__main__":
    app = ZFeiQApp()
    app.run()
