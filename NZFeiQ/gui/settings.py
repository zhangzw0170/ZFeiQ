import sys
import os
import platform
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QTabWidget, QWidget, 
                             QFormLayout, QLineEdit, QComboBox, QPushButton, 
                             QMessageBox, QLabel, QGroupBox, QHBoxLayout, 
                             QFileDialog, QCheckBox, QTextBrowser)
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDesktopServices, QPixmap
import os
from gui.lang import L, SUPPORTED_LANGS
from gui.styles import SUPPORTED_THEMES

# 尝试导入版本号
try:
    from core import __version__ as CORE_VERSION
except ImportError:
    CORE_VERSION = "Unknown"

class SettingsDialog(QDialog):
    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        self.setWindowTitle(L('settings_title'))
        self.resize(550, 420) # 稍微宽一点以容纳路径选择
        
        self.my_info = self.bridge.get_my_info()
        self._setup_ui()
        # Listen to theme changes so Settings dialog updates when theme changes elsewhere
        try:
            if hasattr(self.bridge, 'sig_theme_changed'):
                self.bridge.sig_theme_changed.connect(self._on_theme_changed)
                # Apply initial theme
                try:
                    tc = getattr(self.bridge.core, 'theme', 'light')
                    self._on_theme_changed(tc)
                except Exception:
                    pass
        except Exception:
            pass

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        # --- Tab 1: 基础设置 (用户、网络、文件) ---
        self.tab_basic = QWidget()
        self._init_basic(self.tab_basic)
        self.tabs.addTab(self.tab_basic, L('tab_basic'))
        
        # --- Tab 2: 安全与调试 ---
        self.tab_security = QWidget()
        self._init_security(self.tab_security)
        self.tabs.addTab(self.tab_security, L('tab_security'))
        
        # --- Tab 3: 关于 ---
        self.tab_about = QWidget()
        self._init_about(self.tab_about)
        self.tabs.addTab(self.tab_about, L('tab_about'))
        
        # 底部按钮
        btn_box = QHBoxLayout()
        btn_box.addStretch()
        
        self.btn_save = QPushButton(L('btn_save'))
        self.btn_save.setFixedSize(100, 35)
        # initial style will be applied in _on_theme_changed
        self.btn_save.setStyleSheet("font-weight: bold; border-radius: 4px;")
        self.btn_save.clicked.connect(self._save_and_close)
        
        btn_box.addWidget(self.btn_save)
        layout.addLayout(btn_box)

    def _init_basic(self, parent):
        layout = QVBoxLayout(parent)
        layout.setSpacing(10)
        
        # Group 1: 个人信息
        grp_user = QGroupBox(L('grp_user'))
        fl_user = QFormLayout(grp_user)
        
        self.inp_name = QLineEdit(self.my_info.get('name', ''))
        fl_user.addRow(f"{L('lbl_nickname')}:", self.inp_name)
        
        self.cmb_status = QComboBox()
        # status labels from i18n
        self.cmb_status.addItems([L('status_online'), L('status_busy'), L('status_away')])
        # 状态回显
        curr = self.my_info.get('status', 'online')
        idx = 0
        if 'busy' in curr: idx = 1
        elif 'away' in curr: idx = 2
        self.cmb_status.setCurrentIndex(idx)
        fl_user.addRow(f"{L('lbl_status')}:", self.cmb_status)
        
        fl_user.addRow(f"{L('lbl_bound_ip')}:", QLabel(self.my_info.get('ip', 'Unknown')))
        
        layout.addWidget(grp_user)

        # Group 2: 界面与国际化 + 加密与目录
        grp_ui = QGroupBox(L('grp_ui'))
        fl_ui = QFormLayout(grp_ui)

        # 外观主题
        self.cmb_theme = QComboBox()
        # 使用 SUPPORTED_THEMES 动态填充，但显示本地化名称，保存实际主题代码为 item data
        try:
            themes = list(SUPPORTED_THEMES)
            for t in themes:
                # 本地化显示名使用 lang 键：theme_light / theme_dark
                label = L(f'theme_{t}') if isinstance(t, str) else str(t)
                self.cmb_theme.addItem(label, t)
            # 读取已有主题并回显（查找 data 匹配）
            theme = getattr(self.bridge.core, 'theme', themes[0] if themes else 'light')
            # findData 返回 index of item with matching userData
            idx = self.cmb_theme.findData(theme)
            if idx is None or idx < 0:
                idx = 0
            self.cmb_theme.setCurrentIndex(idx)
        except Exception:
            # 回退到默认两个选项（带本地化标签）
            self.cmb_theme.clear()
            self.cmb_theme.addItem(L('theme_light'), 'light')
            self.cmb_theme.addItem(L('theme_dark'), 'dark')
            try:
                theme = getattr(self.bridge.core, 'theme', 'light')
                idx = self.cmb_theme.findData(theme)
                if idx is None or idx < 0:
                    idx = 0
                self.cmb_theme.setCurrentIndex(idx)
            except Exception:
                self.cmb_theme.setCurrentIndex(0)
        fl_ui.addRow(f"{L('lbl_theme')}:", self.cmb_theme)

        # 编码切换
        self.cmb_encoding = QComboBox()
        self.cmb_encoding.addItems(["utf-8", "gbk", "cp936"])
        try:
            enc = getattr(self.bridge.core, 'encoding', 'utf-8')
            idx = max(0, self.cmb_encoding.findText(enc))
            self.cmb_encoding.setCurrentIndex(idx)
        except Exception:
            self.cmb_encoding.setCurrentIndex(0)
        fl_ui.addRow(f"{L('lbl_encoding')}:", self.cmb_encoding)

        # 语言切换
        self.cmb_language = QComboBox()
        # 从 SUPPORTED_LANGS 中读取显示名（第二行）和代码（第一行）
        try:
            labels = SUPPORTED_LANGS[1]
            self.cmb_language.addItems(list(labels))
        except Exception:
            self.cmb_language.addItems(["简体中文 (zhCN)", "English (enUS)"])
        try:
            lang = getattr(self.bridge.core, 'language', 'zhCN')
            codes = SUPPORTED_LANGS[0]
            if lang in codes:
                self.cmb_language.setCurrentIndex(codes.index(lang))
            else:
                self.cmb_language.setCurrentIndex(0)
        except Exception:
            self.cmb_language.setCurrentIndex(0)
        fl_ui.addRow(f"{L('lbl_language')}:", self.cmb_language)

        layout.addWidget(grp_ui)

        # Group 3: 文件路径
        grp_file = QGroupBox(L('grp_file'))
        fl_file = QFormLayout(grp_file)
        
        # 下载目录
        # 从配置读取下载目录
        try:
            dl = getattr(self.bridge.core, 'download_dir', None) or getattr(self.bridge.core, 'config', {}).get('download_dir')
        except Exception:
            dl = None
        self.path_down = self._create_path_selector(dl or "./common/downloads")
        fl_file.addRow(f"{L('lbl_download_dir')}:", self.path_down)
        
        # 截图目录
        try:
            shot = getattr(self.bridge.core, 'screenshot_dir', None)
        except Exception:
            shot = None
        self.path_shot = self._create_path_selector(shot or "./common/screenshots")
        fl_file.addRow(f"{L('lbl_screenshot_dir')}:", self.path_shot)
        
        layout.addWidget(grp_file)

        layout.addStretch()

    def _create_path_selector(self, default_path):
        # 容器 widget
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0,0,0,0)
        
        inp = QLineEdit(os.path.abspath(default_path))
        inp.setReadOnly(True)
        btn = QPushButton(L('btn_browse'))
        btn.setFixedWidth(30)
        btn.clicked.connect(lambda: self._choose_dir(inp))
        
        h.addWidget(inp)
        h.addWidget(btn)
        return w

    def _choose_dir(self, line_edit):
        d = QFileDialog.getExistingDirectory(self, L('choose_dir'), line_edit.text())
        if d:
            line_edit.setText(d)

    def _init_security(self, parent):
        layout = QVBoxLayout(parent)
        # 加密模式（使用频率高，置于顶部）
        grp_enc = QGroupBox(L('grp_session_enc'))
        f_enc = QFormLayout(grp_enc)
        self.cmb_encrypt = QComboBox()
        # 按安全程度排序：off < on < strict
        self.cmb_encrypt.addItems([L('enc_off'), L('enc_on'), L('enc_strict')])
        try:
            encm = getattr(self.bridge.core, 'encrypt_mode', 'on')
            self.cmb_encrypt.setCurrentIndex({"off":0, "on":1, "strict":2}.get(encm, 1))
        except Exception:
            self.cmb_encrypt.setCurrentIndex(1)
        f_enc.addRow(f"{L('lbl_encrypt_mode')}:", self.cmb_encrypt)
        layout.addWidget(grp_enc)

        # 加密指纹信息（次要项，置于加密模式之后）
        grp_sec = QGroupBox(L('grp_fingerprint'))
        v_sec = QVBoxLayout(grp_sec)
        
        fp = "Unknown"
        if hasattr(self.bridge.core, 'identity_pub_bytes'):
            import hashlib
            raw = self.bridge.core.identity_pub_bytes
            if raw:
                fp = hashlib.sha256(raw).hexdigest()

        self.lbl_fp = QLabel(fp)
        self.lbl_fp.setWordWrap(True)
        self.lbl_fp.setStyleSheet("font-family: Consolas; color: #555; background: #eee; padding: 5px; border-radius: 3px;")
        v_sec.addWidget(self.lbl_fp)
        
        btn_regen = QPushButton(L('btn_regen'))
        btn_regen.setFixedWidth(150)
        btn_regen.clicked.connect(self._regen_keys)
        v_sec.addWidget(btn_regen)
        layout.addWidget(grp_sec)
        
        # Group 2: 调试
        grp_dbg = QGroupBox(L('grp_debug'))
        v_dbg = QVBoxLayout(grp_dbg)
        
        self.chk_raw = QCheckBox(L('chk_raw'))
        self.chk_log_debug = QCheckBox(L('chk_log_debug'))
        
        v_dbg.addWidget(self.chk_raw)
        v_dbg.addWidget(self.chk_log_debug)
        layout.addWidget(grp_dbg)
        
        layout.addStretch()

    def _init_about(self, parent):
        layout = QVBoxLayout(parent)
        layout.setAlignment(Qt.AlignTop)
        
        # 简单的 Logo 区域：优先使用资源目录下的图标
        try:
            icon_path = os.path.join(os.path.dirname(__file__), "assets", "zfeiq_icon_128x128.ico")
            if os.path.exists(icon_path):
                pix = QPixmap(icon_path).scaled(96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                lbl_logo = QLabel()
                lbl_logo.setAlignment(Qt.AlignCenter)
                lbl_logo.setPixmap(pix)
                layout.addWidget(lbl_logo)
            else:
                lbl_logo = QLabel("ZFeiQ")
                lbl_logo.setAlignment(Qt.AlignCenter)
                lbl_logo.setStyleSheet("font-size: 24px; font-weight: bold; color: #0078d7; margin: 20px;")
                layout.addWidget(lbl_logo)
        except Exception:
            lbl_logo = QLabel("ZFeiQ")
            lbl_logo.setAlignment(Qt.AlignCenter)
            lbl_logo.setStyleSheet("font-size: 24px; font-weight: bold; color: #0078d7; margin: 20px;")
            layout.addWidget(lbl_logo)
        
        form = QFormLayout()
        form.setSpacing(10)
        form.addRow(f"{L('lbl_core_version')}:", QLabel(CORE_VERSION))
        form.addRow(f"{L('lbl_last_update')}:", QLabel("2025-12-05"))
        
        sys_info = f"{platform.system()} {platform.release()} ({platform.machine()})"
        form.addRow(f"{L('lbl_system_platform')}:", QLabel(sys_info))

        python_info = f"{platform.python_version()} (Qt 5)"
        form.addRow(f"{L('lbl_runtime')}:", QLabel(python_info))
        
        layout.addLayout(form)
        
        layout.addSpacing(20)
        btn_link = QPushButton(L('btn_open_repo'))
        btn_link.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/YourRepo/NZFeiQ")))
        layout.addWidget(btn_link)

    def _regen_keys(self):
        ret = QMessageBox.warning(self, L('warn_title'), L('regen_warning'), 
                                  QMessageBox.Yes | QMessageBox.No)
        if ret == QMessageBox.Yes:
            try:
                self.bridge.core.regenerate_identity()
                # refresh displayed fingerprint
                try:
                    raw = getattr(self.bridge.core, 'identity_pub_bytes', None)
                    if raw:
                        import hashlib
                        new_fp = hashlib.sha256(raw).hexdigest()
                    else:
                        new_fp = 'Unknown'
                    try:
                        self.lbl_fp.setText(new_fp)
                    except Exception:
                        pass
                except Exception:
                    pass
                QMessageBox.information(self, L('info_title'), L('regen_success'))
            except Exception as e:
                QMessageBox.critical(self, L('err_title'), L('regen_fail').format(err=str(e)))

    def _save_and_close(self):
        name = self.inp_name.text().strip()
        status_map = ["online", "busy", "away"]
        status = status_map[self.cmb_status.currentIndex()]
        
        # 保存路径配置到 config.json
        try:
            path_dl = self.path_down.findChild(QLineEdit).text()
            path_sh = self.path_shot.findChild(QLineEdit).text()
        except Exception:
            path_dl = None
            path_sh = None
        
        if not name:
            QMessageBox.warning(self, "错误", "昵称不能为空")
            return
            
        old_name = getattr(self.bridge.core, 'username', '')
        old_status = getattr(self.bridge.core, 'status', 'online')
        old_ip = getattr(self.bridge.core, 'local_ip', '')

        self.bridge.core.username = name
        self.bridge.core.status = status
        # 保存界面/国际化设置并接入 core
        try:
            # theme selected via SUPPORTED_THEMES
            try:
                # 读取选中项的 userData（实际主题代码）
                theme = self.cmb_theme.currentData()
                if not theme:
                    # 回退到默认
                    themes = list(SUPPORTED_THEMES)
                    theme = themes[self.cmb_theme.currentIndex()] if themes else 'light'
            except Exception:
                theme = 'light'
            # language code from SUPPORTED_LANGS
            try:
                codes = SUPPORTED_LANGS[0]
                language = codes[self.cmb_language.currentIndex()]
            except Exception:
                language = 'zhCN'
            encoding = self.cmb_encoding.currentText()
            setattr(self.bridge.core, 'theme', theme)
            setattr(self.bridge.core, 'language', language)
            # 保存时同时设置全局语言以让 L(...) 立即生效
            try:
                from gui.lang import set_language
                set_language(language)
            except Exception:
                pass
            self.bridge.core.encoding = encoding
            # 加密模式
            enc_mode = ['off','on','strict'][self.cmb_encrypt.currentIndex()]
            setattr(self.bridge.core, 'encrypt_mode', enc_mode)
            # 路径保存到 core 配置引用（若存在）
            if path_dl:
                setattr(self.bridge.core, 'download_dir', path_dl)
            if path_sh:
                setattr(self.bridge.core, 'screenshot_dir', path_sh)
        except Exception:
            pass
        # 立即更新 core 的本地 registry，保证本地 GUI 能看到最新昵称/状态
        try:
            self.bridge.core.registry.upsert(self.bridge.core.local_ip, name, self.bridge.core.hostname, status)
        except Exception:
            pass
        # 持久化配置
        try:
            # 更新 core 的内部配置对象（若有）并保存
            cfg = getattr(self.bridge.core, 'config', {})
            if isinstance(cfg, dict):
                cfg['username'] = name
                cfg['status'] = status
                cfg['encoding'] = getattr(self.bridge.core, 'encoding', 'utf-8')
                cfg['language'] = getattr(self.bridge.core, 'language', 'zhCN')
                cfg['theme'] = getattr(self.bridge.core, 'theme', 'light')
                cfg['encrypt_mode'] = getattr(self.bridge.core, 'encrypt_mode', 'on')
                if path_dl:
                    cfg['download_dir'] = path_dl
                if path_sh:
                    cfg['screenshot_dir'] = path_sh
                setattr(self.bridge.core, 'config', cfg)
            self.bridge.core._save_config()
        except Exception:
            pass

        # 通知 GUI 变更了界面语言（如果有）以便即时刷新 UI 文本
        try:
            lang_code = getattr(self.bridge.core, 'language', None)
            if lang_code and hasattr(self.bridge, 'sig_lang_changed'):
                self.bridge.sig_lang_changed.emit(lang_code)
        except Exception:
            pass
        # 发出主题变更信号，供界面实时应用样式
        try:
            theme_code = getattr(self.bridge.core, 'theme', None)
            if theme_code and hasattr(self.bridge, 'sig_theme_changed'):
                self.bridge.sig_theme_changed.emit(theme_code)
        except Exception:
            pass
        # 主动广播一次 presence，促使远端节点接收到状态变化
        # 仅在对其他用户有影响的字段变化时主动广播
        try:
            if (name != old_name) or (status != old_status) or (getattr(self.bridge.core, 'local_ip', '') != old_ip):
                self.bridge.core._broadcast_presence()
        except Exception:
            pass
        # 通知前端刷新用户列表（事件驱动 / 直接 emit 作保底）
        try:
            # 首先尝试使用 core 的事件触发（Bridge 会转发），作为优先路径
            try:
                self.bridge.core._emit("node.update")
            except Exception:
                pass
            cnt = len(self.bridge.core.registry.list_nodes())
            self.bridge.sig_nodes_changed.emit(cnt)
        except Exception:
            try:
                self.bridge.sig_nodes_changed.emit(0)
            except Exception:
                pass

        self.bridge.sig_log.emit("INFO", f"设置已保存: {name}")
        self.accept()

    def _on_theme_changed(self, theme_code: str):
        """Apply minimal theme styles to Settings dialog widgets."""
        try:
            from gui.styles import get_color, qss_fragment
            try:
                # Apply dialog-wide fragment
                frag = qss_fragment(theme_code)
                self.setStyleSheet(frag)
            except Exception:
                pass
            try:
                btn_bg = get_color('BTN_BG', theme_code)
                btn_text = get_color('BTN_TEXT', theme_code)
                self.btn_save.setStyleSheet(f"background-color: {btn_bg}; color: {btn_text}; font-weight: bold; border-radius: 4px;")
            except Exception:
                pass
            try:
                # Update path labels / other labels colors
                for lbl in self.findChildren(QLabel):
                    lbl.setStyleSheet(f"color: {get_color('PRIMARY_TEXT', theme_code)};")
            except Exception:
                pass
        except Exception:
            pass