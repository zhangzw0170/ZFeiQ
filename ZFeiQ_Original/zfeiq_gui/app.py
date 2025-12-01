import os
import sys
import platform
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtGui import QFontDatabase

from .main_window import MainWindow
from .backend import GuiBackend


def _ensure_qt_plugin_paths() -> None:
    """Configure QT plugin paths to avoid platform plugin load errors."""
    try:
        plugins_path = QtCore.QLibraryInfo.location(QtCore.QLibraryInfo.PluginsPath)
        if plugins_path and os.path.isdir(plugins_path):
            os.environ.setdefault("QT_PLUGIN_PATH", plugins_path)
            plat_dir = os.path.join(plugins_path, "platforms")
            if os.path.isdir(plat_dir):
                os.environ.setdefault("QT_QPA_PLATFORM_PLUGIN_PATH", plat_dir)
        qt_bin = os.path.join(os.path.dirname(plugins_path), "bin") if plugins_path else None
        if qt_bin and os.path.isdir(qt_bin):
            if qt_bin not in os.environ.get("PATH", ""):
                os.environ["PATH"] = qt_bin + os.pathsep + os.environ.get("PATH", "")
    except Exception:
        pass

def _disable_ui_animations() -> None:
    """Best-effort: disable global UI animations/effects to reduce CPU/GPU cost."""
    try:
        # Some effects may not be supported on all styles/platforms; ignore failures.
        for eff in (
            getattr(QtCore.Qt, 'UI_AnimateMenu', None),
            getattr(QtCore.Qt, 'UI_AnimateCombo', None),
            getattr(QtCore.Qt, 'UI_AnimateTooltip', None),
            getattr(QtCore.Qt, 'UI_FadeMenu', None),
            getattr(QtCore.Qt, 'UI_FadeTooltip', None),
        ):
            if eff is not None:
                try:
                    QtWidgets.QApplication.setEffectEnabled(eff, False)
                except Exception:
                    pass
    except Exception:
        pass


def launch_gui() -> None:
    _ensure_qt_plugin_paths()
    # 抑制字体枚举告警
    try:
        QtCore.QLoggingCategory.setFilterRules("qt.qpa.fonts=false")
    except Exception:
        pass
    # 软件 OpenGL 回退（RK3566 等）
    try:
        if (platform.system() == "Linux" and platform.machine().lower() in ("aarch64", "arm64", "armv7l")) or os.environ.get("ZFEIQ_FORCE_SOFTGL"):
            QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_UseSoftwareOpenGL)
            os.environ.setdefault("QT_OPENGL", "software")
    except Exception:
        pass

    app = QtWidgets.QApplication.instance()
    owns_app = False
    if app is None:
        app = QtWidgets.QApplication(sys.argv)
        # 尝试设置字体（含 Emoji 优先）
        try:
            preferred = [
                ("Noto Color Emoji", 10),
                ("Segoe UI Emoji", 10),
                ("Segoe UI", 10),
                ("Ubuntu", 10),
                ("Arial", 10),
            ]
            fam = None
            for name, sz in preferred:
                f = QtGui.QFont(name, sz)
                if QtGui.QFontInfo(f).family():
                    fam = f
                    break
            if fam:
                app.setFont(fam)
        except Exception:
            pass
        # 额外加载 ./fonts 目录
        try:
            fonts_dir = os.path.join(os.getcwd(), "fonts")
            if os.path.isdir(fonts_dir):
                for fn in os.listdir(fonts_dir):
                    if fn.lower().endswith((".ttf", ".otf", ".ttc")):
                        QFontDatabase.addApplicationFont(os.path.join(fonts_dir, fn))
        except Exception:
            pass
        # 设置全局 UI 字体：优先使用支持中/英/西班牙语的跨平台字体
        try:
            db = QFontDatabase()
            fams = []
            try:
                fams = db.families()
            except Exception:
                fams = []
            # Prefer an editable, monospaced UI font so that code/keys align nicely.
            # Fall back through common monospace families across platforms.
            preferred_ui = [
                'Noto Sans Mono',
                'DejaVu Sans Mono',
                'Consolas',
                'Courier New',
                'WenQuanYi Zen Hei Mono',
                'Microsoft YaHei Mono',
                'DejaVu Sans',
                'Arial',
                'Segoe UI',
            ]
            chosen = None
            for p in preferred_ui:
                try:
                    if p in fams:
                        chosen = p
                        break
                except Exception:
                    continue
            if chosen:
                ui_font = QtGui.QFont(chosen, 11)
                # Encourage monospace rendering where possible
                try:
                    ui_font.setStyleHint(QtGui.QFont.Monospace)
                    ui_font.setFixedPitch(True)
                except Exception:
                    pass
                try:
                    app.setFont(ui_font)
                except Exception:
                    try:
                        QtWidgets.QApplication.instance().setFont(ui_font)
                    except Exception:
                        pass
        except Exception:
            pass
        owns_app = True

    # 全局关闭 UI 动画（如样式支持），减少切换/菜单等过渡开销
    _disable_ui_animations()

    window = MainWindow()
    # 设置应用与窗口图标（如存在）
    try:
        icon_path = os.path.join(os.getcwd(), "zfeiq_icon_128x128.ico")
        if os.path.isfile(icon_path):
            ico = QtGui.QIcon(icon_path)
            try:
                window.setWindowIcon(ico)
            except Exception:
                pass
    except Exception:
        pass
    backend = GuiBackend()
    window.bind_backend(backend)
    window.show()
    if owns_app:
        app.exec_()
