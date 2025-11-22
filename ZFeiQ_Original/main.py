import os
import sys


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
    if "--cli" in sys.argv: # CLI mode
        port, bind_ip = parse_port_and_bind(sys.argv[1:])
        from zfeiq_cli.cli import ZFeiQCli
        app = ZFeiQCli(port=port if port else 2425, bind_ip=bind_ip if bind_ip else None)
        app.start()
        app.loop()
    else: # GUI mode
        try:
            from zfeiq_gui import launch_gui
        except ImportError as exc:
            print("[ERROR] 无法加载 GUI 组件，确保已安装 PyQt5 5.15.0 以及 zfeiq_gui 模块。")
            print(f"详细: {exc}")
            sys.exit(1)
        launch_gui()


if __name__ == "__main__":
    main()
