#!/usr/bin/env python3
"""
rdq_store.py

用來封裝 RDQ Phase 7 寫入邏輯的 CLI 工具。
這支腳本接收 JSON 格式的資料，會呼叫 leitner 邏輯並寫入 review_index.db。

用法：
python rdq_store.py '<json_string>'
"""

import sys
import json
import sqlite3
import os
from datetime import datetime

# 將 RDQ-Shared-Schema 加入路徑以便 import leitner.py
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'RDQ-Shared-Schema'))
try:
    import leitner
except ImportError:
    print("Error: 無法載入 leitner 模組，請確定 RDQ-Shared-Schema 存在。", file=sys.stderr)
    sys.exit(1)

def write_to_db(data):
    db_path = os.path.expanduser('~/.education_ecosystem/review_index.db')
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    subject = data.get('subject')
    topic = data.get('topic')
    date_str = data.get('date', datetime.now().strftime('%Y-%m-%d'))
    items = data.get('items', [])

    for item in items:
        # 從資料庫尋找最近一筆紀錄的 box
        cursor.execute('''
            SELECT box FROM review_index
            WHERE subject = ? AND item_id = ?
            ORDER BY date DESC LIMIT 1
        ''', (subject, item['id']))
        row = cursor.fetchone()
        current_box = row[0] if row else 1

        # 呼叫 leitner 取得 next_box 和 next_review
        status = item.get('status')
        source = item.get('source')
        priority = item.get('priority')

        next_box, next_review = leitner.next_box(current_box, status, priority, source)

        try:
            cursor.execute('''
                INSERT INTO review_index (
                    subject, topic, item_id, quadrant, status, source, priority, box,
                    mc_id, mc_probe_count, mc_probe_variant, date, last_reviewed, next_review,
                    scope_disputed, scope_confirmed, file_path, eds_x_code, loss_reason
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?
                )
            ''', (
                subject, topic, item['id'], item.get('quadrant'), status, source, priority, next_box,
                item.get('mc_id'), item.get('mc_probe_count', 0), item.get('mc_probe_variant'),
                date_str, date_str, next_review,
                1 if item.get('scope_disputed') else 0,
                1 if item.get('scope_confirmed') else 0,
                data.get('file_path'), item.get('eds_x_code'), item.get('loss_reason')
            ))
        except sqlite3.IntegrityError:
            # 忽略唯一鍵衝突 (同一天同一項目)
            pass

    conn.commit()
    conn.close()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python rdq_store.py '<json_string>'", file=sys.stderr)
        sys.exit(1)

    try:
        data = json.loads(sys.argv[1])
        write_to_db(data)
        print("Data successfully stored.")
    except json.JSONDecodeError:
        print("Error: 傳入的不是合法的 JSON 字串。", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)
