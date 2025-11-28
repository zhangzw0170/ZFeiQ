import os
import sys
import faulthandler
import signal
import warnings
import traceback
import platform


def parse_port_and_bind(argv):
    # allow --port 2426 or --port=2426; fallback to env ZFEIQ_PORT; default 2425
    port = None
    bind_ip = None
    for i, a in enumerate(argv):
        if a == "--port" and i + 1 < len(argv):
            try:
                port = int(argv[i + 1])
            except ValueError:
                pass
        elif a.startswith("--port="):
            try:
                port = int(a.split("=", 1)[1])
            except ValueError:
                pass
        elif a == "--bind" and i + 1 < len(argv):
            bind_ip = argv[i + 1]
        elif a.startswith("--bind="):
            bind_ip = a.split("=", 1)[1]
    if port is None:
        envp = os.environ.get("ZFEIQ_PORT")
        if envp:
            try:
                port = int(envp)
            except ValueError:
                port = None
    return port, bind_ip

def main():
    # Ensure project root is on sys.path so top-level packages (e.g. zfeiq_common)
    # are importable when running this script from its directory.
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    if "--cli" in sys.argv: # CLI mode
        port, bind_ip = parse_port_and_bind(sys.argv[1:])
        from zfeiq_cli.cli import ZFeiQCli
        app = ZFeiQCli(port=port if port else 2425, bind_ip=bind_ip if bind_ip else None)
        app.start()
        app.loop()
    else: # GUI mode
        # enable faulthandler to get Python-level traceback on native crashes
        try:
            faulthandler.enable()
            # register signals to dump trace on crash-like signals
            try:
                faulthandler.register(signal.SIGSEGV, all_threads=True)
                faulthandler.register(signal.SIGABRT, all_threads=True)
            except Exception:
                # some platforms may not allow registering signals
                pass
        except Exception:
            pass

        # show helpful runtime / dependency hints to stderr (non-fatal)
        try:
            sys.stderr.write(f"Python: {platform.python_version()} ({platform.platform()})\n")
            try:
                import importlib
                def _print_mod(name):
                    try:
                        m = importlib.import_module(name)
                        ver = getattr(m, '__version__', None) or getattr(m, 'version', None)
                        sys.stderr.write(f"  {name}: present, version={ver}\n")
                    except Exception as _:
                        sys.stderr.write(f"  {name}: not installed or import failed\n")
                # avoid importing heavy packages that may register Qt plugins (e.g. OpenCV) before the GUI
                for modname in ('paddle', 'paddleocr', 'PIL', 'rknnlite', 'cryptography', 'requests', 'urllib3', 'chardet'):
                    _print_mod(modname)
            except Exception:
                pass
        except Exception:
            pass

        try:
            from zfeiq_gui import launch_gui
        except ImportError as exc:
            print("[ERROR] 无法加载 GUI 组件，确保已安装 PyQt5 5.15.0 以及 zfeiq_gui 模块。")
            print(f"详细: {exc}")
            sys.exit(1)
        launch_gui()


if __name__ == "__main__":
    main()
