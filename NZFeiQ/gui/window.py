from PyQt5.QtWidgets import QMainWindow, QStackedWidget, QMessageBox
from gui.login import LoginPage  # 下一步我们会写这个

class MainWindow(QMainWindow):
    def __init__(self, bridge):
        super().__init__()
        self.bridge = bridge
        self.setWindowTitle("ZFeiQ")
        
        # 适配 7寸屏 (1024x600) 或更小分辨率
        self.resize(800, 500)
        
        # 核心容器：堆栈窗口
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        
        # 1. 初始化登录页 (轻量)
        self.login_page = LoginPage(bridge)
        
        # 绑定信号：登录成功 -> 切换到聊天
        self.login_page.sig_login_success.connect(self.switch_to_chat)
        
        self.stack.addWidget(self.login_page)
        
        # 2. 聊天页先留空 (Lazy Load)
        self.chat_page = None

    def switch_to_chat(self):
        """
        只有当确实需要显示聊天界面时，才加载相关模块。
        省内存的关键一步。
        """
        if not self.chat_page:
            try:
                # 动态导入，避免启动时加载大量 UI 库
                from gui.chat import ChatPage
                self.chat_page = ChatPage(self.bridge, self)
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