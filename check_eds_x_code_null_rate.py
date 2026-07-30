#!/usr/bin/env python3
"""
check_eds_x_code_null_rate.py

這支腳本用來檢查 review_index.db 之中，
`eds_x_code` 欄位為 null 的比例。

如果未填寫課綱代碼的比例過高，可能會嚴重影響下游 EDS (Educational Decision System)
計算投資報酬率 (ROI) 與派題的精準度。腳本會給出目前的統計數據與警告。

環境變數（選填）：
    ECOSYSTEM_DB_PATH  — 資料庫路徑，未設定則使用 ~/.education_ecosystem/review_index.db
"""

import sqlite3
import os
import sys

# Windows 終端機 UTF-8 相容
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# 警告門檻，若 null 比例大於這個值則顯示警告
WARNING_THRESHOLD = 0.20


def _get_db_path() -> str:
    """優先讀取 ECOSYSTEM_DB_PATH 環境變數，否則使用預設路徑。"""
    env = os.environ.get('ECOSYSTEM_DB_PATH')
    if env:
        return os.path.expanduser(env)
    return os.path.expanduser('~/.education_ecosystem/review_index.db')


def check_null_rate():
    db_path = _get_db_path()

    if not os.path.exists(db_path):
        print(f"找不到資料庫檔案：{db_path}。可能是尚未產生任何覆盤紀錄。")
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 檢查表格是否存在
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='review_index';")
        if not cursor.fetchone():
            print("資料庫中尚未建立 review_index 表格。請先執行 migrate_db.py 或寫入覆盤資料。")
            return

        # 檢查 eds_x_code 欄位是否存在
        cursor.execute("PRAGMA table_info(review_index);")
        columns = [col[1] for col in cursor.fetchall()]
        if "eds_x_code" not in columns:
            print("資料表缺少 eds_x_code 欄位，請先執行 migrate_db.py 進行資料庫升級。")
            return

        # 計算總筆數
        cursor.execute("SELECT COUNT(*) FROM review_index")
        total_count = cursor.fetchone()[0]

        if total_count == 0:
            print("資料庫中目前沒有任何紀錄。")
            return

        # 計算 eds_x_code 為 null 或空字串的筆數
        cursor.execute(
            "SELECT COUNT(*) FROM review_index WHERE eds_x_code IS NULL OR trim(eds_x_code) = '';")
        null_count = cursor.fetchone()[0]

        null_rate = null_count / total_count

        print("=== eds_x_code 防呆檢驗報告 ===")
        print(f"總紀錄筆數: {total_count}")
        print(f"未填寫 eds_x_code 筆數: {null_count}")
        print(f"空缺比例: {null_rate:.2%}")

        if null_rate > WARNING_THRESHOLD:
            print("\n⚠️ [警告] eds_x_code 空缺比例過高！")
            print(f"目前空缺比例已超過警戒值 ({WARNING_THRESHOLD:.2%})。")
            print("過多未標記 108 課綱代碼的知識點將導致下游 EDS 系統無法準確對應考題，")
            print("進而影響 ROI 計算與弱點派題的品質。請檢視 AI 的提問是否偏離課綱，或修訂 prompt 要求標示代碼。")
        else:
            print("\n✅ [正常] eds_x_code 空缺比例在安全範圍內。下游 EDS 系統應可正常運作。")

    except sqlite3.Error as e:
        print(f"資料庫讀取錯誤: {e}", file=sys.stderr)
    finally:
        if 'conn' in locals():
            conn.close()


if __name__ == '__main__':
    check_null_rate()
