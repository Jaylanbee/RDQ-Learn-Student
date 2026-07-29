import sqlite3
import os

db_path = os.path.expanduser('~/.rdq/review_index.db')

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("ALTER TABLE review_index ADD COLUMN eds_x_code TEXT;")
        print("[OK] 新增欄位：eds_x_code")
    except sqlite3.OperationalError:
        print("[..] 欄位 eds_x_code 已存在，跳過。")

    try:
        cursor.execute("ALTER TABLE review_index ADD COLUMN loss_reason TEXT;")
        print("[OK] 新增欄位：loss_reason")
    except sqlite3.OperationalError:
        print("[..] 欄位 loss_reason 已存在，跳過。")

    conn.commit()
    print("[Done] 資料庫升級完成！EDS 現在可以安全讀取了。")

except Exception as e:
    print(f"[Error] {e}")
finally:
    if 'conn' in locals():
        conn.close()
