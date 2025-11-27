from __future__ import annotations

import os
import shutil
from typing import Dict, Optional

from PyQt5 import QtCore, QtGui, QtWidgets
from zfeiq_gui.lang import t


class EmotesPage(QtWidgets.QWidget):
    """Reusable grid picker for custom emoji packs."""

    sigSend = QtCore.pyqtSignal(str)

    def __init__(self, default_dir: Optional[str] = None, core=None, parent=None):
        super().__init__(parent)
        self.core = core
        self._translations = t
        # Project root — module location-based
        PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        self._dir = default_dir or os.path.join(PROJECT_ROOT, "emotes")
        os.makedirs(self._dir, exist_ok=True)
        self._build()
        self._load_emotes()

    def _build(self) -> None:
        t_local = self._translations
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        dir_row = QtWidgets.QHBoxLayout()
        self.dir_edit = QtWidgets.QLineEdit(self._dir)
        self.btn_pick_dir = QtWidgets.QPushButton(t_local["emotes_pick_dir"])
        self.btn_add_emote = QtWidgets.QPushButton(t_local["emotes_add"])
        self.btn_back = QtWidgets.QPushButton(t_local["emotes_back"])
        for button in (self.btn_pick_dir, self.btn_add_emote, self.btn_back):
            button.setFixedHeight(button.fontMetrics().height() + 12)
        dir_row.addWidget(self.dir_edit, 1)
        dir_row.addWidget(self.btn_pick_dir)
        dir_row.addWidget(self.btn_add_emote)
        dir_row.addWidget(self.btn_back)
        layout.addLayout(dir_row)

        self.list = QtWidgets.QListWidget()
        self.list.setViewMode(QtWidgets.QListView.IconMode)
        self.list.setIconSize(QtCore.QSize(64, 64))
        self.list.setResizeMode(QtWidgets.QListView.Adjust)
        self.list.setMovement(QtWidgets.QListView.Static)
        self.list.setSpacing(8)
        layout.addWidget(self.list, 1)

        send_row = QtWidgets.QHBoxLayout()
        self.btn_send = QtWidgets.QPushButton(t_local["emotes_send"])
        self.btn_send.setFixedHeight(self.btn_send.fontMetrics().height() + 12)
        send_row.addStretch()
        send_row.addWidget(self.btn_send)
        layout.addLayout(send_row)

        self.btn_pick_dir.clicked.connect(self._pick_dir)
        self.btn_add_emote.clicked.connect(self._add_emotes)
        self.btn_send.clicked.connect(self._send_selected)
        self.list.itemDoubleClicked.connect(lambda _: self._send_selected())

    def apply_language(self, translations: Dict[str, str]) -> None:
        try:
            self.btn_back.setText(translations['emotes_back'])
            self.btn_send.setText(translations['emotes_send'])
            self.btn_pick_dir.setText(translations['emotes_pick_dir'])
            self.btn_add_emote.setText(translations['emotes_add'])
            self.btn_back.setFixedHeight(self.btn_back.fontMetrics().height() + 12)
        except Exception:
            pass

    def _pick_dir(self) -> None:
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "选择表情目录")
        if directory:
            self._dir = directory
            self.dir_edit.setText(directory)
            self._load_emotes()

    def _add_emotes(self) -> None:
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(self, "选择图片作为表情", filter="Images (*.png *.jpg *.jpeg *.gif)")
        if not files:
            return
        os.makedirs(self._dir, exist_ok=True)
        for src in files:
            try:
                dst = os.path.join(self._dir, os.path.basename(src))
                if os.path.abspath(src) != os.path.abspath(dst):
                    shutil.copyfile(src, dst)
            except Exception:
                pass
        self._load_emotes()

    def _load_emotes(self) -> None:
        self.list.clear()
        if not os.path.isdir(self._dir):
            return
        exts = {".png", ".jpg", ".jpeg", ".gif"}
        for name in sorted(os.listdir(self._dir)):
            if os.path.splitext(name)[1].lower() in exts:
                path = os.path.join(self._dir, name)
                icon = QtGui.QIcon(path)
                item = QtWidgets.QListWidgetItem(icon, name)
                item.setData(QtCore.Qt.UserRole, path)
                self.list.addItem(item)

    def _send_selected(self) -> None:
        item = self.list.currentItem()
        if not item:
            return
        path = item.data(QtCore.Qt.UserRole)
        if path and os.path.isfile(path):
            self.sigSend.emit(path)
