from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLabel, QLineEdit, 
                             QPushButton, QMessageBox, QGraphicsDropShadowEffect, QCheckBox)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QPixmap
import os
from gui.styles import get_color

class LoginPage(QWidget):
    # 登录成功信号
    sig_login_success = pyqtSignal()

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        # determine initial theme from bridge if available
        try:
            self._current_theme = getattr(self.bridge.core, 'theme', 'light')
        except Exception:
            self._current_theme = 'light'

        self._setup_ui()

        # apply theme immediately
        try:
            self._apply_theme(self._current_theme)
        except Exception:
            pass

        # subscribe to theme changes
        try:
            self.bridge.sig_theme_changed.connect(self._on_theme_changed)
        except Exception:
            pass

    def _setup_ui(self):
        # 1. 整体布局：居中
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignCenter)
        
        # 2. 登录卡片容器
        self.card = QWidget()
        self.card.setFixedWidth(320)
        # 卡片样式将由主题填充
        self.card.setStyleSheet("")
        
        # 给卡片加一点阴影，更有层次感 (软渲染下可能稍耗资源，不想要可注释掉)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(Qt.gray)
        shadow.setOffset(0, 0)
        self.card.setGraphicsEffect(shadow)

        # 3. 卡片内部元素
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(30, 40, 30, 40)
        card_layout.setSpacing(20)

        # 标题（使用应用图标替代纯文本）
        try:
            icon_path = os.path.join(os.path.dirname(__file__), "assets", "zfeiq_icon_128x128.ico")
            if os.path.exists(icon_path):
                pix = QPixmap(icon_path).scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.lbl_logo = QLabel()
                self.lbl_logo.setAlignment(Qt.AlignCenter)
                self.lbl_logo.setPixmap(pix)
                card_layout.addWidget(self.lbl_logo)
            else:
                self.lbl_title = QLabel("ZFeiQ")
                self.lbl_title.setAlignment(Qt.AlignCenter)
                card_layout.addWidget(self.lbl_title)
        except Exception:
            self.lbl_title = QLabel("ZFeiQ")
            self.lbl_title.setAlignment(Qt.AlignCenter)
            card_layout.addWidget(self.lbl_title)
        
        self.lbl_sub = QLabel("局域网即时通讯系统")
        self.lbl_sub.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self.lbl_sub)

        # 用户名输入
        self.inp_name = QLineEdit()
        # 若 core 中已有保存的用户名，作为回显
        try:
            self.inp_name.setText(getattr(self.bridge.core, 'username', '') or '')
        except Exception:
            pass
        self.inp_name.setPlaceholderText("请输入您的昵称")
        self.inp_name.setFixedHeight(45)
        # 样式由主题决定，稍后通过 _apply_theme 设置
        self.inp_name.setStyleSheet("")
        self.inp_name.returnPressed.connect(self._do_login)
        card_layout.addWidget(self.inp_name)

        # 自动登录选项
        try:
            self.chk_auto_login = QCheckBox("启动时自动登录")
            try:
                self.chk_auto_login.setChecked(bool(getattr(self.bridge.core, 'auto_login', False)))
            except Exception:
                pass
            card_layout.addWidget(self.chk_auto_login)
        except Exception:
            self.chk_auto_login = None

        # 登录按钮
        self.btn_login = QPushButton("立即登录")
        self.btn_login.setFixedHeight(45)
        self.btn_login.setCursor(Qt.PointingHandCursor)
        # 按钮样式由主题驱动
        self.btn_login.setStyleSheet("")
        self.btn_login.clicked.connect(self._do_login)
        card_layout.addWidget(self.btn_login)

        # 将卡片加入主布局
        main_layout.addWidget(self.card)

    def _on_theme_changed(self, theme_code: str):
        try:
            self._current_theme = theme_code
            self._apply_theme(theme_code)
        except Exception:
            pass

    def _apply_theme(self, theme_code: str):
        """Apply theme colors to login page widgets."""
        try:
            bg = get_color('BACKGROUND_PANEL', theme_code) or '#ffffff'
            card_bg = get_color('MENU_BG', theme_code) or get_color('INPUT_BG', theme_code) or '#ffffff'
            primary = get_color('PRIMARY_TEXT', theme_code) or '#000000'
            secondary = get_color('SECONDARY_TEXT', theme_code) or '#666666'
            border = get_color('BORDER', theme_code) or '#dddddd'
            btn_bg = get_color('BTN_BG', theme_code) or '#0078d7'
            btn_text = get_color('BTN_TEXT', theme_code) or '#ffffff'

            # apply background directly to this widget and the card (avoid selector scope issues)
            self.setStyleSheet(f"background: {bg};")
            # remove card border; rely on shadow + radius for separation
            self.card.setStyleSheet(f"background: {card_bg}; border-radius: 10px;")
            try:
                self.lbl_title.setStyleSheet(f"font-size: 28px; font-weight: bold; color: {primary};")
            except Exception:
                pass
            try:
                self.lbl_sub.setStyleSheet(f"font-size: 14px; color: {secondary}; margin-bottom: 10px;")
            except Exception:
                pass

            # input box
            self.inp_name.setStyleSheet(
                f"QLineEdit {{ border: 1px solid {border}; border-radius: 5px; padding: 0 10px; font-size: 14px; background: {get_color('INPUT_BG', theme_code)}; color: {primary}; }}"
                f"QLineEdit:focus {{ border: 1px solid {get_color('ACCENT', theme_code)}; background: {get_color('INPUT_BG', theme_code)}; }}"
            )

            # login button
            self.btn_login.setStyleSheet(
                f"QPushButton {{ background-color: {btn_bg}; color: {btn_text}; font-size: 16px; font-weight: bold; border-radius: 5px; }}"
                f"QPushButton:hover {{ background-color: {get_color('BTN_ACCENT', theme_code)}; }}"
            )
        except Exception:
            pass

    def _do_login(self):
        name = self.inp_name.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "请输入一个昵称")
            self.inp_name.setFocus()
            return
            
        # 1. 调用后台登录接口
        self.bridge.login(name)
        # 保存自动登录偏好（持久化）
        try:
            if hasattr(self, 'chk_auto_login') and self.chk_auto_login is not None:
                setattr(self.bridge.core, 'auto_login', bool(self.chk_auto_login.isChecked()))
            # 保存配置到磁盘
            try:
                self.bridge.core._save_config()
            except Exception:
                pass
        except Exception:
            pass
        
        # 2. 发射信号，通知 Window 切换到聊天页
        self.sig_login_success.emit()