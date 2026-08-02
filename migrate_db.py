#!/usr/bin/env python3
import sqlite3, os

DB_PATH = os.path.expanduser(r"~\.education_ecosystem\review_index.db")

def migrate():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    mapped = {
        'science': '自然',
        'math': '數學',
        'chinese': '國文',
        'social': '社會',
        'english': '英語'
    }

    old_rows = c.execute("SELECT * FROM review_index").fetchall()
    migrated = 0

    for r in old_rows:
        iid = r['item_id'] if r['item_id'] else f"old_item_{r['id']}"
        subj_raw = r['subject'] or 'science'
        subj = mapped.get(subj_raw, subj_raw)
        topic = r['topic'] or '舊錯題記錄'
        q = f"[{subj}] {topic}"
        ans = "請在閃卡特訓中進行實體阻力打字練習。"
        box = r['box'] if r['box'] else 1
        st = 'mastered' if r['status'] == 'mastered' else 'pending'

        c.execute("""
            INSERT OR IGNORE INTO review_index_current
            (item_id, subject, topic, question, answer, box_level, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (iid, subj, topic, q, ans, box, st))
        migrated += 1

    conn.commit()
    conn.close()
    print("SUCCESS: Migrated", migrated, "records to review_index_current!")

if __name__ == "__main__":
    migrate()
