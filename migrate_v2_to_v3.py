import sqlite3
import os
import argparse

def run_migration(db_path):
    print(f"Migrating database at: {db_path}")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # 1. 建立 ingestion_staging
    cur.execute('''
    CREATE TABLE IF NOT EXISTS ingestion_staging (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        image_path TEXT,
        extracted_text TEXT,
        subject TEXT,
        eds_x_code TEXT,
        priority TEXT CHECK(priority IN ('red','yellow','green')),
        llm_confidence REAL,
        status TEXT CHECK(status IN ('pending', 'approved', 'rejected')),
        promoted_item_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        reviewed_at TIMESTAMP
    );
    ''')
    print("Created ingestion_staging table.")

    # 2. 建立 review_index_log (由於原本有 review_index, 我們將舊資料移轉到 log)
    # 先確認 review_index 是否存在
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='review_index';")
    if cur.fetchone():
        print("Found existing review_index. Renaming to review_index_log and altering schema...")
        cur.execute("ALTER TABLE review_index RENAME TO review_index_log;")

        # 由於 SQLite ALTER TABLE 限制，我們需要重建 log 表以加入新欄位和變更結構
        cur.execute('''
        CREATE TABLE review_index_log_new (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            eds_x_code TEXT,
            source TEXT CHECK(source IN ('daily','external')) NOT NULL DEFAULT 'daily',
            media_path TEXT,
            llm_confidence REAL,
            priority TEXT CHECK(priority IN ('red','yellow','green')) NOT NULL DEFAULT 'yellow',
            box INTEGER NOT NULL CHECK(box BETWEEN 1 AND 5),
            status TEXT CHECK(status IN ('active','confirmed','rejected', 'uncertain', 'clarified')) NOT NULL,
            next_review DATE,
            action TEXT CHECK(action IN ('initial','correct','incorrect','manual_reject')) NOT NULL DEFAULT 'initial',
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        ''')

        # 將舊資料導回 log_new (這裡做一些狀態對應，uncertain/clarified 轉為 active)
        cur.execute('''
        INSERT INTO review_index_log_new (item_id, subject, eds_x_code, priority, box, status, next_review, timestamp)
        SELECT id, subject, item_id, priority, box,
               CASE WHEN status IN ('uncertain', 'clarified') THEN 'active' ELSE status END,
               next_review, date
        FROM review_index_log;
        ''')

        cur.execute("DROP TABLE review_index_log;")
        cur.execute("ALTER TABLE review_index_log_new RENAME TO review_index_log;")
        cur.execute("CREATE INDEX idx_log_item ON review_index_log(item_id, timestamp);")
        print("Migrated old review_index to review_index_log.")
    else:
        # 如果是空庫，直接建立
        cur.execute('''
        CREATE TABLE IF NOT EXISTS review_index_log (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            eds_x_code TEXT,
            source TEXT CHECK(source IN ('daily','external')) NOT NULL,
            media_path TEXT,
            llm_confidence REAL,
            priority TEXT CHECK(priority IN ('red','yellow','green')) NOT NULL DEFAULT 'yellow',
            box INTEGER NOT NULL CHECK(box BETWEEN 1 AND 5),
            status TEXT CHECK(status IN ('active','confirmed','rejected')) NOT NULL,
            next_review DATE,
            action TEXT CHECK(action IN ('initial','correct','incorrect','manual_reject')) NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        ''')
        cur.execute("CREATE INDEX IF NOT EXISTS idx_log_item ON review_index_log(item_id, timestamp);")
        print("Created new review_index_log table.")

    # 3. 建立 review_index_current
    cur.execute('''
    CREATE TABLE IF NOT EXISTS review_index_current (
        item_id INTEGER PRIMARY KEY,
        subject TEXT NOT NULL,
        eds_x_code TEXT,
        priority TEXT CHECK(priority IN ('red','yellow','green')),
        box INTEGER NOT NULL,
        status TEXT CHECK(status IN ('active','confirmed')),
        next_review DATE,
        updated_at TIMESTAMP
    );
    ''')
    cur.execute("CREATE INDEX IF NOT EXISTS idx_current_schedule ON review_index_current(next_review, box, priority);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_current_subject ON review_index_current(subject, status);")
    print("Created review_index_current table and indexes.")

    # 4. 建立 Trigger
    cur.execute("DROP TRIGGER IF EXISTS trg_update_current_state;")
    cur.execute('''
    CREATE TRIGGER trg_update_current_state
    AFTER INSERT ON review_index_log
    BEGIN
        DELETE FROM review_index_current WHERE item_id = NEW.item_id AND NEW.status = 'rejected';

        INSERT INTO review_index_current (item_id, subject, eds_x_code, priority, box, status, next_review, updated_at)
        SELECT NEW.item_id, NEW.subject, NEW.eds_x_code, NEW.priority, NEW.box, NEW.status, NEW.next_review, NEW.timestamp
        WHERE NEW.status != 'rejected'
        ON CONFLICT(item_id) DO UPDATE SET
            priority = excluded.priority,
            box = excluded.box,
            status = excluded.status,
            next_review = excluded.next_review,
            updated_at = excluded.updated_at;
    END;
    ''')
    print("Created trg_update_current_state trigger.")

    # 5. 回填 review_index_current
    cur.execute("DELETE FROM review_index_current;")
    cur.execute('''
    INSERT INTO review_index_current (item_id, subject, eds_x_code, priority, box, status, next_review, updated_at)
    SELECT item_id, subject, eds_x_code, priority, box, status, next_review, timestamp
    FROM (
        SELECT *, ROW_NUMBER() OVER (PARTITION BY item_id ORDER BY timestamp DESC) as rn
        FROM review_index_log
    )
    WHERE rn = 1 AND status != 'rejected';
    ''')
    conn.commit()
    print("Backfilled review_index_current from review_index_log.")

    conn.close()
    print("Migration completed successfully.")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--db-path', default=os.path.expanduser('~/.education_ecosystem/review_index.db'))
    args = parser.parse_args()

    db_dir = os.path.dirname(args.db_path)
    os.makedirs(db_dir, exist_ok=True)

    run_migration(args.db_path)
