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
        self.btn_help = QtWidgets.QPushButton(t.get("help", "帮助"))
        self.btn_help.setFixedHeight(self.btn_help.fontMetrics().height() + 10)
        top_row.addWidget(self.btn_help)
        layout.addLayout(top_row)

        self.lbl_welcome = QtWidgets.QLabel(t.get("login_welcome", "欢迎使用 ZFeiQ，请先登录"))
        self.lbl_welcome.setAlignment(QtCore.Qt.AlignCenter)
        font = self.lbl_welcome.font()
        font.setPointSize(14)
        self.lbl_welcome.setFont(font)

        self.name_edit = QtWidgets.QLineEdit()
        self.name_edit.setPlaceholderText(t.get("username_ph", "输入用户名…"))

        ip_row = QtWidgets.QHBoxLayout()
        self.ip_combo = QtWidgets.QComboBox()
        self.ip_combo.setEditable(False)
        self.lbl_pick_ip = QtWidgets.QLabel(t.get("pick_ip", "选择IP"))
        ip_row.addWidget(self.lbl_pick_ip)
        ip_row.addWidget(self.ip_combo, 1)

        self.login_btn = QtWidgets.QPushButton(t.get("login", "登录"))
        self.login_btn.setFixedHeight(self.login_btn.fontMetrics().height() + 12)

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
        QtWidgets.QMessageBox.information(
            self,
            t.get("help", "帮助"),
            t.get(
                "login_help_text",
                "1) 输入用户名并选择 IP\n2) 登录后在用户/组页面选择聊天对象\n3) 聊天：Enter 发送，Shift+Enter 换行；Ctrl+V 可粘贴文件加入待发送。\n   表情：点击‘表情’打开对话框，含 Emoji 与自定义表情。\n   截图：支持框选区域，按 ESC 取消。\n4) 设置：语言/状态/编码/主题、下载与截图目录、头像；编码自检位于 设置-通用。\n",
            ),
        )

    def apply_language(self, translations: Dict[str, str]) -> None:
        self._translations = translations
        t = self._translations
        self.btn_help.setText(t.get("help", self.btn_help.text()))
        self.lbl_welcome.setText(t.get("login_welcome", self.lbl_welcome.text()))
        self.name_edit.setPlaceholderText(t.get("username_ph", self.name_edit.placeholderText()))
        self.lbl_pick_ip.setText(t.get("pick_ip", self.lbl_pick_ip.text()))
        self.login_btn.setText(t.get("login", self.login_btn.text()))
