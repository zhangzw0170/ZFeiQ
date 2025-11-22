"""Run demos and tests, collect results, and write a concise summary to `logs/test_summary.txt`.

Usage (PowerShell):
  $env:PYTHONPATH='e:/Main/JuniorI/Course_Linux_RK3566/ZFeiQ/ZFeiQ_Python'; python demos/generate_test_report.py
"""
import subprocess
import sys
import pathlib
import os
import time
from datetime import datetime, timezone

BASE = pathlib.Path(__file__).resolve().parent
ROOT = BASE.parent
LOGDIR = BASE / "logs"
LOGDIR.mkdir(parents=True, exist_ok=True)

DEMOS = [
    "run_demo.py",
    "run_demo_network.py",
    "run_demo_filetransfer.py",
    "run_demo_crypto.py",
    "run_demo_protocol.py",
]

TEST_DIR = ROOT / "tests"

PY = sys.executable

results = {
    'demos': [],
    'tests': []
}

# Helper to run a script and capture output
def run_script(path: pathlib.Path, cwd: pathlib.Path):
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = path.name
    log_file = LOGDIR / f"{name}.{ts}.log"
    env = os.environ.copy()
    env['PYTHONPATH'] = str(ROOT)
    try:
        with open(log_file, 'wb') as lf:
            proc = subprocess.Popen([PY, str(path)], cwd=str(cwd), stdout=lf, stderr=subprocess.STDOUT, env=env)
            proc.wait(timeout=10)
            returncode = proc.returncode
    except subprocess.TimeoutExpired:
        returncode = -1
    except Exception as e:
        # write exception to log
        with open(log_file, 'w', encoding='utf-8') as lf:
            lf.write(f"Exception running {name}: {e}\n")
        returncode = -2
    return (name, returncode, str(log_file))

# Run demos
for demo in DEMOS:
    p = BASE / demo
    if not p.exists():
        results['demos'].append((demo, None, 'missing'))
        continue
    out = run_script(p, BASE)
    results['demos'].append(out)

# Run tests (all *.py in tests directory)
if TEST_DIR.exists():
    for f in sorted(TEST_DIR.glob('*.py')):
        out = run_script(f, TEST_DIR)
        results['tests'].append(out)

# Summarize
summary_lines = []
summary_lines.append(f"Test summary generated: {datetime.now(timezone.utc).isoformat()}\n")
summary_lines.append("Demos:\n")
for name, code, log in results['demos']:
    if code is None:
        status = 'MISSING'
    elif code == 0:
        status = 'OK'
    elif code == -1:
        status = 'TIMEOUT'
    else:
        status = f'FAIL({code})'
    summary_lines.append(f"- {name}: {status} -> {log}\n")

summary_lines.append('\nTests:\n')
for name, code, log in results['tests']:
    if code == 0:
        status = 'PASS'
    elif code is None:
        status = 'MISSING'
    elif code == -1:
        status = 'TIMEOUT'
    else:
        status = f'FAIL({code})'
    summary_lines.append(f"- {name}: {status} -> {log}\n")

summary_text = ''.join(summary_lines)
with open(LOGDIR / 'test_summary.txt', 'w', encoding='utf-8') as f:
    f.write(summary_text)

print(summary_text)
print('Wrote', LOGDIR / 'test_summary.txt')
