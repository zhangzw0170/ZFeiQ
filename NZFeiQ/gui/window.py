from PyQt5.QtWidgets import QMainWindow, QStackedWidget, QMessageBox
from PyQt5.QtGui import QIcon
import os
from gui.login import LoginPage  # 下一步我们会写这个
from gui.lang import L
from gui.styles import get_color

class MainWindow(QMainWindow):
    def __init__(self, bridge):
        super().__init__()
        self.bridge = bridge
        self.setWindowTitle("ZFeiQ")
        # 尝试设置窗口图标
        try:
            icon_path = os.path.join(os.path.dirname(__file__), "assets", "zfeiq_icon_128x128.ico")
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
        except Exception:
            pass
        
        # 适配 7寸屏 (1024x600) 或更小分辨率
        self.resize(800, 500)
        
        # 核心容器：堆栈窗口
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        # 状态栏
        self.statusBar().showMessage(L('ready'))
        # 初始样式（将由主题更新覆盖）
        try:
            theme = getattr(self.bridge.core, 'theme', 'light')
        except Exception:
            theme = 'light'
        try:
            sb_color = get_color('SECONDARY_TEXT', theme)
            sb_bg = get_color('BACKGROUND_PANEL', theme)
            sb_border = get_color('BORDER', theme)
            self.statusBar().setStyleSheet(f"QStatusBar {{ color: {sb_color}; background: {sb_bg}; border-top: 1px solid {sb_border}; }}")
            # apply theme to main window root so login page sits on themed background
            self._current_theme = theme
            root_bg = get_color('BACKGROUND_PANEL', theme)
            root_text = get_color('PRIMARY_TEXT', theme)
            # set simple root styling directly
            self.setStyleSheet(f"background: {root_bg}; color: {root_text};")
        except Exception:
            self.statusBar().setStyleSheet("QStatusBar { color: #666; background: #f0f0f0; border-top: 1px solid #ccc; }")

        # 监听主题变化以适配状态栏
        try:
            self.bridge.sig_theme_changed.connect(self._on_theme_changed)
        except Exception:
            pass

        # 1. 初始化登录页 (轻量)
        self.login_page = LoginPage(self.bridge)

        # 绑定信号：登录成功 -> 切换到聊天
        self.login_page.sig_login_success.connect(self.switch_to_chat)

        self.stack.addWidget(self.login_page)

        # 2. 聊天页先留空 (Lazy Load)
        self.chat_page = None

    def _on_theme_changed(self, theme_code: str):
        try:
            # update stored theme and statusbar/root styles
            self._current_theme = theme_code
            sb_color = get_color('SECONDARY_TEXT', theme_code)
            sb_bg = get_color('BACKGROUND_PANEL', theme_code)
            sb_border = get_color('BORDER', theme_code)
            self.statusBar().setStyleSheet(f"QStatusBar {{ color: {sb_color}; background: {sb_bg}; border-top: 1px solid {sb_border}; }}")
            # also update main window root background/text
            root_bg = get_color('BACKGROUND_PANEL', theme_code)
            root_text = get_color('PRIMARY_TEXT', theme_code)
            self.setStyleSheet(f"background: {root_bg}; color: {root_text};")
        except Exception:
            try:
                self.statusBar().setStyleSheet("QStatusBar { color: #666; background: #f0f0f0; border-top: 1px solid #ccc; }")
            except Exception:
                pass
        

    def switch_to_chat(self):
        """
        只有当确实需要显示聊天界面时，才加载相关模块。
        省内存的关键一步。
        """
        if not self.chat_page:
            try:
                # Before creating the chat page, refresh theme so newly-created widgets pick it up
                try:
                    theme_now = getattr(self.bridge.core, 'theme', getattr(self, '_current_theme', 'light'))
                except Exception:
                    theme_now = getattr(self, '_current_theme', 'light')
                try:
                    # update main window styling immediately
                    self._on_theme_changed(theme_now)
                except Exception:
                    pass

                # 动态导入，避免启动时加载大量 UI 库
                from gui.chat import ChatPage
                self.chat_page = ChatPage(self.bridge, self)
                # try to notify chat page of current theme if it implements handler
                try:
                    if hasattr(self.chat_page, '_on_theme_changed'):
                        self.chat_page._on_theme_changed(theme_now)
                except Exception:
                    pass
                self.stack.addWidget(self.chat_page)
            except Exception as e:
                import traceback
                traceback.print_exc()
                QMessageBox.critical(self, "加载失败", f"无法加载聊天模块:\n{e}")
                return

        # 切换页面
        self.stack.setCurrentWidget(self.chat_page)
        
        # 可以在这里根据屏幕大小决定是否最大化
        # self.showMaximized()