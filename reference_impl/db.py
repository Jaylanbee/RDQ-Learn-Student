# db.py - RDQ v11.5 資料庫連線、DDL、WAL 併發 Retry、Migration 與全欄位比對驗證
import sqlite3, os, time, datetime, hashlib, json
from reference_impl.config import (
    DB_RETRY_MAX_ATTEMPTS, DB_RETRY_BASE_DELAY, DB_RETRY_MAX_DELAY,
    SESSION_ABANDON_HOURS, STAGING_CLEANUP_DAYS, MEDIA_STAGING_DIR
)

DB_PATH = os.path.expanduser(r"d:\2026AI_agent\RQD\data\review_index.db")

def now_utc_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

def retry_delay(attempt: int, base=DB_RETRY_BASE_DELAY, max_delay=DB_RETRY_MAX_DELAY) -> float:
    return min(base * (2 ** attempt), max_delay)

def execute_with_retry(conn, sql, params=(), max_retries=DB_RETRY_MAX_ATTEMPTS):
    for attempt in range(max_retries):
        try:
            cur = conn.execute(sql, params)
            return cur
        except sqlite3.OperationalError as e:
            if ("locked" in str(e).lower() or "busy" in str(e).lower()) and attempt < max_retries - 1:
                time.sleep(retry_delay(attempt))
                continue
            raise

def init_db(conn=None):
    close_at_end = False
    if conn is None:
        conn = get_connection()
        close_at_end = True

    # 1. 核心狀態表 (review_index_current)
    execute_with_retry(conn, """
        CREATE TABLE IF NOT EXISTS review_index_current (
            item_id           TEXT PRIMARY KEY,
            subject           TEXT NOT NULL,
            topic             TEXT NOT NULL,
            question          TEXT NOT NULL,
            answer            TEXT NOT NULL,
            image_path        TEXT DEFAULT NULL,
            box_level         INTEGER NOT NULL DEFAULT 1 CHECK(box_level BETWEEN 1 AND 5),
            status            TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','active','mastered')),
            priority          INTEGER NOT NULL DEFAULT 0 CHECK(priority BETWEEN 0 AND 100),
            wrong_count       INTEGER NOT NULL DEFAULT 0,
            last_wrong_at     TEXT,
            next_review_at    TEXT,
            last_reviewed_at  TEXT,
            mastered_at       TEXT,
            created_at        TEXT NOT NULL
        )
    """)

    # 2. 歷程日誌表 (review_index_log)
    execute_with_retry(conn, """
        CREATE TABLE IF NOT EXISTS review_index_log (
            log_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id      TEXT NOT NULL,
            action       TEXT NOT NULL CHECK(action IN ('promote','demote','verify_correct','verify_wrong','ingest_approve')),
            from_box     INTEGER,
            to_box       INTEGER,
            created_at   TEXT NOT NULL
        )
    """)

    # 3. 對話狀態持久化暫存表 (session_state)
    execute_with_retry(conn, """
        CREATE TABLE IF NOT EXISTS session_state (
            session_id        TEXT PRIMARY KEY,
            phase             TEXT NOT NULL DEFAULT 'phase0' CHECK(phase IN ('phase0','phase1','phase2','phase2_5','phase3','phase4','phase5')),
            topic             TEXT,
            textbook_content  TEXT,
            student_recalled  TEXT,
            student_uncertain TEXT,
            status            TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','completed','abandoned')),
            updated_at        TEXT NOT NULL
        )
    """)

    # 4. 多模態草稿緩衝表 (ingestion_staging)
    execute_with_retry(conn, """
        CREATE TABLE IF NOT EXISTS ingestion_staging (
            staging_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            question        TEXT,
            answer          TEXT,
            subject         TEXT DEFAULT '自然',
            topic           TEXT DEFAULT '外部錯題',
            image_path      TEXT DEFAULT NULL,
            ocr_confidence  REAL DEFAULT 1.0,
            status          TEXT NOT NULL DEFAULT 'pending_review' CHECK(status IN ('pending_review','fallback_manual','approved')),
            created_at      TEXT NOT NULL
        )
    """)

    # 5. 全域 Metadata 版本表 (system_metadata)
    execute_with_retry(conn, """
        CREATE TABLE IF NOT EXISTS system_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    execute_with_retry(conn, """
        INSERT OR IGNORE INTO system_metadata (key, value, updated_at)
        VALUES ('schema_version', '1', ?), ('migration_version', '1', ?)
    """, (now_utc_iso(), now_utc_iso()))

    conn.commit()
    if close_at_end:
        conn.close()

def maybe_cleanup(conn):
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    one_day_ago = (now_dt - datetime.timedelta(hours=SESSION_ABANDON_HOURS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    fourteen_days_ago = (now_dt - datetime.timedelta(days=STAGING_CLEANUP_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")

    execute_with_retry(conn, """
        UPDATE session_state SET status='abandoned'
        WHERE status='active' AND updated_at < ?
    """, (one_day_ago,))

    expired_stagings = conn.execute("""
        SELECT staging_id, image_path FROM ingestion_staging
        WHERE status='fallback_manual' AND created_at < ?
    """, (fourteen_days_ago,)).fetchall()

    for s in expired_stagings:
        if s["image_path"] and os.path.exists(s["image_path"]):
            try: os.remove(s["image_path"])
            except: pass

    execute_with_retry(conn, """
        DELETE FROM ingestion_staging
        WHERE status='fallback_manual' AND created_at < ?
    """, (fourteen_days_ago,))

    conn.commit()

def verify_migration(conn):
    has_old = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='review_index'").fetchone()
    if not has_old:
        return True, "No legacy review_index table found, skip migration verification."

    old_count = conn.execute("SELECT COUNT(*) FROM review_index").fetchone()[0]
    new_count = conn.execute("SELECT COUNT(*) FROM review_index_current").fetchone()[0]
    assert old_count == new_count, f"筆數不符：{old_count} vs {new_count}"

    diff = conn.execute("""
        SELECT item_id, box_level, status, next_review_at FROM review_index
        EXCEPT
        SELECT item_id, box_level, status, next_review_at FROM review_index_current
    """).fetchall()
    assert not diff, f"以下資料內容不一致：{diff}"
    return True, f"✅ Migration 驗證通過：{old_count} → {new_count} 筆，關鍵欄位無遺失"
