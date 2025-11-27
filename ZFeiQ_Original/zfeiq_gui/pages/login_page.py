from __future__ import annotations

from typing import Dict

from PyQt5 import QtCore, QtWidgets


class LoginPage(QtWidgets.QWidget):
    """Minimal login prompt used as the first step in the workflow."""

    sigLogin = QtCore.pyqtSignal(str, str)

    def __init__(self, lang: str = "zhCN"):
        super().__init__()
        from zfeiq_gui.lang import get_translations
        self._translations = get_translations(lang)
        self._build()

    def _build(self) -> None:
        t = self._translations
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(60, 60, 60, 60)
        layout.setSpacing(12)

        top_row = QtWidgets.QHBoxLayout()
        top_row.addStretch()
        self.btn_help = QtWidgets.QPushButton(t['help'])
        self.btn_help.setFixedHeight(self.btn_help.fontMetrics().height() + 22)
        top_row.addWidget(self.btn_help)
        layout.addLayout(top_row)

        self.lbl_welcome = QtWidgets.QLabel(t['login_welcome'])
        self.lbl_welcome.setAlignment(QtCore.Qt.AlignCenter)
        font = self.lbl_welcome.font()
        font.setPointSize(14)
        self.lbl_welcome.setFont(font)

        self.name_edit = QtWidgets.QLineEdit()
        self.name_edit.setPlaceholderText(t['username_ph'])

        ip_row = QtWidgets.QHBoxLayout()
        self.ip_combo = QtWidgets.QComboBox()
        self.ip_combo.setEditable(False)
        self.lbl_pick_ip = QtWidgets.QLabel(t['pick_ip'])
        ip_row.addWidget(self.lbl_pick_ip)
        ip_row.addWidget(self.ip_combo, 1)

        self.login_btn = QtWidgets.QPushButton(t['login'])
        self.login_btn.setFixedHeight(self.btn_help.fontMetrics().height() + 22)

        layout.addStretch()
        layout.addWidget(self.lbl_welcome)
        layout.addWidget(self.name_edit)
        layout.addLayout(ip_row)
        layout.addWidget(self.login_btn)
        layout.addStretch()

        self.login_btn.clicked.connect(self._on_login)
        try:
            self.name_edit.returnPressed.connect(self._on_login)
        except Exception:
            pass

        self.btn_help.clicked.connect(self._show_help_dialog)

    def _on_login(self) -> None:
        name = self.name_edit.text().strip()
        ip = self.ip_combo.currentText().strip()
        if name:
            self.sigLogin.emit(name, ip)

    def _show_help_dialog(self) -> None:
        t = self._translations
        QtWidgets.QMessageBox.information(self, t['help'], t['login_help_text'])

    def apply_language(self, translations: Dict[str, str]) -> None:
        self._translations = translations
        t = self._translations
        self.btn_help.setText(t['help'])
        self.lbl_welcome.setText(t['login_welcome'])
        self.name_edit.setPlaceholderText(t['username_ph'])
        self.lbl_pick_ip.setText(t['pick_ip'])
        self.login_btn.setText(t['login'])
