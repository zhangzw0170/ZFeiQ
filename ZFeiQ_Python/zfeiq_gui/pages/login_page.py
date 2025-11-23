from PyQt5 import QtWidgets
from zfeiq_gui.lang import t


class LoginPage(QtWidgets.QWidget):
    def __init__(self, core=None):
        super().__init__()
        self.core = core
        self._build()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        label = QtWidgets.QLabel(t['login_welcome'])
        layout.addWidget(label)
        self.input = QtWidgets.QLineEdit()
        self.input.setPlaceholderText(t['username_ph'])
        layout.addWidget(self.input)
        btn = QtWidgets.QPushButton(t['login'])
        btn.clicked.connect(self._on_login)
        layout.addWidget(btn)

    def _on_login(self):
        username = self.input.text().strip()
        if not username:
            QtWidgets.QMessageBox.warning(self, t['login'], t['username_ph'])
            return
        if self.core:
            try:
                self.core.login(username)
            except Exception:
                pass
        QtWidgets.QMessageBox.information(self, t['login'], "OK")
