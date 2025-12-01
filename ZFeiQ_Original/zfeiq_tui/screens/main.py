from __future__ import annotations
import os, time
from typing import List
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.reactive import reactive
from textual.containers import Horizontal, Vertical, Container
from textual.widgets import Header, Footer, Label, RichLog, ListView, ListItem, TabbedContent, TabPane, TextArea
from textual.screen import Screen

from ..widgets.common import ChatTextArea, MessageModal, InputModal, FilePickerModal, SelectionModal
from ..services.client import ClientAdapter

class UserItem(ListItem):
    def __init__(self, username: str, ip: str, hostname: str, status: str, is_local: bool=False):
        self.username=username; self.ip=ip; self.status=status; self.is_local=is_local
        super().__init__()
    def compose(self) -> ComposeResult:
        if self.ip == 'all':
            display_name = f"📡 所有在线 (广播)"
        else:
            icon = "🟢" if self.status=="online" else "🟠" if self.status=="busy" else "⚫"
            local_tag = "[LOCAL] " if self.is_local else ""
            display_name = f"{icon} {local_tag}{self.username}"
        yield Label(display_name)
        if self.ip != 'all': yield Label(f"   {self.ip}", classes="sub-text")

class GroupItem(ListItem):
    def __init__(self, name: str, count: int):
        self.group_name=name; self.count=count
        super().__init__()
    def compose(self) -> ComposeResult:
        yield Label(f"👥 {self.group_name}")
        yield Label(f"   ({self.count} 成员)", classes="sub-text")

