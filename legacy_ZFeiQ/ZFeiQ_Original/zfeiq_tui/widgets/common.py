from __future__ import annotations
import os
from typing import Callable, List
from textual import on, events
from textual.app import ComposeResult
from textual.message import Message
from textual.screen import ModalScreen
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.widgets import Label, DirectoryTree, Input, ListView, ListItem, TextArea, Button, Select

class ChatTextArea(TextArea):
    class Submitted(Message):
        def __init__(self, value: str):
            self.value = value
            super().__init__()

    async def _on_key(self, event: events.Key) -> None:
        if event.key == "enter":
            # Textual Key event exposes shift/ctrl/alt as booleans
            if getattr(event, "shift", False):
                self.insert("\n")
            else:
                try:
                    event.prevent_default()
                except Exception:
                    pass
                try:
                    event.stop()
                except Exception:
                    pass
                self.post_message(self.Submitted(self.text))
                self.text = ""
        else:
            await super()._on_key(event)

class MessageModal(ModalScreen):
    BINDINGS = [Binding("enter","close","确定",priority=True), Binding("escape","close","关闭",priority=True)]
    def __init__(self, title: str, message: str):
        super().__init__(); self.box_title=title; self.message=message
    def compose(self) -> ComposeResult:
        with Container(classes="modal-box modal-sm"):
            yield Label(self.box_title, classes="modal-title")
            yield Label(self.message, classes="modal-message")
            yield Label("Enter 确认 / Esc 关闭", classes="key-hint")
    def action_close(self): self.dismiss()

class FilePickerModal(ModalScreen):
    BINDINGS = [Binding("escape","cancel","取消",priority=True)]
    def __init__(self, title: str, select_callback: Callable[[str],None]):
        super().__init__(); self.picker_title=title; self.callback=select_callback
    def compose(self) -> ComposeResult:
        with Container(classes="modal-box modal-md"):
            yield Label(self.picker_title, classes="modal-title")
            yield DirectoryTree(os.getcwd(), id="file_tree")
            yield Label("Enter 选择 / Esc 取消", classes="key-hint")
    @on(DirectoryTree.FileSelected)
    def on_file_selected(self, event: DirectoryTree.FileSelected):
        if os.path.isfile(event.path): self.callback(event.path)
        self.dismiss()
    def action_cancel(self): self.dismiss()

class InputModal(ModalScreen):
    BINDINGS=[Binding("enter","confirm","确定",priority=True), Binding("escape","cancel","取消",priority=True)]
    def __init__(self, title: str, placeholder: str, callback: Callable[[str],None]):
        super().__init__(); self.title_text=title; self.ph=placeholder; self.callback=callback
    def compose(self) -> ComposeResult:
        with Container(classes="modal-box modal-sm"):
            yield Label(self.title_text, classes="modal-title")
            yield Input(placeholder=self.ph, id="modal_input")
            yield Label("Enter 确定 / Esc 取消", classes="key-hint")
    def on_mount(self): self.query_one("#modal_input").focus()
    def action_confirm(self): self.callback(self.query_one("#modal_input").value); self.dismiss()
    @on(Input.Submitted)
    def submit(self): self.action_confirm()
    def action_cancel(self): self.dismiss()

class SelectionModal(ModalScreen):
    BINDINGS=[Binding("escape","close","返回",priority=True)]
    def __init__(self, title:str, items:List[str], callback:Callable[[str],None]):
        super().__init__(); self.title_text=title; self.items=items; self.callback=callback
    def compose(self)->ComposeResult:
        with Container(classes="modal-box modal-md"):
            yield Label(self.title_text, classes="modal-title")
            yield ListView(*[ListItem(Label(i)) for i in self.items], id="sel_list")
            yield Label("Enter 选择 / Esc 返回", classes="key-hint")
    @on(ListView.Selected)
    def on_selected(self, event: ListView.Selected):
        label = event.item.query_one(Label)
        if label: self.callback(str(label.renderable))
        self.dismiss()

class EncryptSettingsModal(ModalScreen):
    BINDINGS=[Binding("enter","confirm","保存",priority=True), Binding("escape","cancel","取消",priority=True)]
    def __init__(self, mode: str, cipher_on: bool, edtag_on: bool, callback: Callable[[str,bool,bool],None]):
        super().__init__()
        self._mode = mode if mode in ("off","on","strict") else "on"
        self._cipher = bool(cipher_on)
        self._edtag = bool(edtag_on)
        self._callback = callback

    def compose(self) -> ComposeResult:
        with Container(classes="modal-box modal-md"):
            yield Label("加密设置", classes="modal-title")
            yield Label("模式", classes="modal-label")
            yield Select((("关闭","off"),("启用","on"),("严格","strict")), value=self._mode, id="sel_mode")
            yield Label("显示原始密文 (cipher)", classes="modal-label")
            yield Select((("关闭","off"),("开启","on")), value="on" if self._cipher else "off", id="sel_cipher")
            yield Label("显示 [E-D OK]", classes="modal-label")
            yield Select((("关闭","off"),("开启","on")), value="on" if self._edtag else "off", id="sel_edtag")
            with Horizontal():
                yield Button("保存", id="btn_save")
                yield Button("取消", id="btn_cancel")
            yield Label("回车保存 / Esc 取消", classes="key-hint")

    def on_mount(self):
        try:
            self.query_one("#sel_mode", Select).focus()
        except Exception:
            pass

    def action_confirm(self):
        try:
            self._submit()
        finally:
            self.dismiss()

    def action_cancel(self):
        self.dismiss()

    @on(Button.Pressed, "#btn_save")
    def _on_save(self):
        self.action_confirm()

    @on(Button.Pressed, "#btn_cancel")
    def _on_cancel(self):
        self.action_cancel()

    def _submit(self):
        try:
            mode = self.query_one("#sel_mode", Select).value or "on"
            cipher = self.query_one("#sel_cipher", Select).value == "on"
            edtag = self.query_one("#sel_edtag", Select).value == "on"
            self._callback(mode, cipher, edtag)
        except Exception:
            pass
