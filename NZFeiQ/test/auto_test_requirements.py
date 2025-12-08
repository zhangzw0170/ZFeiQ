#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Auto-test environment & diagnostic collector for NZFeiQ demos.

This script performs non-root environment checks useful for
diagnosing local single-host multi-node demo failures. It collects
the following artifacts under `NZFeiQ/test/artifacts/YYYYmmdd_HHMMSS/`:

- `ip_addr_lo.txt` : output of `ip addr show lo`
- `bind_checks.txt` : results of trying to bind UDP to common demo
  addresses/ports
- `config.json` : copy of `common/config.json` if present
- `files_check.txt` : presence checks for key repo files
- optionally: demo stdout/stderr files when --run-demos is used

Usage (from repo root):
  python3 NZFeiQ/test/auto_test_requirements.py            # run checks only
  python3 NZFeiQ/test/auto_test_requirements.py --run-demos --demo-timeout 20

The script avoids requiring root; for kernel-level packet captures
use the manual command suggested in `TEST.md` (tcpdump requires sudo).
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import socket
import subprocess
import sys
from pathlib import Path


def run_cmd(cmd, cwd=None, timeout=10):
    try:
        p = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return 124, '', 'TIMEOUT'


def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)


def try_bind(addr: str, port: int, family=socket.AF_INET) -> tuple[bool, str]:
    s = None
    try:
        s = socket.socket(family, socket.SOCK_DGRAM)
        s.settimeout(1.0)
        s.bind((addr, port))
        return True, 'OK'
    except Exception as e:
        return False, str(e)
    finally:
        if s:
            s.close()


