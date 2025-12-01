from __future__ import annotations

import os
import platform
import sys
from typing import Dict

from PyQt5 import QtCore, QtGui, QtWidgets

from zfeiq_version import APP_VERSION

from ..widgets import NavigationButton
from .key_page import KeyPage


class SettingsPage(QtWidgets.QWidget):
    """Aggregated settings view split into personal/general/network/file tabs."""

    sigApply = QtCore.pyqtSignal(dict)
    sigLogout = QtCore.pyqtSignal()
    sigEncodingSelfTest = QtCore.pyqtSignal()

    def __init__(self, lang: str = "zhCN") -> None:
        super().__init__()
        from zfeiq_gui.lang import get_translations
        self._translations = get_translations(lang)
        self._platform_desc = self._detect_platform_desc()
        self._personal_username = "-"
        self._personal_ip = "-.-.-.-"
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        # 放宽最小尺寸，避免切换到本页时强制增高窗口
        self.setMinimumSize(0, 0)
        self._build()
        self.apply_language(self._translations)

    def _build(self) -> None:
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        top_info = QtWidgets.QHBoxLayout()
        self.lbl_platform = QtWidgets.QLabel()
        self.lbl_version = QtWidgets.QLabel()
        top_info.addWidget(self.lbl_platform)
        top_info.addStretch(1)
        top_info.addWidget(self.lbl_version)
        # 原先将平台/版本显示在设置页顶部；现在改为移动到“关于”页，故不在此处加入布局

        tabs = QtWidgets.QTabWidget()
        self._tabs = tabs
        outer.addWidget(tabs, 1)

        t = self._translations
        tab_personal = QtWidgets.QWidget()
        tabs.addTab(tab_personal, t['personal_tab'])
        pform = QtWidgets.QFormLayout(tab_personal)
        pform.setContentsMargins(12, 12, 12, 12)
        pform.setSpacing(10)
        self.lbl_p_username = QtWidgets.QLabel()
        self.lbl_p_ip = QtWidgets.QLabel()
        pform.addRow(self.lbl_p_username)
        pform.addRow(self.lbl_p_ip)
        self.lbl_status = QtWidgets.QLabel(t['status'])
        self.cmb_status = QtWidgets.QComboBox()
        self._status_codes = ["online", "busy", "away"]
        # 为状态下拉添加内侧彩色图标（小圆点）
        def _color_icon(color: str, size: int = 12) -> QtGui.QIcon:
            pix = QtGui.QPixmap(size, size)
            pix.fill(QtCore.Qt.transparent)
            p = QtGui.QPainter(pix)
            p.setRenderHint(QtGui.QPainter.Antialiasing)
            brush = QtGui.QBrush(QtGui.QColor(color))
            p.setBrush(brush)
            p.setPen(QtGui.QPen(QtCore.Qt.NoPen))
            r = size // 2
            p.drawEllipse(0, 0, size, size)
            p.end()
            return QtGui.QIcon(pix)

        status_colors = {"online": "#2ecc71", "busy": "#f97316", "away": "#9ca3af"}
        for code in self._status_codes:
            icon = _color_icon(status_colors.get(code, "#999999"))
            # addItem(icon, visibleText, userData) — 使用本地化文本作为可见项
            visible = t.get(code, code) if isinstance(t, dict) else code
            self.cmb_status.addItem(icon, visible, code)
        pform.addRow(self.lbl_status, self.cmb_status)
        # 头像输入与选择（已隐藏，保留代码以便将来恢复）
        # self.edit_avatar = QtWidgets.QLineEdit()
        # self.edit_avatar.setPlaceholderText(t['avatar_placeholder'])
        # self.btn_pick_avatar = NavigationButton(t['pick_avatar'])
        # # 这里更新了“头像”文本框
        # self.lbl_avatar = QtWidgets.QLabel(t['avatar'])
        # pform.addRow(self.lbl_avatar, self._row_widget(self.edit_avatar, self.btn_pick_avatar))
        # 将密钥/安全管理移到独立的 tab：Security (与个人/文件同级)
        try:
            self.key_section = KeyPage()
            tab_security = QtWidgets.QWidget()
            sec_layout = QtWidgets.QVBoxLayout(tab_security)
            sec_layout.setContentsMargins(12, 12, 12, 12)
            sec_layout.setSpacing(8)
            sec_layout.addWidget(self.key_section)
            tabs.addTab(tab_security, t.get('security_tab', '安全'))
        except Exception:
            pass

        tab_general = QtWidgets.QWidget()
        tabs.addTab(tab_general, t['general_tab'])
        gform = QtWidgets.QFormLayout(tab_general)
        gform.setContentsMargins(12, 12, 12, 12)
        gform.setSpacing(10)
        self.cmb_lang = QtWidgets.QComboBox()
        self.cmb_lang.addItems(["zhCN", "enUS", "esES"])
        self.cmb_enc = QtWidgets.QComboBox()
        self.cmb_enc.addItems(["utf-8", "gbk"])
        self.cmb_theme = QtWidgets.QComboBox()
        self.cmb_theme.addItems(["light", "dark"])
        self.chk_debug = QtWidgets.QCheckBox(t['debug'])
        self.chk_trace = QtWidgets.QCheckBox(t['trace'])
        self.lbl_lang = QtWidgets.QLabel(t['lang'])
        self.lbl_encoding = QtWidgets.QLabel(t['encoding'])
        self.lbl_theme = QtWidgets.QLabel(t['theme'])
        gform.addRow(self.lbl_lang, self.cmb_lang)
        self.btn_enc_test = NavigationButton(t['encoding_selftest'])
        enc_container = QtWidgets.QWidget()
        enc_layout = QtWidgets.QHBoxLayout(enc_container)
        enc_layout.setContentsMargins(0, 0, 0, 0)
        enc_layout.addWidget(self.cmb_enc, 1)
        enc_layout.addWidget(self.btn_enc_test)
        gform.addRow(self.lbl_encoding, enc_container)
        gform.addRow(self.lbl_theme, self.cmb_theme)
        # 将“调试日志”和“诊断日志”分为两行显示，便于阅读
        gform.addRow(self.chk_debug)
        gform.addRow(self.chk_trace)

        tab_net = QtWidgets.QWidget()
        tabs.addTab(tab_net, t['network_tab'])
        nform = QtWidgets.QFormLayout(tab_net)
        nform.setContentsMargins(12, 12, 12, 12)
        nform.setSpacing(10)
        self.cmb_iface = QtWidgets.QComboBox()
        self.edit_mask = QtWidgets.QLineEdit()
        self.edit_mask.setPlaceholderText(t['subnet_mask'])
        # 新增端口号输入（位于绑定 IP 与子网掩码之间）
        self.edit_port = QtWidgets.QLineEdit()
        self.edit_port.setPlaceholderText(t.get('port', '端口号'))
        self.edit_keepalive = QtWidgets.QLineEdit()
        self.edit_keepalive.setPlaceholderText(t['keepalive'])
        self.edit_expire = QtWidgets.QLineEdit()
        self.edit_expire.setPlaceholderText(t['expire'])
        self.lbl_iface = QtWidgets.QLabel(t['iface'])
        self.lbl_keepalive = QtWidgets.QLabel(t['keepalive'])
        self.lbl_expire = QtWidgets.QLabel(t['expire'])
        self.lbl_mask = QtWidgets.QLabel(t['subnet_mask'])
        self.lbl_port = QtWidgets.QLabel(t.get('port', '端口号'))
        nform.addRow(self.lbl_iface, self.cmb_iface)
        nform.addRow(self.lbl_port, self.edit_port)
        nform.addRow(self.lbl_mask, self.edit_mask)
        nform.addRow(self.lbl_keepalive, self.edit_keepalive)
        nform.addRow(self.lbl_expire, self.edit_expire)

        tab_files = QtWidgets.QWidget()
        tabs.addTab(tab_files, t['files_tab'])
        fform = QtWidgets.QFormLayout(tab_files)
        fform.setContentsMargins(12, 12, 12, 12)
        fform.setSpacing(10)
        self.edit_dir = QtWidgets.QLineEdit()
        self.edit_dir.setPlaceholderText(t['download_dir'])
        self.btn_browse_dir = NavigationButton(t['browse'])
        self.edit_ss_dir = QtWidgets.QLineEdit()
        self.edit_ss_dir.setPlaceholderText(t['screenshot_dir'])
        self.btn_browse_ss = NavigationButton(t['browse_ss'])
        self.lbl_download = QtWidgets.QLabel(t['download_dir'])
        self.lbl_ss_dir = QtWidgets.QLabel(t['screenshot_dir'])
        fform.addRow(self.lbl_download, self._row_widget(self.edit_dir, self.btn_browse_dir))
        fform.addRow(self.lbl_ss_dir, self._row_widget(self.edit_ss_dir, self.btn_browse_ss))

        # 关于页：显示 Logo、当前平台、版本和 GitHub 链接
        try:
            tab_about = QtWidgets.QWidget()
            tabs.addTab(tab_about, t.get('about_tab', '关于'))
            about_layout = QtWidgets.QVBoxLayout(tab_about)
            about_layout.setContentsMargins(12, 12, 12, 12)
            about_layout.setSpacing(8)
            # 将关于页内容放到一个居中的容器中（四向居中）
            center_widget = QtWidgets.QWidget()
            center_layout = QtWidgets.QVBoxLayout(center_widget)
            center_layout.setContentsMargins(0, 0, 0, 0)
            center_layout.setSpacing(8)

            # Logo
            logo_lbl = QtWidgets.QLabel()
            try:
                icon_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'zfeiq_icon_128x128.ico'))
                pix = QtGui.QPixmap(icon_path)
                if not pix.isNull():
                    pix = pix.scaled(128, 128, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
                    logo_lbl.setPixmap(pix)
            except Exception:
                pass
            logo_lbl.setAlignment(QtCore.Qt.AlignCenter)
            center_layout.addWidget(logo_lbl, 0, QtCore.Qt.AlignHCenter)

            # 平台与版本（使用顶部创建的 self.lbl_platform / self.lbl_version）
            try:
                self.lbl_platform.setAlignment(QtCore.Qt.AlignCenter)
                self.lbl_version.setAlignment(QtCore.Qt.AlignCenter)
                center_layout.addWidget(self.lbl_platform)
                center_layout.addWidget(self.lbl_version)
            except Exception:
                pass

            # GitHub 按钮
            try:
                self.gh_btn = QtWidgets.QPushButton(self._translations.get('gh_button', '跳转到源码仓库'))
                # 避免固定高度，允许关于页在竖向上收缩
                try:
                    self.gh_btn.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Preferred)
                except Exception:
                    pass
                def _open_repo():
                    try:
                        QtGui.QDesktopServices.openUrl(QtCore.QUrl("https://github.com/zhangzw0170/ZFeiQ"))
                    except Exception:
                        pass
                self.gh_btn.clicked.connect(_open_repo)
                center_layout.addWidget(self.gh_btn, 0, QtCore.Qt.AlignHCenter)
            except Exception:
                pass

            # 在 about_layout 中四向居中显示 center_widget
            about_layout.addStretch()
            about_layout.addWidget(center_widget, 0, QtCore.Qt.AlignHCenter)
            about_layout.addStretch()
        except Exception:
            pass

        btn_row = QtWidgets.QHBoxLayout()
        self.btn_apply = NavigationButton(t['apply'])
        self.btn_logout = NavigationButton(t['logout_long'])
        btn_row.addStretch(1)
        btn_row.addWidget(self.btn_apply)
        btn_row.addWidget(self.btn_logout)
        outer.addLayout(btn_row)

        self.btn_apply.clicked.connect(self._emit_apply)
        self.btn_browse_dir.clicked.connect(self._pick_download_dir)
        self.btn_browse_ss.clicked.connect(self._pick_screenshot_dir)
        self.btn_logout.clicked.connect(lambda: self.sigLogout.emit())
        # 头像选择与预览已隐藏：保持方法存在但不连接信号或创建控件
        # self.btn_pick_avatar.clicked.connect(self._pick_avatar)
        self.btn_enc_test.clicked.connect(lambda: self.sigEncodingSelfTest.emit())
        # if not hasattr(self, "avatar_preview"):
        #     self.avatar_preview = QtWidgets.QLabel("预览")
        #     self.avatar_preview.setFixedSize(90, 90)
        #     self.avatar_preview.setAlignment(QtCore.Qt.AlignCenter)
        #     self.avatar_preview.setStyleSheet(
        #         "background:#e0e0e0; border:1px solid #ccc; border-radius:6px;"
        #     )
        #     pform.insertRow(pform.rowCount() - 1, self.avatar_preview)
        # self.edit_avatar.textChanged.connect(self._update_avatar_preview)
        # self._update_avatar_preview()
        # 语言切换统一用 apply_language，不再保留 apply_translations

    def _detect_platform_desc(self) -> str:
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
                try:
                    ver = sys.getwindowsversion()  # type: ignore[attr-defined]
                    build = getattr(ver, "build", 0)
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
            return f"{name} {arch_str}".strip()
        except Exception:
            return "Unknown"

    def _row_widget(self, left: QtWidgets.QWidget, right: QtWidgets.QWidget) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(left, 1)
        layout.addWidget(right)
        return widget
    def _emit_apply(self) -> None:
        prefer_iface_ip = self.cmb_iface.currentText().strip()
        cfg = dict(
            language=self.cmb_lang.currentText(),
            status=self.cmb_status.currentData() or self.cmb_status.currentText(),
            encoding=self.cmb_enc.currentText(),
            ui_theme=self.cmb_theme.currentText(),
            debug=self.chk_debug.isChecked(),
            trace=self.chk_trace.isChecked(),
            keepalive=self.edit_keepalive.text().strip(),
            expire=self.edit_expire.text().strip(),
            bind_ip=(prefer_iface_ip or None),
            port=self.edit_port.text().strip(),
            subnet_mask=self.edit_mask.text().strip(),
            download_dir=self.edit_dir.text().strip().replace("\\", "/"),
            screenshot_dir=self.edit_ss_dir.text().strip().replace("\\", "/"),
            # ui_avatar=self.edit_avatar.text().strip().replace("\\", "/"),
        )
        self.sigApply.emit(cfg)

    def _pick_download_dir(self) -> None:
        t = self._translations
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, t['pick_download_dir'])
        if directory:
            self.edit_dir.setText(directory.replace("\\", "/"))

    def _pick_avatar(self) -> None:
        t = self._translations
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            t['pick_avatar_dialog'],
            filter=t['images_filter'],
        )
        if path:
            # 头像输入已隐藏，暂不自动填充或更新预览
            # self.edit_avatar.setText(path.replace("\\", "/"))
            # self._update_avatar_preview()
            pass

    def _pick_screenshot_dir(self) -> None:
        t = self._translations
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, t['pick_screenshot_dir'])
        if directory:
            self.edit_ss_dir.setText(directory.replace("\\", "/"))

    def apply_language(self, translations: Dict[str, str]) -> None:
        self._translations = translations
        # 顶部信息
        self.lbl_platform.setText(f"{translations.get('platform', '当前平台')}：{self._platform_desc}")
        self.lbl_version.setText(f"{translations.get('version', '版本')}：{APP_VERSION}")

        # 个人信息区
        self.update_personal_info(self._personal_username, self._personal_ip)
        self.lbl_status.setText(translations.get('status', self.lbl_status.text()))
        # 头像文本与控件被隐藏，不更新语言
        # self.lbl_avatar.setText(translations.get('avatar', self.lbl_avatar.text()))
        # self.edit_avatar.setPlaceholderText(translations.get('avatar_placeholder', self.edit_avatar.placeholderText()))
        # self.btn_pick_avatar.setText(translations.get('pick_avatar', self.btn_pick_avatar.text()))

        # KeyPage 分组标题
        if hasattr(self, 'key_section'):
            group = self.key_section.parentWidget()
            if group and isinstance(group, QtWidgets.QGroupBox):
                group.setTitle(translations.get('key_section', group.title()))
            try:
                self.key_section.apply_language(translations)
            except Exception:
                pass

        # tab页标题
        tabs = getattr(self, '_tabs', None)
        if tabs:
            tab_titles = ['personal_tab', 'security_tab', 'general_tab', 'network_tab', 'files_tab', 'about_tab']
            for idx, key in enumerate(tab_titles):
                if idx < tabs.count():
                    tabs.setTabText(idx, translations.get(key, tabs.tabText(idx)))

        # 通用设置区
        self.lbl_lang.setText(translations.get('lang', self.lbl_lang.text()))
        self.lbl_encoding.setText(translations.get('encoding', self.lbl_encoding.text()))
        self.lbl_theme.setText(translations.get('theme', self.lbl_theme.text()))
        self.chk_debug.setText(translations.get('debug', self.chk_debug.text()))
        self.chk_trace.setText(translations.get('trace', self.chk_trace.text()))
        self.btn_enc_test.setText(translations.get('encoding_selftest', self.btn_enc_test.text()))

        # ComboBox 选项（语言、状态、编码、主题）
        current_status_code = self.cmb_status.currentData()
        for idx, code in enumerate(self._status_codes):
            label = translations.get(code, code)
            if idx < self.cmb_status.count():
                self.cmb_status.setItemText(idx, label)
                self.cmb_status.setItemData(idx, code)
            else:
                self.cmb_status.addItem(label, code)
        if current_status_code:
            idx = self.cmb_status.findData(current_status_code)
            if idx >= 0:
                self.cmb_status.setCurrentIndex(idx)

        # 网络设置区
        self.lbl_iface.setText(translations.get('iface', self.lbl_iface.text()))
        self.lbl_keepalive.setText(translations.get('keepalive', self.lbl_keepalive.text()))
        self.lbl_expire.setText(translations.get('expire', self.lbl_expire.text()))
        self.lbl_mask.setText(translations.get('subnet_mask', self.lbl_mask.text()))
        if hasattr(self, 'lbl_port'):
            self.lbl_port.setText(translations.get('port', self.lbl_port.text()))
        if hasattr(self, 'edit_port'):
            self.edit_port.setPlaceholderText(translations.get('port', self.edit_port.placeholderText()))
        self.edit_mask.setPlaceholderText(translations.get('subnet_mask', self.edit_mask.placeholderText()))
        if hasattr(self, 'edit_port'):
            self.edit_port.setPlaceholderText(translations.get('port', self.edit_port.placeholderText()))

        # 文件设置区
        self.lbl_download.setText(translations.get('download_dir', self.lbl_download.text()))
        self.lbl_ss_dir.setText(translations.get('screenshot_dir', self.lbl_ss_dir.text()))
        self.edit_dir.setPlaceholderText(translations.get('download_dir', self.edit_dir.placeholderText()))
        self.edit_ss_dir.setPlaceholderText(translations.get('screenshot_dir', self.edit_ss_dir.placeholderText()))

        # 文件区按钮
        self.btn_browse_dir.setText(translations.get('browse', self.btn_browse_dir.text()))
        self.btn_browse_ss.setText(translations.get('browse_ss', self.btn_browse_ss.text()))

        # 应用/登出按钮
        self.btn_apply.setText(translations.get('apply', self.btn_apply.text()))
        self.btn_logout.setText(translations.get('logout_long', self.btn_logout.text()))

        # 关于页 GitHub 按钮文本
        try:
            if hasattr(self, 'gh_btn') and self.gh_btn:
                self.gh_btn.setText(translations.get('gh_button', self.gh_btn.text()))
        except Exception:
            pass

        # 头像预览（已隐藏）
        # self.avatar_preview.setText(translations.get('preview', self.avatar_preview.text()))

    def update_personal_info(self, username: str, ip: str) -> None:
        self._personal_username = username or "-"
        self._personal_ip = ip or "-.-.-.-"
        t = getattr(self, '_translations', {})
        self.lbl_p_username.setText(f"{t['username']}：{self._personal_username}")
        self.lbl_p_ip.setText(f"{t['ip']}：{self._personal_ip}")

    def _update_avatar_preview(self) -> None:
        # 头像预览功能已隐藏；保留方法以便将来恢复但不执行任何操作
        # t = self._translations
        # try:
        #     path = self.edit_avatar.text().strip()
        #     if path and os.path.isfile(path):
        #         pixmap = QtGui.QPixmap(path)
        #         if not pixmap.isNull():
        #             self.avatar_preview.setPixmap(
        #                 pixmap.scaled(90, 90, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        #             )
        #             self.avatar_preview.setText("")
        #             return
        #     # 路径无效或图片加载失败时，仅清空图片，不覆盖 setText
        #     self.avatar_preview.setPixmap(QtGui.QPixmap())
        # except Exception:
        #     self.avatar_preview.setPixmap(QtGui.QPixmap())
        return

    def refresh_avatar_preview(self) -> None:
        """Public wrapper to refresh avatar preview (safe to call from outside)."""
        try:
            # no-op while avatar UI is hidden
            return
        except Exception:
            pass
