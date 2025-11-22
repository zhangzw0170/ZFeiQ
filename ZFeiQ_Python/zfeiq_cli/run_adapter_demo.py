from adapter import CLIAdapter


def run_demo():
    a = CLIAdapter(username="demo_runner")
    # perform scripted actions
    a.cmd_discover()
    a.cmd_send("all", "automated hello from demo")
    # show history
    hist = a.core.get_history(5)
    print("History:")
    for h in hist:
        print(h)
    # stop services
    a.cmd_logout()


if __name__ == "__main__":
    run_demo()
