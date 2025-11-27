from __future__ import annotations

from typing import Dict

from PyQt5 import QtWidgets
from zfeiq_gui.lang import t


class KeyPage(QtWidgets.QWidget):
    """Embedded key-management helper hosted inside the settings page."""

    def __init__(self, core=None, parent=None):
        super().__init__(parent)
        self.core = core
        self._translations = t
        self._build()

    def _build(self) -> None:
        t_local = self._translations
        layout = QtWidgets.QFormLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        self.cmb_mode = QtWidgets.QComboBox()
        self.cmb_mode.addItems(["off", "on", "strict"])
        self.lbl_fp = QtWidgets.QLabel(t_local['key_fp'])
        self.btn_refresh = QtWidgets.QPushButton(t_local["key_refresh"])
        self.btn_regen = QtWidgets.QPushButton(t_local["key_regen"])
        self.btn_export = QtWidgets.QPushButton(t_local["key_export"])
        for button in (self.btn_refresh, self.btn_regen, self.btn_export):
            button.setFixedHeight(button.fontMetrics().height() + 12)
        self.lbl_enc_mode = QtWidgets.QLabel(t_local['enc_mode'])
        layout.addRow(self.lbl_enc_mode, self.cmb_mode)
        layout.addRow(self.lbl_fp)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(self.btn_refresh)
        row.addWidget(self.btn_regen)
        row.addWidget(self.btn_export)
        row.addStretch()
        layout.addRow(row)

    def apply_language(self, translations: Dict[str, str]) -> None:
        self._translations = translations
        try:
            self.lbl_enc_mode.setText(translations.get("enc_mode", self.lbl_enc_mode.text()))
            self.lbl_fp.setText(translations.get("key_fp", self.lbl_fp.text()))
            self.btn_refresh.setText(translations.get("key_refresh", "刷新指纹"))
            self.btn_regen.setText(translations.get("key_regen", "重生成密钥"))
            self.btn_export.setText(translations.get("key_export", "导出公钥…"))
        except Exception:
            pass
