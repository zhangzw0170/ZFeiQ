import subprocess
import shlex
import sys
import time
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = str(ROOT / "main.py")


def _primary_ip() -> str:
    try:
        out = subprocess.check_output(shlex.split("hostname -I"), timeout=3).decode().strip()
        ips = [p for p in out.split() if p and p.count(".") == 3]
        for ip in ips:
            if not ip.startswith("127."):
                return ip
        if ips:
            return ips[0]
    except Exception:
        pass
    return "127.0.0.1"

def start_cli(port: int, bind_ip: str = None):
    if not bind_ip:
        bind_ip = _primary_ip()
    p = subprocess.Popen(
        [sys.executable, MAIN, "--cli", "--port", str(port), "--bind", bind_ip],
        cwd=str(ROOT),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    return p


def send_cmd(proc: subprocess.Popen, cmd: str):
    assert proc.stdin is not None
    proc.stdin.write(cmd + "\n")
    proc.stdin.flush()


def communicate_slice(proc: subprocess.Popen, timeout: float = 5.0) -> str:
    try:
        out, _ = proc.communicate(timeout=timeout)
        return out or ""
    except subprocess.TimeoutExpired:
        try:
            proc.terminate()
        except Exception:
            pass
        try:
            out, _ = proc.communicate(timeout=2.0)
            return out or ""
        except Exception:
            return ""


def extract_sid(encinfo: str) -> str:
    in_sess = False
    for line in encinfo.splitlines():
        if line.strip().startswith("Sessions:"):
            in_sess = True
            continue
        if in_sess:
            if not line.strip():
                break
            m = re.search(r"sid=([^\s]+)", line)
            if m:
                return m.group(1)
    m = re.search(r"session established .* sid=([A-Za-z0-9+/=]+)", encinfo)
    if m:
        return m.group(1)
    return ""


def main() -> int:
    bind = _primary_ip()
    a = start_cli(2425, bind_ip=bind)
    b = start_cli(2426, bind_ip=bind)
    try:
        time.sleep(1.0)
        send_cmd(a, "/login a"); send_cmd(b, "/login b")
        send_cmd(a, "/set debug on"); send_cmd(b, "/set debug on")
        send_cmd(a, "/set encrypt on"); send_cmd(b, "/set encrypt on")
        time.sleep(1.5)
        send_cmd(a, f"/discover ip:{bind}:2426")
        time.sleep(1.0)
        send_cmd(a, f"/kx {bind}:2426")
        time.sleep(3.0)
        send_cmd(a, "/debug encinfo"); send_cmd(b, "/debug encinfo")
        time.sleep(1.0)
        send_cmd(a, "/quit"); send_cmd(b, "/quit")
        enc_a = communicate_slice(a, timeout=6.0)
        enc_b = communicate_slice(b, timeout=6.0)
        print("=== ENCINFO A ==="); print(enc_a)
        print("=== ENCINFO B ==="); print(enc_b)
        sid_a = extract_sid(enc_a); sid_b = extract_sid(enc_b)
        if not sid_a or not sid_b:
            print("[FAIL] 未能从 /debug encinfo 中解析到 sid", file=sys.stderr)
            return 1
        if sid_a != sid_b:
            print(f"[FAIL] sid 不一致: A={sid_a} B={sid_b}", file=sys.stderr)
            return 1
        print(f"[OK] sid 一致: {sid_a}")
        return 0
    finally:
        for p in (a, b):
            try:
                p.terminate()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
