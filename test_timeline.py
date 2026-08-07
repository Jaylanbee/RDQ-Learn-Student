import sqlite3
import requests
import time

conn = sqlite3.connect("data/review_index.db")
conn.execute("""
    INSERT INTO student_cognitive_profile (subject, topic, weakness_summary, loss_reason, occurred_count, is_resolved, created_at, updated_at)
    VALUES ('數學', '國二上 1-1 乘法公式', '-(a-b)² 負號分配律變號陷阱', '概念錯誤', 2, 0, '2026-08-01T10:00:00Z', '2026-08-05T10:00:00Z')
""")
conn.commit()
conn.close()

time.sleep(1) # wait for uvicorn
resp = requests.get("http://127.0.0.1:8000/api/student/timeline")
print(resp.json())