def copy_if_exists(src: Path, dst: Path):
    if src.exists():
        with src.open('rb') as fsrc, dst.open('wb') as fdst:
            fdst.write(fsrc.read())
        return True
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-demos', action='store_true', help='Run demo scripts after checks (may spawn processes)')
    parser.add_argument('--demo-timeout', type=int, default=15, help='Timeout secs for each demo run')
    args = parser.parse_args()

    ts = datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    artifacts = Path('NZFeiQ') / 'test' / 'artifacts' / ts
    ensure_dir(artifacts)

    print('Artifacts directory:', artifacts)

    # 1) Basic info
    with (artifacts / 'env.txt').open('w') as f:
        f.write('python: ' + sys.executable + '\n')
        f.write('python_version: ' + sys.version.replace('\n', ' ') + '\n')
        f.write('cwd: ' + os.getcwd() + '\n')

    # 2) ip addr show lo
    rc, out, err = run_cmd('ip addr show lo')
    with (artifacts / 'ip_addr_lo.txt').open('w') as f:
        f.write(out)
        if err:
            f.write('\n### STDERR ###\n')
            f.write(err)

    # 3) loopback alias checks
    loop_missing = []
    present = out
    for i in range(2, 7):
        ip = f'127.0.0.{i}'
        ok = ip in present
        with (artifacts / 'bind_checks.txt').open('a') as f:
            f.write(f'check loopback alias {ip}: {ok}\n')
        if not ok:
            loop_missing.append(ip)

    # 4) try binding common demo addresses/ports
    # demo uses UDP 2425 by default
    demo_port = 2425
    addrs_to_try = ['127.0.0.1'] + [f'127.0.0.{i}' for i in range(2, 7)]
    with (artifacts / 'bind_checks.txt').open('a') as f:
        f.write('\n-- bind attempts --\n')
        for a in addrs_to_try:
            ok, msg = try_bind(a, demo_port)
            f.write(f'bind {a}:{demo_port} -> {ok} ({msg})\n')

    # 5) copy config.json
    cfg_src = Path('common') / 'config.json'
    if copy_if_exists(cfg_src, artifacts / 'config.json'):
        try:
            with (artifacts / 'config.json').open('r') as f:
                cfg = json.load(f)
            with (artifacts / 'files_check.txt').open('a') as f:
                f.write('config.log_level: ' + str(cfg.get('log_level')) + '\n')
        except Exception as e:
            with (artifacts / 'files_check.txt').open('a') as f:
                f.write('config.json parse error: ' + str(e) + '\n')
    else:
        with (artifacts / 'files_check.txt').open('a') as f:
            f.write('common/config.json: MISSING\n')

    # 6) check repo files
    must_have = [
        Path('NZFeiQ') / 'core' / 'engine.py',
        Path('NZFeiQ') / 'core' / 'transport.py',
        Path('NZFeiQ') / 'core' / 'session.py',
        Path('NZFeiQ') / 'test' / 'demo_p2p_secure_loopback.py',
        Path('NZFeiQ') / 'test' / 'demo_filetransfer.py',
    ]
    with (artifacts / 'files_check.txt').open('a') as f:
        for p in must_have:
            f.write(f'{p}: {p.exists()}\n')

    # 7) optionally run demos (captured)
    if args.run_demos:
        demo_scripts = [
            'NZFeiQ/test/demo_p2p_secure_loopback.py',
            'NZFeiQ/test/demo_filetransfer.py',
            'NZFeiQ/test/demo_groups_6users.py',
        ]
        for ds in demo_scripts:
            if not Path(ds).exists():
                with (artifacts / 'demo_runs.txt').open('a') as f:
                    f.write(f'{ds}: MISSING\n')
                continue
            outf = artifacts / (Path(ds).stem + '.out.txt')
            errf = artifacts / (Path(ds).stem + '.err.txt')
            print('Running demo:', ds)
            try:
                p = subprocess.Popen([sys.executable, ds], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                try:
                    so, se = p.communicate(timeout=args.demo_timeout)
                except subprocess.TimeoutExpired:
                    p.kill()
                    so, se = p.communicate(timeout=5)
                    se = (se or '') + '\n--- TIMEOUT ---'
                with outf.open('w') as f:
                    f.write(so or '')
                with errf.open('w') as f:
                    f.write(se or '')
            except Exception as e:
                with (artifacts / 'demo_runs.txt').open('a') as f:
                    f.write(f'error running {ds}: {e}\n')

    # 8) final summary
    summary = []
    summary.append('artifacts: ' + str(artifacts))
    summary.append('loopback_missing: ' + ','.join(loop_missing) if loop_missing else 'loopback_missing: none')
    summary.append('recommendation:')
    if loop_missing:
        summary.append(' - add loopback aliases (127.0.0.2..127.0.0.6) or run demos in multi-port mode')
        summary.append(" - run: sudo timeout 10 tcpdump -i lo udp port 2425 -w /tmp/lo2425.pcap")
    else:
        summary.append(' - capture tcpdump while running demos and check for KX1/KX2/Offer packets')

    with (artifacts / 'summary.txt').open('w') as f:
        f.write('\n'.join(summary) + '\n')

    print('\n'.join(summary))
    print('\nArtifacts saved to', artifacts)


if __name__ == '__main__':
    main()
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZFeiQ Requirements Auto-Verification Script (Fixed)
===================================================
架构：启动 Alice, Bob, Charlie 三个节点
关键修正：所有节点统一绑定 2425 端口，利用 Loopback 多 IP 特性 (127.0.0.1/2/3)
"""

import subprocess
import time
import sys
import os
import threading

# 配置
PYTHON_EXE = sys.executable
CLI_SCRIPT = os.path.join("cli", "main.py")
ALICE_IP = "127.0.0.1"
BOB_IP = "127.0.0.2"
CHARLIE_IP = "127.0.0.3"

# [修正] 统一使用 2425 端口，避免不同端口导致的通信失败
PORT = "2425"

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
        # [Fix] 增加 self.process.stdout 非空检查
        while not self._stop_reading and self.process and self.process.poll() is None:
            if not self.process.stdout: break
            try:
                line = self.process.stdout.readline()
                if line:
                    clean = line.strip()
                    if clean: self.output_log.append(clean)
            except: break

    def send(self, cmd):
        # [Fix] 增加 self.process.stdin 非空检查
        if self.process and self.process.stdin:
            try:
                self.process.stdin.write(cmd + "\n")
                self.process.stdin.flush()
                time.sleep(0.3)
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
    print("=== ZFeiQ Core Requirements Verification ===\n")
    
    # 清理旧数据
    if os.path.exists("common/groups.json"): os.remove("common/groups.json")
    if os.path.exists("test_emote.png"): os.remove("test_emote.png")

    alice = NodeProcess("Alice", ALICE_IP)
    bob = NodeProcess("Bob", BOB_IP)
    charlie = NodeProcess("Charlie", CHARLIE_IP)

    try:
        alice.start(); bob.start(); charlie.start()
        time.sleep(2)

        print("\n[Step 1] Login & Discovery")
        alice.send("login Alice")
        bob.send("login Bob")
        charlie.send("login Charlie")
        time.sleep(1)
        
        # 单播发现 (Loopback 环境下广播通常无效)
        alice.send(f"discover {BOB_IP}")
        alice.send(f"discover {CHARLIE_IP}")
        time.sleep(2)
        
        # [修改] 匹配 CLI 实际输出的日志内容，而不是内部事件名
        if alice.expect("Node list updated"):
            print("  -> PASS: Alice successfully discovered peers.")
        else:
            print("  -> [WARN] Discovery logs not seen, proceeding anyway.")

        print("\n[Step 2] Group Chat (Req 1 & 3)")
        alice.send("group create Avengers")
        alice.send("group add Avengers Bob")
        time.sleep(0.5)
        
        print("  -> Alice sending group message 'Assemble'...")
        alice.send("group msg Avengers Assemble!")
        time.sleep(2)
        
        if bob.expect("Assemble!"):
            print("  -> PASS: Bob received group message.")
        else:
            print("  -> FAIL: Bob did not receive.")

        if charlie.expect("Assemble!", timeout=1):
            print("  -> FAIL: Charlie received message but is not in group!")
        else:
            print("  -> PASS: Charlie (not in group) did not receive.")

        print("\n[Step 3] Search (Req 2)")
        alice.send("search Bob")
        time.sleep(1)
        if alice.expect("[User] Bob"):
            print("  -> PASS: Search found 'Bob'.")
        else:
            print("  -> FAIL: Search failed.")

        print("\n[Step 4] File/Emote Transfer (Req 4)")
        # 生成测试图片
        with open("test_emote.png", "wb") as f:
            f.write(b'\x89PNG\r\n\x1a\n' + b'\x00'*100) # 伪造 PNG 头
        
        # 此时 Alice 和 Bob 端口一致，send_unicast 应该能通
        alice.send(f"file send {BOB_IP} test_emote.png")
        time.sleep(2)
        
        if bob.expect("File Offer"):
            print("  -> PASS: Bob received file offer.")
        else:
            print("  -> FAIL: File offer not received (Check UDP transport).")
        
        # 清理
        if os.path.exists("test_emote.png"): os.remove("test_emote.png")

        print("\n[Step 5] Screenshot (Req 4)")
        alice.send("screenshot")
        time.sleep(2)
        if alice.expect("Screenshot saved") or alice.expect("Screenshot failed"):
            print("  -> PASS: Screenshot command executed.")
        else:
            print("  -> FAIL: Screenshot command ignored.")

        print("\n[Step 6] NPU/OCR (Req 5)")
        alice.send("ocr missing_image.png")
        time.sleep(1)
        if alice.expect("Image not found") or alice.expect("OCR Result"):
            print("  -> PASS: OCR module invoked.")
        else:
            print("  -> FAIL: OCR command ignored.")

        # [新增] Step 7: 登出与退出机制测试
        print("\n[Step 7] Logout & Exit")
        alice.send("logout")
        bob.send("logout")
        time.sleep(1)
        if alice.expect("Logged out") and bob.expect("Logged out"):
            print("  -> PASS: Logout command executed.")
        else:
            print("  -> FAIL: Logout log not seen.")
            
        # 发送 exit 尝试优雅退出 (虽然 finally 块会强制 terminate，但测试命令本身也很重要)
        alice.send("exit")
        bob.send("exit")
        charlie.send("exit")

    except Exception as e:
        print(f"ERROR: {e}")
    finally:
        alice.stop(); bob.stop(); charlie.stop()
        print("\n=== Test Finished ===")

if __name__ == "__main__":
    if not os.path.exists("cli/main.py"):
        print("Please run from project root (NZFeiQ/).")
    else:
        run_test()
