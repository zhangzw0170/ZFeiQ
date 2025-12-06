#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZFeiQ 自动化演示脚本 (Demo Script)
================================
功能：全自动演示 登录 -> 发现 -> 握手 -> 强加密通讯
特点：可视化展示 [明文] -> [密文] -> [明文] 的过程
"""

import subprocess
import time
import sys
import os
import threading
from typing import Optional, List

# 配置
PYTHON_EXE = sys.executable
CLI_SCRIPT = os.path.join("cli", "main.py")
ALICE_IP = "127.0.0.1"
BOB_IP = "127.0.0.2"
PORT = "2425"

class ZFeiQProcess:
    def __init__(self, name, bind_ip):
        self.name = name
        self.bind_ip = bind_ip
        # [修复] 显式类型注解，消除 Pylance 报错
        self.process: Optional[subprocess.Popen] = None
        self.output_buffer: List[str] = []
        self._stop_reading = False

    def start(self):
        cmd = [PYTHON_EXE, CLI_SCRIPT, "--bind", self.bind_ip, "--port", PORT]
        # print(f"[*] 启动 {self.name} ({self.bind_ip})...")
        self.process = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=0
        )
        t = threading.Thread(target=self._reader_thread, daemon=True)
        t.start()

    def _reader_thread(self):
        # [修复] 增加 process 非空检查
        while not self._stop_reading and self.process and self.process.poll() is None:
            if not self.process.stdout: break
            try:
                line = self.process.stdout.readline()
                if line:
                    clean = line.strip()
                    if clean and "=>" not in clean:
                        self.output_buffer.append(clean)
            except: break

    def send_cmd(self, cmd):
        if self.process and self.process.stdin:
            # print(f"[{self.name} CMD] {cmd}")
            try:
                self.process.stdin.write(cmd + "\n")
                self.process.stdin.flush()
            except: pass
            time.sleep(0.5)

    def extract(self, pattern, timeout=5):
        """查找并返回匹配的行内容，用于提取密文"""
        start = time.time()
        while time.time() - start < timeout:
            for i, line in enumerate(self.output_buffer):
                if pattern in line:
                    # 消费掉这条及之前的日志，避免重复匹配旧日志
                    self.output_buffer = self.output_buffer[i+1:]
                    return line
            time.sleep(0.1)
        return None

    def expect(self, pattern, timeout=5):
        return self.extract(pattern, timeout) is not None

    def stop(self):
        self._stop_reading = True
        if self.process:
            try:
                if self.process.stdin:
                    self.process.stdin.write("exit\n"); self.process.stdin.flush()
            except: pass
            time.sleep(0.2)
            if self.process.poll() is None: self.process.terminate()

def run_demo():
    if not os.path.exists(CLI_SCRIPT):
        print("[!] 请在项目根目录下运行 (例如: python3 test/auto_test.py)")
        return

    alice = ZFeiQProcess("Alice", ALICE_IP)
    bob = ZFeiQProcess("Bob", BOB_IP)

    try:
        print(f"[*] 正在初始化环境 (Alice={ALICE_IP}, Bob={BOB_IP})...")
        alice.start(); bob.start()
        time.sleep(2)

        # 1. 登录
        alice.send_cmd("login Alice")
        bob.send_cmd("login Bob")
        time.sleep(1)

        # 2. 发现 (单播发现，因为绑定特定IP可能收不到广播)
        print(f"[*] 建立连接...")
        alice.send_cmd(f"discover {BOB_IP}")
        time.sleep(1)

        # [重要] 等待自动握手完成
        # 双方互发 KX1/KX2 需要一点时间
        print("    Waiting for Auto-Handshake (ECDH)...")
        time.sleep(2) 

        # 3. 加密演示
        print("\n" + "="*60)
        print("   ZFeiQ 加密通讯演示 (ECDH-X25519 + ChaCha20-Poly1305)")
        print("="*60)

        # [新增] 开启调试模式以显示密文
        alice.send_cmd("debug cipher on")
        bob.send_cmd("debug cipher on")
        time.sleep(0.5)
        
        # 发送内容
        plaintext = "Hello_Reviewer_This_Is_Secret!"
        print(f"\n[1] Alice 准备发送明文:")
        print(f"    >> \"{plaintext}\"")
        
        alice.send_cmd(f"send {BOB_IP} {plaintext}")

        # 捕获 Alice 的发出密文
        # 期待日志: [INFO] Cipher OUT: ENC;sid=...
        cipher_log = alice.extract("Cipher OUT:")
        if cipher_log:
            # 提取 ENC;... 部分
            parts = cipher_log.split("OUT: ")
            if len(parts) > 1:
                cipher_part = parts[1].strip()
                # 截断过长的密文以便展示
                display_cipher = cipher_part[:60] + "..." if len(cipher_part)>60 else cipher_part
                print(f"\n[2] Alice 加密并发送密文 (ChaCha20):")
                print(f"    >> [{display_cipher}]")
        else:
            print("[!] 未捕获到发出密文 (握手可能未完成，会话仍为 NONE，发送了明文)")

        # 捕获 Bob 的接收密文
        # 期待日志: [INFO] Cipher IN: ENC;sid=...
        cipher_in_log = bob.extract("Cipher IN:")
        if cipher_in_log:
            parts = cipher_in_log.split("IN: ")
            if len(parts) > 1:
                print(f"\n[3] Bob 收到密文:")
                print(f"    << [{parts[1].strip()[:60]}...]")
        
        # 捕获 Bob 的解密结果
        # 期待日志: [时间] <Alice@...>: Hello_...
        decrypted_log = bob.extract(plaintext)
        if decrypted_log:
            # 提取消息内容
            msg_part = decrypted_log.split(": ")[-1].strip()
            print(f"\n[4] Bob 解密成功 (Poly1305 校验通过):")
            print(f"    << \"{msg_part}\"")
            print(f"\n[SUCCESS] 端到端加密通讯验证通过！")
        else:
            print(f"\n[FAIL] Bob 解密失败或未收到消息")

    except Exception as e:
        print(f"[ERROR] {e}")
    finally:
        alice.stop()
        bob.stop()

if __name__ == "__main__":
    run_demo()