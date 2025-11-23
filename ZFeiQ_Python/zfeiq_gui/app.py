from PyQt5 import QtWidgets
from importlib import import_module


def launch_gui(core_bridge=None, use_full: bool = True):
    app = QtWidgets.QApplication([])
    # Prefer the full main window if available
    MainWin = None
    if use_full:
        try:
            m = import_module('.main_window_full', package=__package__)
            MainWin = getattr(m, 'MainWindow', None)
        except Exception:
            MainWin = None
    if MainWin is None:
        # fall back to light-weight main_window implementation
        m = import_module('.main_window', package=__package__)
        MainWin = getattr(m, 'MainWindow')
    # Instantiate the main window. Prefer passing core_bridge where supported.
    win = None
    # First try keyword instantiation (some windows accept core_bridge)
    try:
        win = MainWin(core_bridge=core_bridge)
    except TypeError:
        # constructor does not accept the kwarg; try no-arg construction
        try:
            win = MainWin()
        except Exception as e:
            # Construction failed; raise to surface the original error instead of
            # attempting to call methods on a class object (which causes confusing TypeError).
            raise

    # If we have an instance and a core_bridge adaptor, attempt to bind it.
    try:
        if core_bridge is not None and hasattr(win, 'bind_backend'):
            try:
                win.bind_backend(core_bridge)
            except Exception:
                # best-effort: ignore binding failures here and let the UI run
                pass
    except Exception:
        pass

    # Finally show the window and run the app loop
    win.show()
    app.exec_()
