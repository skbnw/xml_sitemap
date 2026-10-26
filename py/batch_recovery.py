import time
import subprocess
import os
import sys
from pathlib import Path

# 全ての file-g*.py 実行する
scripts = sorted([f.name for f in Path('py').glob('file-g*.py')])

# venvのpythonパス（既存の run_all_scripts.py から引用）
python_exe = r"C:\Users\user\Documents\Github\Project_NewsDB\venv\Scripts\python.exe"

def run_recovery():
    for script in scripts:
        try:
            print(f"[{time.strftime('%H:%M:%S')}] Running {script}...", flush=True)
            subprocess.run([python_exe, f"py/{script}"], check=True)
            print(f"[{time.strftime('%H:%M:%S')}] Finished {script}. Waiting for 2 seconds...", flush=True)
            time.sleep(2)
        except subprocess.CalledProcessError as e:
            print(f"Error occurred while running {script}: {e}", flush=True)
            continue

if __name__ == "__main__":
    run_recovery()
