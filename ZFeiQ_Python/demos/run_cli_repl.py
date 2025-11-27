import os
import sys

# Ensure top-level package is importable when running from demos/
root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if root not in sys.path:
    sys.path.insert(0, root)
# also add repository root (one level above ZFeiQ_Python) so zfeiq_gui can be imported
repo_root = os.path.abspath(os.path.join(root, '..'))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from zfeiq_cli.adapter import CLIAdapter


def main():
    a = CLIAdapter(username='demo_cli')
    print("Starting ZFeiQ CLI demo. Type 'help' for commands. Ctrl-D to exit.")
    try:
        a.repl()
    except KeyboardInterrupt:
        print("\nInterrupted, exiting.")


if __name__ == '__main__':
    main()
