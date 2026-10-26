import glob
import re
from pathlib import Path

# 修正内容:
# 1. JST/TARGET_DATE の標準化 (yesterday)
# 2. max_pages=10 -> max_pages=20 (URL取得および本文取得の両方)

jst_block = """# 日本時間のタイムゾーンを指定
JST = pytz.timezone('Asia/Tokyo')

# 作業日（実行日）の前日を日本時間で設定
TARGET_DATE = datetime.now(JST) - timedelta(days=1)
"""

files = glob.glob('py/file-g*.py')

for file_path in files:
    content = Path(file_path).read_text(encoding='utf-8')
    orig_content = content
    
    # 1. タイムゾーンと日付の修正
    if 'import pytz' not in content:
        content = content.replace('from datetime import datetime, timedelta', 'from datetime import datetime, timedelta\nimport pytz')
    
    # TARGET_DATE の記述を標準化
    # 既存のコメントや定義を置換
    content = re.sub(r'# 作業日.*?\nTARGET_DATE = .*?\n', jst_block + '\n', content, flags=re.DOTALL)
    if 'TARGET_DATE =' in content and jst_block not in content:
        content = re.sub(r'TARGET_DATE = .*', jst_block, content)

    # 2. max_pages の修正
    content = content.replace('max_pages=10', 'max_pages=20')

    # 重複する import pytz を掃除
    lines = content.splitlines()
    new_lines = []
    seen_pytz = False
    for line in lines:
        if 'import pytz' in line:
            if seen_pytz: continue
            seen_pytz = True
        new_lines.append(line)
    content = '\n'.join(new_lines)

    if content != orig_content:
        Path(file_path).write_text(content, encoding='utf-8')
        print(f"Optimized {file_path}")
    else:
        print(f"No changes needed for {file_path}")
