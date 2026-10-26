import time
import subprocess
import os
import sys
import argparse
from datetime import datetime, timedelta

# 実行するPythonスクリプトのリスト
scripts = [
    "file-g01.py",
    "file-g02.py",
    "file-g03.py",
    "file-g04.py",
    "file-g05.py",
    "file-g06.py",
    "file-g07.py",
    "file-g08.py",
    "file-g09.py",
    "file-g10.py",
    "file-g11.py",
    "file-g12.py",
    "file-g13.py",
    "file-g14.py",
    "file-g15.py",
    "file-g16.py",
]

# venvのpythonパス
python_exe = r"C:\Users\user\Documents\Github\Project_NewsDB\venv\Scripts\python.exe"

def main():
    parser = argparse.ArgumentParser(description='Run all scrapers for a specific date.')
    parser.add_argument('--date', type=str, help='Target date in YYYY-MM-DD format. Defaults to yesterday.')
    args = parser.parse_args()

    target_date = args.date
    if not target_date:
        # デフォルトは昨日
        target_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    print(f"Target Date: {target_date}")

    # 各スクリプトを順次実行
    for script in scripts:
        try:
            print(f"Running {script} for {target_date}...", flush=True)
            # 各スクリプトに引数として日付を渡す
            subprocess.run([python_exe, f"py/{script}", target_date], check=True)
            print(f"Finished {script}. Waiting for 5 seconds...", flush=True)
            time.sleep(5)  # 5秒待機
        except subprocess.CalledProcessError as e:
            print(f"Error occurred while running {script}: {e}", flush=True)
            # 次のスクリプトに進む
            continue

if __name__ == "__main__":
    main()

