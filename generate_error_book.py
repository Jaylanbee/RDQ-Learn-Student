#!/usr/bin/env python3
"""
generate_error_book.py

這支腳本是「錯題本 (Error Log)」模組的核心 API 介接層。
它會從 review_index.db 中，撈取最近 N 天內學生標記為
`uncertain` (待確認) 或 `clarified` (迷思已澄清) 的知識點。

可以將輸出導出為 JSON 格式 (供系統使用) 或 Markdown 格式 (供學生列印/閱讀)。

用法:
    python generate_error_book.py [天數, 預設 7] [--format=json|md]

環境變數（選填）：
    ECOSYSTEM_DB_PATH  — 資料庫路徑，未設定則使用 ~/.education_ecosystem/review_index.db
"""

import sqlite3
import os
import sys
import json
from datetime import datetime, timedelta

def _get_db_path() -> str:
    """優先讀取 ECOSYSTEM_DB_PATH 環境變數，否則使用預設路徑。"""
    env = os.environ.get('ECOSYSTEM_DB_PATH')
    if env:
        return os.path.expanduser(env)
    return os.path.expanduser('~/.education_ecosystem/review_index.db')


def get_error_log(days=7):
    db_path = _get_db_path()
    if not os.path.exists(db_path):
        return []

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row  # 讓回傳結果可以像 dict 一樣操作
        cursor = conn.cursor()

        target_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        # 撈取不確定的與迷思題
        query = """
            SELECT
                subject, topic, item_id, eds_x_code, status,
                loss_reason, mc_id, date, next_review
            FROM review_index
            WHERE status IN ('uncertain', 'clarified')
              AND date >= ?
            ORDER BY subject, topic, date DESC
        """
        cursor.execute(query, (target_date,))
        rows = cursor.fetchall()

        # 轉換為 dict list
        results = [dict(row) for row in rows]
        return results

    except sqlite3.Error as e:
        print(f"資料庫讀取錯誤: {e}", file=sys.stderr)
        return []
    finally:
        if 'conn' in locals():
            conn.close()

def print_markdown(data, days):
    print(f"# 🎯 你的專屬錯題本 (過去 {days} 天)\n")
    if not data:
        print("太棒了！這段時間內沒有任何錯題紀錄。繼續保持！")
        return

    current_subject = ""
    for item in data:
        if item['subject'] != current_subject:
            current_subject = item['subject']
            print(f"## 📚 科目：{current_subject}")

        status_icon = "❓" if item['status'] == 'uncertain' else "⚠️"
        loss_text = f" (卡關原因: {item['loss_reason']})" if item['loss_reason'] else ""
        eds_text = f" `[{item['eds_x_code']}]`" if item['eds_x_code'] else ""
        mc_text = f" - 迷思代碼: {item['mc_id']}" if item['mc_id'] else ""

        print(f"* {status_icon} **{item['topic']}** - 節點 ID: `{item['item_id']}`{eds_text}")
        print(f"  * 複習日期: {item['date']} -> 下次排程: {item['next_review']}")
        if loss_text or mc_text:
            print(f"  * 診斷: {loss_text}{mc_text}")
    print("\n---\n*建議：請針對上述 ❓ 項目重新閱讀課本，或使用 EDS 技能抽取相關考題進行特訓。*")

if __name__ == '__main__':
    days = 7
    out_format = "md"

    for arg in sys.argv[1:]:
        if arg.startswith("--format="):
            out_format = arg.split("=")[1].lower()
        elif arg.isdigit():
            days = int(arg)

    data = get_error_log(days)

    if out_format == "json":
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print_markdown(data, days)
