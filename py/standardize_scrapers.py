import glob
import re
from pathlib import Path

# 全ての scraper スクリプトのインポート部と定数部を一貫した形式に修正します。
# 1. JST タイムゾーンの定義を確実に追加
# 2. TARGET_DATE を「前日 (Yesterday)」に統一
# 3. pytz のインポート漏れを修正

jst_definition = """import pytz

# 日本時間のタイムゾーンを指定
JST = pytz.timezone('Asia/Tokyo')

# 作業日（実行日）の前日を日本時間で設定
TARGET_DATE = datetime.now(JST) - timedelta(days=1)
"""

# インポートセクションのパターン
import_pattern = re.compile(r'(from datetime import datetime, timedelta.*?\n)')

files = glob.glob('py/file-g*.py')

for file_path in files:
    content = Path(file_path).read_text(encoding='utf-8')
    orig_content = content
    
    # すでに JST 定義があるか確認
    if 'JST = pytz.timezone' in content:
        # すでにある場合は TARGET_DATE だけ置換
        content = re.sub(r'TARGET_DATE = .*', 'TARGET_DATE = datetime.now(JST) - timedelta(days=1)', content)
    else:
        # JST 定義がない場合は追加
        # インポートセクションの直後に追加
        if 'import pytz' not in content:
            content = content.replace('from datetime import datetime, timedelta', 'from datetime import datetime, timedelta\nimport pytz')
        
        # 既存の TARGET_DATE 公式やコメントを削除して JST ブロックを挿入
        content = re.sub(r'# 作業日.*?\nTARGET_DATE = .*?\n', jst_definition, content, flags=re.DOTALL)
        # もし上の正規表現で引っかからなかった場合（コメントの形式が違うなど）
        if jst_definition not in content and 'TARGET_DATE =' in content:
             content = re.sub(r'TARGET_DATE = .*', jst_definition, content)

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
        print(f"Standardized JST and TARGET_DATE in {file_path}")
    else:
        print(f"Already correct: {file_path}")
