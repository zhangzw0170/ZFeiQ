from PyQt5.QtWidgets import (QDialog, QHBoxLayout, QVBoxLayout, QListWidget, QListWidgetItem,
                             QPushButton, QLabel, QSplitter, QWidget, QInputDialog, QMessageBox)
from PyQt5.QtCore import Qt
from gui.lang import L
from gui.styles import get_color

class GroupManagerDialog(QDialog):
    """Minimal group manager dialog (30/70 split).

    Left: list of groups with checkboxes to toggle visibility in user list.
    Right: five action buttons wired to Bridge helpers:
      - New group
      - Delete group
      - Rename group
      - Add member
      - Remove member

    The dialog uses the parent (ChatPage) to access `bridge`.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(L('btn_group'))
        self.setMinimumSize(560, 320)
        self.parent = parent
        # Parent is expected to be ChatPage instance with `.bridge`
        self.bridge = getattr(parent, 'bridge', None)
        self._current_theme = getattr(parent, '_current_theme', 'light')
        self._init_ui()
        # connect signals for language/theme changes if available
        try:
            if self.bridge is not None:
                self.bridge.sig_lang_changed.connect(self._on_lang_changed)
                self.bridge.sig_theme_changed.connect(self._on_theme_changed)
        except Exception:
            pass
        self._refresh()

    def _init_ui(self):
        main = QHBoxLayout(self)
        main.setContentsMargins(8,8,8,8)
        main.setSpacing(8)

        splitter = QSplitter(Qt.Horizontal)
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0,0,0,0)
        left_layout.setSpacing(6)

        self.lbl_left = QLabel(L('group_prefix'))
        left_layout.addWidget(self.lbl_left)

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.SingleSelection)
        left_layout.addWidget(self.list_widget)

        splitter.addWidget(left_widget)
        left_widget.setMinimumWidth(160)
        left_widget.setMaximumWidth(320)

        # right panel (buttons + members list)
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0,0,0,0)
        right_layout.setSpacing(8)

        # Top row: New / Delete / Rename (in one line)
        top_row = QWidget()
        top_row_layout = QHBoxLayout(top_row)
        top_row_layout.setContentsMargins(0,0,0,0)
        top_row_layout.setSpacing(6)

        self.btn_new = QPushButton(L('group_new') if L('group_new', None) else 'New Group')
        self.btn_delete = QPushButton(L('group_delete') if L('group_delete', None) else 'Delete Group')
        self.btn_rename = QPushButton(L('group_rename') if L('group_rename', None) else 'Rename Group')
        for b in (self.btn_new, self.btn_delete, self.btn_rename):
            b.setMinimumHeight(36)
            top_row_layout.addWidget(b)

        right_layout.addWidget(top_row)

        # Middle: members list (fills most space)
        self.member_list = QListWidget()
        self.member_list.setSelectionMode(QListWidget.SingleSelection)
        right_layout.addWidget(self.member_list, 1)

        # Bottom row: Add / Remove (in one line)
        bottom_row = QWidget()
        bottom_row_layout = QHBoxLayout(bottom_row)
        bottom_row_layout.setContentsMargins(0,0,0,0)
        bottom_row_layout.setSpacing(6)

        self.btn_add = QPushButton(L('group_add_member') if L('group_add_member', None) else 'Add Member')
        self.btn_remove = QPushButton(L('group_remove_member') if L('group_remove_member', None) else 'Remove Member')
        for b in (self.btn_add, self.btn_remove):
            b.setMinimumHeight(36)
            bottom_row_layout.addWidget(b)

        right_layout.addWidget(bottom_row)

        splitter.addWidget(right_widget)

        # 2:3 split
        try:
            splitter.setStretchFactor(0, 2)
            splitter.setStretchFactor(1, 3)
        except Exception:
            splitter.setSizes([200, 300])
        main.addWidget(splitter)

        # wire up buttons
        self.btn_new.clicked.connect(self._on_new)
        self.btn_delete.clicked.connect(self._on_delete)
        self.btn_rename.clicked.connect(self._on_rename)
        self.btn_add.clicked.connect(self._on_add_member)
        self.btn_remove.clicked.connect(self._on_remove_member)

        # checkbox toggle handled by itemChanged
        self.list_widget.itemChanged.connect(self._on_item_toggled)
        # when selection changes, refresh members
        self.list_widget.currentItemChanged.connect(lambda cur, prev: self._refresh_members())

        self._apply_theme(self._current_theme)

    def _apply_theme(self, theme_code: str):
        self._current_theme = theme_code or 'light'
        try:
            bg = get_color('BACKGROUND_PANEL', self._current_theme)
            txt = get_color('PRIMARY_TEXT', self._current_theme)
            self.setStyleSheet(f"background: {bg}; color: {txt};")
        except Exception:
            pass

    def _tpl(self, key: str, **kwargs) -> str:
        """Fetch localized template and format with kwargs. Safe on formatting errors."""
        try:
            t = L(key)
        except Exception:
            t = key
        try:
            return t.format(**kwargs)
        except Exception:
            return t

    def _on_lang_changed(self, lang_code: str):
        # update visible labels/buttons
        try:
            self.setWindowTitle(L('btn_group'))
            self.lbl_left.setText(L('group_prefix'))
            self.btn_new.setText(L('group_new'))
            self.btn_delete.setText(L('group_delete'))
            self.btn_rename.setText(L('group_rename'))
            self.btn_add.setText(L('group_add_member'))
            self.btn_remove.setText(L('group_remove_member'))
        except Exception:
            pass

    def _on_theme_changed(self, theme_code: str):
        self._apply_theme(theme_code)

    def _refresh(self):
        # reload groups from bridge
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        groups = []
        try:
            groups = self.bridge.get_groups() if self.bridge else []
        except Exception:
            groups = []
        # groups: list of (name, count)
        visible = None
        try:
            visible = getattr(self.bridge.core, 'visible_groups', None)
        except Exception:
            visible = None

        for name, count in groups:
            item = QListWidgetItem(f"{name} ({count})")
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            checked = Qt.Checked if (visible is None or name in visible) else Qt.Unchecked
            item.setCheckState(checked)
            # store raw name
            item.setData(Qt.UserRole, name)
            self.list_widget.addItem(item)

        self.list_widget.blockSignals(False)

        # select first item by default and refresh members
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)
            self._refresh_members()

    def _get_selected_group(self):
        it = self.list_widget.currentItem()
        if not it: return None
        return it.data(Qt.UserRole)

    def _refresh_members(self):
        """Refresh member_list for currently selected group."""
        self.member_list.clear()
        name = self._get_selected_group()
        if not name:
            return
        try:
            members = self.bridge.get_group_members(name) if self.bridge else []
        except Exception:
            members = []
        for m in members:
            item = QListWidgetItem(m)
            self.member_list.addItem(item)

    def _on_item_toggled(self, item: QListWidgetItem):
        # toggle visibility
        name = item.data(Qt.UserRole)
        visible = item.checkState() == Qt.Checked
        try:
            if self.bridge:
                self.bridge.set_group_visibility(name, visible)
        except Exception:
            pass

    def _on_new(self):
        text, ok = QInputDialog.getText(self, L('group_new') or 'New Group', L('enter_new_name') or 'New group name:')
        if ok and text:
            if self.bridge and self.bridge.create_group(text):
                self._refresh()
            else:
                QMessageBox.warning(self, L('group_new') or 'New Group', L('op_failed') or 'Operation failed')

    def _on_delete(self):
        name = self._get_selected_group()
        if not name:
            QMessageBox.information(self, L('group_delete') or 'Delete Group', L('select_group') or 'Select a group first')
            return
        msg = self._tpl('confirm_delete_group', name=name)
        ok = QMessageBox.question(self, L('group_delete') or 'Delete Group', msg)
        if ok != QMessageBox.Yes:
            return
        try:
            if self.bridge and self.bridge.delete_group(name):
                self._refresh()
            else:
                QMessageBox.warning(self, L('group_delete') or 'Delete Group', L('op_failed') or 'Operation failed')
        except Exception:
            QMessageBox.warning(self, L('group_delete') or 'Delete Group', L('op_failed') or 'Operation failed')

    def _on_rename(self):
        name = self._get_selected_group()
        if not name:
            QMessageBox.information(self, L('group_rename') or 'Rename Group', L('select_group') or 'Select a group first')
            return
        text, ok = QInputDialog.getText(self, L('group_rename') or 'Rename Group', L('enter_new_name') or 'New name:', text=name)
        if ok and text and text != name:
            if self.bridge and self.bridge.rename_group(name, text):
                self._refresh()
            else:
                QMessageBox.warning(self, L('group_rename') or 'Rename Group', L('op_failed') or 'Operation failed')

    def _on_add_member(self):
        name = self._get_selected_group()
        if not name:
            QMessageBox.information(self, L('group_add_member') or 'Add Member', L('select_group') or 'Select a group first')
            return
        text, ok = QInputDialog.getText(self, L('group_add_member') or 'Add Member', L('enter_member') or 'Username to add:')
        if ok and text:
            if self.bridge and self.bridge.add_to_group(name, text):
                self._refresh()
            else:
                QMessageBox.warning(self, L('group_add_member') or 'Add Member', L('op_failed') or 'Operation failed')

    def _on_remove_member(self):
        name = self._get_selected_group()
        if not name:
            QMessageBox.information(self, L('group_remove_member') or 'Remove Member', L('select_group') or 'Select a group first')
            return
        # Prefer deleting the currently selected member in the member list.
        cur = self.member_list.currentItem()
        if cur is not None:
            username = cur.text()
            msg = self._tpl('confirm_remove_member', username=username, name=name)
            ok = QMessageBox.question(self, L('group_remove_member') or 'Remove Member', msg)
            if ok == QMessageBox.Yes:
                try:
                    if self.bridge and self.bridge.remove_from_group(name, username):
                        # refresh only members to keep group selection
                        self._refresh_members()
                    else:
                        QMessageBox.warning(self, L('group_remove_member') or 'Remove Member', L('op_failed') or 'Operation failed')
                except Exception:
                    QMessageBox.warning(self, L('group_remove_member') or 'Remove Member', L('op_failed') or 'Operation failed')
            return

        # Fallback: ask for username if no member is selected
        text, ok = QInputDialog.getText(self, L('group_remove_member') or 'Remove Member', L('enter_member') or 'Username to remove:')
        if ok and text:
            if self.bridge and self.bridge.remove_from_group(name, text):
                # refresh members view
                self._refresh_members()
            else:
                QMessageBox.warning(self, L('group_remove_member') or 'Remove Member', L('op_failed') or 'Operation failed')
