from PyQt5 import QtWidgets
from zfeiq_gui.lang import t


class ChatPage(QtWidgets.QWidget):
    def __init__(self, core=None):
        super().__init__()
        self.core = core
        self._build()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        self.info = QtWidgets.QLabel(t['chat'])
        layout.addWidget(self.info)
        self.msgs = QtWidgets.QTextEdit()
        self.msgs.setReadOnly(True)
        layout.addWidget(self.msgs)
        h = QtWidgets.QHBoxLayout()
        self.to = QtWidgets.QLineEdit()
        self.to.setPlaceholderText(t['chat_target_unselected'])
        self.text = QtWidgets.QLineEdit()
        send = QtWidgets.QPushButton(t['send'])
        send.clicked.connect(self._on_send)
        h.addWidget(self.to)
        h.addWidget(self.text)
        h.addWidget(send)
        layout.addLayout(h)

    def _on_send(self):
        target = self.to.text().strip()
        text = self.text.text().strip()
        if not target or not text:
            QtWidgets.QMessageBox.warning(self, t['usage_send'], t['usage_send'])
            return
        if self.core:
            try:
                self.core.send_message(target, text)
                self.msgs.append(f"Me -> {target}: {text}")
            except Exception:
                QtWidgets.QMessageBox.critical(self, t['send'], "send failed")
