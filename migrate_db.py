import sqlite3
import os

db_path = os.path.expanduser('~/.education_ecosystem/review_index.db')

try:
    # 確保資料夾存在
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 首先建立表格，確保資料庫不是空的
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS review_index (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        subject       TEXT    NOT NULL,
        topic         TEXT    NOT NULL,
        item_id       TEXT    NOT NULL,
        quadrant      TEXT,
        status        TEXT    NOT NULL CHECK (status IN ('confirmed', 'uncertain', 'clarified')),
        source        TEXT    CHECK (source IN ('self', 'prompted')),
        priority      TEXT    NOT NULL CHECK (priority IN ('red', 'yellow', 'green')),
        box           INTEGER NOT NULL DEFAULT 1 CHECK (box BETWEEN 1 AND 5),
        mc_id         TEXT,
        mc_probe_count INTEGER DEFAULT 0,
        mc_probe_variant TEXT,
        date          TEXT    NOT NULL,
        last_reviewed TEXT    NOT NULL,
        next_review   TEXT    NOT NULL,
        scope_disputed INTEGER DEFAULT 0,
        scope_confirmed INTEGER DEFAULT 0,
        file_path     TEXT,
        UNIQUE(subject, topic, item_id, date)
    );
    """)

    # 檢查 eds_x_code 欄位
    cursor.execute("PRAGMA table_info(review_index);")
    columns = [col[1] for col in cursor.fetchall()]

    if "eds_x_code" not in columns:
        cursor.execute("ALTER TABLE review_index ADD COLUMN eds_x_code TEXT;")
        print("[OK] 新增欄位：eds_x_code")
    else:
        print("[..] 欄位 eds_x_code 已存在，跳過。")

    if "loss_reason" not in columns:
        cursor.execute("ALTER TABLE review_index ADD COLUMN loss_reason TEXT;")
        print("[OK] 新增欄位：loss_reason")
    else:
        print("[..] 欄位 loss_reason 已存在，跳過。")

    conn.commit()
    print("[Done] 資料庫升級完成！EDS 現在可以安全讀取了。")

except Exception as e:
    print(f"[Error] {e}")
finally:
    if 'conn' in locals():
        conn.close()
