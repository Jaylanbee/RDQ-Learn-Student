import sqlite3
import os
import json
import csv

def _get_db_path():
    _BASE = os.path.dirname(os.path.abspath(__file__))
    _CONST_PATH = os.path.join(_BASE, 'RDQ-Shared-Schema', 'config', 'constants.json')
    _CONST = {}
    if os.path.exists(_CONST_PATH):
        with open(_CONST_PATH, encoding='utf-8') as f:
            _CONST = json.load(f)

    env = os.environ.get('ECOSYSTEM_DB_PATH')
    if env:
        return os.path.expanduser(env)
    default = _CONST.get(
        'db_default_path', '~/.education_ecosystem/review_index.db')
    return os.path.expanduser(default)

def migrate_phase2():
    db_path = _get_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # --- 1. 恢復核心 review_index 表的建置與維護邏輯 ---
    cur.execute("""
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

    # 檢查並補齊缺失欄位
    cur.execute("PRAGMA table_info(review_index);")
    columns = [col[1] for col in cur.fetchall()]

    if "eds_x_code" not in columns:
        cur.execute("ALTER TABLE review_index ADD COLUMN eds_x_code TEXT;")
        print("[OK] 新增欄位：eds_x_code")
    else:
        print("[..] 欄位 eds_x_code 已存在，跳過。")

    if "loss_reason" not in columns:
        cur.execute("ALTER TABLE review_index ADD COLUMN loss_reason TEXT;")
        print("[OK] 新增欄位：loss_reason")
    else:
        print("[..] 欄位 loss_reason 已存在，跳過。")

    # --- 2. 建置與更新 exam_weights 表 ---
    # 先刪除舊表，確保 schema 始終為最新 (包含新增的 exam_frequency 等欄位)
    cur.execute("DROP TABLE IF EXISTS exam_weights;")
    cur.execute('''
    CREATE TABLE exam_weights (
        item_id      TEXT PRIMARY KEY,
        subject      TEXT NOT NULL,
        exam_frequency INTEGER NOT NULL DEFAULT 0,
        avg_difficulty REAL NOT NULL DEFAULT 0.0,
        exam_weight  REAL NOT NULL DEFAULT 0.1,
        last_updated TEXT NOT NULL
    );
    ''')
    print("[OK] 資料表重建：exam_weights (已對齊最新欄位)")

    # 匯入 54 筆權重數據
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # 修正：指向 exam-data 資料夾
    csv_path = os.path.join(script_dir, 'exam-data', 'eds_roi_weights.csv')

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
        INSERT INTO exam_weights (item_id, subject, exam_frequency, avg_difficulty, exam_weight, last_updated)
        VALUES (?, ?, ?, ?, ?, ?);
        ''', items)
        print(f"[OK] 成功匯入 {len(items)} 筆 eds_roi_weights 數據至 exam_weights 表")
    else:
        print(f"[Warn] 找不到 {csv_path}，跳過匯入初始權重數據。")

    # --- 3. 建立 weakness_stats 視圖 (供 EDS 的 analyzer.py JOIN 查詢) ---
    cur.execute("DROP VIEW IF EXISTS weakness_stats;")
    cur.execute('''
    CREATE VIEW weakness_stats AS
    SELECT
        item_id,
        subject,
        MAX(CASE WHEN status = 'uncertain' THEN 1.0 ELSE 0 END) +
        MAX(CASE WHEN source = 'prompted' THEN 0.3 ELSE 0 END) +
        COUNT(CASE WHEN status = 'uncertain' AND date >= DATE('now', '-30 days') THEN 1 END) * 0.5 AS weakness_score,
        COUNT(*) AS total_reviews,
        COUNT(CASE WHEN status = 'uncertain' THEN 1 END) AS uncertain_count
    FROM review_index
    GROUP BY item_id, subject;
    ''')
    print("[OK] 視圖確保：weakness_stats")

    conn.commit()

    # 驗證結果
    cur.execute("SELECT COUNT(*) FROM exam_weights;")
    count = cur.fetchone()[0]
    print(f"Verified: exam_weights table has {count} rows.")

    conn.close()
    print(f"[Done] 資料庫升級完成！路徑：{db_path}")

if __name__ == '__main__':
    migrate_phase2()
