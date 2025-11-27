from __future__ import annotations

from typing import Dict

from PyQt5 import QtCore, QtWidgets

from ..widgets import NavigationButton


class GroupsPage(QtWidgets.QWidget):
    """Group management helper with create/rename/member tools."""

    sigAdd = QtCore.pyqtSignal(str, str)
    sigRemove = QtCore.pyqtSignal(str, str)
    sigEnterChat = QtCore.pyqtSignal(str)
    sigRename = QtCore.pyqtSignal(str, str)

    def __init__(self, lang: str = "zhCN"):
        super().__init__()
        from zfeiq_gui.lang import get_translations
        self._translations = get_translations(lang)
        self._cached_groups: Dict[str, set] = {}
        self._build()

    def _build(self) -> None:
        t = self._translations
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        top_row = QtWidgets.QHBoxLayout()
        self.member_filter = QtWidgets.QLineEdit()
        self.member_filter.setPlaceholderText(t["group_search_ph"])

        def _mk_nav_btn(text: str) -> NavigationButton:
            btn = NavigationButton(text)
            btn.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Fixed)
            return btn

        self.btn_new_group = _mk_nav_btn(t["group_new"])
        self.btn_rename = _mk_nav_btn(t["group_rename"])
        top_row.addWidget(self.member_filter, 1)
        top_row.addWidget(self.btn_new_group)
        top_row.addWidget(self.btn_rename)
        layout.addLayout(top_row)

        self.group_cards = QtWidgets.QListWidget()
        self.group_cards.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.group_cards.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        layout.addWidget(self.group_cards, 3)

        bottom = QtWidgets.QVBoxLayout()
        bottom.setSpacing(6)
        self.members_list = QtWidgets.QListWidget()
        self.members_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        bottom.addWidget(self.members_list, 2)
        self.member_edit = QtWidgets.QLineEdit()
        self.member_edit.setPlaceholderText(t["member_ph"])
        bottom.addWidget(self.member_edit)
        ctrl = QtWidgets.QHBoxLayout()
        btn_add = NavigationButton("+")
        btn_del = NavigationButton("-")
        self.btn_enter_chat = NavigationButton("=>")
        ctrl.addStretch(1)
        ctrl.addWidget(btn_add)
        ctrl.addWidget(btn_del)
        ctrl.addWidget(self.btn_enter_chat)
        bottom.addLayout(ctrl)
        layout.addLayout(bottom, 2)

        try:
            self.group_cards.itemDoubleClicked.connect(lambda item: self.sigEnterChat.emit(item.data(QtCore.Qt.UserRole)))
        except Exception:
            pass
        try:
            self.btn_enter_chat.clicked.connect(lambda: self.sigEnterChat.emit(self._current_group() or ""))
        except Exception:
            pass

        def _create_group():
            base = "New Group "
            idx = 1
            names = set(self._cached_groups.keys())
            while f"{base}{idx}" in names:
                idx += 1
            group_name = f"{base}{idx}"
            self._cached_groups[group_name] = set()
            self.update_groups(self._cached_groups)
            try:
                for row in range(self.group_cards.count()):
                    item = self.group_cards.item(row)
                    if item and item.data(QtCore.Qt.UserRole) == group_name:
                        self.group_cards.setCurrentRow(row)
                        break
            except Exception:
                pass

        self.btn_new_group.clicked.connect(_create_group)
        self.btn_rename.clicked.connect(self._prompt_rename)

        btn_add.clicked.connect(lambda: self._apply_member_edit(self.member_edit.text().strip(), self.sigAdd))
        btn_del.clicked.connect(lambda: self._apply_member_edit(self.member_edit.text().strip(), self.sigRemove))

    def _apply_member_edit(self, username: str, signal):
        group = self._current_group()
        if not group or not username:
            return
        signal.emit(group, username)
        self.member_edit.clear()

    def apply_language(self, translations: Dict[str, str]) -> None:
        self._translations = translations
        try:
            self.member_filter.setPlaceholderText(translations.get("group_search_ph", "搜索组名/成员…"))
            self.member_edit.setPlaceholderText(translations.get("member_ph", "添加/移除成员…"))
            self.btn_new_group.setText(translations.get("group_new", "新建分组"))
            self.btn_rename.setText(translations.get("group_rename", "重命名"))
        except Exception:
            pass

    def _prompt_rename(self):
        old = self._current_group()
        if not old:
            return
        t = getattr(self, "_translations", {})
        new_name, ok = QtWidgets.QInputDialog.getText(
            self,
            t["group_rename"],
            t["group_new_name"],
            text=old,
        )
        new_name = (new_name or "").strip()
        if ok and new_name and new_name != old:
            self.sigRename.emit(old, new_name)

    def update_groups(self, groups: Dict[str, set]) -> None:
        local_groups = getattr(self, "_cached_groups", {}) or {}
        merged = dict(local_groups)
        for name, members in (groups or {}).items():
            merged[name] = set(members)
        self._cached_groups = merged
        current = self._current_group()
        self.group_cards.blockSignals(True)
        self.group_cards.clear()
        for group_name in sorted(self._cached_groups.keys()):
            members = list(self._cached_groups.get(group_name, []))
            header = f"{group_name} ({len(members)}/{len(members)})"
            lines = [header]
            for idx, member in enumerate(members):
                prefix = "┣" if idx < len(members) - 1 else "┗"
                lines.append(f"{prefix} {member}")
            text = "\n".join(lines)
            item = QtWidgets.QListWidgetItem(text)
            item.setData(QtCore.Qt.UserRole, group_name)
            item.setTextAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            try:
                font = item.font()
                font.setPointSize(font.pointSize() + 1)
                item.setFont(font)
            except Exception:
                pass
            self.group_cards.addItem(item)
        if current:
            for row in range(self.group_cards.count()):
                item = self.group_cards.item(row)
                if item and item.data(QtCore.Qt.UserRole) == current:
                    self.group_cards.setCurrentRow(row)
                    break
        self.group_cards.blockSignals(False)
        self._update_members()

    def _update_members(self) -> None:
        group_name = self._current_group()
        members = sorted(list(self._cached_groups.get(group_name, []))) if group_name else []
        self.members_list.clear()
        for member in members:
            item = QtWidgets.QListWidgetItem(member)
            try:
                font = item.font()
                font.setPointSize(font.pointSize() + 1)
                item.setFont(font)
            except Exception:
                pass
            self.members_list.addItem(item)

    def _current_group(self) -> str:
        item = self.group_cards.currentItem()
        if item:
            return item.data(QtCore.Qt.UserRole)
        return ""
