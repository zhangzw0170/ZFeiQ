from __future__ import annotations

import os
from typing import Dict

from PyQt5 import QtCore, QtWidgets


class FilesPage(QtWidgets.QWidget):
    """Legacy file-offer inspector (kept for future reuse)."""

    sigAccept = QtCore.pyqtSignal(str, str)
    sigCancel = QtCore.pyqtSignal(str)
    sigPickDir = QtCore.pyqtSignal()
    sigApplyDir = QtCore.pyqtSignal(str)

    def __init__(self, lang: str = "zhCN"):
        super().__init__()
        from zfeiq_gui.lang import get_translations
        self._translations = get_translations(lang)
        self._build()
        self._offers: Dict[str, dict] = {}
        self._prog_bars: Dict[str, QtWidgets.QProgressBar] = {}

    def _build(self) -> None:
        t = self._translations
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        dir_row = QtWidgets.QHBoxLayout()
        self.dir_edit = QtWidgets.QLineEdit()
        btn_pick = QtWidgets.QPushButton(t["pickdir"])
        btn_apply = QtWidgets.QPushButton(t["setdefault"])
        for button in (btn_pick, btn_apply):
            try:
                # 使用较小的最小高度并允许垂直收缩
                button.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Preferred)
            except Exception:
                pass
        dir_row.addWidget(self.dir_edit, 1)
        dir_row.addWidget(btn_pick)
        dir_row.addWidget(btn_apply)
        layout.addLayout(dir_row)

        self.list = QtWidgets.QListWidget()
        layout.addWidget(self.list, 1)

        ctrl = QtWidgets.QHBoxLayout()
        self.btn_accept = QtWidgets.QPushButton(t["accept"])
        self.btn_cancel = QtWidgets.QPushButton(t["cancel"])
        for button in (self.btn_accept, self.btn_cancel):
            try:
                button.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Preferred)
            except Exception:
                pass
        ctrl.addWidget(self.btn_accept)
        ctrl.addWidget(self.btn_cancel)
        ctrl.addStretch()
        layout.addLayout(ctrl)

        btn_pick.clicked.connect(lambda: self.sigPickDir.emit())
        btn_apply.clicked.connect(lambda: self.sigApplyDir.emit(self.dir_edit.text().strip()))
        self.btn_accept.clicked.connect(self._on_accept)
        self.btn_cancel.clicked.connect(self._on_cancel)

    def pick_dir(self) -> None:
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "选择保存目录")
        if directory:
            self.dir_edit.setText(directory)

    def update_offers(self, offers: Dict[str, dict]) -> None:
        self._offers = offers or {}
        self.list.clear()
        self._prog_bars.clear()
        for oid, meta in self._offers.items():
            name = meta.get("name", "file")
            size = int(meta.get("size", 0))
            src = f"{meta.get('ip','?')}:{meta.get('port','-')}" if meta.get("method") != "ipmsg" else f"{meta.get('ip','?')}:2425/ipmsg"
            uname = meta.get("uname") or meta.get("ip", "?")
            ts_val = meta.get("ts")
            ts_txt = QtCore.QDateTime.fromSecsSinceEpoch(int(ts_val)).toString("yyyy-MM-dd hh:mm:ss") if ts_val else "--"
            display = (
                f"{uname}[IP:{meta.get('ip','?')}] {name} {ts_txt} | {size} bytes | {src}"
                if uname
                else f"{oid} | {name} | {size} bytes | from {src}"
            )
            item = QtWidgets.QListWidgetItem()
            item.setData(QtCore.Qt.UserRole, oid)
            widget = QtWidgets.QWidget()
            row = QtWidgets.QHBoxLayout(widget)
            row.setContentsMargins(6, 2, 6, 2)
            row.setSpacing(8)
            lbl = QtWidgets.QLabel(display)
            bar = QtWidgets.QProgressBar()
            bar.setMinimum(0)
            bar.setMaximum(size if size > 0 else 0)
            bar.setTextVisible(True)
            row.addWidget(lbl, 1)
            row.addWidget(bar, 1)
            self.list.addItem(item)
            self.list.setItemWidget(item, widget)
            self._prog_bars[oid] = bar

    def _on_accept(self) -> None:
        item = self.list.currentItem()
        if not item:
            return
        oid = item.data(QtCore.Qt.UserRole)
        self.sigAccept.emit(oid, self.dir_edit.text().strip())

    def _on_cancel(self) -> None:
        item = self.list.currentItem()
        if not item:
            return
        oid = item.data(QtCore.Qt.UserRole)
        self.sigCancel.emit(oid)

    def update_progress(self, oid: str, total: int) -> None:
        bar = self._prog_bars.get(oid)
        if not bar:
            return
        meta = self._offers.get(oid) or {}
        size = int(meta.get("size", 0)) if meta else 0
        if size > 0:
            if bar.maximum() != size:
                bar.setMaximum(size)
            bar.setValue(max(0, min(total, size)))
            pct = (total * 100 // size) if size else 0
            bar.setFormat(f"{pct}% ({total}/{size})")
        else:
            bar.setMaximum(0)
            bar.setFormat(f"{oid}: {total} bytes")

    def on_saved(self, oid: str, path: str) -> None:
        QtWidgets.QMessageBox.information(self, "保存完成", f"要约 {oid} 已保存至:\n{path}")
