#!/usr/bin/env python3
"""
generate_daily_tasks.py

這支腳本負責處理「五合一生態系」中的「複習計畫 (Study Plan)」。
它會連線到 review_index.db，並撈取 `next_review <= 今天`
的到期知識點，作為學生今天的任務清單。

可以選擇輸出為 json 或 md。
用法: python generate_daily_tasks.py [--format=json|md]

環境變數（選填）：
    ECOSYSTEM_DB_PATH  — 資料庫路徑，未設定則使用 ~/.education_ecosystem/review_index.db
"""

import sqlite3
import os
import sys
import json
from datetime import datetime


def _get_db_path() -> str:
    """優先讀取 ECOSYSTEM_DB_PATH 環境變數，否則使用預設路徑。"""
    env = os.environ.get('ECOSYSTEM_DB_PATH')
    if env:
        return os.path.expanduser(env)
    return os.path.expanduser('~/.education_ecosystem/review_index.db')


def get_daily_tasks():
    db_path = _get_db_path()
    if not os.path.exists(db_path):
        return []

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        today = datetime.now().strftime('%Y-%m-%d')

        # 撈取今天 (含之前) 到期需要複習的項目
        query = """
            SELECT
                subject, topic, item_id, eds_x_code, status, priority, box, date
            FROM review_index
            WHERE next_review <= ?
            ORDER BY
                subject ASC,
                CASE priority
                    WHEN 'red' THEN 1
                    WHEN 'yellow' THEN 2
                    WHEN 'green' THEN 3
                    ELSE 4
                END ASC,
                next_review ASC,
                topic ASC
        """
        cursor.execute(query, (today,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    except sqlite3.Error as e:
        print(f"資料庫讀取錯誤: {e}", file=sys.stderr)
        return []
    finally:
        if 'conn' in locals():
            conn.close()


def print_markdown(data):
    today_str = datetime.now().strftime('%Y-%m-%d')
    print(f"# 📅 今日複習任務清單 ({today_str})\n")

    if not data:
        print("🎉 太棒了！今天沒有任何需要複習的任務，好好休息或學習新進度吧！")
        return

    print(f"今天共有 **{len(data)}** 個知識點需要複習：\n")

    current_subject = ""
    for item in data:
        if item['subject'] != current_subject:
            current_subject = item['subject']
            print(f"## 📚 科目：{current_subject}")

        # 標示緊急度 (priority)
        prio_icon = "🔴"
        if item['priority'] == 'yellow':
            prio_icon = "🟡"
        elif item['priority'] == 'green':
            prio_icon = "🟢"

        box_text = f" (Leitner Box {item['box']})"
        eds_text = f" `[{item['eds_x_code']}]`" if item['eds_x_code'] else ""

        print(
            f"* {prio_icon} **{item['topic']}** - 節點 ID: `{item['item_id']}`{eds_text}{box_text}")

    print("\n---\n*你可以選擇將這些任務交給 T2N 產出專屬考前精華，或交給 EDS 進行實戰抽考。*")


if __name__ == '__main__':
    out_format = "md"
    for arg in sys.argv[1:]:
        if arg.startswith("--format="):
            out_format = arg.split("=")[1].lower()

    data = get_daily_tasks()
    if out_format == "json":
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print_markdown(data)
