"""Run all demos sequentially and log outputs to `logs/`.

Usage (PowerShell):
    $env:PYTHONPATH='e:/Main/JuniorI/Course_Linux_RK3566/ZFeiQ/ZFeiQ_Python'; python demos/run_all.py
"""
import subprocess
import sys
import pathlib
from datetime import datetime, timezone

BASE = pathlib.Path(__file__).resolve().parent
LOGDIR = BASE / "logs"
LOGDIR.mkdir(parents=True, exist_ok=True)

DEMOS = [
    "run_demo.py",
    "run_demo_network.py",
    "run_demo_filetransfer.py",
    "run_demo_crypto.py",
    "run_demo_protocol.py",
]

PY = sys.executable

for demo in DEMOS:
    demo_path = BASE / demo
    if not demo_path.exists():
        print(f"skip (missing): {demo}")
        continue
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_file = LOGDIR / f"{demo}.{ts}.log"
    print(f"Running {demo} -> {log_file}")
    with open(log_file, "wb") as lf:
        # run the demo with PYTHONPATH pointing to BASE's parent (ZFeiQ_Python)
        env = dict(**dict())
        proc = subprocess.Popen([PY, str(demo_path)], cwd=str(BASE), stdout=lf, stderr=subprocess.STDOUT)
        proc.wait(timeout=5)
    print(f"Finished {demo}")

print("All demos completed. Logs in:", LOGDIR)
