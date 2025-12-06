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
from PyQt5.QtGui import QIcon
from PyQt5 import QtWidgets, QtCore

# 确保能引用到同级模块
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from gui.bridge import Bridge
from gui.window import MainWindow
from gui.lang import set_language

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
    # 设置全局窗口图标（使用 repo 内的 assets）
    try:
        icon_path = os.path.join(os.path.dirname(__file__), "assets", "zfeiq_icon_128x128.ico")
        if os.path.exists(icon_path):
            app.setWindowIcon(QIcon(icon_path))
    except Exception:
        pass
    
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

    # 3.5 尽力禁用 Qt 的内建 UI 动画/效果以减少 CPU/GPU 开销
    try:
        for eff in (
            getattr(QtCore.Qt, 'UI_AnimateMenu', None),
            getattr(QtCore.Qt, 'UI_AnimateCombo', None),
            getattr(QtCore.Qt, 'UI_AnimateTooltip', None),
            getattr(QtCore.Qt, 'UI_FadeMenu', None),
            getattr(QtCore.Qt, 'UI_FadeTooltip', None),
        ):
            if eff is not None:
                try:
                    QApplication.setEffectEnabled(eff, False)
                except Exception:
                    pass
    except Exception:
        pass

    # 4. 启动后台桥梁 (独立线程)
    bridge = Bridge()
    bridge.start()

    # 根据全局配置应用界面语言
    try:
        lang = getattr(bridge.core, 'language', 'zhCN')
        set_language(lang)
    except Exception:
        pass

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