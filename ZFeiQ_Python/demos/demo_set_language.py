import os
import sys
import time
root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if root not in sys.path:
    sys.path.insert(0, root)
repo_root = os.path.abspath(os.path.join(root, '..'))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

import importlib.util
adapter_path = os.path.join(root, 'zfeiq_cli', 'adapter.py')
spec = importlib.util.spec_from_file_location('zfeiq_cli.adapter', adapter_path)
adapter_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter_mod)
CLIAdapter = adapter_mod.CLIAdapter


def main():
    a = CLIAdapter(username='lang_demo')
    print('Help (before):')
    a.cmd_help()
    print('\nSetting language to enUS...')
    a.cmd_set_language('enUS')
    time.sleep(0.2)
    print('\nHelp (after):')
    a.cmd_help()
    try:
        a.cmd_logout()
    except Exception:
        pass

if __name__ == '__main__':
    main()
