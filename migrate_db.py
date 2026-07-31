import sqlite3
import os
import json

_BASE = os.path.dirname(os.path.abspath(__file__))
_CONST_PATH = os.path.join(_BASE, 'RDQ-Shared-Schema',
                           'config', 'constants.json')
_CONST = {}
if os.path.exists(_CONST_PATH):
    with open(_CONST_PATH, encoding='utf-8') as f:
        _CONST = json.load(f)


def _get_db_path():
    env = os.environ.get('ECOSYSTEM_DB_PATH')
    if env:
        return os.path.expanduser(env)
    default = _CONST.get(
        'db_default_path', '~/.education_ecosystem/review_index.db')
    return os.path.expanduser(default)


db_path = _get_db_path()

try:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

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

    if "traffic_light" not in columns:
        cursor.execute("ALTER TABLE review_index ADD COLUMN traffic_light TEXT DEFAULT 'YELLOW';")
        print("[OK] 新增欄位：traffic_light")
    else:
        print("[..] 欄位 traffic_light 已存在，跳過。")

    conn.commit()
    print(f"[Done] 資料庫升級完成！路徑：{db_path}")

except Exception as e:
    print(f"[Error] {e}")
finally:
    if 'conn' in locals():
        conn.close()
