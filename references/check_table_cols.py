"""
快速檢查 question-bank.md 所有表格的表頭與分隔線欄位數是否一致。
發現不一致即印出，return code 1；全部正確 return 0。
"""
import os, sys

f = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'question-bank.md')
with open(f, 'r', encoding='utf-8') as fh:
    lines = fh.readlines()

errors = []
for i, line in enumerate(lines):
    s = line.rstrip()
    if '|' not in s:
        continue
    # header or separator line?  if all non-| chars are just -- then it's a separator
    content = s.replace('|', '').replace('-', '').strip()
    if content == '' and '-' in s and '|' in s:
        # separator line
        sep_cols = s.count('|')
        # find the previous header (nearest non-empty line with | that's not a separator)
        prev_pipes = 0
        for j in range(i - 1, -1, -1):
            prev = lines[j].rstrip()
            if not prev or prev.replace('|', '').replace('-', '').strip() == '':
                continue
            if '|' in prev:
                prev_pipes = prev.count('|')
                break
        if prev_pipes and sep_cols != prev_pipes:
            errors.append(f'L{i+1}: 分隔線 {sep_cols} pipes vs 表頭 {prev_pipes} pipes ({line.rstrip()[:40]})')

if errors:
    for e in errors:
        print(f'ERROR: {e}')
    sys.exit(1)
else:
    print('OK: 全部表格表頭與分隔線欄位數一致')
