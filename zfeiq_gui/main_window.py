from PyQt5 import QtCore, QtGui, QtWidgets


class NavigationButton(QtWidgets.QToolButton):
    def __init__(self, text: str, icon: QtGui.QIcon = None, parent=None):
        super().__init__(parent)
        self.setText(text)
        # 紧凑型：无图标时仅文字，小于图标布局
        if icon:
            self.setIcon(icon)
            self.setIconSize(QtCore.QSize(16, 16))
            self.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        else:
            self.setToolButtonStyle(QtCore.Qt.ToolButtonTextOnly)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        # 高度 = 字体高度 + 额外留白
        h = self.fontMetrics().height() + 8
        self.setFixedHeight(h)


class UserPage(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(15)

        header = QtWidgets.QHBoxLayout()
        avatar = QtWidgets.QLabel()
        avatar.setFixedSize(80, 80)
        avatar.setStyleSheet("background-color: #d9d9d9; border-radius: 8px;")
        avatar.setAlignment(QtCore.Qt.AlignCenter)
        avatar.setText("头像")

        info_box = QtWidgets.QVBoxLayout()
        self.username_label = QtWidgets.QLabel("用户名：未登录")
        self.ip_label = QtWidgets.QLabel("IP：-.-.-.-")
        self.username_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.ip_label.setStyleSheet("color: #666666;")
        info_box.addWidget(self.username_label)
        info_box.addWidget(self.ip_label)
        info_box.addStretch()

        header.addWidget(avatar)
        header.addLayout(info_box)
        header.addStretch()

        self.inbox = QtWidgets.QTextEdit()
        self.inbox.setReadOnly(True)
        self.inbox.setPlaceholderText("消息接收区：显示聊天记录及文件提示")

        actions_row = QtWidgets.QHBoxLayout()
        self.emoji_btn = QtWidgets.QPushButton("表情")
        self.screenshot_btn = QtWidgets.QPushButton("截图")
        self.quicktext_btn = QtWidgets.QPushButton("常用语")
        # 统一按钮高度：略高于文字
        for b in (self.emoji_btn, self.screenshot_btn, self.quicktext_btn):
            b.setFixedHeight(b.fontMetrics().height() + 8)
        actions_row.addWidget(self.emoji_btn)
        actions_row.addWidget(self.screenshot_btn)
        actions_row.addWidget(self.quicktext_btn)
        actions_row.addStretch()

        self.outbox = QtWidgets.QTextEdit()
        self.outbox.setPlaceholderText("在此输入要发送的消息…")
        self.outbox.setFixedHeight(120)

        send_row = QtWidgets.QHBoxLayout()
        send_row.addStretch()
        self.send_btn = QtWidgets.QPushButton("发送")
        self.send_btn.setFixedWidth(100)
        self.send_btn.setFixedHeight(self.send_btn.fontMetrics().height() + 8)
        send_row.addWidget(self.send_btn)

        root.addLayout(header)
        root.addWidget(self.inbox, stretch=1)
        root.addLayout(actions_row)
        root.addWidget(self.outbox)
        root.addLayout(send_row)

    def append_message(self, sender: str, ip: str, text: str) -> None:
        prefix = f"[{sender}@{ip}] "
        self.inbox.append(prefix + text)

    def append_file_notice(self, sender: str, file_name: str) -> None:
        notice = f"[{sender}] 【文件】{file_name}"
        self.inbox.append(notice)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ZFeiQ LAN Messenger")
        self.resize(500, 800)
        self._build_ui()

    def _build_ui(self) -> None:
        central = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.nav_panel = self._build_nav_panel()
        self.content_panel = self._build_content_panel()

        layout.addWidget(self.nav_panel)
        layout.addWidget(self.content_panel, stretch=1)

        self.setCentralWidget(central)

    def _build_nav_panel(self) -> QtWidgets.QWidget:
        panel = QtWidgets.QWidget()
        panel.setFixedWidth(100)
        panel.setStyleSheet("background-color: #f5f5f5;")

        outer_layout = QtWidgets.QVBoxLayout(panel)
        outer_layout.setContentsMargins(8, 12, 8, 12)
        outer_layout.setSpacing(12)

        search = QtWidgets.QLineEdit()
        search.setPlaceholderText("搜索…")
        search.setFixedHeight(32)

        top_box = QtWidgets.QVBoxLayout()
        top_box.setSpacing(8)
        btn_users = NavigationButton("用户")
        btn_groups = NavigationButton("组")
        btn_capture = NavigationButton("截图")
        top_box.addWidget(btn_users)
        top_box.addWidget(btn_groups)
        top_box.addWidget(btn_capture)
        top_box.addStretch()

        bottom_box = QtWidgets.QVBoxLayout()
        bottom_box.setSpacing(8)
        btn_emotes = NavigationButton("表情")
        btn_profile = NavigationButton("信息")
        btn_settings = NavigationButton("设置")
        bottom_box.addWidget(btn_emotes)
        bottom_box.addWidget(btn_profile)
        bottom_box.addWidget(btn_settings)

        outer_layout.addWidget(search)
        outer_layout.addLayout(top_box, stretch=1)
        outer_layout.addLayout(bottom_box)

        return panel

    def _build_content_panel(self) -> QtWidgets.QWidget:
        page = UserPage()
        container = QtWidgets.QStackedWidget()
        container.addWidget(page)
        return container
