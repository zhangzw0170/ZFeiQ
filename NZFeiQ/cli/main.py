# NZFeiQ/cli/main.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import sys
import os

# 将项目根目录 (NZFeiQ) 加入路径，确保 core 包可被发现
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from cli.shell import ZFeiQShell

def main():
    parser = argparse.ArgumentParser(description="ZFeiQ Refactored CLI")
    parser.add_argument("--port", type=int, default=2425, help="UDP port (default: 2425)")
    parser.add_argument("--bind", type=str, default=None, help="Bind IP address")
    args = parser.parse_args()

    shell = ZFeiQShell(port=args.port, bind_ip=args.bind)
    shell.run()

if __name__ == "__main__":
    main()