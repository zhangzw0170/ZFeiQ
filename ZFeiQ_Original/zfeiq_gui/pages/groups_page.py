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

        top_row.addWidget(self.member_filter, 1)
        layout.addLayout(top_row)

        self.group_cards = QtWidgets.QListWidget()
        self.group_cards.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.group_cards.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        layout.addWidget(self.group_cards, 3)

        # Row for group operations: New / Delete / Rename (evenly distributed)
        grp_ctrl = QtWidgets.QHBoxLayout()
        grp_ctrl.setSpacing(8)
        self.btn_new_group = _mk_nav_btn(t["group_new"])
        self.btn_delete_group = _mk_nav_btn(t.get("group_delete", "删除分组"))
        self.btn_rename = _mk_nav_btn(t["group_rename"])
        grp_ctrl.addWidget(self.btn_new_group, 1)
        grp_ctrl.addWidget(self.btn_delete_group, 1)
        grp_ctrl.addWidget(self.btn_rename, 1)
        layout.addLayout(grp_ctrl)
        # Member input row: single line input
        mem_input_row = QtWidgets.QHBoxLayout()
        mem_input_row.setSpacing(8)
        self.member_edit = QtWidgets.QLineEdit()
        self.member_edit.setPlaceholderText(t["member_ph"])
        mem_input_row.addWidget(self.member_edit, 1)
        layout.addLayout(mem_input_row)

        # Member action row: Add / Remove buttons (evenly distributed)
        mem_buttons_row = QtWidgets.QHBoxLayout()
        mem_buttons_row.setSpacing(8)
        self.btn_add = _mk_nav_btn(t.get("member_add", "+"))
        self.btn_del = _mk_nav_btn(t.get("member_del", "-"))
        mem_buttons_row.addWidget(self.btn_add, 1)
        mem_buttons_row.addWidget(self.btn_del, 1)
        layout.addLayout(mem_buttons_row)

        try:
            self.group_cards.itemDoubleClicked.connect(lambda item: self.sigEnterChat.emit(item.data(QtCore.Qt.UserRole)))
        except Exception:
            pass

        def _create_group():
            # base name for auto-created groups comes from translations when available
            base = t.get("group_new_prefix", t.get("group_new", "New Group") + " ")
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

            # Notify listeners to persist/create the new group (no members yet)
            try:
                # emit empty username to indicate creation-only
                self.sigAdd.emit(group_name, "")
            except Exception:
                pass

        # connect created controls
        self.btn_new_group.clicked.connect(_create_group)
        self.btn_rename.clicked.connect(self._prompt_rename)
        # delete group -> emit sigRemove with empty username to indicate deletion
        try:
            self.btn_delete_group.clicked.connect(lambda: self.sigRemove.emit(self._current_group() or "", ""))
        except Exception:
            pass

        self.btn_add.clicked.connect(lambda: self._apply_member_edit(self.member_edit.text().strip(), self.sigAdd))
        self.btn_del.clicked.connect(lambda: self._apply_member_edit(self.member_edit.text().strip(), self.sigRemove))

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
            try:
                self.btn_delete_group.setText(translations.get("group_delete", "删除分组"))
            except Exception:
                pass
            try:
                self.btn_add.setText(translations.get("member_add", "添加成员"))
                self.btn_del.setText(translations.get("member_del", "移除成员"))
            except Exception:
                pass
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
            # Prevent renaming to an existing group name
            existing = set(getattr(self, "_cached_groups", {}).keys())
            if new_name in existing:
                try:
                    msg = t.get("group_rename_conflict", "组名已存在，请换一个名称。")
                    QtWidgets.QMessageBox.warning(self, t.get("error", "错误"), msg)
                except Exception:
                    pass
                return
            self.sigRename.emit(old, new_name)

    def update_groups(self, groups: Dict[str, set]) -> None:
        # Replace local cache with the authoritative groups dict from backend.
        # Previously this method merged local and remote which caused deleted
        # groups to persist in the UI. Use the backend-provided snapshot directly.
        self._cached_groups = {name: set(members) for name, members in (groups or {}).items()}
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
        # Members are displayed inside each group item in `self.group_cards`.
        # This method is kept as a no-op to avoid referencing the removed
        # `members_list` widget. UI updates happen in `update_groups()` which
        # rebuilds the group_cards contents.
        return

    def _current_group(self) -> str:
        item = self.group_cards.currentItem()
        if item:
            return item.data(QtCore.Qt.UserRole)
        return ""
