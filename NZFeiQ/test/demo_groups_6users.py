#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZFeiQ Requirements Auto-Verification Script (6-User Group Demo)
===============================================================
架构：启动 6 个节点 (Alice, Bob, Charlie, Dave, Eve, Frank)
分组：
  - Group 1 (Avengers): Alice, Bob, Charlie
  - Group 2 (JusticeLeague): Dave, Eve, Frank
功能：验证分组隔离性，群组消息互不干扰，并实时展示执行命令
"""

import subprocess
import time
import sys
import os
import threading

# 配置
PYTHON_EXE = sys.executable
CLI_SCRIPT = os.path.join("cli", "main.py")
PORT = "2425"

# 定义用户配置：利用 Loopback 别名 IP 实现单机多节点
USERS = [
    {"name": "Alice",   "ip": "127.0.0.1"},
    {"name": "Bob",     "ip": "127.0.0.2"},
    {"name": "Charlie", "ip": "127.0.0.3"},
    {"name": "Dave",    "ip": "127.0.0.4"},
    {"name": "Eve",     "ip": "127.0.0.5"},
    {"name": "Frank",   "ip": "127.0.0.6"},
]

class NodeProcess:
    def __init__(self, name, bind_ip):
        self.name = name
        self.ip = bind_ip
        self.port = PORT
        self.process = None
        self.output_log = []
        self._stop_reading = False

    def start(self):
        print(f"[*] 启动 {self.name} ({self.ip}:{self.port})...")
        # 确保 PYTHONUNBUFFERED=1 以便实时获取日志
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        
        cmd = [PYTHON_EXE, CLI_SCRIPT, "--bind", self.ip, "--port", self.port]
        self.process = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=0, env=env
        )
        t = threading.Thread(target=self._reader, daemon=True)
        t.start()

    def _reader(self):
        while not self._stop_reading and self.process and self.process.poll() is None:
            if not self.process.stdout: break
            try:
                line = self.process.stdout.readline()
                if line:
                    clean = line.strip()
                    if clean: self.output_log.append(clean)
            except: break

    def send(self, cmd):
        # [新增] 明确展示当前哪个用户正在执行什么命令
        print(f"[{self.name}] >>> {cmd}")
        
        if self.process and self.process.stdin:
            try:
                self.process.stdin.write(cmd + "\n")
                self.process.stdin.flush()
                time.sleep(0.3) # 模拟人类输入间隔，并给系统处理时间
            except: pass

    def expect(self, pattern, timeout=5):
        start = time.time()
        while time.time() - start < timeout:
            # 倒序查找，优先匹配最新的日志
            for line in reversed(self.output_log):
                if pattern in line:
                    return True
            time.sleep(0.2)
        return False

    def stop(self):
        self._stop_reading = True
        if self.process:
            self.process.terminate()

def run_test():
    print("=== ZFeiQ 6-User Group Isolation Test ===\n")
    
    # 清理旧数据，确保环境干净
    if os.path.exists("common/groups.json"): os.remove("common/groups.json")

    # 实例化所有节点
    nodes = {}
    for u in USERS:
        nodes[u['name']] = NodeProcess(u['name'], u['ip'])

    try:
        # 1. 启动
        for name, node in nodes.items():
            node.start()
        time.sleep(2)

        print("\n[Step 1] Login All Users")
        for name, node in nodes.items():
            node.send(f"login {name}")
        time.sleep(1)

        print("\n[Step 2] Network Discovery (Establishing Connections)")
        # 为了演示隔离性，我们让 Group 1 和 Group 2 内部互通
        # 同时也建立一些跨组连接 (如 Alice <-> Dave) 来证明即使连接了也不会收到非本组消息
        
        # Group 1 (Alice, Bob, Charlie) 互相发现
        g1 = ["Alice", "Bob", "Charlie"]
        for i in range(len(g1)):
            for j in range(len(g1)):
                if i != j:
                    nodes[g1[i]].send(f"discover {nodes[g1[j]].ip}")
        
        # Group 2 (Dave, Eve, Frank) 互相发现
        g2 = ["Dave", "Eve", "Frank"]
        for i in range(len(g2)):
            for j in range(len(g2)):
                if i != j:
                    nodes[g2[i]].send(f"discover {nodes[g2[j]].ip}")

        # 跨组连接测试：Alice 连接 Dave
        nodes["Alice"].send(f"discover {nodes['Dave'].ip}")
        time.sleep(2)
        print("  -> P2P Mesh established.")

        print("\n[Step 3] Creating Groups")
        # Alice 创建 Avengers
        nodes["Alice"].send("group create Avengers")
        nodes["Alice"].send("group add Avengers Bob")
        nodes["Alice"].send("group add Avengers Charlie")
        
        # Dave 创建 JusticeLeague
        nodes["Dave"].send("group create JusticeLeague")
        nodes["Dave"].send("group add JusticeLeague Eve")
        nodes["Dave"].send("group add JusticeLeague Frank")
        time.sleep(1)

        print("\n[Step 4] Testing Group 1 (Avengers) Msg Flow")
        msg_1 = "Avengers_Assemble!"
        nodes["Alice"].send(f"group msg Avengers {msg_1}")
        time.sleep(2)

        # 验证 Bob 收到
        if nodes["Bob"].expect(msg_1):
            print(f"  -> PASS: Bob received '{msg_1}'")
        else:
            print(f"  -> FAIL: Bob missed message")

        # 验证 Dave (Group 2, 但物理上连接了 Alice) 没收到
        if nodes["Dave"].expect(msg_1, timeout=1):
            print(f"  -> FAIL: Dave (Group 2) received Group 1 message!")
        else:
            print(f"  -> PASS: Dave (Group 2) correctly ignored Group 1 message.")

        print("\n[Step 5] Testing Group 2 (JusticeLeague) Msg Flow")
        msg_2 = "Justice_League_Unite!"
        nodes["Dave"].send(f"group msg JusticeLeague {msg_2}")
        time.sleep(2)

        if nodes["Eve"].expect(msg_2):
            print(f"  -> PASS: Eve received '{msg_2}'")
        else:
            print(f"  -> FAIL: Eve missed message")
            
        if nodes["Alice"].expect(msg_2, timeout=1):
            print(f"  -> FAIL: Alice (Group 1) received Group 2 message!")
        else:
            print(f"  -> PASS: Alice (Group 1) correctly ignored Group 2 message.")

        print("\n[Step 6] Concurrent Traffic Test (Group 1 & 2 sending together)")
        nodes["Alice"].send("group msg Avengers G1_Report")
        nodes["Dave"].send("group msg JusticeLeague G2_Report")
        time.sleep(2)
        
        # 验证 Charlie (G1) 只收到 G1 的
        if nodes["Charlie"].expect("G1_Report") and not nodes["Charlie"].expect("G2_Report", timeout=0.5):
            print("  -> PASS: Charlie received G1 msg only.")
        else:
            print("  -> FAIL: Charlie message mix-up.")

        # 验证 Frank (G2) 只收到 G2 的
        if nodes["Frank"].expect("G2_Report") and not nodes["Frank"].expect("G1_Report", timeout=0.5):
            print("  -> PASS: Frank received G2 msg only.")
        else:
            print("  -> FAIL: Frank message mix-up.")

        print("\n[Step 7] Exit")
        for name, node in nodes.items():
            node.send("exit")

    except Exception as e:
        print(f"ERROR: {e}")
    finally:
        for name, node in nodes.items():
            node.stop()
        print("\n=== Test Finished ===")

if __name__ == "__main__":
    if not os.path.exists("cli/main.py"):
        print("Please run from project root (NZFeiQ/).")
    else:
        run_test()