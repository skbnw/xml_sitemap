import glob
import re
from pathlib import Path
import sys

def set_date(date_str):
    # date_str: "2026, 2, 24"
    pattern = r'TARGET_DATE = datetime\.now\(JST\) - timedelta\(days=1\)'
    replacement = f'TARGET_DATE = datetime({date_str}, tzinfo=JST)'
    
    files = glob.glob('py/file-g*.py')
    for file_path in files:
        content = Path(file_path).read_text(encoding='utf-8')
        if re.search(pattern, content):
            new_content = re.sub(pattern, replacement, content)
            Path(file_path).write_text(new_content, encoding='utf-8')
            print(f"Set date to {date_str} in {file_path}")
        else:
            print(f"Pattern not found in {file_path}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        set_date(sys.argv[1])
    else:
        print("Usage: python py/inject_date.py \"YYYY, M, D\"")
