from __future__ import annotations

import os
import tempfile
import time
from html import escape
from typing import Dict, List, Optional

from PyQt5 import QtCore, QtGui, QtWidgets

from ..widgets import NavigationButton
from .emotes_page import EmotesPage


class ChatPage(QtWidgets.QWidget):
    """Chat surface that handles conversation tabs, composer, and attachments."""

    sigSend = QtCore.pyqtSignal()
    sigAnchor = QtCore.pyqtSignal(str)

    def __init__(self, parent=None, lang: str = "zhCN"):
        super().__init__(parent)
        from zfeiq_gui.lang import get_translations
        self._translations = get_translations(lang)
        self._local_ip = ""
        self._logs: Dict[str, List[str]] = {}
        self._pending_files: List[str] = []
        self._current_language = lang
        self._localization = {
            "status_prefix": self._translations["status_prefix"],
            "all_tab": self._translations["all_tab"],
            "me_label": self._translations["me_label"],
            "file_sent_prefix": self._translations["file_sent_prefix"],
        }
        self._status_token = ""
        self._status_colors = {
            "online": "#2ecc71",
            "busy": "#f97316",
            "away": "#9ca3af",
            self._translations.get("online", "在线"): "#2ecc71",
            self._translations.get("busy", "忙碌"): "#f97316",
            self._translations.get("away", "离开"): "#9ca3af",
        }
        self._current_status_display = "-"
        self._current_ip_display = "-.-.-.-"
        self._build_ui()

    def eventFilter(self, a0, a1):
        return False

    def _ensure_view(self, key: str, label: str) -> QtWidgets.QTextBrowser:
        label = label or self._target_labels.get(key) or key
        t = self._translations
        if key not in self._chat_views:
            view = QtWidgets.QTextBrowser()
            view.setOpenExternalLinks(False)
            view.setOpenLinks(False)
            view.setReadOnly(True)
            view.setPlaceholderText(t['chat_placeholder'])
            view.anchorClicked.connect(lambda url, self=self: self.sigAnchor.emit(url.toString()))
            self._chat_views[key] = view
            self._view_targets[view] = key
            self.tabs.addTab(view, label)
        else:
            view = self._chat_views[key]
            idx = self.tabs.indexOf(view)
            if idx >= 0 and key != "all":
                self.tabs.setTabText(idx, label)
        if key != "all":
            self._target_labels[key] = label
        return view

    def _append_log(self, target: str, line: str):
        try:
            self._logs.setdefault(target, []).append(line)
        except Exception:
            pass

    def target_for_index(self, idx: int) -> Optional[str]:
        if idx < 0:
            return None
        widget = self.tabs.widget(idx)
        # 只处理 QTextBrowser 类型 tab
        if isinstance(widget, QtWidgets.QTextBrowser):
            return self._view_targets.get(widget)
        return None

    def current_target_id(self) -> Optional[str]:
        return self.target_for_index(self.tabs.currentIndex())

    def focus_chat_tab(self, target_id: str, label: str) -> None:
        view = self._ensure_view(target_id, label)
        idx = self.tabs.indexOf(view)
        if idx >= 0:
            self.tabs.setCurrentIndex(idx)

    def remove_chat_tab(self, target_id: str) -> None:
        if target_id == "all":
            return
        view = self._chat_views.pop(target_id, None)
        if not view:
            return
        self._target_labels.pop(target_id, None)
        self._view_targets.pop(view, None)
        idx = self.tabs.indexOf(view)
        if idx >= 0:
            self.tabs.removeTab(idx)
        view.deleteLater()

    def _close_chat_tab(self, idx: int) -> None:
        if idx <= 0:
            return
        target_id = self.target_for_index(idx)
        if target_id:
            self.remove_chat_tab(target_id)

    def do_gui_screenshot(self) -> None:
        """Hide the window briefly, then capture the primary screen."""
        self._pending_gui_screenshot_ts = time.time()
        win = self.window()
        if win:
            win.hide()
        QtCore.QTimer.singleShot(500, self._perform_screenshot_logic)

    def _perform_screenshot_logic(self) -> None:
        """Grab the screen and enqueue the image for sending."""
        win = self.window()
        try:
            screen = QtWidgets.QApplication.primaryScreen()
            if not screen:
                raise RuntimeError("primary screen unavailable")
            pixmap = screen.grabWindow(0)
            if pixmap.isNull():
                print("截图失败：图像为空")
                return
            fd, path = tempfile.mkstemp(suffix=".png", prefix="zfeiq_gui_ss_")
            os.close(fd)
            if not pixmap.save(path, "PNG"):
                print("截图失败：无法保存 PNG")
                try:
                    os.remove(path)
                except Exception:
                    pass
                return
            self.add_pending_file(path)
        except Exception as e:
            print(f"截图异常: {e}")
        finally:
            if win:
                win.showNormal()
                win.activateWindow()

    def set_avatar(self, path: str):
        try:
            # 注释掉头像实际渲染以隐藏头像控件（保留方法以防外部调用）
            # if path and os.path.isfile(path):
            #     pm = QtGui.QPixmap(path)
            #     if not pm.isNull():
            #         self.avatar.setPixmap(pm.scaled(80, 80, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
            pass
        except Exception:
            pass

    def _build_ui(self) -> None:
        t = self._translations
        root = QtWidgets.QVBoxLayout(self)
        # 收窄外边距与间距，降低整体高度占用
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        header = QtWidgets.QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(6)
        self.avatar = QtWidgets.QLabel()
        # 注释掉头像控件的可视化设置与初始文本，保持属性以避免引用错误
        # self.avatar.setFixedSize(80, 80)
        # self.avatar.setStyleSheet("background-color: #d9d9d9; border-radius: 8px;")
        # self.avatar.setAlignment(QtCore.Qt.AlignCenter)
        # self.avatar.setText(t['avatar'])

        info_box = QtWidgets.QVBoxLayout()
        info_box.setContentsMargins(0, 0, 0, 0)
        info_box.setSpacing(4)
        self.username_label = QtWidgets.QLabel(f"{t['username']}：未登录")
        self.status_label = QtWidgets.QLabel(f"{t['status_prefix']}-")
        self.ip_label = QtWidgets.QLabel(f"{t['ip_label_prefix']}：-.-.-.-")
        from zfeiq_gui.lang import t
        self.enc_label = QtWidgets.QLabel(t['enc_off'])
        self.enc_label.setStyleSheet("color:#a33; font-size:12px;")
        # 将用户名与状态放在同一行（左对齐），IP 右对齐
        self.status_indicator = QtWidgets.QLabel()
        self.status_indicator.setFixedSize(10, 10)
        self.status_indicator.setStyleSheet("background:#c4c4c4; border-radius:5px;")
        self.username_label.setStyleSheet("font-size:18px; font-weight:600;")
        self.status_label.setStyleSheet("color:#333333; font-size:13px;")
        self.ip_label.setStyleSheet("color:#555555; font-size:13px;")
        self.me_info_label = QtWidgets.QLabel("")
        self.me_info_label.setStyleSheet("color:#777777; font-size:12px;")

        top_row = QtWidgets.QHBoxLayout()
        # 左侧：用户名 + 状态指示器与状态文本
        left_group = QtWidgets.QWidget()
        left_layout = QtWidgets.QHBoxLayout(left_group)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)
        left_layout.addWidget(self.username_label)
        left_layout.addWidget(self.status_indicator, 0, QtCore.Qt.AlignVCenter)
        left_layout.addWidget(self.status_label, 0, QtCore.Qt.AlignVCenter)
        top_row.addWidget(left_group)
        top_row.addStretch(1)
        enc_wrap = QtWidgets.QHBoxLayout()
        enc_wrap.setContentsMargins(0,0,0,0)
        enc_wrap.setSpacing(6)
        enc_wrap.addWidget(self.enc_label)
        enc_wrap.addWidget(self.ip_label)
        enc_container = QtWidgets.QWidget()
        enc_container.setLayout(enc_wrap)
        top_row.addWidget(enc_container)
        info_box.addLayout(top_row)
        info_box.addWidget(self.me_info_label)
        info_box.addStretch()

        # 不将头像控件加入布局，从而在界面中隐藏该控件
        # header.addWidget(self.avatar)
        header.addLayout(info_box)

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self._close_chat_tab)
        self.tabs.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.tabs.setMinimumHeight(90)
        self._chat_views: Dict[str, QtWidgets.QTextBrowser] = {}
        self._view_targets: Dict[QtWidgets.QTextBrowser, str] = {}
        self._target_labels: Dict[str, str] = {}
        self._view_all = QtWidgets.QTextBrowser()
        self._view_all.setOpenExternalLinks(False)
        self._view_all.setOpenLinks(False)
        self._view_all.setReadOnly(True)
        self._view_all.anchorClicked.connect(lambda url: self.sigAnchor.emit(url.toString()))
        self._view_all.setPlaceholderText(t['chat_placeholder'])
        self._view_all.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self._view_all.setMinimumHeight(60)
        self.local_msg_color_light = "#00561F"
        self.local_msg_color_dark = "#29c94f"
        self._current_local_color = self.local_msg_color_light
        all_label = self._localization.get("all_tab", t['all_tab'])
        self.tabs.addTab(self._view_all, all_label)
        self._chat_views["all"] = self._view_all
        self._view_targets[self._view_all] = "all"
        self._target_labels["all"] = all_label
        try:
            tabbar = self.tabs.tabBar()
            if tabbar:
                for side in (QtWidgets.QTabBar.LeftSide, QtWidgets.QTabBar.RightSide):
                    btn = tabbar.tabButton(0, side)
                    if btn:
                        btn.hide()
                        tabbar.setTabButton(0, side, btn)
        except Exception:
            pass

        actions_row = QtWidgets.QHBoxLayout()
        actions_row.setContentsMargins(0, 0, 0, 0)
        actions_row.setSpacing(6)

        def _make_action_btn(text: str) -> NavigationButton:
            btn = NavigationButton(text)
            # Allow buttons to stretch with available width on different window sizes
            btn.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.Preferred)
            return btn

        self.emoji_btn = _make_action_btn(t['emoji'])
        self.screenshot_btn = _make_action_btn(t['screenshot'])
        self.screenshot_btn.clicked.connect(self.do_gui_screenshot)
        self.quicktext_btn = _make_action_btn(t['quick'])
        # 历史按钮在当前UX中移除（保留对象以兼容外部引用，但隐藏且不加入布局）
        self.history_btn = _make_action_btn(t['history'])
        try:
            self.history_btn.setVisible(False)
            self.history_btn.setEnabled(False)
        except Exception:
            pass
        self.send_file_btn = _make_action_btn(t['sendfile'])
        self.ocr_btn = _make_action_btn(t.get('ocr', '文字识别'))
        # 交换公钥按钮：仅在加密模式 ON/STRICT 时由外部控制显示
        self.kx_btn = _make_action_btn(t.get('key_exchange', '交换公钥'))
        actions_row.addWidget(self.emoji_btn)
        actions_row.addWidget(self.screenshot_btn)
        actions_row.addWidget(self.quicktext_btn)
        # 不再添加历史按钮到操作行
        actions_row.addWidget(self.send_file_btn)
        actions_row.addWidget(self.ocr_btn)
        actions_row.addWidget(self.kx_btn)
        actions_row.addStretch()

        def _open_ocr_page():
            # 轻量入口：直接选择图片，然后调用后端OCR，无预览大窗口
            try:
                img_path, _ = QtWidgets.QFileDialog.getOpenFileName(self, t.get('ocr_pick', '选择图片识别'), filter=t.get('images_filter', 'Images (*.png *.jpg *.jpeg *.bmp *.gif)'))
                if not img_path:
                    return
                try:
                    from zfeiq_cli.ocr import ZFeiQOcr
                    engine = ZFeiQOcr.get_instance()
                    text = engine.run(img_path)
                except Exception as e:
                    text = f"OCR Error: {e}"
                if text:
                    self.outbox.insertPlainText(text)
                    cursor = self.outbox.textCursor()
                    cursor.movePosition(QtGui.QTextCursor.End)
                    self.outbox.setTextCursor(cursor)
            except Exception:
                pass

        self.ocr_btn.clicked.connect(_open_ocr_page)
        # 默认隐藏，外部根据加密模式控制显示
        try:
            self.kx_btn.setVisible(False)
        except Exception:
            pass

        def _open_emotes_picker():
            t_local = self._translations
            dlg = QtWidgets.QDialog(self)
            dlg.setWindowTitle(t_local['emoji_dialog_title'])
            layout = QtWidgets.QVBoxLayout(dlg)
            layout.setContentsMargins(8, 8, 8, 8)
            layout.setSpacing(8)
            tabs = QtWidgets.QTabWidget()
            layout.addWidget(tabs)

            emoji_page = QtWidgets.QWidget()
            tabs.addTab(emoji_page, t_local['emoji_tab_standard'])
            grid = QtWidgets.QGridLayout(emoji_page)
            grid.setContentsMargins(6, 6, 6, 6)
            grid.setSpacing(6)
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
            for i, emo in enumerate(emojis[: rows * cols]):
                r, c = divmod(i, cols)
                btn = QtWidgets.QPushButton(emo)
                btn.setFixedSize(28, 28)
                btn.setStyleSheet(
                    "QPushButton{border:1px solid #ddd; border-radius:4px; background:#fff;} "
                    "QPushButton:hover{background:#f5f5f5}"
                )
                btn.clicked.connect(lambda _, e=emo: (self.outbox.insertPlainText(e), dlg.accept()))
                grid.addWidget(btn, r, c)

            custom_page = QtWidgets.QWidget()
            tabs.addTab(custom_page, t_local['emoji_tab_custom'])
            custom_layout = QtWidgets.QVBoxLayout(custom_page)
            custom_layout.setContentsMargins(0, 0, 0, 0)
            custom_layout.setSpacing(6)
            try:
                picker = EmotesPage()
                if hasattr(picker, "btn_back"):
                    picker.btn_back.hide()

                def _on_pick(path: str):
                    try:
                        if path and os.path.isfile(path):
                            self.add_pending_file(path)
                            dlg.accept()
                    except Exception:
                        pass

                picker.sigSend.connect(_on_pick)
                custom_layout.addWidget(picker)
            except Exception:
                lbl = QtWidgets.QLabel(t_local['custom_emotes_unavailable'])
                lbl.setAlignment(QtCore.Qt.AlignCenter)
                custom_layout.addWidget(lbl)
            dlg.resize(520, 420)
            dlg.exec_()

        self.emoji_btn.clicked.connect(_open_emotes_picker)

        self.file_bar = QtWidgets.QWidget()
        self.file_bar.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.file_bar.setVisible(False)
        self._file_bar_layout = QtWidgets.QHBoxLayout(self.file_bar)
        self._file_bar_layout.setContentsMargins(4, 2, 4, 2)
        self._file_bar_layout.setSpacing(4)
        self._file_bar_layout.addStretch()

        self.outbox = QtWidgets.QTextEdit()
        self.outbox.setPlaceholderText(t['outbox_placeholder'])
        self.outbox.setAcceptRichText(False)
        self.outbox.setMinimumHeight(56)
        self.outbox.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        try:
            # 提示输入法为多行文本，避免某些桥接环境误判
            self.outbox.setInputMethodHints(QtCore.Qt.ImhMultiLine)
        except Exception:
            pass

        send_row = QtWidgets.QHBoxLayout()
        send_row.setContentsMargins(0, 0, 0, 0)
        send_row.setSpacing(6)
        self.send_btn = QtWidgets.QPushButton(t['send'])
        try:
            self.send_btn.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding, QtWidgets.QSizePolicy.Preferred)
        except Exception:
            pass
        send_row.addStretch(1)
        send_row.addWidget(self.send_btn)

        root.addLayout(header)
        root.addWidget(self.tabs, 3)
        root.addLayout(actions_row)
        root.addWidget(self.file_bar)
        root.addWidget(self.outbox, 1)
        root.addLayout(send_row)

        class _OutboxFilter(QtCore.QObject):
            def __init__(self, outer):
                super().__init__(outer)
                self.outer = outer

            def eventFilter(self, a0, a1):
                try:
                    if a0 is self.outer.outbox and a1.type() == QtCore.QEvent.KeyPress:
                        get_key = getattr(a1, "key", None)
                        key_val = get_key() if callable(get_key) else None
                        mods = int(QtWidgets.QApplication.keyboardModifiers())
                        if key_val == QtCore.Qt.Key_Return and not (mods & int(QtCore.Qt.ShiftModifier)):
                            self.outer.sigSend.emit()
                            return True
                        if key_val == QtCore.Qt.Key_Backspace:
                            if not self.outer.outbox.toPlainText().strip() and self.outer._pending_files:
                                self.outer._remove_last_file_chip()
                                return True
                except Exception:
                    pass
                return False

        self._outbox_filter = _OutboxFilter(self)
        self.outbox.installEventFilter(self._outbox_filter)

    def add_pending_file(self, path: str):
        if not path:
            return
        self._pending_files.append(path)
        chip = QtWidgets.QFrame()
        chip.setStyleSheet("QFrame{background:#e6f0ff; border:1px solid #b3d1ff; border-radius:6px;}")
        layout = QtWidgets.QHBoxLayout(chip)
        layout.setContentsMargins(8, 2, 6, 2)
        layout.setSpacing(6)
        lbl = QtWidgets.QLabel(f"📎 {os.path.basename(path)}")
        btn = QtWidgets.QToolButton()
        btn.setText("×")
        btn.setAutoRaise(True)

        def _rm():
            try:
                self._pending_files.remove(path)
            except ValueError:
                pass
            self._file_bar_layout.removeWidget(chip)
            chip.hide()
            chip.deleteLater()
            self.file_bar.setVisible(bool(self._pending_files))

        btn.clicked.connect(_rm)
        layout.addWidget(lbl)
        layout.addWidget(btn)
        self._file_bar_layout.insertWidget(max(0, self._file_bar_layout.count() - 1), chip)
        self.file_bar.setVisible(True)

    @staticmethod
    def _is_image(path: str) -> bool:
        if not path:
            return False
        ext = os.path.splitext(path)[1].lower()
        return ext in {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}

    def _image_preview_html(self, path: str) -> str:
        try:
            if not self._is_image(path):
                return ""
            abs_path = os.path.abspath(path)
            if not os.path.isfile(abs_path):
                return ""
            url = escape(QtCore.QUrl.fromLocalFile(abs_path).toString(), quote=True)
            # 使用较小的缩略图尺寸（例如宽 160px，高度按比例自适应）
            return (
                "<div style='margin-top:4px; text-align:center;'>"
                f"<img src='{url}' style='max-width:160px; border-radius:6px; border:1px solid #d0d0d0;'/>"
                "</div>"
            )
        except Exception:
            return ""

    def get_pending_files(self) -> List[str]:
        return list(self._pending_files)

    def clear_pending_files(self):
        self._pending_files.clear()
        for i in reversed(range(self._file_bar_layout.count() - 1)):
            widget = self._file_bar_layout.itemAt(i).widget()
            if widget is not None:
                self._file_bar_layout.removeWidget(widget)
                widget.hide()
                widget.deleteLater()
        self.file_bar.setVisible(False)

    def _remove_last_file_chip(self):
        if not self._pending_files:
            return
        self._pending_files.pop()
        idx = self._file_bar_layout.count() - 2
        if idx >= 0:
            widget = self._file_bar_layout.itemAt(idx).widget()
            if widget is not None:
                self._file_bar_layout.removeWidget(widget)
                widget.hide()
                widget.deleteLater()
        self.file_bar.setVisible(bool(self._pending_files))

    def apply_localization(self, lang: str, data: Dict[str, str]) -> None:
        self._current_language = lang
        for key, val in data.items():
            if val:
                self._localization[key] = val
        all_label = self._localization.get("all_tab", "全部")
        idx = self.tabs.indexOf(self._view_all)
        if idx >= 0:
            self.tabs.setTabText(idx, all_label)
        self._target_labels["all"] = all_label

    def append_message(self, sender: str, ip: str, text: str) -> None:
        key = f"ip:{ip}" if ip else sender
        label = f"{sender}@{ip}" if ip else sender
        # handshake / system events: 以居中灰色系统行渲染
        if text.startswith("[ENC] "):
            safe = escape(text)
            html = (
                "<div style='margin:6px 0; text-align:center;'>"
                "<span style='display:inline-block; max-width:80%; padding:4px 10px;"
                " color:#666; font-size:12px; background:#f3f4f6; border-radius:10px; border:1px solid #e5e7eb;'>"
                f"{safe}"
                "</span></div>"
            )
            self._view_all.append(html)
            self._ensure_view(key, label).append(html)
            self._append_log(key, f"sys {text}")
            return

        # 加密/握手原始帧抑制：不展示密文原文
        raw = (text or "").strip()
        if (
            raw.startswith("ENC ") or raw.startswith("ENC2 ") or
            raw.startswith("ENC;") or raw.startswith("ENC2;") or raw.startswith("ENCREADY;") or
            raw.startswith("KX1 ") or raw.startswith("KX2 ") or
            raw.startswith("KX1;") or raw.startswith("KX2;")
        ):
            display = self._translations.get('cipher_not_shown', '加密消息解密失败')
            bubble_bg = "#FFFFFF"
            html_bubble = (
                "<table width='100%' cellpadding='0' cellspacing='0' style='border-collapse:collapse; margin:2px 0;'>"
                "<tr><td align='left' style='border:none;'>"
                f"<span style='display:inline-block; max-width:70%; background:{bubble_bg}; color:#111; padding:6px 10px;"
                " border-radius:10px; border:1px solid #e6e6e6;'>"
                f"<b>{escape(sender)}</b> @ {escape(ip)}<br/>{escape(display)}"
                "</span>"
                "</td></tr></table>"
            )
            self._view_all.append(html_bubble)
            self._ensure_view(key, label).append(html_bubble)
            self._append_log(key, f"<< {sender}@{ip}: [cipher suppressed]")
            return

        bubble_bg = "#FFFFFF"
        # 使用 table 100% 宽度 + 单元格对齐，避免不同平台对 div/p align 解释不一致
        html_bubble = (
            "<table width='100%' cellpadding='0' cellspacing='0' style='border-collapse:collapse; margin:2px 0;'>"
            "<tr><td align='left' style='border:none;'>"
            f"<span style='display:inline-block; max-width:70%; background:{bubble_bg}; color:#111; padding:6px 10px;"
            " border-radius:10px; border:1px solid #e6e6e6;'>"
            f"<b>{escape(sender)}</b> @ {escape(ip)}<br/>{escape(text)}"
            "</span>"
            "</td></tr></table>"
        )
        self._view_all.append(html_bubble)
        self._ensure_view(key, label).append(html_bubble)
        self._append_log(key, f"<< {sender}@{ip}: {text}")

    def append_file_notice(self, sender: str, file_name: str) -> None:
        local_name = self._localization.get("me_label", "我")
        color = self._current_local_color if sender == local_name else "#555555"
        html = f"<span style='color:{color}'>&lt;&lt; [{escape(sender)}] {self._translations.get('file_offer_label', '文件')}: {escape(file_name)}</span>"
        self._view_all.append(html)

    def append_outgoing(self, target_id: str, target_display: str, text: str, tab_label: Optional[str] = None) -> None:
        key = target_id or target_display
        me_label = escape(self._localization.get("me_label", "我"))
        html_bubble = (
            "<table width='100%' cellpadding='0' cellspacing='0' style='border-collapse:collapse; margin:2px 0;'>"
            "<tr><td align='right' style='border:none;'>"
            "<span style='display:inline-block; max-width:70%; background:#DCF8C6; color:#0a0a0a; padding:6px 10px; border-radius:10px; border:1px solid #d8f0c0;'>"
            f"<b>{me_label}</b> -> {escape(target_display)}<br/>{escape(text)}"
            "</span>"
            "</td></tr></table>"
        )
        view = self._ensure_view(key, tab_label or target_display)
        if view is not self._view_all:
            self._view_all.append(html_bubble)
        view.append(html_bubble)
        self._append_log(key, f">> {text}")

    def append_incoming_offer(self, oid: str, uname: str, ip: str, name: str, size: int):
        size_txt = f"{size} bytes" if size else "? bytes"
        html_bubble = (
            "<table width='100%' cellpadding='0' cellspacing='0' style='border-collapse:collapse; margin:2px 0;'>"
            "<tr><td align='left' style='border:none;'>"
            "<span style='display:inline-block; max-width:70%; background:#FFFFFF; color:#111; padding:6px 10px; border-radius:10px; border:1px solid #e6e6e6;'>"
            f"<b>{escape(uname)}</b> @ {escape(ip)}<br/>{self._translations.get('file_offer_label','文件要约')}: {escape(name)} ({size_txt}) "
            f"<a href='accept:{oid}'>[{self._translations.get('accept','接收')}]</a> "
            f"<a href='cancel:{oid}'>[{self._translations.get('cancel','放弃')}]</a>"
            "</span>"
            "</td></tr></table>"
        )
        self._view_all.append(html_bubble)

    def append_offer_progress(self, oid: str, name: str, done: int, total: int):
        if total > 0:
            pct = int(done * 100 / total)
            txt = f"{self._translations.get('file_progress_label', '进度')} {pct}% ({done}/{total})"
        else:
            txt = f"{self._translations.get('file_progress_label', '进度')} {done} bytes"
        self._view_all.append(
            "<table width='100%' cellpadding='0' cellspacing='0' style='border-collapse:collapse; margin:2px 0;'>"
            "<tr><td align='left' style='border:none;'>"
            f"<span style='display:inline-block; background:#fff; color:#666; padding:4px 8px; border-radius:8px; border:1px solid #eee;'>[{self._translations.get('file_progress_label','文件进度')}] {escape(name)} {escape(txt)}</span>"
            "</td></tr></table>"
        )

    def append_offer_saved(self, name: str, path: str, sender: Optional[str] = None, ip: Optional[str] = None):
        done_label = self._translations.get('file_done_label', '文件完成')
        saved_to = self._translations.get('saved_to', '保存到')
        img_html = self._image_preview_html(path)
        display_name = sender or ip or self._translations.get('file_sender_unknown', '对方')
        html = (
            "<table width='100%' cellpadding='0' cellspacing='0' style='border-collapse:collapse; margin:2px 0;'>"
            "<tr><td align='left' style='border:none;'>"
            "<span style='display:inline-block; max-width:70%; background:#FFFFFF; color:#111; padding:6px 10px; border-radius:10px; border:1px solid #e0e0e0;'>"
            f"<b>{escape(display_name)}</b><br/>[{done_label}] {escape(name)} {saved_to} {escape(path)}{img_html}"
            "</span>"
            "</td></tr></table>"
        )
        self._view_all.append(html)
        if ip:
            label = f"{display_name}@{ip}" if display_name and ip else display_name or ip
            view = self._ensure_view(f"ip:{ip}", label)
            view.append(html)

    def append_file_sent(self, target_id: str, target_display: str, path: str, tab_label: Optional[str] = None):
        key = target_id or target_display
        name = os.path.basename(path)
        img_html = self._image_preview_html(path)
        html_bubble = (
            "<table width='100%' cellpadding='0' cellspacing='0' style='border-collapse:collapse; margin:2px 0;'>"
            "<tr><td align='right' style='border:none;'>"
            "<span style='display:inline-block; max-width:70%; background:#DCF8C6; color:#0a0a0a; padding:6px 10px; border-radius:10px; border:1px solid #d8f0c0;'>"
            f"<b>{escape(self._localization.get('me_label','我'))}</b> -> {escape(target_display)}<br/>{escape(self._localization.get('file_sent_prefix','已发送文件: '))}{escape(name)}{img_html}"
            "</span>"
            "</td></tr></table>"
        )
        view = self._ensure_view(key, tab_label or target_display)
        if view is not self._view_all:
            self._view_all.append(html_bubble)
        view.append(html_bubble)

    def set_local_color(self, dark: bool):
        self._current_local_color = self.local_msg_color_dark if dark else self.local_msg_color_light

    def set_local_ip(self, ip: str):
        self._local_ip = ip or ""
        self._current_ip_display = ip if ip else "-.-.-.-"
        prefix = self._translations.get('ip_label_prefix', 'IP')
        try:
            self.ip_label.setText(f"{prefix}：{self._current_ip_display}")
        except Exception:
            pass

    def set_encryption_state(self, on: bool):
        try:
            if on:
                from zfeiq_gui.lang import t
                self.enc_label.setText(t['enc_on'])
                self.enc_label.setStyleSheet("color:#2a7; font-size:12px;")
            else:
                from zfeiq_gui.lang import t
                self.enc_label.setText(t['enc_off'])
                self.enc_label.setStyleSheet("color:#a33; font-size:12px;")
        except Exception:
            pass

    def set_local_profile(self, uname: str, status_disp: str, ip: str):
        try:
            prefix = self._localization.get("status_prefix", "状态：")
            ip_prefix = self._translations.get('ip_label_prefix', 'IP')
            txt = f"我：{uname}  {prefix}{status_disp}  {ip_prefix}：{ip or '-.-.-.-'}"
            self.me_info_label.setText(txt)
        except Exception:
            pass

    def set_user_status(self, uname: str, status: str, status_tag: Optional[str] = None):
        try:
            if uname:
                self.username_label.setText(f"{uname}")
            if status:
                prefix = self._localization.get("status_prefix", "状态：")
                self._current_status_display = status
                self.status_label.setText(f"{prefix}{status}")
            token = (status_tag or "").lower()
            if not token and status:
                token = status.lower()
            color = self._status_colors.get(token) or self._status_colors.get(status) or "#c4c4c4"
            self._apply_status_color(color)
            self._status_token = token or status or ""
        except Exception:
            pass

    def apply_language(self, translations: Dict[str, str]) -> None:
        self._translations = translations
        self._localization.update(
            {
                "status_prefix": translations.get("status_prefix", self._localization.get("status_prefix", "状态：")),
                "all_tab": translations.get("all_tab", self._localization.get("all_tab", "全部")),
                "me_label": translations.get("me_label", self._localization.get("me_label", "我")),
                "file_sent_prefix": translations.get("file_sent_prefix", self._localization.get("file_sent_prefix", "已发送文件: ")), 
            }
        )
        self._status_colors.update(
            {
                "online": "#2ecc71",
                "busy": "#f97316",
                "away": "#9ca3af",
                translations.get("online", "online"): "#2ecc71",
                translations.get("busy", "busy"): "#f97316",
                translations.get("away", "away"): "#9ca3af",
            }
        )
        # 头像标签已隐藏/移除到布局，跳过语言文本更新
        # self.avatar.setText(translations.get("avatar", self.avatar.text()))
        prefix = self._localization.get("status_prefix", "状态：")
        self.status_label.setText(f"{prefix}{self._current_status_display}")
        ip_prefix = translations.get("ip_label_prefix", "IP")
        self.ip_label.setText(f"{ip_prefix}：{self._current_ip_display}")
        try:
            self.enc_label.setText(translations.get('enc_off', self.enc_label.text()))
        except Exception:
            pass
        self.emoji_btn.setText(translations.get("emoji", self.emoji_btn.text()))
        self.screenshot_btn.setText(translations.get("screenshot", self.screenshot_btn.text()))
        self.quicktext_btn.setText(translations.get("quick", self.quicktext_btn.text()))
        self.history_btn.setText(translations.get("history", self.history_btn.text()))
        self.send_file_btn.setText(translations.get("sendfile", self.send_file_btn.text()))
        try:
            self.ocr_btn.setText(translations.get('ocr', self.ocr_btn.text()))
            self.kx_btn.setText(translations.get('key_exchange', self.kx_btn.text()))
        except Exception:
            pass
        self.outbox.setPlaceholderText(translations.get("outbox_placeholder", self.outbox.placeholderText()))
        self.send_btn.setText(translations.get("send", self.send_btn.text()))
        chat_placeholder = translations.get("chat_placeholder", self._view_all.placeholderText())
        for view in self._chat_views.values():
            try:
                view.setPlaceholderText(chat_placeholder)
            except Exception:
                pass
        all_label = translations.get("all_tab", "全部")
        idx = self.tabs.indexOf(self._view_all)
        if idx >= 0:
            self.tabs.setTabText(idx, all_label)
        self._target_labels["all"] = all_label

    def _apply_status_color(self, color: str):
        try:
            self.status_indicator.setStyleSheet(f"background:{color}; border-radius:5px;")
        except Exception:
            pass
