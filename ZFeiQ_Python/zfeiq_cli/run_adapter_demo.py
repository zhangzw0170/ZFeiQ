from adapter import CLIAdapter
try:
    from zfeiq_gui.lang import t as _t_global
except Exception:
    _t_global = None


def run_demo():
    a = CLIAdapter(username="demo_runner")
    # perform scripted actions
    a.cmd_discover()
    a.cmd_send("all", "automated hello from demo")
    # show history
    hist = a.core.get_history(5)
    header = _t_global['history_header'] if _t_global is not None else 'History:'
    print(header)
    for h in hist:
        print(h)
    # stop services
    a.cmd_logout()


if __name__ == "__main__":
    run_demo()
