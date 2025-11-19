from PyQt5 import QtCore, QtGui, QtWidgets
from typing import List, Dict, Optional
from html import escape
import platform
import sys
import os
import shutil
import tempfile
from zfeiq_version import APP_VERSION
import datetime


class NavigationButton(QtWidgets.QToolButton):
    def __init__(self, text: str, icon: Optional[QtGui.QIcon] = None, parent=None):
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
        h = self.fontMetrics().height() + 12
        self.setFixedHeight(h)


class UserPage(QtWidgets.QWidget):
    sigSend = QtCore.pyqtSignal()
    sigAnchor = QtCore.pyqtSignal(str)
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._local_ip = ""
        self._logs = {}
        self._pending_files = []  # type: List[str]

    def eventFilter(self, a0, a1):  # basic passthrough; wrapper installed later may delegate
        return False

    def _ensure_view(self, key: str) -> QtWidgets.QTextBrowser:
        if key not in self._chat_views:
            view = QtWidgets.QTextBrowser(); view.setOpenExternalLinks(False)
            view.setReadOnly(True)
            view.setPlaceholderText("消息接收区：显示聊天记录及文件提示")
            view.anchorClicked.connect(lambda url, self=self: self.sigAnchor.emit(url.toString()))
            self._chat_views[key] = view
            self.tabs.addTab(view, key)
        return self._chat_views[key]

    def _append_log(self, target: str, line: str):
        try:
            self._logs.setdefault(target, []).append(line)
        except Exception:
            pass

    def set_avatar(self, path: str):
        try:
            if path and os.path.isfile(path):
                pm = QtGui.QPixmap(path)
                if not pm.isNull():
                    self.avatar.setPixmap(pm.scaled(80, 80, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
        except Exception:
            pass

    def _build_ui(self) -> None:
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(15)

        header = QtWidgets.QHBoxLayout()
        self.avatar = QtWidgets.QLabel()
        self.avatar.setFixedSize(80, 80)
        self.avatar.setStyleSheet("background-color: #d9d9d9; border-radius: 8px;")
        self.avatar.setAlignment(QtCore.Qt.AlignCenter)
        self.avatar.setText("头像")

        info_box = QtWidgets.QVBoxLayout()
        self.username_label = QtWidgets.QLabel("用户名：未登录")
        self.status_label = QtWidgets.QLabel("状态：-")
        self.ip_label = QtWidgets.QLabel("IP：-.-.-.-")
        self.username_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.status_label.setStyleSheet("color:#444444; font-size:12px;")
        self.ip_label.setStyleSheet("color: #666666; font-size:12px;")
        self.encoding_label = QtWidgets.QLabel("编码: -")
        self.me_info_label = QtWidgets.QLabel("")
        info_box.addWidget(self.username_label)
        info_box.addWidget(self.status_label)
        info_box.addWidget(self.ip_label)
        info_box.addWidget(self.encoding_label)
        info_box.addWidget(self.me_info_label)
        info_box.addStretch()

        header.addWidget(self.avatar)
        header.addLayout(info_box)

        # 聊天标签页：每个用户一个独立视图，含一个“全部”汇总
        self.tabs = QtWidgets.QTabWidget()
        self._chat_views = {}  # key(display) -> QTextEdit
        self._view_all = QtWidgets.QTextBrowser(); self._view_all.setOpenExternalLinks(False)
        self._view_all.setReadOnly(True)
        self._view_all.anchorClicked.connect(lambda url: self.sigAnchor.emit(url.toString()))
        self._view_all.setPlaceholderText("消息接收区：显示聊天记录及文件提示")
        self.local_msg_color_light = "#00561F"
        self.local_msg_color_dark = "#29c94f"
        self._current_local_color = self.local_msg_color_light
        self.tabs.addTab(self._view_all, "全部")

        actions_row = QtWidgets.QHBoxLayout()
        self.emoji_btn = QtWidgets.QPushButton("表情管理")
        self.screenshot_btn = QtWidgets.QPushButton("截图")
        self.quicktext_btn = QtWidgets.QPushButton("常用语")
        self.enc_test_btn = QtWidgets.QPushButton("编码自检")
        self.history_btn = QtWidgets.QPushButton("历史")
        self.send_file_btn = QtWidgets.QPushButton("发送文件")
        # 简易 Emoji 选择器
        self.emoji_unicode_btn = QtWidgets.QPushButton("😀")
        self.emoji_unicode_btn.setFixedWidth(44)
        def _show_emoji_grid():
            dlg = QtWidgets.QDialog(self)
            dlg.setWindowTitle("选择 Emoji")
            lay = QtWidgets.QGridLayout(dlg); lay.setContentsMargins(10,10,10,10); lay.setSpacing(6)
            emojis = [
                "😀","😁","😂","🤣","😊","😍","😎","🤔","🙃","🙂","😉","😇","😅","😭","😤",
                "😡","😱","🤩","🤗","🤨","🥳","🥹","🫠","😴","🤤","🤒","🤕","🤧","🤮","😷",
                "👍","👎","👌","🙏","👏","🙌","🤝","🫶","💪","👀","👋","✌️","🤘","👑","🎩",
                "🎉","✨","🔥","💥","💯","💡","📎","📌","🖊️","📝","📁","📂","📦","🗂️","🔍",
                "❤️","🧡","💛","💚","💙","💜","🖤","🤍","🤎","💖","💗","💓","💞","💕","💘",
                "🍎","🍊","🍋","🍉","🍇","🍓","🍒","🍑","🥝","🥥","🥑","🌶️","🍔","🍕","🍟",
                "☕","🍵","🍺","🍻","🍷","🍾","🥂","🥤","🧋","🧃","🍰","🎂","🍩","🍪","🍫",
            ]
            rows, cols = 7, 15
            for i, emo in enumerate(emojis[:rows*cols]):
                r, c = divmod(i, cols)
                btn = QtWidgets.QPushButton(emo)
                btn.setFixedSize(28, 28)
                btn.setStyleSheet("QPushButton{border:1px solid #ddd; border-radius:4px; background:#fff;} QPushButton:hover{background:#f5f5f5}")
                btn.clicked.connect(lambda _, e=emo: (self.outbox.insertPlainText(e), dlg.accept()))
                lay.addWidget(btn, r, c)
            dlg.exec_()
        self.emoji_unicode_btn.clicked.connect(_show_emoji_grid)
        for b in (self.emoji_btn, self.screenshot_btn, self.quicktext_btn, self.enc_test_btn, self.history_btn, self.send_file_btn):
            b.setFixedHeight(b.fontMetrics().height() + 12)
            b.setStyleSheet("QPushButton{border: none; background: #ededed; padding:4px 8px; border-radius:6px;} QPushButton:hover{background:#e0e0e0}")
        actions_row.addWidget(self.emoji_btn)
        actions_row.addWidget(self.screenshot_btn)
        actions_row.addWidget(self.quicktext_btn)
        actions_row.addWidget(self.emoji_unicode_btn)
        actions_row.addWidget(self.enc_test_btn)
        actions_row.addWidget(self.history_btn)
        actions_row.addWidget(self.send_file_btn)
        actions_row.addStretch()

        # 待发送文件块容器（紧贴输入框上方，支持回退删除最后一个文件）
        self.file_bar = QtWidgets.QWidget()
        self.file_bar.setVisible(False)
        self._file_bar_layout = QtWidgets.QHBoxLayout(self.file_bar)
        self._file_bar_layout.setContentsMargins(4, 4, 4, 4)
        self._file_bar_layout.setSpacing(6)
        self._file_bar_layout.addStretch()

        self.outbox = QtWidgets.QTextEdit()
        self.outbox.setPlaceholderText("输入消息，Enter 发送，Shift+Enter 换行")
        self.outbox.setAcceptRichText(False)

        # 目标与发送行（保留以兼容现有逻辑；后续可按需隐藏）
        send_row = QtWidgets.QHBoxLayout()
        self.target_combo = QtWidgets.QComboBox()
        self.refresh_targets_btn = QtWidgets.QPushButton("刷新")
        self.send_btn = QtWidgets.QPushButton("发送")
        self.send_btn.setFixedHeight(self.send_btn.fontMetrics().height() + 12)
        send_row.addWidget(QtWidgets.QLabel("目标"))
        send_row.addWidget(self.target_combo, 1)
        send_row.addWidget(self.refresh_targets_btn)
        send_row.addWidget(self.send_btn)

        # 组装布局
        root.addLayout(header)
        # 接收区更大
        root.addWidget(self.tabs, 3)
        root.addLayout(actions_row)
        root.addWidget(self.file_bar)
        root.addWidget(self.outbox, 1)
        root.addLayout(send_row)

        # Enter 发送快捷键（Shift+Enter 换行）
        class _OutboxFilter(QtCore.QObject):
            def __init__(self, outer):
                super().__init__(outer)
                self.outer = outer
            def eventFilter(self, a0, a1):
                try:
                    if a0 is self.outer.outbox and a1.type() == QtCore.QEvent.KeyPress:
                        # Enter 发送（Shift+Enter 换行）
                        get_key = getattr(a1, 'key', None)
                        k = get_key() if callable(get_key) else None
                        mods = int(QtWidgets.QApplication.keyboardModifiers())
                        if k == QtCore.Qt.Key_Return and not (mods & int(QtCore.Qt.ShiftModifier)):
                            self.outer.sigSend.emit()
                            return True
                        # Backspace 删除最后一个待发送文件（当输入框为空时）
                        if k == QtCore.Qt.Key_Backspace:
                            if not self.outer.outbox.toPlainText().strip() and self.outer._pending_files:
                                self.outer._remove_last_file_chip()
                                return True
                except Exception:
                    pass
                return False
        self._outbox_filter = _OutboxFilter(self)
        self.outbox.installEventFilter(self._outbox_filter)

    # ---- pending file chips api ----
    def add_pending_file(self, path: str):
        if not path:
            return
        self._pending_files.append(path)
        chip = QtWidgets.QFrame()
        chip.setStyleSheet("QFrame{background:#e6f0ff; border:1px solid #b3d1ff; border-radius:6px;}")
        hl = QtWidgets.QHBoxLayout(chip); hl.setContentsMargins(8,2,6,2); hl.setSpacing(6)
        lbl = QtWidgets.QLabel(f"📎 {os.path.basename(path)}")
        btn = QtWidgets.QToolButton(); btn.setText("×"); btn.setAutoRaise(True)
        def _rm():
            try:
                self._pending_files.remove(path)
            except ValueError:
                pass
            self._file_bar_layout.removeWidget(chip)
            chip.hide(); chip.deleteLater()
            self.file_bar.setVisible(bool(self._pending_files))
        btn.clicked.connect(_rm)
        hl.addWidget(lbl)
        hl.addWidget(btn)
        # 将 chip 插入到末尾、但在拉伸之前
        self._file_bar_layout.insertWidget(max(0, self._file_bar_layout.count()-1), chip)
        self.file_bar.setVisible(True)

    def get_pending_files(self) -> List[str]:
        return list(self._pending_files)

    def clear_pending_files(self):
        self._pending_files.clear()
        # 清空 chips
        for i in reversed(range(self._file_bar_layout.count()-1)):
            w = self._file_bar_layout.itemAt(i).widget()
            if w is not None:
                self._file_bar_layout.removeWidget(w)
                w.hide(); w.deleteLater()
        self.file_bar.setVisible(False)

    def _remove_last_file_chip(self):
        if not self._pending_files:
            return
        self._pending_files.pop()
        # 移除最后一个 chip（拉伸之前的最后一个）
        idx = self._file_bar_layout.count()-2
        if idx >= 0:
            w = self._file_bar_layout.itemAt(idx).widget()
            if w is not None:
                self._file_bar_layout.removeWidget(w)
                w.hide(); w.deleteLater()
        self.file_bar.setVisible(bool(self._pending_files))

    def append_message(self, sender: str, ip: str, text: str) -> None:
        key = f"{sender}[IP:{ip}]"
        is_local = bool(self._local_ip and ip == self._local_ip)
        bubble_bg = "#DCF8C6" if is_local else "#FFFFFF"
        align = "right" if is_local else "left"
        color = "#111" if not is_local else "#0a0a0a"
        html_bubble = (
            f"<div style='text-align:{align};'>"
            f"  <span style='display:inline-block; max-width:70%; background:{bubble_bg}; color:{color}; padding:6px 10px; border-radius:10px; border:1px solid #e6e6e6;'>"
            f"    <b>{escape(sender)}</b> @ {escape(ip)}<br/>{escape(text)}"
            f"  </span>"
            f"</div>"
        )
        self._view_all.append(html_bubble)
        self._ensure_view(key).append(html_bubble)
        self._append_log(key, f"<< {sender}@{ip}: {text}")

    def append_file_notice(self, sender: str, file_name: str) -> None:
        color = self._current_local_color if sender == "我" else "#555555"
        html = f"<span style='color:{color}'>&lt;&lt; [{sender}] 文件: {escape(file_name)}</span>"
        self._view_all.append(html)

    def append_outgoing(self, target_display: str, text: str) -> None:
        key = target_display
        html_bubble = (
            f"<div style='text-align:right;'>"
            f"  <span style='display:inline-block; max-width:70%; background:#DCF8C6; color:#0a0a0a; padding:6px 10px; border-radius:10px; border:1px solid #d8f0c0;'>"
            f"    <b>我</b> -> {escape(target_display)}<br/>{escape(text)}"
            f"  </span>"
            f"</div>"
        )
        self._view_all.append(html_bubble)
        self._ensure_view(key).append(html_bubble)
        self._append_log(key, f">> {text}")

    def append_incoming_offer(self, oid: str, uname: str, ip: str, name: str, size: int):
        size_txt = f"{size} bytes" if size else "? bytes"
        html_bubble = (
            f"<div style='text-align:left;'>"
            f"  <span style='display:inline-block; max-width:70%; background:#FFFFFF; color:#111; padding:6px 10px; border-radius:10px; border:1px solid #e6e6e6;'>"
            f"    <b>{escape(uname)}</b> @ {escape(ip)}<br/>文件要约: {escape(name)} ({size_txt}) "
            f"    <a href='accept:{oid}'>[接收]</a> <a href='cancel:{oid}'>[放弃]</a>"
            f"  </span>"
            f"</div>"
        )
        self._view_all.append(html_bubble)

    def append_offer_progress(self, oid: str, name: str, done: int, total: int):
        if total > 0:
            pct = int(done * 100 / total)
            txt = f"进度 {pct}% ({done}/{total})"
        else:
            txt = f"进度 {done} bytes"
        self._view_all.append(
            f"<div style='text-align:left;'><span style='display:inline-block; background:#fff; color:#666; padding:4px 8px; border-radius:8px; border:1px solid #eee;'>[文件进度] {escape(name)} {escape(txt)}</span></div>"
        )

    def append_offer_saved(self, name: str, path: str):
        self._view_all.append(
            f"<div style='text-align:left;'><span style='display:inline-block; background:#e6ffed; color:#065f46; padding:4px 8px; border-radius:8px; border:1px solid #c7f5d9;'>[文件完成] {escape(name)} 保存到 {escape(path)}</span></div>"
        )

    def append_file_sent(self, target_display: str, path: str):
        key = target_display
        name = os.path.basename(path)
        html_bubble = (
            f"<div style='text-align:right;'>"
            f"  <span style='display:inline-block; max-width:70%; background:#DCF8C6; color:#0a0a0a; padding:6px 10px; border-radius:10px; border:1px solid #d8f0c0;'>"
            f"    <b>我</b> -> {escape(target_display)}<br/>已发送文件: {escape(name)}"
            f"  </span>"
            f"</div>"
        )
        self._view_all.append(html_bubble)
        self._ensure_view(key).append(html_bubble)

    def set_local_color(self, dark: bool):
        self._current_local_color = self.local_msg_color_dark if dark else self.local_msg_color_light

    def set_local_ip(self, ip: str):
        self._local_ip = ip or ""
        try:
            self.ip_label.setText(f"IP：{ip}" if ip else "IP：-.-.-.-")
        except Exception:
            pass

    def set_user_status(self, uname: str, status: str):
        try:
            if uname:
                self.username_label.setText(f"{uname}")
            if status:
                self.status_label.setText(f"状态：{status}")
        except Exception:
            pass


class LoginPage(QtWidgets.QWidget):
    sigLogin = QtCore.pyqtSignal(str, str)  # username, selected_ip

    def __init__(self):
        super().__init__()
        self._build()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(60, 60, 60, 60)
        layout.setSpacing(12)
        top_row = QtWidgets.QHBoxLayout()
        top_row.addStretch()
        btn_help = QtWidgets.QPushButton("帮助")
        btn_help.setFixedHeight(btn_help.fontMetrics().height() + 10)
        top_row.addWidget(btn_help)
        layout.addLayout(top_row)
        lbl = QtWidgets.QLabel("欢迎使用 ZFeiQ，请先登录")
        lbl.setAlignment(QtCore.Qt.AlignCenter)
        font = lbl.font(); font.setPointSize(14); lbl.setFont(font)
        self.name_edit = QtWidgets.QLineEdit()
        self.name_edit.setPlaceholderText("输入用户名…")
        # IP 选择
        ip_row = QtWidgets.QHBoxLayout()
        self.ip_combo = QtWidgets.QComboBox()
        self.ip_combo.setEditable(False)
        ip_row.addWidget(QtWidgets.QLabel("选择IP"))
        ip_row.addWidget(self.ip_combo, 1)
        self.login_btn = QtWidgets.QPushButton("登录")
        self.login_btn.setFixedHeight(self.login_btn.fontMetrics().height() + 12)
        layout.addStretch()
        layout.addWidget(lbl)
        layout.addWidget(self.name_edit)
        layout.addLayout(ip_row)
        layout.addWidget(self.login_btn)
        layout.addStretch()
        self.login_btn.clicked.connect(self._on_login)
        # 回车也可登录
        try:
            self.name_edit.returnPressed.connect(self._on_login)
        except Exception:
            pass
        def _show_help():
            QtWidgets.QMessageBox.information(self, "帮助", "1) 输入用户名并选择 IP\n2) 登录后在用户/组页面选择聊天对象\n3) 聊天页支持表情、截图、历史、发送文件；Enter 发送，Shift+Enter 换行\n4) 设置页可更改语言/状态/编码/主题、下载与截图目录、头像等")
        btn_help.clicked.connect(_show_help)

    def _on_login(self):
        name = self.name_edit.text().strip()
        ip = self.ip_combo.currentText().strip()
        if name:
            self.sigLogin.emit(name, ip)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ZFeiQ")
        self.resize(500, 800)
        self._build_ui()
        self._current_theme = "light"

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
        # 未登录前隐藏侧边导航
        try:
            self.nav_panel.setVisible(False)
        except Exception:
            pass

    def _build_nav_panel(self) -> QtWidgets.QWidget:
        panel = QtWidgets.QWidget()
        panel.setObjectName("navPanel")
        panel.setFixedWidth(100)

        outer_layout = QtWidgets.QVBoxLayout(panel)
        outer_layout.setContentsMargins(8, 12, 8, 12)
        outer_layout.setSpacing(12)

        # 移除冗余搜索入口，统一从用户页进行搜索

        top_box = QtWidgets.QVBoxLayout()
        top_box.setSpacing(8)
        self.btn_chat = NavigationButton("聊天")
        self.btn_users = NavigationButton("用户")
        self.btn_groups = NavigationButton("组")
        top_box.addWidget(self.btn_chat)
        top_box.addWidget(self.btn_users)
        top_box.addWidget(self.btn_groups)
        # 顶部不添加内部拉伸，避免占满空间导致搜索按钮无法居中

        bottom_box = QtWidgets.QVBoxLayout()
        bottom_box.setSpacing(8)
        self.btn_emotes = NavigationButton("表情管理")
        self.btn_keys = NavigationButton("密钥")
        self.btn_profile = NavigationButton("信息")
        self.btn_settings = NavigationButton("设置")
        bottom_box.addWidget(self.btn_emotes)
        bottom_box.addWidget(self.btn_keys)
        bottom_box.addWidget(self.btn_profile)
        bottom_box.addWidget(self.btn_settings)
        # 布局顺序：顶部按钮组 -> 拉伸 -> 底部按钮组
        outer_layout.addLayout(top_box)
        outer_layout.addStretch()
        outer_layout.addLayout(bottom_box)

        # 保持样式由全局主题控制，避免固定浅色影响暗色模式

        return panel

    def _build_content_panel(self) -> QtWidgets.QWidget:
        self._stack = QtWidgets.QStackedWidget()
        # 登录页（优先）
        self._login_page = LoginPage()
        self._stack.addWidget(self._login_page)
        # 聊天页
        self._user_page = UserPage()
        self._stack.addWidget(self._user_page)
        # 用户列表页
        self._users_page = UsersListPage()
        self._stack.addWidget(self._users_page)
        # 组管理页
        self._groups_page = GroupsPage()
        self._stack.addWidget(self._groups_page)
        # 文件要约在 bind_backend 中处理（此处仅保留页面搭建）
        # 截图页仍保留类以便复用逻辑，但不放入导航
        # 表情页
        self._emotes_page = EmotesPage()
        self._stack.addWidget(self._emotes_page)
        # 信息页
        self._info_page = InfoPage()
        self._stack.addWidget(self._info_page)
        # 密钥页
        self._keys_page = KeyPage()
        self._stack.addWidget(self._keys_page)
        # 设置页
        self._settings_page = SettingsPage()
        self._stack.addWidget(self._settings_page)

        # 绑定导航
        self.btn_users.clicked.connect(lambda: self._stack.setCurrentWidget(self._users_page))
        self.btn_chat.clicked.connect(lambda: self._stack.setCurrentWidget(self._user_page))
        self.btn_groups.clicked.connect(lambda: self._stack.setCurrentWidget(self._groups_page))
        # 截图不再作为独立页面入口
        self.btn_emotes.clicked.connect(lambda: self._stack.setCurrentWidget(self._emotes_page))
        self.btn_keys.clicked.connect(lambda: self._stack.setCurrentWidget(self._keys_page))
        self.btn_profile.clicked.connect(lambda: self._stack.setCurrentWidget(self._info_page))
        self.btn_settings.clicked.connect(lambda: self._stack.setCurrentWidget(self._settings_page))
        # 默认进入聊天页
        self._stack.setCurrentWidget(self._login_page)
        # 已移除左侧搜索按钮，保留用户页自身搜索框
        return self._stack

    def bind_backend(self, backend):
        # backend: instance of GuiBackend
        try:
            backend.message_signal.connect(self._user_page.append_message)
            backend.file_offer_signal.connect(lambda sender, name, size: self._user_page.append_file_notice(sender, name))
            backend.start()
            # ---- 文件要约整合到聊天页 ----
            self._known_offers = set()
            def _refresh_offers():
                try:
                    offers = backend.list_incoming_offers() or {}
                except Exception:
                    offers = {}
                for oid, meta in offers.items():
                    if oid not in self._known_offers:
                        self._known_offers.add(oid)
                        self._user_page.append_incoming_offer(
                            oid,
                            meta.get('uname') or meta.get('ip','?'),
                            meta.get('ip','?'),
                            meta.get('name','file'),
                            int(meta.get('size',0))
                        )
            _refresh_offers()
            try:
                backend.offers_updated.connect(_refresh_offers)
            except Exception:
                pass
            def _on_file_progress(oid: str, bytes_done: int):
                try:
                    meta = backend.list_incoming_offers().get(oid, {})
                except Exception:
                    meta = {}
                name = meta.get('name','file')
                total = int(meta.get('size',0))
                self._user_page.append_offer_progress(oid, name, bytes_done, total)
            try:
                backend.file_progress.connect(_on_file_progress)
            except Exception:
                pass
            def _on_file_saved(oid: str, path: str):
                try:
                    meta = backend.list_incoming_offers().get(oid, {})
                except Exception:
                    meta = {}
                name = meta.get('name','file')
                self._user_page.append_offer_saved(name, path)
                self._stack.setCurrentWidget(self._user_page)
            try:
                backend.file_saved.connect(_on_file_saved)
            except Exception:
                pass
            def _on_anchor(href: str):
                try:
                    if href.startswith('accept:'):
                        oid = href.split(':',1)[1]
                        try:
                            dl_dir = getattr(getattr(backend,'zcli',None),'download_dir','') or os.getcwd()
                        except Exception:
                            dl_dir = os.getcwd()
                        backend.accept_offer(oid, dl_dir)
                    elif href.startswith('cancel:'):
                        oid = href.split(':',1)[1]
                        backend.cancel_offer(oid)
                except Exception:
                    pass
            try:
                self._user_page.sigAnchor.connect(_on_anchor)
            except Exception:
                pass
            # 初始同步设置页 UI 与后端配置
            try:
                z = getattr(backend, 'zcli', None)
                if z:
                    self._settings_page.cmb_lang.setCurrentText(getattr(z, 'language', 'zhCN'))
                    self._settings_page.cmb_status.setCurrentText(getattr(z, 'status', 'online'))
                    self._settings_page.cmb_enc.setCurrentText(getattr(z, 'encoding', 'utf-8'))
                    try:
                        self._user_page.encoding_label.setText(f"编码: {getattr(z,'encoding','utf-8')}")
                    except Exception:
                        pass
                    try:
                        dld = getattr(z, 'download_dir', '') or ''
                        if dld:
                            self._settings_page.edit_dir.setText(dld)
                    except Exception:
                        pass
                self._settings_page.cmb_theme.setCurrentText(backend.get_ui_theme())
                try:
                    ss = backend.get_screenshot_dir() or ''
                    if ss:
                        self._settings_page.edit_ss_dir.setText(ss)
                except Exception:
                    pass
                try:
                    av = backend.get_ui_avatar() if hasattr(backend, 'get_ui_avatar') else ''
                    if av:
                        self._settings_page.edit_avatar.setText(av)
                except Exception:
                    pass
            except Exception:
                pass
            # 初始不预设用户信息，由目标变化与登录事件更新
            # populate target combo
            def update_targets():
                try:
                    cb = self._user_page.target_combo
                    cb.blockSignals(True)
                    cb.clear()
                    cb.addItem("all")
                    cb.setItemData(0, "all")
                    # 本地用户显示为 用户名[IP:xxx][LOCAL]
                    local_ip = ""
                    try:
                        local_ip = backend.get_net_info().get('local_ip','')
                        uname = getattr(getattr(backend, 'zcli', None), 'username', '') or '我'
                        if local_ip:
                            local_disp = f"{uname}[IP:{local_ip}][LOCAL]"
                            cb.addItem(local_disp)
                            cb.setItemData(cb.count()-1, f"ip:{local_ip}")
                    except Exception:
                        pass
                    for n in backend.get_nodes():
                        # 跳过已作为本地的节点条目（IP 相同）
                        try:
                            if local_ip and n.ip == local_ip:
                                continue
                        except Exception:
                            pass
                        disp = f"{n.username}[IP:{n.ip}]"
                        cb.addItem(disp)
                        cb.setItemData(cb.count()-1, f"ip:{n.ip}")
                    cb.blockSignals(False)
                except Exception:
                    pass
            # refresh on button
            self._user_page.refresh_targets_btn.clicked.connect(update_targets)
            # periodic refresh
            timer = QtCore.QTimer(self)
            timer.timeout.connect(update_targets)
            timer.start(3000)

            # wire send button
            def _resolve_target_for_send():
                cb = self._user_page.target_combo
                idx = cb.currentIndex()
                data = cb.itemData(idx)
                return data or cb.currentText()

            def on_send():
                target = _resolve_target_for_send()
                text = self._user_page.outbox.toPlainText().strip()
                files = self._user_page.get_pending_files()
                if not text and not files:
                    return
                # 计算显示名
                cb = self._user_page.target_combo
                disp = cb.currentText()
                if disp == "all":
                    if target.startswith("ip:"):
                        disp = f"[IP:{target[3:]}]"
                    else:
                        disp = target
                try:
                    if text:
                        backend.send_text(target, text)
                        self._user_page.append_outgoing(disp, text)
                    for p in files:
                        try:
                            backend.send_file(target, p)
                            self._user_page.append_file_sent(disp, p)
                        except Exception:
                            pass
                    self._user_page.outbox.clear()
                    self._user_page.clear_pending_files()
                except Exception:
                    pass

            self._user_page.send_btn.clicked.connect(on_send)
            # Enter 触发发送
            try:
                self._user_page.sigSend.connect(on_send)
            except Exception:
                pass

            # 监听输入框粘贴文件（类似微信）：若剪贴板中包含文件 URL，则直接按当前目标发送文件
            try:
                def _maybe_send_clipboard_files():
                    cb = QtWidgets.QApplication.clipboard()
                    md = cb.mimeData()
                    if not md or not md.hasUrls():
                        return False
                    paths = []
                    for url in md.urls():
                        p = url.toLocalFile()
                        if p:
                            paths.append(p)
                    if not paths:
                        return False
                    # 将粘贴的文件转为“待发送文件块”，不立即发送
                    for p in paths:
                        self._user_page.add_pending_file(p)
                    return True

                # 在 outbox 的 keyRelease 上挂一个过滤器：检测 Ctrl+V 粘贴是否为文件
                # 使用独立 QObject 过滤器代替直接覆盖 eventFilter
                class _PasteFilter(QtCore.QObject):
                    def __init__(self, outer):
                        super().__init__(outer)
                        self.outer = outer
                    def eventFilter(self, a0, a1):
                        try:
                            if a0 is self.outer._user_page.outbox and a1.type() == QtCore.QEvent.KeyRelease:
                                # 使用快捷键匹配方式：检查键与修饰键
                                get_key = getattr(a1, 'key', None)
                                k = get_key() if callable(get_key) else None
                                mods = int(QtWidgets.QApplication.keyboardModifiers())
                                if (k == QtCore.Qt.Key_V) and (mods & int(QtCore.Qt.ControlModifier)):
                                    if _maybe_send_clipboard_files():
                                        return True
                        except Exception:
                            pass
                        return False
                self._paste_filter = _PasteFilter(self)
                self._user_page.outbox.installEventFilter(self._paste_filter)
            except Exception:
                pass

            # 快捷跳转到表情页；截图使用区域选择对话（不在侧栏单独页面）
            self._user_page.emoji_btn.clicked.connect(lambda: self._stack.setCurrentWidget(self._emotes_page))
            # 早期连接误用 _on_region_capture_send，这里移除并统一到类方法 on_region_capture_send（见后文绑定）

            def on_send_file():
                files, _ = QtWidgets.QFileDialog.getOpenFileNames(self, "选择要发送的文件")
                if not files:
                    return
                for p in files:
                    self._user_page.add_pending_file(p)

            # 绑定 UserPage 里预留的发送文件按钮
            try:
                self._user_page.send_file_btn.clicked.connect(on_send_file)
            except Exception:
                pass
            # 编码自检：向本机 IP 发送一条包含中/英/Emoji 的测试文本
            try:
                def _enc_self_test():
                    ip = backend.get_net_info().get('local_ip','')
                    tgt = f"ip:{ip}" if ip else "all"
                    sample = "编码自检：中文✓ English✓ Emoji😀 αßé"
                    backend.send_text(tgt, sample)
                    self._user_page.append_outgoing(self._user_page.target_combo.currentText() or tgt, sample)
                self._user_page.enc_test_btn.clicked.connect(_enc_self_test)
            except Exception:
                pass

            # LoginPage 登录处理：登录后显示导航并切回聊天页
            try:
                def _on_login_from_page(name: str, ip: str):
                    if not name:
                        return
                    # 先绑定选定 IP（如有），再登录与发现
                    try:
                        if ip:
                            backend.bind_ip(ip)
                    except Exception:
                        pass
                    backend.login(name)
                    backend.discover()
                    update_targets()
                    # 默认选中 LOCAL 目标
                    try:
                        local_ip = backend.get_net_info().get('local_ip','')
                        cb = self._user_page.target_combo
                        # 找到 itemData 为 ip:local_ip 的项
                        found = -1
                        for i in range(cb.count()):
                            if (cb.itemData(i) or "") == (f"ip:{local_ip}"):
                                found = i; break
                        if found >= 0:
                            cb.setCurrentIndex(found)
                    except Exception:
                        pass
                    # 显示左侧导航
                    try:
                        self.nav_panel.setVisible(True)
                    except Exception:
                        pass
                    # 在发送行显示当前登录用户信息
                    try:
                        local_ip = ip or getattr(backend, 'get_net_info', lambda: {}).__call__().get('local_ip','')
                        uname = getattr(getattr(backend, 'zcli', None), 'username', name)
                        status_raw = getattr(getattr(backend, 'zcli', None), 'status', 'online')
                        lang = getattr(getattr(backend, 'zcli', None), 'language', 'zhCN')
                        status_map = {
                            'zhCN': {'online':'在线','busy':'忙碌','away':'离开'},
                            'enUS': {'online':'online','busy':'busy','away':'away'},
                        }
                        status_disp = status_map.get(lang, status_map['zhCN']).get(status_raw, status_raw)
                        self._user_page.set_local_ip(local_ip)
                        self._user_page.set_user_status(uname, status_disp)
                        # 设置页网卡 IP 下拉选中登录时选择的 IP
                        try:
                            if local_ip:
                                idx = self._settings_page.cmb_iface.findText(local_ip)
                                if idx >= 0:
                                    self._settings_page.cmb_iface.setCurrentIndex(idx)
                        except Exception:
                            pass
                    except Exception:
                        pass
                    # 切回聊天页
                    self._stack.setCurrentWidget(self._user_page)
                self._login_page.sigLogin.connect(_on_login_from_page)
            except Exception:
                pass

            # discover 来自用户列表页的发现按钮
            try:
                self._users_page.sigDiscover.connect(lambda ip: (backend.discover(ip or None), update_targets()))
            except Exception:
                pass

            # 历史查看（基于当前目标）
            def on_show_history():
                # 使用 itemData 解析底层 target(ip:/group:/all)，兼容本地与显示名变体
                cb = self._user_page.target_combo
                idx = cb.currentIndex()
                target_raw = cb.itemData(idx) or cb.currentText()
                if not target_raw:
                    return
                dlg = QtWidgets.QDialog(self)
                dlg.setWindowTitle("历史记录")
                v = QtWidgets.QVBoxLayout(dlg)
                text = QtWidgets.QTextEdit(); text.setReadOnly(True)
                v.addWidget(text)
                btn = QtWidgets.QPushButton("关闭"); btn.clicked.connect(dlg.accept)
                v.addWidget(btn)
                lines = []
                try:
                    if target_raw.startswith("user:"):
                        name = target_raw[5:]
                        items = backend.get_user_history(name)
                        for ts, d, t, ip in items:
                            arrow = ">>" if d == "out" else "<<"
                            lines.append(f"[{QtCore.QDateTime.fromSecsSinceEpoch(int(ts)).toString('yyyy-MM-dd hh:mm:ss')}] {arrow} {t}")
                    elif target_raw.startswith("group:"):
                        g = target_raw[6:]
                        items = backend.get_group_history(g)
                        for ts, d, t, uname, ip in items:
                            arrow = ">>" if d == "out" else "<<"
                            lines.append(f"[{QtCore.QDateTime.fromSecsSinceEpoch(int(ts)).toString('yyyy-MM-dd hh:mm:ss')}] {uname}@{ip} {arrow} {t}")
                    elif target_raw == "all":
                        # 聚合所有节点历史
                        for n in backend.get_nodes():
                            msgs = getattr(backend.zcli, 'history', {}).get(n.ip, [])
                            for ts, d, t in msgs:
                                arrow = ">>" if d == "out" else "<<"
                                lines.append(f"[{QtCore.QDateTime.fromSecsSinceEpoch(int(ts)).toString('yyyy-MM-dd hh:mm:ss')}] {n.username}@{n.ip} {arrow} {t}")
                    elif target_raw.startswith("ip:"):
                        ip = target_raw[3:]
                        msgs = getattr(backend.zcli, 'history', {}).get(ip, [])
                        # 找用户名
                        uname = ip
                        for n in backend.get_nodes():
                            if n.ip == ip:
                                uname = n.username; break
                        for ts, d, t in msgs:
                            arrow = ">>" if d == "out" else "<<"
                            lines.append(f"[{QtCore.QDateTime.fromSecsSinceEpoch(int(ts)).toString('yyyy-MM-dd hh:mm:ss')}] {uname}@{ip} {arrow} {t}")
                    else:
                        # 形如 显示名[IP:...] 或 本地显示；提取 IP
                        if "[IP:" in target_raw:
                            ip = target_raw.split("[IP:",1)[1].split("]",1)[0]
                            msgs = getattr(backend.zcli, 'history', {}).get(ip, [])
                            uname = target_raw.split("[IP:",1)[0]
                            for ts, d, t in msgs:
                                arrow = ">>" if d == "out" else "<<"
                                lines.append(f"[{QtCore.QDateTime.fromSecsSinceEpoch(int(ts)).toString('yyyy-MM-dd hh:mm:ss')}] {uname}@{ip} {arrow} {t}")
                except Exception:
                    pass
                text.setPlainText("\n".join(lines) if lines else "(无记录)")
                dlg.resize(480, 360)
                dlg.exec_()

            self._user_page.history_btn.clicked.connect(on_show_history)

            # 用户列表页交互
            def refresh_users_page():
                try:
                    self._users_page.update_nodes(backend.get_nodes(), backend.list_groups(), backend.get_net_info().get('local_ip',''))
                except Exception:
                    pass

            refresh_users_page()
            timer2 = QtCore.QTimer(self)
            timer2.timeout.connect(refresh_users_page)
            timer2.start(3000)

            def on_pick_target(text: str):
                try:
                    if text:
                        # 选择后切到聊天页，并按 itemData(ip:...) 匹配项
                        cb = self._user_page.target_combo
                        found = -1
                        for i in range(cb.count()):
                            if (cb.itemData(i) or "") == text:
                                found = i; break
                        if found >= 0:
                            cb.setCurrentIndex(found)
                        else:
                            cb.setCurrentText("all")
                        self._stack.setCurrentWidget(self._user_page)
                except Exception:
                    pass

            self._users_page.targetPicked.connect(on_pick_target)

            # 目标改变时，更新聊天页顶部与窗口标题
            def _refresh_target_header_from_targettext(tgt: str):
                # 未登录（侧栏隐藏）时，标题固定为 ZFeiQ
                try:
                    if not self.nav_panel.isVisible():
                        self.setWindowTitle("ZFeiQ")
                        return
                except Exception:
                    pass
                name_disp = "-"; ip_disp = "-"
                try:
                    if tgt.startswith("ip:"):
                        ip_disp = tgt[3:]
                        for n in backend.get_nodes():
                            if n.ip == ip_disp:
                                name_disp = n.username; break
                    elif "[IP:" in tgt:
                        name_disp = tgt.split("[IP:",1)[0]
                        ip_disp = tgt.split("[IP:",1)[1].rstrip("]")
                    elif tgt.startswith("group:"):
                        name_disp = tgt
                    elif tgt == "all":
                        name_disp = "all"
                except Exception:
                    pass
                try:
                    head = name_disp if ip_disp in ("-", "") else f"{name_disp}[IP:{ip_disp}]"
                    # 若为本地 IP，追加 [LOCAL]
                    try:
                        local_ip = backend.get_net_info().get('local_ip','')
                        if ip_disp == local_ip and ip_disp not in ("-", ""):
                            head += "[LOCAL]"
                    except Exception:
                        pass
                    self._user_page.username_label.setText(head)
                    self._user_page.ip_label.setText("")
                    self.setWindowTitle(f"{head} - ZFeiQ" if name_disp != "-" else "ZFeiQ")
                except Exception:
                    pass

            try:
                def _on_target_changed(idx: int):
                    cb = self._user_page.target_combo
                    data = cb.itemData(idx) or cb.itemText(idx)
                    _refresh_target_header_from_targettext(data)
                self._user_page.target_combo.currentIndexChanged.connect(_on_target_changed)
                _on_target_changed(self._user_page.target_combo.currentIndex())
            except Exception:
                pass

            # 组管理页绑定
            def refresh_groups_page():
                try:
                    self._groups_page.update_groups(backend.list_groups())
                except Exception:
                    pass

            refresh_groups_page()
            timer3 = QtCore.QTimer(self)
            timer3.timeout.connect(refresh_groups_page)
            timer3.start(3000)

            def on_group_add(group: str, user: str):
                if group and user:
                    backend.group_add(group, user)
                    refresh_groups_page()

            def on_group_remove(group: str, user: str):
                if group and user:
                    backend.group_remove(group, user)
                    refresh_groups_page()

            self._groups_page.sigAdd.connect(on_group_add)
            self._groups_page.sigRemove.connect(on_group_remove)
            def _enter_group_chat(g: str):
                if not g:
                    return
                # 在聊天页选择目标为 group:g
                try:
                    cb = self._user_page.target_combo
                    # 查找是否已有该 group 目标，没有则添加
                    found = False
                    for i in range(cb.count()):
                        if cb.itemText(i) == g or cb.itemData(i) == f"group:{g}":
                            cb.setCurrentIndex(i)
                            found = True
                            break
                    if not found:
                        cb.addItem(g)
                        cb.setItemData(cb.count()-1, f"group:{g}")
                        cb.setCurrentIndex(cb.count()-1)
                    self._stack.setCurrentWidget(self._user_page)
                except Exception:
                    self._stack.setCurrentWidget(self._user_page)
            self._groups_page.sigEnterChat.connect(_enter_group_chat)

            def _rename_group(old: str, new: str):
                if not old or not new or old == new:
                    return
                try:
                    groups = backend.list_groups() or {}
                    members = list(groups.get(old, []))
                    # 新建新组并迁移成员
                    for u in members:
                        try:
                            backend.group_add(new, u)
                        except Exception:
                            pass
                    # 删除旧组
                    try:
                        backend.group_remove(old, None)
                    except Exception:
                        pass
                    # 刷新分组页
                    refresh_groups_page()
                    # 刷新聊天目标下拉
                    update_targets()
                    # 刷新用户页分组列表
                    if hasattr(self._users_page, "update_nodes"):
                        self._users_page.update_nodes(backend.get_nodes(), backend.list_groups(), backend.get_net_info().get('local_ip',''))
                except Exception:
                    pass
            self._groups_page.sigRename.connect(_rename_group)

            # 独立文件页已移除；文件要约逻辑已在 bind_backend 中整合到聊天页

            # 信息页绑定
            def refresh_info():
                info = backend.get_net_info()
                self._info_page.set_net_info(info)
                self._info_page.update_nodes(backend.get_nodes())
                # 同步子网掩码到设置页（若后端提供或可从前缀推导）
                try:
                    mask = None
                    if hasattr(backend, 'get_subnet_mask'):
                        mask = backend.get_subnet_mask() or None
                    if not mask:
                        pre = info.get('iface_prefix','')
                        if isinstance(pre, str) and '/' in pre:
                            try:
                                bits = int(pre.split('/',1)[1])
                                if 0 <= bits <= 32:
                                    m = (0xffffffff << (32 - bits)) & 0xffffffff
                                    mask = '.'.join(str((m >> (8*i)) & 0xff) for i in [3,2,1,0])
                            except Exception:
                                pass
                    if mask:
                        self._settings_page.edit_mask.setText(mask)
                except Exception:
                    pass
                # 刷新网卡下拉
                try:
                    ifaces = backend.get_local_ifaces()
                    self._settings_page.cmb_iface.blockSignals(True)
                    cur = self._settings_page.cmb_iface.currentText()
                    self._settings_page.cmb_iface.clear()
                    for ip, pre in ifaces:
                        self._settings_page.cmb_iface.addItem(f"{ip}")
                    # 还原选择
                    if cur:
                        idx = self._settings_page.cmb_iface.findText(cur)
                        if idx >= 0:
                            self._settings_page.cmb_iface.setCurrentIndex(idx)
                    self._settings_page.cmb_iface.blockSignals(False)
                except Exception:
                    pass
                # 同步发送行本地用户信息
                try:
                    uname = getattr(getattr(backend, 'zcli', None), 'username', '')
                    local_ip = info.get('local_ip','')
                    status_raw = getattr(getattr(backend, 'zcli', None), 'status', 'online')
                    lang = getattr(getattr(backend, 'zcli', None), 'language', 'zhCN')
                    status_map = {
                        'zhCN': {'online':'在线','busy':'忙碌','away':'离开'},
                        'enUS': {'online':'online','busy':'busy','away':'away'},
                    }
                    status_disp = status_map.get(lang, status_map['zhCN']).get(status_raw, status_raw)
                    if uname:
                        self._user_page.set_local_ip(local_ip)
                        self._user_page.set_user_status(uname, status_disp)
                    try:
                        enc = getattr(getattr(backend, 'zcli', None), 'encoding', 'utf-8')
                        self._user_page.encoding_label.setText(f"编码: {enc}")
                    except Exception:
                        pass
                except Exception:
                    pass
                # 同步登录页 IP 下拉
                try:
                    ifaces = backend.get_local_ifaces()
                    self._login_page.ip_combo.blockSignals(True)
                    cur = self._login_page.ip_combo.currentText()
                    self._login_page.ip_combo.clear()
                    for ip, pre in ifaces:
                        self._login_page.ip_combo.addItem(f"{ip}")
                    if cur:
                        idx = self._login_page.ip_combo.findText(cur)
                        if idx >= 0:
                            self._login_page.ip_combo.setCurrentIndex(idx)
                    self._login_page.ip_combo.blockSignals(False)
                except Exception:
                    pass
            refresh_info()
            tinfo = QtCore.QTimer(self)
            tinfo.timeout.connect(refresh_info)
            tinfo.start(3000)
            self._info_page.sigDiscover.connect(lambda ip: backend.discover(ip or None))

            # 设置页绑定
            self._settings_page.sigApply.connect(lambda cfg: self._apply_settings(backend, cfg))
            # 设置页登出
            try:
                self._settings_page.sigLogout.connect(lambda: self._on_logout_to_login(backend))
            except Exception:
                pass

            # 初始主题应用
            try:
                theme = backend.get_ui_theme()
                self._settings_page.cmb_theme.setCurrentText(theme)
                self._apply_theme(theme)
            except Exception:
                pass
            # 初始头像应用（若已配置）
            try:
                if hasattr(backend, 'get_ui_avatar'):
                    ap = backend.get_ui_avatar()
                    if ap:
                        self._user_page.set_avatar(ap)
            except Exception:
                pass

            # 表情页与截图页发送绑定（按当前聊天目标发送）
            def _current_target():
                cb = self._user_page.target_combo
                idx = cb.currentIndex()
                return (cb.itemData(idx) or cb.currentText())

            def _send_path(path: str):
                tgt = _current_target()
                if not tgt or not path:
                    return
                try:
                    backend.send_file(tgt, path)
                    # 在聊天区提示已发送文件/表情
                    self._user_page.append_file_notice("我", os.path.basename(path))
                    # 发送后切回聊天页
                    self._stack.setCurrentWidget(self._user_page)
                except Exception:
                    pass

            self._emotes_page.sigSend.connect(_send_path)
            # 不使用单独截图页发送；事件改为类方法
            try:
                self._user_page.screenshot_btn.clicked.connect(lambda: self.on_region_capture_send(backend))
            except Exception:
                pass
            # 常用语菜单
            try:
                self._user_page.quicktext_btn.clicked.connect(self.on_quicktext_menu)
            except Exception:
                pass
            # 密钥管理页绑定
            try:
                try:
                    self._keys_page.cmb_mode.setCurrentText(getattr(backend, 'get_encrypt_mode', lambda: 'off')())
                except Exception:
                    pass
                def _refresh_fp():
                    try:
                        fp = getattr(backend, 'get_pubkey_fingerprint', lambda: '(n/a)')()
                        self._keys_page.lbl_fp.setText(f"指纹：{fp}")
                    except Exception:
                        self._keys_page.lbl_fp.setText("指纹：(error)")
                _refresh_fp()
                self._keys_page.btn_refresh.clicked.connect(_refresh_fp)
                self._keys_page.cmb_mode.currentTextChanged.connect(lambda v: (backend.set_encrypt_mode(v), backend.save_state()))
                def _on_regen():
                    ok = getattr(backend, 'regenerate_keys', lambda: False)()
                    _refresh_fp()
                    QtWidgets.QMessageBox.information(self, "密钥", "已重生成密钥" if ok else "重生成失败")
                self._keys_page.btn_regen.clicked.connect(_on_regen)
                def _on_export():
                    path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "导出公钥", os.path.join(os.getcwd(), "keys", "pub_export.pem"), filter="PEM (*.pem)")
                    if not path:
                        return
                    res = getattr(backend, 'export_pubkey', lambda p: None)(path)
                    QtWidgets.QMessageBox.information(self, "导出公钥", f"已导出至:\n{res}" if res else "导出失败")
                self._keys_page.btn_export.clicked.connect(_on_export)
            except Exception:
                pass
            # 表情页返回聊天
            try:
                self._emotes_page.btn_back.clicked.connect(lambda: self._stack.setCurrentWidget(self._user_page))
            except Exception:
                pass
        except Exception:
            pass

    def _on_logout_to_login(self, backend):
        try:
            backend.logout()
        except Exception:
            pass
        try:
            # 清空聊天页顶部与发送行显示
            self._user_page.username_label.setText("用户名：未登录")
            self._user_page.ip_label.setText("IP：-.-.-.-")
            self._user_page.me_info_label.setText("")
            self.setWindowTitle("ZFeiQ")
            # 隐藏侧边导航并回到登录页
            self.nav_panel.setVisible(False)
            self._stack.setCurrentWidget(self._login_page)
        except Exception:
            pass

    def _apply_settings(self, backend, cfg: Dict):
        try:
            if "language" in cfg:
                backend.set_language(cfg["language"]) 
                self._apply_language(cfg["language"]) 
            if "status" in cfg:
                backend.set_status(cfg["status"]) 
            if "encoding" in cfg:
                backend.set_encoding(cfg["encoding"]) 
            if "ui_theme" in cfg:
                backend.set_ui_theme(cfg["ui_theme"]) 
                self._apply_theme(cfg["ui_theme"]) 
            if "debug" in cfg:
                backend.set_debug(bool(cfg["debug"]))
            if "trace" in cfg:
                backend.set_trace(bool(cfg["trace"]))
            if "keepalive" in cfg:
                backend.set_keepalive(float(cfg["keepalive"]))
            if "expire" in cfg:
                backend.set_expire(float(cfg["expire"]))
            if "bind_ip" in cfg and cfg["bind_ip"]:
                backend.bind_ip(cfg["bind_ip"]) 
            if "subnet_mask" in cfg and cfg["subnet_mask"]:
                try:
                    if hasattr(backend, 'set_subnet_mask'):
                        backend.set_subnet_mask(cfg["subnet_mask"])  # 后端支持时生效
                except Exception:
                    pass
            if "download_dir" in cfg and cfg["download_dir"]:
                backend.set_download_dir(cfg["download_dir"]) 
            if "screenshot_dir" in cfg and cfg["screenshot_dir"]:
                try:
                    backend.set_screenshot_dir(cfg["screenshot_dir"]) 
                except Exception:
                    pass
            if "ui_avatar" in cfg and cfg["ui_avatar"]:
                try:
                    backend.set_ui_avatar(cfg["ui_avatar"]) 
                    # 更新界面头像显示
                    try:
                        self._user_page.set_avatar(cfg["ui_avatar"]) 
                    except Exception:
                        pass
                except Exception:
                    pass
            # persist after applying
            backend.save_state()
        except Exception:
            pass

    def _apply_theme(self, mode: str):
        app = QtWidgets.QApplication.instance()
        self._current_theme = mode if mode in ("light","dark") else "light"
        if self._current_theme == "dark":
            dark_qss = """
            QMainWindow, QWidget { background: #121212; color: #e0e0e0; }
            QLineEdit, QTextEdit, QComboBox, QListWidget, QGroupBox, QSpinBox, QDoubleSpinBox {
              background: #1e1e1e; color: #e0e0e0; border: 1px solid #2a2a2a; border-radius: 6px; }
            QPushButton { background: #2d2d2d; color: #e0e0e0; border: 1px solid #3a3a3a; border-radius: 6px; padding: 6px; }
            QPushButton:hover { background: #3a3a3a; }
            QToolButton { color: #e0e0e0; border: none; padding: 6px; }
            QToolButton:hover { background: #2a2a2a; }
            #navPanel { background: #161616; }
            QProgressBar { background: #1e1e1e; color: #e0e0e0; border: 1px solid #2a2a2a; border-radius: 6px; text-align: center; }
            QProgressBar::chunk { background: #3f7cff; }
            QListWidget::item { background: #1a1a1a; }
                        QListWidget::item:hover { background: #242424; }
                        QListWidget::item:selected { background: #2f2f2f; color: #ffffff; }
            QComboBox QAbstractItemView { background: #1e1e1e; selection-background-color: #3a3a3a; }
            QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; }
                        QTabWidget::pane { border-top: 1px solid #2a2a2a; }
                        QTabBar::tab { background: #1b1b1b; color: #bdbdbd; padding: 6px 10px; border: 1px solid #2a2a2a; border-bottom: none; border-top-left-radius: 6px; border-top-right-radius: 6px; }
                        QTabBar::tab:selected { background: #2a2a2a; color: #ffffff; }
                        QTabBar::tab:hover { background: #242424; }
                        QScrollBar:vertical { background: #1a1a1a; width: 10px; margin: 0; }
                        QScrollBar::handle:vertical { background: #3a3a3a; min-height: 20px; border-radius: 4px; }
                        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
                        QScrollBar:horizontal { background: #1a1a1a; height: 10px; margin: 0; }
                        QScrollBar::handle:horizontal { background: #3a3a3a; min-width: 20px; border-radius: 4px; }
                        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
                        QToolTip { background: #2a2a2a; color: #e0e0e0; border: 1px solid #3a3a3a; }
            """
            if isinstance(app, QtWidgets.QApplication):
                app.setStyleSheet(dark_qss)
        else:
            light_qss = """
            QMainWindow { background: #ffffff; }
            QLineEdit, QTextEdit { border:1px solid #d0d0d0; border-radius:6px; padding:6px; }
            QToolButton { border:none; padding:6px; }
            #navPanel { background: #f7f7f8; }
                        QListWidget::item:hover { background: #f0f0f0; }
                        QTabWidget::pane { border-top: 1px solid #e6e6e6; }
                        QTabBar::tab { background: #fafafa; color: #333333; padding: 6px 10px; border: 1px solid #e6e6e6; border-bottom: none; border-top-left-radius: 6px; border-top-right-radius: 6px; }
                        QTabBar::tab:selected { background: #ffffff; }
            """
            if isinstance(app, QtWidgets.QApplication):
                app.setStyleSheet(light_qss)

    def _apply_language(self, lang: str):
        zh = {
            'chat': '聊天', 'users': '用户', 'groups': '组', 'files': '文件', 'emotes': '表情', 'info': '信息', 'settings': '设置',
            'emoji': '表情', 'screenshot': '截图', 'quick': '常用语', 'history': '历史', 'sendfile': '发送文件', 'send': '发送',
            'login': '登录', 'logout': '注销', 'discover': '发现', 'username_ph': '输入用户名…', 'search_ph': '搜索用户名或IP…',
            'accept': '接收', 'cancel': '放弃', 'pickdir': '选择保存目录', 'setdefault': '设为默认', 'enc_test': '编码自检',
            'lang': '语言', 'status': '状态', 'encoding': '编码', 'theme': '主题', 'iface': '网卡IP', 'download_dir': '下载目录',
            'screenshot_dir': '截图目录', 'avatar': '头像', 'apply': '应用', 'help': '帮助', 'keepalive': '保活间隔(s)', 'expire': '过期时长(s)',
            'bind_ip': '绑定IP', 'subnet_mask': '子网掩码', 'logout_long': '登出 / Logout', 'enc_mode': '加密模式', 'refresh': '刷新',
            'member_add': '添加成员', 'member_del': '移除成员', 'group_send': '群发', 'online_nodes': '在线节点', 'online': '在线', 'group_search_ph': '搜索组名/成员…'
        }
        en = {
            'chat': 'Chat', 'users': 'Users', 'groups': 'Groups', 'files': 'Files', 'emotes': 'Emotes', 'info': 'Info', 'settings': 'Settings',
            'emoji': 'Emotes', 'screenshot': 'Screenshot', 'quick': 'Snippets', 'history': 'History', 'sendfile': 'Send File', 'send': 'Send',
            'login': 'Login', 'logout': 'Logout', 'discover': 'Discover', 'username_ph': 'Enter username…', 'search_ph': 'Search user or IP…',
            'accept': 'Accept', 'cancel': 'Decline', 'pickdir': 'Pick Save Dir', 'setdefault': 'Set Default', 'enc_test': 'Encoding Self-Test',
            'lang': 'Language', 'status': 'Status', 'encoding': 'Encoding', 'theme': 'Theme', 'iface': 'Interface IP', 'download_dir': 'Download Dir',
            'screenshot_dir': 'Screenshot Dir', 'avatar': 'Avatar', 'apply': 'Apply', 'help': 'Help', 'keepalive': 'Keepalive(s)', 'expire': 'Expire(s)',
            'bind_ip': 'Bind IP', 'subnet_mask': 'Subnet Mask', 'logout_long': 'Logout', 'enc_mode': 'Encryption Mode', 'refresh': 'Refresh',
            'member_add': 'Add Member', 'member_del': 'Remove Member', 'group_send': 'Group Send', 'online_nodes': 'Online Nodes', 'online': 'Online', 'group_search_ph': 'Search group/member…'
        }
        t = zh if lang == 'zhCN' else en
        # 逐项设置，避免某一项不存在时整体失败
        def _set(obj, attr, value):
            try:
                getattr(obj, attr).setText(value)
            except Exception:
                pass
        _set(self, 'btn_chat', t['chat'])
        _set(self, 'btn_users', t['users'])
        _set(self, 'btn_groups', t['groups'])
        _set(self, 'btn_emotes', t['emotes'])
        _set(self, 'btn_profile', t['info'])
        _set(self, 'btn_settings', t['settings'])
        _set(self._user_page, 'emoji_btn', t['emoji'])
        _set(self._user_page, 'screenshot_btn', t['screenshot'])
        _set(self._user_page, 'quicktext_btn', t['quick'])
        _set(self._user_page, 'history_btn', t['history'])
        _set(self._user_page, 'send_file_btn', t['sendfile'])
        _set(self._user_page, 'send_btn', t['send'])
        _set(self._user_page, 'enc_test_btn', t.get('enc_test', ''))
        try:
            self._users_page.search_edit.setPlaceholderText(t['search_ph'])
        except Exception:
            pass
        _set(self._users_page, 'discover_btn', t['discover'])
        # 登录页占位符 & 组搜索占位符
        try:
            self._login_page.name_edit.setPlaceholderText(t['username_ph'])
        except Exception:
            pass
        try:
            self._groups_page.member_filter.setPlaceholderText(t.get('group_search_ph',''))
        except Exception:
            pass
        # 设置页标签翻译
        try:
            if hasattr(self._settings_page, 'apply_translations'):
                self._settings_page.apply_translations(t)
        except Exception:
            pass

    # ---- class-level handlers ----
    def on_region_capture_send(self, backend):
        try:
            try:
                # 状态栏提示进入截图模式
                self.statusBar().showMessage("截图模式：拖拽选择区域，Esc 取消", 4000)
            except Exception:
                pass
            # 全屏遮罩选区
            sel = _RegionSelector(None)
            r = sel.exec_()
            if not r or r.width() <= 0 or r.height() <= 0:
                return
            screen = QtWidgets.QApplication.primaryScreen()
            pm = None
            try:
                # 截取当前屏幕，再裁剪到选区
                geo = screen.geometry()
                # 使用 QApplication.desktop().winId() 获取根窗口 ID 进行整屏截图
                root_wid = QtWidgets.QApplication.desktop().winId()
                pm_full = screen.grabWindow(root_wid, geo.x(), geo.y(), geo.width(), geo.height())
                if pm_full and not pm_full.isNull():
                    pm = pm_full.copy(r)
            except Exception:
                pm = None
            if pm is None or pm.isNull():
                return

            # 在截图边缘绘制 5px 灰白色边框以强调区域
            painter = QtGui.QPainter(pm)
            pen = QtGui.QPen(QtGui.QColor(230, 230, 230))
            pen.setWidth(5)
            painter.setPen(pen)
            painter.drawRect(0, 0, pm.width()-1, pm.height()-1)
            painter.end()

            # 保存到截图目录
            try:
                base_dir = backend.get_screenshot_dir() or os.path.join(os.getcwd(), "screenshots")
            except Exception:
                base_dir = os.path.join(os.getcwd(), "screenshots")
            try:
                os.makedirs(base_dir, exist_ok=True)
            except Exception:
                pass
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"shot_{ts}.png"
            path = os.path.join(base_dir, filename)
            try:
                pm.save(path, "PNG")
            except Exception:
                pass

            # 写入剪贴板
            try:
                cb = QtWidgets.QApplication.clipboard()
                cb.setPixmap(pm)
            except Exception:
                pass

            # 状态栏提示
            try:
                self.statusBar().showMessage(f"截图已保存到 {path}，并复制到剪贴板", 5000)
            except Exception:
                pass
        except Exception:
            pass

    def on_quicktext_menu(self):
        try:
            # 从文件加载常用语（可选），否则使用默认
            defaults = [
                "在吗？", "收到。", "稍等一下～", "方便发个文件吗？", "辛苦了！", "谢谢！"
            ]
            items = []
            cfg_path = os.path.join(os.getcwd(), "quick_texts.txt")
            if os.path.isfile(cfg_path):
                try:
                    with open(cfg_path, "r", encoding="utf-8") as f:
                        items = [ln.strip() for ln in f.readlines() if ln.strip()]
                except Exception:
                    items = []
            if not items:
                items = defaults
            if not items:
                return
            m = QtWidgets.QMenu(self)
            acts = []
            for t in items:
                a = m.addAction(t)
                acts.append(a)
            pos = self._user_page.quicktext_btn.mapToGlobal(self._user_page.quicktext_btn.rect().bottomLeft())
            act = m.exec_(pos)
            if act and act.text():
                # 直接插入到输入框光标处
                self._user_page.outbox.insertPlainText(act.text())
                self._user_page.outbox.setFocus()
        except Exception:
            pass


class UsersListPage(QtWidgets.QWidget):
    targetPicked = QtCore.pyqtSignal(str)  # like user:alice or ip:1.2.3.4
    sigDiscover = QtCore.pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._build()
        self._all_items = []  # type: List[str]

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        search_row = QtWidgets.QHBoxLayout()
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("搜索用户名或IP…")
        self.search_edit.textChanged.connect(self._apply_filter)
        self.discover_btn = QtWidgets.QPushButton("发现")
        self.discover_btn.setFixedHeight(self.discover_btn.fontMetrics().height() + 6)
        self.discover_btn.setToolTip("在指定 IP 或广播发现在线用户（留空则广播）")
        search_row.addWidget(self.search_edit, 1)
        search_row.addWidget(self.discover_btn)
        self.list = QtWidgets.QListWidget()
        self.list.itemDoubleClicked.connect(self._emit_pick)
        layout.addLayout(search_row)
        layout.addWidget(self.list, 1)
        self.discover_btn.clicked.connect(lambda: self.sigDiscover.emit(self.search_edit.text().strip()))

    def update_nodes(self, nodes, groups=None, local_ip: str = ""):
        self.list.clear()
        items = []
        for n in nodes:
            tag = " [LOCAL]" if local_ip and getattr(n, 'ip', None) == local_ip else ""
            items.append((f"{n.username} @ {n.ip}{tag}", ("user", n)))
        if groups:
            for g, members in sorted(groups.items()):
                items.append((f"[组] {g} ({len(members)})", ("group", g)))
        self._all_items = [t for t, _ in items]
        for text, meta in items:
            it = QtWidgets.QListWidgetItem(text)
            it.setData(QtCore.Qt.UserRole, meta)
            self.list.addItem(it)
        self._apply_filter()

    def _apply_filter(self):
        q = self.search_edit.text().strip().lower()
        for i in range(self.list.count()):
            it = self.list.item(i)
            if it is None:
                continue
            txt = it.text() if hasattr(it, 'text') else ''
            visible = (q in txt.lower()) if q else True
            if hasattr(it, 'setHidden'):
                it.setHidden(not visible)

    def _emit_pick(self, item: QtWidgets.QListWidgetItem):
        meta = item.data(QtCore.Qt.UserRole)
        if not meta:
            return
        kind, obj = meta
        if kind == "user":
            self.targetPicked.emit(f"ip:{obj.ip}")
        elif kind == "group":
            self.targetPicked.emit(f"group:{obj}")


class GroupsPage(QtWidgets.QWidget):
    sigAdd = QtCore.pyqtSignal(str, str)      # (group, username)
    sigRemove = QtCore.pyqtSignal(str, str)   # (group, username)
    sigEnterChat = QtCore.pyqtSignal(str)     # (group)
    sigRename = QtCore.pyqtSignal(str, str)   # (old, new)

    def __init__(self):
        super().__init__()
        self._build()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        # 顶部：过滤 + 操作按钮
        top_row = QtWidgets.QHBoxLayout()
        self.member_filter = QtWidgets.QLineEdit(); self.member_filter.setPlaceholderText("搜索组名/成员…")
        self.btn_new_group = QtWidgets.QPushButton("新建分组")
        self.btn_rename = QtWidgets.QPushButton("重命名")
        for b in (self.btn_new_group, self.btn_rename):
            b.setFixedHeight(b.fontMetrics().height() + 12)
        top_row.addWidget(self.member_filter, 1)
        top_row.addWidget(self.btn_new_group)
        top_row.addWidget(self.btn_rename)
        layout.addLayout(top_row)

        # 主区：左侧组列表 + 右侧成员与操作
        main_row = QtWidgets.QHBoxLayout()
        self.group_list = QtWidgets.QListWidget(); self.group_list.setMinimumWidth(220)
        main_row.addWidget(self.group_list, 1)

        right = QtWidgets.QVBoxLayout()
        self.members_list = QtWidgets.QListWidget()
        right.addWidget(self.members_list, 1)
        ctrl = QtWidgets.QHBoxLayout()
        self.member_edit = QtWidgets.QLineEdit(); self.member_edit.setPlaceholderText("用户名…")
        btn_add = QtWidgets.QPushButton("添加成员")
        btn_del = QtWidgets.QPushButton("移除成员")
        self.btn_enter_chat = QtWidgets.QPushButton("进入聊天")
        for b in (btn_add, btn_del, self.btn_enter_chat):
            b.setFixedHeight(b.fontMetrics().height() + 12)
        ctrl.addWidget(self.member_edit, 1)
        ctrl.addWidget(btn_add)
        ctrl.addWidget(btn_del)
        ctrl.addWidget(self.btn_enter_chat)
        right.addLayout(ctrl)
        main_row.addLayout(right, 2)

        layout.addLayout(main_row)

        # wiring
        def on_add():
            g = self._current_group()
            u = self.member_edit.text().strip()
            if g and u:
                self.sigAdd.emit(g, u)

        def on_del():
            g = self._current_group()
            item = self.members_list.currentItem()
            if item is not None:
                u = item.text()
            else:
                u = self.member_edit.text().strip()
            if g and u:
                self.sigRemove.emit(g, u)

        btn_add.clicked.connect(on_add)
        btn_del.clicked.connect(on_del)
        self.group_list.currentTextChanged.connect(lambda _: self._update_members())
        self.member_filter.textChanged.connect(self._apply_group_filter)
        self.btn_enter_chat.clicked.connect(lambda: (self.sigEnterChat.emit(self._current_group() or "")))

        def _create_group():
            # 生成唯一默认名 New Group N
            base = "New Group "
            n = 1
            names = set((self._cached_groups or {}).keys())
            while f"{base}{n}" in names:
                n += 1
            g = f"{base}{n}"
            # 在本地视图中先创建空组，真正持久化需添加成员后由后端保存
            self._cached_groups = self._cached_groups or {}
            self._cached_groups[g] = set()
            self.update_groups(self._cached_groups)
            # 选中该组
            items = self.group_list.findItems(g, QtCore.Qt.MatchExactly)
            if items:
                self.group_list.setCurrentItem(items[0])
        self.btn_new_group.clicked.connect(_create_group)

        def _rename_group():
            old = self._current_group()
            if not old:
                return
            new, ok = QtWidgets.QInputDialog.getText(self, "重命名分组", "新名称：", text=old)
            new = (new or "").strip()
            if ok and new and new != old:
                self.sigRename.emit(old, new)
        self.btn_rename.clicked.connect(_rename_group)

    def update_groups(self, groups: dict):
        # groups: {group: set(usernames)}
        # 合并本地空组（可能由“新建分组”创建）
        local = getattr(self, "_cached_groups", {}) or {}
        merged = dict(local)
        for g, m in (groups or {}).items():
            merged[g] = set(m)
        self._cached_groups = merged
        current = self._current_group()
        self.group_list.blockSignals(True)
        self.group_list.clear()
        for g in sorted(self._cached_groups.keys()):
            cnt = len(self._cached_groups.get(g, []))
            it = QtWidgets.QListWidgetItem(f"{g} ({cnt})")
            it.setData(QtCore.Qt.UserRole, g)
            self.group_list.addItem(it)
        # restore selection
        if current:
            for i in range(self.group_list.count()):
                it = self.group_list.item(i)
                if it and it.data(QtCore.Qt.UserRole) == current:
                    self.group_list.setCurrentRow(i)
                    break
        self.group_list.blockSignals(False)
        self._update_members()

    def _update_members(self):
        g = self._current_group()
        members = sorted(list(self._cached_groups.get(g, []))) if g else []
        self.members_list.clear()
        for u in members:
            self.members_list.addItem(u)

    def _apply_group_filter(self):
        q = self.member_filter.text().strip().lower()
        current = self._current_group()
        all_groups = sorted(self._cached_groups.keys())
        self.group_list.blockSignals(True)
        self.group_list.clear()
        for g in all_groups:
            members = self._cached_groups.get(g, [])
            blob = g.lower() + ' ' + ' '.join(m.lower() for m in members)
            if not q or q in blob:
                it = QtWidgets.QListWidgetItem(f"{g} ({len(members)})")
                it.setData(QtCore.Qt.UserRole, g)
                self.group_list.addItem(it)
        # restore selection
        if current:
            for i in range(self.group_list.count()):
                it = self.group_list.item(i)
                if it and it.data(QtCore.Qt.UserRole) == current:
                    self.group_list.setCurrentRow(i)
                    break
        self.group_list.blockSignals(False)
        self._update_members()

    def _current_group(self) -> str:
        it = self.group_list.currentItem()
        if it:
            return it.data(QtCore.Qt.UserRole)
        return ""


class FilesPage(QtWidgets.QWidget):
    sigAccept = QtCore.pyqtSignal(str, str)  # (offer_id, dir)
    sigCancel = QtCore.pyqtSignal(str)
    sigPickDir = QtCore.pyqtSignal()
    sigApplyDir = QtCore.pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._build()
        self._offers = {}
        self._save_dir = ""
        self._prog_bars = {}  # oid -> QProgressBar

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        # 保存目录
        dir_row = QtWidgets.QHBoxLayout()
        self.dir_edit = QtWidgets.QLineEdit()
        btn_pick = QtWidgets.QPushButton("选择保存目录")
        btn_apply = QtWidgets.QPushButton("设为默认")
        for b in (btn_pick, btn_apply):
            b.setFixedHeight(b.fontMetrics().height() + 12)
        dir_row.addWidget(self.dir_edit, 1)
        dir_row.addWidget(btn_pick)
        dir_row.addWidget(btn_apply)
        layout.addLayout(dir_row)

        # 要约列表
        self.list = QtWidgets.QListWidget()
        layout.addWidget(self.list, 1)

        # 操作与进度
        ctrl = QtWidgets.QHBoxLayout()
        self.btn_accept = QtWidgets.QPushButton("接收")
        self.btn_cancel = QtWidgets.QPushButton("放弃")
        for b in (self.btn_accept, self.btn_cancel):
            b.setFixedHeight(b.fontMetrics().height() + 12)
        ctrl.addWidget(self.btn_accept)
        ctrl.addWidget(self.btn_cancel)
        ctrl.addStretch()
        layout.addLayout(ctrl)

        btn_pick.clicked.connect(lambda: self.sigPickDir.emit())
        btn_apply.clicked.connect(lambda: self.sigApplyDir.emit(self.dir_edit.text().strip()))
        self.btn_accept.clicked.connect(self._on_accept)
        self.btn_cancel.clicked.connect(self._on_cancel)

    def pick_dir(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "选择保存目录")
        if d:
            self.dir_edit.setText(d)

    def update_offers(self, offers: Dict[str, dict]):
        self._offers = offers or {}
        self.list.clear()
        self._prog_bars.clear()
        for oid, m in self._offers.items():
            name = m.get("name", "file")
            size = int(m.get("size", 0))
            src = f"{m.get('ip','?')}:{m.get('port','-')}" if m.get("method") != "ipmsg" else f"{m.get('ip','?')}:2425/ipmsg"
            uname = m.get("uname") or m.get("ip","?")
            ts_val = m.get("ts")
            ts_txt = QtCore.QDateTime.fromSecsSinceEpoch(int(ts_val)).toString('yyyy-MM-dd hh:mm:ss') if ts_val else "--"
            ext = os.path.splitext(name)[1]
            display = f"{uname}[IP:{m.get('ip','?')}] {name}{'' if ext else ''} {ts_txt} | {size} bytes | {src}" if uname else f"{oid} | {name} | {size} bytes | from {src}"
            it = QtWidgets.QListWidgetItem()
            it.setData(QtCore.Qt.UserRole, oid)
            # custom widget with labels + progressbar
            w = QtWidgets.QWidget()
            hl = QtWidgets.QHBoxLayout(w); hl.setContentsMargins(6,2,6,2); hl.setSpacing(8)
            lbl = QtWidgets.QLabel(display)
            bar = QtWidgets.QProgressBar(); bar.setMinimum(0)
            if size > 0:
                bar.setMaximum(size)
            else:
                bar.setMaximum(0)
            bar.setTextVisible(True)
            hl.addWidget(lbl, 1)
            hl.addWidget(bar, 1)
            self.list.addItem(it)
            self.list.setItemWidget(it, w)
            self._prog_bars[oid] = bar

    def _on_accept(self):
        it = self.list.currentItem()
        if not it:
            return
        oid = it.data(QtCore.Qt.UserRole)
        self.sigAccept.emit(oid, self.dir_edit.text().strip())

    def _on_cancel(self):
        it = self.list.currentItem()
        if not it:
            return
        oid = it.data(QtCore.Qt.UserRole)
        self.sigCancel.emit(oid)

    def update_progress(self, oid: str, total: int):
        bar = self._prog_bars.get(oid)
        if not bar:
            return
        # 如果已知总大小，使用确定进度；否则仅显示文本
        m = self._offers.get(oid) or {}
        size = int(m.get("size", 0)) if m else 0
        if size > 0:
            if bar.maximum() != size:
                bar.setMaximum(size)
            bar.setValue(max(0, min(total, size)))
            pct = (total * 100 // size) if size else 0
            bar.setFormat(f"{pct}% ({total}/{size})")
        else:
            bar.setMaximum(0)
            bar.setFormat(f"{oid}: {total} bytes")

    def on_saved(self, oid: str, path: str):
        QtWidgets.QMessageBox.information(self, "保存完成", f"要约 {oid} 已保存至:\n{path}")


class InfoPage(QtWidgets.QWidget):
    sigDiscover = QtCore.pyqtSignal(str)  # ip or empty

    def __init__(self):
        super().__init__()
        self._build()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        self.lbl_local = QtWidgets.QLabel("本机：-")
        self.lbl_bcast = QtWidgets.QLabel("广播：-")
        self.lbl_mask = QtWidgets.QLabel("掩码：-")
        row = QtWidgets.QHBoxLayout()
        self.disc_ip = QtWidgets.QLineEdit()
        self.disc_ip.setPlaceholderText("ip: 例如 192.168.1.10，可留空广播")
        btn_disc = QtWidgets.QPushButton("发现")
        btn_disc.setFixedHeight(btn_disc.fontMetrics().height() + 12)
        row.addWidget(self.disc_ip, 1)
        row.addWidget(btn_disc)
        self.nodes = QtWidgets.QListWidget()
        self.lbl_count = QtWidgets.QLabel("在线节点: 0")
        layout.addWidget(self.lbl_local)
        layout.addWidget(self.lbl_bcast)
        layout.addLayout(row)
        layout.addWidget(self.lbl_mask)
        layout.addWidget(self.lbl_count)
        layout.addWidget(self.nodes, 1)
        btn_disc.clicked.connect(lambda: self.sigDiscover.emit(self.disc_ip.text().strip()))

    def set_net_info(self, info: Dict):
        self.lbl_local.setText(f"本机：{info.get('local_ip','-')} / {info.get('iface_prefix','-')}")
        self.lbl_bcast.setText(f"广播：{info.get('broadcast','-')}")
        # 计算或显示掩码
        mask = info.get('subnet_mask')
        if not mask:
            pre = info.get('iface_prefix','')
            if isinstance(pre, str) and '/' in pre:
                try:
                    bits = int(pre.split('/',1)[1])
                    if 0 <= bits <= 32:
                        m = (0xffffffff << (32 - bits)) & 0xffffffff
                        mask = '.'.join(str((m >> (8*i)) & 0xff) for i in [3,2,1,0])
                except Exception:
                    mask = None
        self.lbl_mask.setText(f"掩码：{mask or '-'}")

    def update_nodes(self, nodes):
        self.nodes.clear()
        for n in nodes:
            st = f" [{n.status}]" if getattr(n, 'status', 'online') != 'online' else ""
            self.nodes.addItem(f"{n.username}@{n.ip} ({n.hostname}){st}")
        try:
            self.lbl_count.setText(f"在线节点: {len(nodes)}")
        except Exception:
            pass


class SettingsPage(QtWidgets.QWidget):
    sigApply = QtCore.pyqtSignal(dict)
    sigLogout = QtCore.pyqtSignal()

    def __init__(self):
        super().__init__()
        self._build()

    def _build(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        # 平台信息显示
        self.lbl_platform = QtWidgets.QLabel(self._detect_platform_str())
        self.lbl_version = QtWidgets.QLabel(f"版本：{APP_VERSION}")
        layout.addRow(self.lbl_platform)
        layout.addRow(self.lbl_version)
        self.cmb_lang = QtWidgets.QComboBox(); self.cmb_lang.addItems(["zhCN","enUS"]) 
        self.cmb_status = QtWidgets.QComboBox(); self.cmb_status.addItems(["online","busy","away"]) 
        self.cmb_enc = QtWidgets.QComboBox(); self.cmb_enc.addItems(["utf-8","gbk"]) 
        self.cmb_theme = QtWidgets.QComboBox(); self.cmb_theme.addItems(["light","dark"]) 
        self.cmb_iface = QtWidgets.QComboBox()  # 本机网卡IP下拉
        self.chk_debug = QtWidgets.QCheckBox("调试日志")
        self.chk_trace = QtWidgets.QCheckBox("诊断日志")
        self.spn_keepalive = QtWidgets.QDoubleSpinBox(); self.spn_keepalive.setRange(5.0, 600.0); self.spn_keepalive.setValue(30.0)
        self.spn_expire = QtWidgets.QDoubleSpinBox(); self.spn_expire.setRange(10.0, 3600.0); self.spn_expire.setValue(90.0)
        self.edit_bind = QtWidgets.QLineEdit(); self.edit_bind.setPlaceholderText("绑定 IP（可选）")
        self.edit_mask = QtWidgets.QLineEdit(); self.edit_mask.setPlaceholderText("子网掩码（例如 255.255.255.0，可选）")
        self.edit_dir = QtWidgets.QLineEdit(); self.edit_dir.setPlaceholderText("下载目录（可选）")
        btn_browse_dir = QtWidgets.QPushButton("浏览…")
        btn_browse_dir.setFixedHeight(btn_browse_dir.fontMetrics().height() + 12)
        # 截图目录设置
        self.edit_ss_dir = QtWidgets.QLineEdit(); self.edit_ss_dir.setPlaceholderText("截图目录（可选）")
        btn_browse_ss = QtWidgets.QPushButton("浏览截图…")
        btn_browse_ss.setFixedHeight(btn_browse_ss.fontMetrics().height() + 12)
        # 头像设置与登出
        self.edit_avatar = QtWidgets.QLineEdit(); self.edit_avatar.setPlaceholderText("头像文件（PNG/JPG，可选）")
        btn_pick_avatar = QtWidgets.QPushButton("选择头像…")
        btn_pick_avatar.setFixedHeight(btn_pick_avatar.fontMetrics().height() + 12)
        btn_apply = QtWidgets.QPushButton("应用")
        btn_apply.setFixedHeight(btn_apply.fontMetrics().height() + 12)
        btn_logout = QtWidgets.QPushButton("登出 / Logout")
        btn_logout.setFixedHeight(btn_logout.fontMetrics().height() + 12)
        self.lbl_lang = QtWidgets.QLabel("语言")
        self.lbl_status = QtWidgets.QLabel("状态")
        self.lbl_encoding = QtWidgets.QLabel("编码")
        self.lbl_theme = QtWidgets.QLabel("主题")
        self.lbl_iface = QtWidgets.QLabel("网卡IP")
        layout.addRow(self.lbl_lang, self.cmb_lang)
        layout.addRow(self.lbl_status, self.cmb_status)
        layout.addRow(self.lbl_encoding, self.cmb_enc)
        layout.addRow(self.lbl_theme, self.cmb_theme)
        layout.addRow(self.lbl_iface, self.cmb_iface)
        layout.addRow(self.chk_debug, self.chk_trace)
        self.lbl_keepalive = QtWidgets.QLabel("Keepalive(s)")
        self.lbl_expire = QtWidgets.QLabel("Expire(s)")
        self.lbl_bind = QtWidgets.QLabel("绑定IP")
        self.lbl_mask = QtWidgets.QLabel("子网掩码")
        self.lbl_download = QtWidgets.QLabel("下载目录")
        self.lbl_ss_dir = QtWidgets.QLabel("截图目录")
        self.lbl_avatar = QtWidgets.QLabel("头像")
        layout.addRow(self.lbl_keepalive, self.spn_keepalive)
        layout.addRow(self.lbl_expire, self.spn_expire)
        layout.addRow(self.lbl_bind, self.edit_bind)
        layout.addRow(self.lbl_mask, self.edit_mask)
        layout.addRow(self.lbl_download, self._row_widget(self.edit_dir, btn_browse_dir))
        layout.addRow(self.lbl_ss_dir, self._row_widget(self.edit_ss_dir, btn_browse_ss))
        layout.addRow(self.lbl_avatar, self._row_widget(self.edit_avatar, btn_pick_avatar))
        self.btn_apply = btn_apply
        self.btn_logout = btn_logout
        layout.addRow(self.btn_apply)
        layout.addRow(self.btn_logout)
        btn_apply.clicked.connect(self._emit_apply)
        btn_browse_dir.clicked.connect(self._pick_download_dir)
        btn_browse_ss.clicked.connect(self._pick_screenshot_dir)
        btn_logout.clicked.connect(lambda: self.sigLogout.emit())
        btn_pick_avatar.clicked.connect(self._pick_avatar)
        # expose translation helper
        self.apply_translations = self._apply_translations

    def _detect_platform_str(self) -> str:
        try:
            sysname = platform.system() or ""
            arch_raw = platform.machine() or ""
            arch = arch_raw.lower()
            if arch in ("x86_64", "amd64"):
                arch_str = "x64"
            elif arch in ("i386", "i686", "x86"):
                arch_str = "x86"
            elif arch in ("aarch64", "arm64", "armv8"):
                arch_str = "aarch64"
            else:
                arch_str = arch_raw or "-"

            name = sysname
            if sysname == "Windows":
                # 粗略判断 Win11：构建号 >= 22000 视为 Windows 11
                try:
                    ver = sys.getwindowsversion()  # type: ignore[attr-defined]
                    build = getattr(ver, 'build', 0)
                    name = "Windows 11" if int(build) >= 22000 else "Windows 10"
                except Exception:
                    rel = platform.release()
                    name = f"Windows {rel}" if rel else "Windows"
            elif sysname == "Linux":
                name = "Linux"
            elif sysname == "Darwin":
                name = "macOS"
                try:
                    ver = platform.mac_ver()[0]
                    if ver:
                        name = f"macOS {ver}"
                except Exception:
                    pass
            else:
                name = sysname or "Unknown"

            return f"当前平台：{name} {arch_str}"
        except Exception:
            return "当前平台：Unknown"

    def _row_widget(self, left: QtWidgets.QWidget, right: QtWidgets.QWidget) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        h = QtWidgets.QHBoxLayout(w)
        h.setContentsMargins(0,0,0,0)
        h.addWidget(left, 1)
        h.addWidget(right)
        return w

    def _emit_apply(self):
        prefer_iface_ip = self.cmb_iface.currentText().strip()
        cfg = dict(
            language=self.cmb_lang.currentText(),
            status=self.cmb_status.currentText(),
            encoding=self.cmb_enc.currentText(),
            ui_theme=self.cmb_theme.currentText(),
            debug=self.chk_debug.isChecked(),
            trace=self.chk_trace.isChecked(),
            keepalive=self.spn_keepalive.value(),
            expire=self.spn_expire.value(),
            bind_ip=(prefer_iface_ip or self.edit_bind.text().strip()),
            subnet_mask=self.edit_mask.text().strip(),
            download_dir=self.edit_dir.text().strip().replace("\\", "/"),
            screenshot_dir=self.edit_ss_dir.text().strip().replace("\\", "/"),
            ui_avatar=self.edit_avatar.text().strip().replace("\\", "/"),
        )
        self.sigApply.emit(cfg)

    def _pick_download_dir(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "选择下载目录")
        if d:
            self.edit_dir.setText(d.replace("\\", "/"))

    def _pick_avatar(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "选择头像图片", filter="Images (*.png *.jpg *.jpeg)")
        if path:
            self.edit_avatar.setText(path.replace("\\", "/"))

    def _pick_screenshot_dir(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "选择截图保存目录")
        if d:
            self.edit_ss_dir.setText(d.replace("\\", "/"))

    def _apply_translations(self, t: dict):
        mapping = {
            'lang': self.lbl_lang,
            'status': self.lbl_status,
            'encoding': self.lbl_encoding,
            'theme': self.lbl_theme,
            'iface': self.lbl_iface,
            'keepalive': self.lbl_keepalive,
            'expire': self.lbl_expire,
            'bind_ip': self.lbl_bind,
            'subnet_mask': self.lbl_mask,
            'download_dir': self.lbl_download,
            'screenshot_dir': self.lbl_ss_dir,
            'avatar': self.lbl_avatar,
            'apply': self.btn_apply,
            'logout_long': self.btn_logout,
        }
        for k, w in mapping.items():
            try:
                w.setText(t.get(k, w.text()))
            except Exception:
                pass

class KeyPage(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self._build()

    def _build(self):
        layout = QtWidgets.QFormLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        self.cmb_mode = QtWidgets.QComboBox(); self.cmb_mode.addItems(["off","on","strict"])
        self.lbl_fp = QtWidgets.QLabel("指纹：-")
        self.btn_refresh = QtWidgets.QPushButton("刷新指纹")
        self.btn_regen = QtWidgets.QPushButton("重生成密钥")
        self.btn_export = QtWidgets.QPushButton("导出公钥…")
        for b in (self.btn_refresh, self.btn_regen, self.btn_export):
            b.setFixedHeight(b.fontMetrics().height() + 12)
        layout.addRow("加密模式", self.cmb_mode)
        layout.addRow(self.lbl_fp)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(self.btn_refresh)
        row.addWidget(self.btn_regen)
        row.addWidget(self.btn_export)
        row.addStretch()
        layout.addRow(row)


class EmotesPage(QtWidgets.QWidget):
    sigSend = QtCore.pyqtSignal(str)  # image file path

    def __init__(self, default_dir: Optional[str] = None):
        super().__init__()
        self._dir = default_dir or os.path.join(os.getcwd(), "emotes")
        os.makedirs(self._dir, exist_ok=True)
        self._build()
        self._load_emotes()

    def _build(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        dir_row = QtWidgets.QHBoxLayout()
        self.dir_edit = QtWidgets.QLineEdit(self._dir)
        btn_pick = QtWidgets.QPushButton("选择目录")
        btn_add = QtWidgets.QPushButton("添加表情")
        self.btn_back = QtWidgets.QPushButton("返回聊天")
        for b in (btn_pick, btn_add, self.btn_back):
            b.setFixedHeight(b.fontMetrics().height() + 12)
        dir_row.addWidget(self.dir_edit, 1)
        dir_row.addWidget(btn_pick)
        dir_row.addWidget(btn_add)
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
        self.btn_send = QtWidgets.QPushButton("发送选中")
        self.btn_send.setFixedHeight(self.btn_send.fontMetrics().height() + 12)
        send_row.addStretch()
        send_row.addWidget(self.btn_send)
        layout.addLayout(send_row)

        btn_pick.clicked.connect(self._pick_dir)
        btn_add.clicked.connect(self._add_emotes)
        self.btn_send.clicked.connect(self._send_selected)
        self.list.itemDoubleClicked.connect(lambda _: self._send_selected())

    def _pick_dir(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "选择表情目录")
        if d:
            self._dir = d
            self.dir_edit.setText(d)
            self._load_emotes()

    def _add_emotes(self):
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(self, "选择图片作为表情", filter="Images (*.png *.jpg *.jpeg *.gif)")
        if not files:
            return
        os.makedirs(self._dir, exist_ok=True)
        for f in files:
            try:
                dst = os.path.join(self._dir, os.path.basename(f))
                if os.path.abspath(f) != os.path.abspath(dst):
                    shutil.copyfile(f, dst)
            except Exception:
                pass
        self._load_emotes()

    def _load_emotes(self):
        self.list.clear()
        if not os.path.isdir(self._dir):
            return
        exts = {".png", ".jpg", ".jpeg", ".gif"}
        for name in sorted(os.listdir(self._dir)):
            if os.path.splitext(name)[1].lower() in exts:
                path = os.path.join(self._dir, name)
                icon = QtGui.QIcon(path)
                it = QtWidgets.QListWidgetItem(icon, name)
                it.setData(QtCore.Qt.UserRole, path)
                self.list.addItem(it)

    def _send_selected(self):
        it = self.list.currentItem()
        if not it:
            return
        path = it.data(QtCore.Qt.UserRole)
        if path and os.path.isfile(path):
            self.sigSend.emit(path)



class _RegionSelector(QtWidgets.QWidget):
    """Full-screen transparent overlay to let user rubber-band select a region."""
    def __init__(self, parent=None):
        super().__init__(parent)
        # 顶层全屏半透明遮罩，阻止点击穿透
        self.setWindowFlags(
            QtCore.Qt.WindowStaysOnTopHint
            | QtCore.Qt.FramelessWindowHint
            | QtCore.Qt.Tool
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        # 背景略微变暗以强调“正在截图”
        self._overlay_color = QtGui.QColor(0, 0, 0, 120)
        self._rubber = QtWidgets.QRubberBand(QtWidgets.QRubberBand.Rectangle, self)
        self._start = QtCore.QPoint()
        self._rect = QtCore.QRect()
        # 仅用于简单区域选择，不做预览
        self._pixmap = None

    def exec_(self):
        # 覆盖全屏以确保用户可见并可拖拽
        try:
            self.showFullScreen()
            self.raise_()
            self.activateWindow()
        except Exception:
            try:
                screen = QtWidgets.QApplication.primaryScreen()
                geo = screen.geometry()
                self.setGeometry(geo)
                self.show()
            except Exception:
                self.show()
        self._selected = None
        loop = QtCore.QEventLoop()
        self._loop = loop
        loop.exec_()
        return self._selected

    def paintEvent(self, a0: QtGui.QPaintEvent) -> None:  # rename param for linter compatibility
        painter = QtGui.QPainter(self)
        painter.fillRect(self.rect(), self._overlay_color)
        painter.end()

    def mousePressEvent(self, a0):
        self._start = a0.pos()
        self._rubber.setGeometry(QtCore.QRect(self._start, QtCore.QSize()))
        self._rubber.show()

    def mouseMoveEvent(self, a0):
        if not self._rubber.isVisible():
            return
        r = QtCore.QRect(self._start, a0.pos()).normalized()
        self._rubber.setGeometry(r)

    def mouseReleaseEvent(self, a0):
        if self._rubber.isVisible():
            r = self._rubber.geometry()
            self._rubber.hide()
            self._selected = r
        try:
            self._loop.quit()
        except Exception:
            pass
        self.close()
    # 去除未使用的预览相关方法，避免属性引用错误