class MainScreen(Screen):
    BINDINGS=[
        Binding("ctrl+q","quit","退出",priority=True),
        Binding("f1","show_help","帮助",priority=True),
        Binding("f2","settings","设置",priority=True),
        Binding("ctrl+d","discover","发现",priority=True),
        Binding("ctrl+p","phrase","常用语",priority=True),
        Binding("ctrl+e","emote","表情",priority=True),
        Binding("ctrl+f","file","发文件",priority=True),
        Binding("ctrl+o","ocr","OCR",priority=True),
        Binding("f3","grp_new","新建组"),
        Binding("f4","grp_del","删除组"),
        Binding("f5","grp_ren","重命名"),
        Binding("f6","grp_add","加成员"),
        Binding("f7","grp_rem","删成员"),
    ]

    target_id = reactive("")
    target_display = reactive("未选择")
    target_status = reactive("-")
    target_ip = reactive("-.-.-.-")

    def __init__(self, client: ClientAdapter):
        super().__init__(); self.client = client

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
            with Container(id='sidebar'):
                with TabbedContent(initial='tab_users'):
                    with TabPane('用户', id='tab_users'):
                        yield ListView(id='user_list')
                        with Vertical(id='net_info_box'):
                            yield Label('本机: -', id='lbl_local_ip')
                            yield Label('广播: -', id='lbl_bcast')
                            yield Label('在线: 0', id='lbl_online_count')
                    with TabPane('组', id='tab_groups'):
                        yield ListView(id='group_list')
                        with Vertical(id='net_info_box'):
                            yield Label('请使用下方 F3-F7 快捷键', classes='group-hint')
                            yield Label('管理选中的群组', classes='group-hint')
            with Container(id='chat_container'):
                yield Label('未选择', id='chat_header')
                yield RichLog(id='chat_log', markup=True, wrap=True)
                with Container(id='chat_input_container'):
                    yield ChatTextArea(id='msg_input')
        yield Footer()

    def on_mount(self):
        self.set_interval(2.0, self.refresh_ui)
        self.query_one('#msg_input').focus()
        # 首次进入立即刷新一次，避免等待定时器
        self.refresh_ui()

    # incoming
    def post_backend_message(self, sender: str, ip: str, text: str, is_system: bool=False):
        ts = time.strftime('%H:%M:%S')
        style = 'bold yellow' if is_system else 'bold green'
        pre = '系统' if is_system else f'{sender}@{ip}'
        self.query_one('#chat_log', RichLog).write(f"[dim]{ts}[/] [{style}]{pre}[/]: {text}")

    # selection
    def on_list_view_selected(self, event: ListView.Selected):
        item = event.item
        if isinstance(item, UserItem):
            self.target_id = item.ip
            self.target_display = item.username if item.ip != 'all' else '所有在线'
            self.target_status = item.status
            self.target_ip = item.ip
        elif isinstance(item, GroupItem):
            self.target_id = f'group:{item.group_name}'
            self.target_display = f'群组:{item.group_name}'
            self.target_status = '-'
            self.target_ip = '-'
        self.update_header(); self.query_one('#msg_input').focus()

    def update_header(self):
        txt = '未选择' if not self.target_id else f"{self.target_display} [{self.target_status}] ({self.target_ip})"
        self.query_one('#chat_header', Label).update(txt)

    # refresh
    def refresh_ui(self):
        try:
            zcli = self.client.zcli
            if not zcli:
                return
            # users
            ulist = self.query_one('#user_list', ListView)
            idx = ulist.index
            new_items: List[ListItem] = []
            new_items.append(UserItem('所有在线 (广播)', 'all', 'Broadcast', 'online'))
            nodes = zcli.registry.list_nodes()
            local = zcli.registry.get_by_ip(zcli.local_ip)
            if local is not None:
                new_items.append(UserItem(local.username, local.ip, local.hostname, 'online', is_local=True))
            else:
                new_items.append(UserItem(zcli.username or 'Me', zcli.local_ip, zcli.hostname, 'online', is_local=True))
            for n in sorted(nodes, key=lambda x: x.ip):
                if n.ip == zcli.local_ip:
                    continue
                new_items.append(UserItem(n.username, n.ip, n.hostname, getattr(n, 'status', 'online')))
            ulist.clear()
            for i in new_items:
                ulist.append(i)
            if idx is not None and idx < len(ulist.children):
                ulist.index = idx
            elif ulist.children:
                ulist.index = 0
            # info
            self.query_one('#lbl_local_ip', Label).update(f'本机: {zcli.local_ip}')
            bcast = getattr(zcli.transport, '_broadcast_addr', '-')
            self.query_one('#lbl_bcast', Label).update(f'广播: {bcast}')
            self.query_one('#lbl_online_count', Label).update(f'在线: {len(nodes)}')
            # groups
            glist = self.query_one('#group_list', ListView)
            gidx = glist.index
            glist.clear()
            for g, m in sorted(zcli.groups.items()):
                glist.append(GroupItem(g, len(m)))
            if gidx is not None and gidx < len(glist.children):
                glist.index = gidx
        except Exception as e:
            try:
                self.query_one('#chat_log', RichLog).write(f'[red]刷新失败: {e}[/]')
            except Exception:
                pass

    # actions
    def action_quit(self): self.app.request_quit()
    def action_settings(self): self.app.show_settings()
    def action_show_help(self): self.app.show_help()

    def action_discover(self):
        def _do(ip): self.client.discover(ip if ip else None); self.query_one('#chat_log', RichLog).write('[dim]已发送发现广播...[/]')
        self.app.push_screen(InputModal('发现用户','输入IP (留空则广播)', _do))

    def action_phrase(self):
        phrases = ['在吗？','收到。','稍等一下','方便发个文件吗？','谢谢！']
        try:
            if os.path.exists('quick_texts.txt'):
                lines=[l.strip() for l in open('quick_texts.txt','r',encoding='utf-8') if l.strip()]
                if lines: phrases = lines
        except Exception: pass
        def _pick(s):
            ta = self.query_one('#msg_input', TextArea); ta.insert(s); ta.focus()
        self.app.push_screen(SelectionModal('选择常用语', phrases, _pick))

    def action_emote(self):
        edir = self.client.zcli.emotes_dir if self.client.zcli else 'emotes'
        os.makedirs(edir, exist_ok=True)
        files=[f for f in os.listdir(edir) if f.lower().endswith(('.png','.jpg','.gif'))]
        if not files:
            self.query_one('#chat_log', RichLog).write('[yellow]emotes 目录下无图片[/]'); return
        def _send(name):
            if not self.target_id: return
            self.client.zcli.cmd_file_send(self.target_id, os.path.join(edir, name))
            self.query_one('#chat_log', RichLog).write(f"[dim]已发送表情: {name}[/]")
        self.app.push_screen(SelectionModal('选择表情', files, _send))

    def action_file(self):
        def _pick(path):
            if not self.target_id: self.query_one('#chat_log', RichLog).write('[red]未选择目标[/]'); return
            if os.path.isdir(path): return
            self.client.zcli.cmd_file_send(self.target_id, path)
            self.query_one('#chat_log', RichLog).write(f"[dim]正在发送文件: {path}[/]")
        self.app.push_screen(FilePickerModal('选择文件发送', _pick))

    def action_ocr(self):
        def _run(path):
            if not os.path.isfile(path): return
            self.query_one('#chat_log', RichLog).write(f"[dim]识别中: {os.path.basename(path)}...[/]")
            self.app.run_ocr_worker(path)
        self.app.push_screen(FilePickerModal('选择图片识别', _run))

    def action_grp_new(self):
        def _create(n):
            if n: self.client.zcli.cmd_group(n, '-add', None); self.refresh_ui()
        self.app.push_screen(InputModal('新建群组','输入组名', _create))
    def action_grp_del(self):
        if self.target_id.startswith('group:'):
            g=self.target_id.split(':',1)[1]; self.client.zcli.cmd_group(g,'-delete',None); self.target_id=''; self.update_header(); self.refresh_ui()
        else:
            self.app.push_screen(MessageModal('提示','请先在列表中选中一个群组'))
    def action_grp_ren(self):
        if self.target_id.startswith('group:'):
            old=self.target_id.split(':',1)[1]
            def _ren(n):
                if n: self.client.zcli.cmd_group(old,'-rename',n); self.refresh_ui()
            self.app.push_screen(InputModal('重命名','新名称', _ren))
        else:
            self.app.push_screen(MessageModal('提示','请先在列表中选中一个群组'))
    def action_grp_add(self):
        if self.target_id.startswith('group:'):
            g=self.target_id.split(':',1)[1]
            def _add(m):
                if m: self.client.zcli.cmd_group(g,'-add',m); self.refresh_ui()
            self.app.push_screen(InputModal(f'添加到 {g}','用户名或IP', _add))
        else:
            self.app.push_screen(MessageModal('提示','请先在列表中选中一个群组'))
    def action_grp_rem(self):
        if self.target_id.startswith('group:'):
            g=self.target_id.split(':',1)[1]
            def _rem(m):
                if m: self.client.zcli.cmd_group(g,'-delete',m); self.refresh_ui()
            self.app.push_screen(InputModal(f'从 {g} 移除','用户名或IP', _rem))
        else:
            self.app.push_screen(MessageModal('提示','请先在列表中选中一个群组'))
