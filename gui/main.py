import sys
import os
import signal
import traceback

# 1. 强制使用软件渲染 OpenGL (针对 RK3566/RK3588 优化)
# 很多嵌入式 Linux 的 Qt GPU 驱动不稳定，强切 CPU 渲染虽然慢点，但绝不黑屏。
os.environ["QT_OPENGL"] = "software"
# 抑制 Qt 的一些无关紧要的字体报错
os.environ["QT_LOGGING_RULES"] = "*.debug=false;qt.qpa.*=false"

from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import Qt, QCoreApplication

# 确保能引用到同级模块
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from gui.bridge import Bridge
from gui.window import MainWindow

def excepthook(exc_type, exc_value, exc_tb):
    """全局异常捕获，弹窗提示，避免直接闪退"""
    tb = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    print("CRITICAL ERROR:", tb)
    if QApplication.instance():
        QMessageBox.critical(None, "程序崩溃", f"发生未捕获异常:\n{exc_value}")
    sys.exit(1)

def main():
    # 处理 Ctrl+C，方便在终端杀死进程
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    # 2. 初始化应用
    # 针对高分屏或者特殊分辨率屏幕的缩放适配
    QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    
    app = QApplication(sys.argv)
    app.setApplicationName("ZFeiQ Reborn")
    
    # 3. 全局极简样式 (性能优先，少用渐变和阴影)
    app.setStyleSheet("""
        QWidget { font-family: 'Sans Serif', 'Microsoft YaHei'; font-size: 14px; color: #333; }
        QMainWindow { background: #f2f2f2; }
        QLineEdit { 
            background: white; border: 1px solid #ccc; border-radius: 4px; padding: 4px; selection-background-color: #0078d7; 
        }
        QLineEdit:focus { border: 1px solid #0078d7; }
        QPushButton { 
            background: #e1e1e1; border: 1px solid #adadad; border-radius: 4px; padding: 6px 12px; 
        }
        QPushButton:hover { background: #e5f1fb; border-color: #0078d7; }
        QPushButton:pressed { background: #cce4f7; }
        QListView { background: white; border: none; }
    """)

    sys.excepthook = excepthook

    # 4. 启动后台桥梁 (独立线程)
    bridge = Bridge()
    bridge.start()

    # 5. 启动主窗口
    window = MainWindow(bridge)
    window.show()

    # 进入事件循环
    exit_code = app.exec_()
    
    # 退出清理
    bridge.stop()
    sys.exit(exit_code)

if __name__ == "__main__":
    main()