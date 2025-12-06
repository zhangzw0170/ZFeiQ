from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLabel, QLineEdit, 
                             QPushButton, QMessageBox, QGraphicsDropShadowEffect)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QPixmap
import os

class LoginPage(QWidget):
    # 登录成功信号
    sig_login_success = pyqtSignal()

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.bridge = bridge
        self._setup_ui()

    def _setup_ui(self):
        # 1. 整体布局：居中
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignCenter)
        
        # 2. 登录卡片容器
        card = QWidget()
        card.setFixedWidth(320)
        # 卡片样式：白底、圆角
        card.setStyleSheet("""
            QWidget {
                background-color: white;
                border-radius: 10px;
            }
        """)
        
        # 给卡片加一点阴影，更有层次感 (软渲染下可能稍耗资源，不想要可注释掉)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(Qt.gray)
        shadow.setOffset(0, 0)
        card.setGraphicsEffect(shadow)

        # 3. 卡片内部元素
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(30, 40, 30, 40)
        card_layout.setSpacing(20)

        # 标题（使用应用图标替代纯文本）
        try:
            icon_path = os.path.join(os.path.dirname(__file__), "assets", "zfeiq_icon_128x128.ico")
            if os.path.exists(icon_path):
                pix = QPixmap(icon_path).scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                lbl_logo = QLabel()
                lbl_logo.setAlignment(Qt.AlignCenter)
                lbl_logo.setPixmap(pix)
                card_layout.addWidget(lbl_logo)
            else:
                lbl_title = QLabel("ZFeiQ")
                lbl_title.setAlignment(Qt.AlignCenter)
                lbl_title.setStyleSheet("font-size: 28px; font-weight: bold; color: #333; font-family: 'Segoe UI', sans-serif;")
                card_layout.addWidget(lbl_title)
        except Exception:
            lbl_title = QLabel("ZFeiQ")
            lbl_title.setAlignment(Qt.AlignCenter)
            lbl_title.setStyleSheet("font-size: 28px; font-weight: bold; color: #333; font-family: 'Segoe UI', sans-serif;")
            card_layout.addWidget(lbl_title)
        
        lbl_sub = QLabel("局域网即时通讯系统")
        lbl_sub.setAlignment(Qt.AlignCenter)
        lbl_sub.setStyleSheet("font-size: 14px; color: #888; margin-bottom: 10px;")
        card_layout.addWidget(lbl_sub)

        # 用户名输入
        self.inp_name = QLineEdit()
        self.inp_name.setPlaceholderText("请输入您的昵称")
        self.inp_name.setFixedHeight(45)
        # 输入框样式
        self.inp_name.setStyleSheet("""
            QLineEdit {
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 0 10px;
                font-size: 14px;
                background: #f9f9f9;
            }
            QLineEdit:focus {
                border: 1px solid #0078d7;
                background: white;
            }
        """)
        self.inp_name.returnPressed.connect(self._do_login)
        card_layout.addWidget(self.inp_name)

        # 登录按钮
        self.btn_login = QPushButton("立即登录")
        self.btn_login.setFixedHeight(45)
        self.btn_login.setCursor(Qt.PointingHandCursor)
        # 按钮样式：仿微信绿/Win10蓝
        self.btn_login.setStyleSheet("""
            QPushButton {
                background-color: #0078d7;
                color: white;
                font-size: 16px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #0063b1; }
            QPushButton:pressed { background-color: #004e8c; }
        """)
        self.btn_login.clicked.connect(self._do_login)
        card_layout.addWidget(self.btn_login)

        # 将卡片加入主布局
        main_layout.addWidget(card)

    def _do_login(self):
        name = self.inp_name.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "请输入一个昵称")
            self.inp_name.setFocus()
            return
            
        # 1. 调用后台登录接口
        self.bridge.login(name)
        
        # 2. 发射信号，通知 Window 切换到聊天页
        self.sig_login_success.emit()