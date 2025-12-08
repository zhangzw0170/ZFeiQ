#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZFeiQ 文件传输专项测试脚本 (WSL 优化版)
======================================
解决端口冲突策略：
1. 启动前强制 kill 所有旧的 cli/main.py 进程
2. 使用 loopback 别名 (127.0.0.1 vs 127.0.0.2) 隔离
3. 增加文件传输的完整性校验 (MD5)
"""

import subprocess
import time
import sys
import os
import threading
import re
import hashlib
import platform
import shutil

# --- 配置区 ---
ROOT_DIR = os.path.abspath(os.path.dirname(__file__) + "/..")
PYTHON_EXE = sys.executable
CLI_SCRIPT = os.path.abspath(os.path.join(ROOT_DIR, "cli", "main.py"))
ALICE_IP = "127.0.0.1"
BOB_IP = "127.0.0.2"
PORT = "2425"  # 保持默认端口，依靠 IP 隔离
TEST_FILE = os.path.join(ROOT_DIR, "test_data.bin")
DOWNLOAD_DIR = os.path.abspath(os.path.join(ROOT_DIR, "common", "downloads"))

def calculate_md5(filepath):
    """计算文件 MD5"""
    if not os.path.exists(filepath):
        return None
    hash_md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def kill_zombies():
    """强力清理残留进程，防止 [Errno 98] Address already in use"""
    print("[*] 正在清理环境 (kill old processes)...")
    if platform.system() == "Windows":
        os.system("taskkill /f /im python.exe /fi \"WINDOWTITLE eq ZFeiQ*\" >nul 2>&1")
    else:
        # Linux/WSL: 匹配命令行包含 cli/main.py 的进程
        os.system("pkill -f 'cli/main.py' >/dev/null 2>&1")
    time.sleep(1.5)  # 等待 OS 回收端口

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
        # 强制无缓冲输出，确保能实时捕获日志
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
                    if clean: 
                        self.output_log.append(clean)
                        # 可选：打印日志以便调试
                        # print(f"[{self.name}] {clean}")
            except: break

    def send(self, cmd):
        if self.process and self.process.stdin:
            try:
                print(f"[{self.name}] >>> {cmd}")
                self.process.stdin.write(cmd + "\n")
                self.process.stdin.flush()
                time.sleep(0.5) # 给一点处理时间
            except: pass

    def expect(self, pattern, timeout=10):
        """等待日志中出现特定字符串"""
        start = time.time()
        while time.time() - start < timeout:
            for line in reversed(self.output_log):
                if pattern in line:
                    return True
            time.sleep(0.2)
        return False

    def extract_pattern(self, regex, timeout=10):
        """正则提取日志中的关键信息 (如 Offer ID)"""
        start = time.time()
        pat = re.compile(regex)
        while time.time() - start < timeout:
            for line in reversed(self.output_log):
                m = pat.search(line)
                if m:
                    return m.group(1)
            time.sleep(0.2)
        return None

    def stop(self):
        self._stop_reading = True
        if self.process:
            self.process.terminate()

def run_test():
    # 1. 清理环境
    kill_zombies()
    
    # 2. 准备测试数据
    if os.path.exists(TEST_FILE): os.remove(TEST_FILE)
    if os.path.exists(DOWNLOAD_DIR): shutil.rmtree(DOWNLOAD_DIR)
    
    print(f"[*] 生成测试文件: {TEST_FILE} (10KB)")
    with open(TEST_FILE, "wb") as f:
        f.write(os.urandom(1024 * 10))
    src_md5 = calculate_md5(TEST_FILE)
    print(f"    MD5: {src_md5}")

    alice = NodeProcess("Alice", ALICE_IP)
    bob = NodeProcess("Bob", BOB_IP)

    try:
        # 3. 启动节点
        alice.start()
        bob.start()
        time.sleep(2)

        print("\n[Step 1] 登录")
        alice.send("login Alice")
        bob.send("login Bob")
        time.sleep(1)
        
        # 使用单播发现，确保连通性
        alice.send(f"discover {BOB_IP}")
        time.sleep(2)

        if alice.expect("Node list updated") or alice.expect("Bob"):
            print("  -> 发现成功 (UDP 连通)")
        else:
            print("  -> [警告] 未检测到发现日志，尝试继续...")

        print("\n[Step 2] 发送文件请求")
        # Alice 发送文件给 Bob
        alice.send(f"file send {BOB_IP} {TEST_FILE}")
        
        # 4. Bob 等待接收 Offer (UDP)
        print("  -> 等待 Bob 收到 Offer...")
        # 匹配 CLI 输出: "ID: ipmsg-xxxx-xxxx" 或 "offer=ipmsg-xxxx"
        # 这里的正则兼容多种 CLI 输出格式
        # 兼容 CLI 两种输出："ID: <pkt:aid>" 或 "offer=<pkt:aid>"
        offer_id = bob.extract_pattern(r"(?:ID:|offer=)\s*([0-9]+:[0-9]+)", timeout=10)
        
        if not offer_id:
            print("  -> [FAIL] Bob 未收到文件 Offer (可能是端口绑定失败或 UDP 丢包)")
            # 检查 Alice 是否有报错
            if alice.expect("Send file failed") or alice.expect("Address already in use"):
                print("  -> 原因: Alice 端口被占用，请确保没有其他 ZFeiQ 进程运行。")
            return

        print(f"  -> 收到 Offer ID: {offer_id}")

        print(f"\n[Step 3] 接收文件 (TCP)")
        # Bob 接受文件
        bob.send(f"file accept {offer_id}")
        
        # 等待传输完成
        if bob.expect("File saved", timeout=20) or bob.expect("saved to"):
            print("  -> [SUCCESS] 传输日志已捕获")
        else:
            print("  -> [FAIL] 传输超时或失败")
            return

        print("\n[Step 4] 校验文件")
        downloaded_path = os.path.join(DOWNLOAD_DIR, os.path.basename(TEST_FILE))
        if os.path.exists(downloaded_path):
            dst_md5 = calculate_md5(downloaded_path)
            print(f"    源文件 MD5: {src_md5}")
            print(f"    下载件 MD5: {dst_md5}")
            if src_md5 == dst_md5:
                print("  -> [PASS] 文件校验通过！")
            else:
                print("  -> [FAIL] 文件内容不一致！")
        else:
            print(f"  -> [FAIL] 下载目录未找到文件: {downloaded_path}")

    except Exception as e:
        print(f"[ERROR] {e}")
    finally:
        alice.stop()
        bob.stop()
        # 清理
        if os.path.exists(TEST_FILE): os.remove(TEST_FILE)
        print("\n=== 测试结束 ===")

if __name__ == "__main__":
    if not os.path.exists(CLI_SCRIPT):
        print(f"未找到 CLI 脚本: {CLI_SCRIPT}\n请确认路径是否正确")
    else:
        run_test()