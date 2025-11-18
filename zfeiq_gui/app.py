import os
import sys
from PyQt5 import QtWidgets, QtCore

from .main_window import MainWindow


def _ensure_qt_plugin_paths() -> None:
    """Ensure Qt can locate its platform plugins (e.g., platforms/windows or xcb).

    This helps avoid common errors like:
    - "Could not load the Qt platform plugin ..."

    Uses PyQt5's QLibraryInfo to set environment variables for the current process.
    """
    try:
        plugins_path = QtCore.QLibraryInfo.location(QtCore.QLibraryInfo.PluginsPath)
        if plugins_path and os.path.isdir(plugins_path):
            os.environ.setdefault("QT_PLUGIN_PATH", plugins_path)
            plat_dir = os.path.join(plugins_path, "platforms")
            if os.path.isdir(plat_dir):
                os.environ.setdefault("QT_QPA_PLATFORM_PLUGIN_PATH", plat_dir)
        # On Windows wheels, Qt bin may be required on PATH for some systems
        qt_bin = os.path.join(os.path.dirname(plugins_path), "bin") if plugins_path else None
        if qt_bin and os.path.isdir(qt_bin):
            if qt_bin not in os.environ.get("PATH", ""):
                os.environ["PATH"] = qt_bin + os.pathsep + os.environ.get("PATH", "")
        # Optional debug
        if os.environ.get("ZFEIQ_QT_DEBUG"):
            print("[QT] QT_VERSION:", QtCore.QT_VERSION_STR)
            print("[QT] PluginsPath:", plugins_path)
            print("[QT] Platform plugin path:", os.environ.get("QT_QPA_PLATFORM_PLUGIN_PATH"))
    except Exception as e:
        if os.environ.get("ZFEIQ_QT_DEBUG"):
            print(f"[QT] ensure plugin paths failed: {e}")


def launch_gui() -> None:
    _ensure_qt_plugin_paths()
    app = QtWidgets.QApplication.instance()
    owns_app = False
    if app is None:
        # Prefer sys.argv so Qt parses standard flags even in GUI mode
        app = QtWidgets.QApplication(sys.argv)
        owns_app = True
    window = MainWindow()
    window.show()
    if owns_app:
        app.exec_()
