import sqlite3
import os
import argparse

def run_migration(db_path):
    print(f"Migrating database at: {db_path}")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

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

    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='review_index';")
    if cur.fetchone():
        cur.execute("ALTER TABLE review_index RENAME TO review_index_log;")
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
    else:
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
    conn.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--db-path', default=os.path.expanduser('~/.education_ecosystem/review_index.db'))
    args = parser.parse_args()
    os.makedirs(os.path.dirname(args.db_path), exist_ok=True)
    run_migration(args.db_path)
