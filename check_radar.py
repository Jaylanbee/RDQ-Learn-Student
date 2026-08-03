#!/usr/bin/env python3
import sqlite3, os, json

DB_PATH = os.path.expanduser(r"~\.education_ecosystem\review_index.db")

def check_radar():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    subjects = ["國文", "英語", "數學", "自然", "社會"]
    radar = {}

    print("=== 資料庫真實數據計算過程 ===")
    for s in subjects:
        total = conn.execute("SELECT COUNT(*) FROM review_index_current WHERE subject=?", (s,)).fetchone()[0]
        mastered = conn.execute("SELECT COUNT(*) FROM review_index_current WHERE subject=? AND status='mastered'", (s,)).fetchone()[0]
        score = round(((mastered + 1) / (total + 2)) * 100)
        radar[s] = score
        print(f"【{s}】總題目數: {total} 題 | 已精通(mastered): {mastered} 題  ==>  Laplace 計算得分: ({mastered}+1)/({total}+2) = {score}%")

    print("\nAPI `/api/radar` 回傳之真實 JSON 資料:")
    print(json.dumps(radar, ensure_ascii=False, indent=2))
    conn.close()

if __name__ == "__main__":
    check_radar()
