from __future__ import annotations
import os
from typing import Callable, List
from textual import on, events
from textual.app import ComposeResult
from textual.message import Message
from textual.screen import ModalScreen
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.widgets import Label, DirectoryTree, Input, ListView, ListItem, TextArea

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
