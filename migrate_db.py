import sqlite3
import os
import csv

def migrate_phase2():
    db_dir = os.path.expanduser('~/.education_ecosystem')
    os.makedirs(db_dir, exist_ok=True)
    db_path = os.path.join(db_dir, 'review_index.db')

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # 1. 建置 exam_weights 表
    cur.execute('''
    CREATE TABLE IF NOT EXISTS exam_weights (
        item_id      TEXT PRIMARY KEY,
        subject      TEXT NOT NULL,
        exam_frequency INTEGER NOT NULL DEFAULT 0,
        avg_difficulty REAL NOT NULL DEFAULT 0.0,
        exam_weight  REAL NOT NULL DEFAULT 0.1,
        last_updated TEXT NOT NULL
    );
    ''')

    # 2. 匯入 54 筆權重數據
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(script_dir, 'eds_roi_weights.csv')
    
    if os.path.exists(csv_path):
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            items = []
            for r in reader:
                items.append((
                    r['eds_x_code'],
                    r['subject'],
                    int(r['exam_frequency']),
                    float(r['avg_difficulty']),
                    float(r['roi_weight']),
                    r['last_updated']
                ))
        cur.executemany('''
        INSERT OR REPLACE INTO exam_weights (item_id, subject, exam_frequency, avg_difficulty, exam_weight, last_updated)
        VALUES (?, ?, ?, ?, ?, ?);
        ''', items)
        print(f"Successfully migrated {len(items)} items into exam_weights table.")

    # 3. 建立 weakness_stats 視圖 (供 EDS 的 analyzer.py JOIN 查詢)
    cur.execute('''
    CREATE VIEW IF NOT EXISTS weakness_stats AS
    SELECT
        item_id,
        subject,
        MAX(CASE WHEN status = 'uncertain' THEN 1.0 ELSE 0 END) +
        MAX(CASE WHEN source = 'prompted' THEN 0.3 ELSE 0 END) +
        COUNT(CASE WHEN status = 'uncertain' AND date >= DATE('now', '-30 days') THEN 1 END) * 0.5 AS weakness_score,
        COUNT(*) AS total_reviews,
        COUNT(CASE WHEN status = 'uncertain' THEN 1 END) AS uncertain_count
    FROM review_index
    GROUP BY item_id;
    ''')

    conn.commit()

    # 驗證結果
    cur.execute("SELECT COUNT(*) FROM exam_weights;")
    count = cur.fetchone()[0]
    print(f"Verified: exam_weights table has {count} rows.")

    cur.execute("SELECT name FROM sqlite_master WHERE type='view' AND name='weakness_stats';")
    view_exists = cur.fetchone() is not None
    print(f"Verified: weakness_stats view created: {view_exists}")

    conn.close()

if __name__ == '__main__':
    migrate_phase2()
