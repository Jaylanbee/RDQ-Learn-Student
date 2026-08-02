import os
import json
import sqlite3
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

DB_PATH = os.path.expanduser(r"~\.education_ecosystem\review_index.db")
TEMPLATE_PATH = r"d:\2026AI_agent\RQD\templates\dashboard.html"

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS review_index_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id TEXT NOT NULL,
        subject TEXT,
        topic TEXT,
        action TEXT NOT NULL,
        box_level INTEGER,
        loss_reason TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS review_index_current (
        item_id TEXT PRIMARY KEY,
        subject TEXT NOT NULL,
        topic TEXT NOT NULL,
        question TEXT NOT NULL,
        answer TEXT NOT NULL,
        box_level INTEGER DEFAULT 1,
        status TEXT DEFAULT 'pending',
        eds_x_code TEXT,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    cursor.execute("SELECT COUNT(*) FROM review_index_current")
    if cursor.fetchone()[0] == 0:
        sample_data = [
            ("sci_ch3_001", "自然", "光合作用", "光合作用中的暗反應主要利用何種物質合成葡萄糖？", "利用光反應產生的 ATP、NADPH 與二氧化碳合成葡萄糖。", 2, "pending", "BIO_3_1"),
            ("math_ch2_002", "數學", "一元二次方程式", "一元二次方程式 ax^2 + bx + c = 0 的判別式為？", "判別式為 Δ = b^2 - 4ac", 1, "pending", "MATH_2_2"),
            ("chi_ch1_003", "國文", "聲音鐘", "聲音鐘一文中，作者將街巷間小販的叫賣聲比喻為？", "比喻為水草般柔韌搖曳的聲音、時間的鐘聲。", 3, "pending", "CHI_1_1"),
        ]
        cursor.executemany("""
            INSERT INTO review_index_current (item_id, subject, topic, question, answer, box_level, status, eds_x_code)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, sample_data)
        
    conn.commit()
    conn.close()

init_db()

class RDQHandler(BaseHTTPRequestHandler):
    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, content_str, status=200):
        body = content_str.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path == "/" or path == "/dashboard":
            if os.path.exists(TEMPLATE_PATH):
                with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
                    self.send_html(f.read())
            else:
                self.send_html("<h1>Dashboard template not found</h1>", 404)
        elif path == "/api/tasks":
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM review_index_current ORDER BY box_level ASC, updated_at DESC")
            rows = cursor.fetchall()
            conn.close()
            self.send_json({"tasks": [dict(r) for r in rows]})
        else:
            self.send_json({"error": "Not Found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else "{}"
        try:
            payload = json.loads(post_data)
        except Exception:
            payload = {}

        if path == "/api/ingest":
            item_id = f"ingest_{os.urandom(4).hex()}"
            subject = payload.get("subject", "通用")
            topic = payload.get("topic", "外部錯題")
            question = payload.get("question", "未知題目")
            answer = payload.get("answer", "待分析解答")
            
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO review_index_current (item_id, subject, topic, question, answer, box_level, status)
                VALUES (?, ?, ?, ?, ?, 1, 'staged')
            """, (item_id, subject, topic, question, answer))
            cursor.execute("""
                INSERT INTO review_index_log (item_id, subject, topic, action, box_level)
                VALUES (?, ?, ?, 'ingest', 1)
            """, (item_id, subject, topic))
            conn.commit()
            conn.close()
            self.send_json({"status": "success", "item_id": item_id})

        elif path.startswith("/task/") and path.endswith("/correct"):
            item_id = path.split("/")[2]
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT box_level, subject, topic FROM review_index_current WHERE item_id = ?", (item_id,))
            row = cursor.fetchone()
            if row:
                curr_box, subject, topic = row
                new_box = min(curr_box + 1, 5)
                cursor.execute("UPDATE review_index_current SET box_level = ?, status = 'mastered', updated_at = CURRENT_TIMESTAMP WHERE item_id = ?", (new_box, item_id))
                cursor.execute("INSERT INTO review_index_log (item_id, subject, topic, action, box_level) VALUES (?, ?, ?, 'promote', ?)", (item_id, subject, topic, new_box))
                conn.commit()
                conn.close()
                self.send_json({"status": "promoted", "new_box_level": new_box})
            else:
                conn.close()
                self.send_json({"error": "Item not found"}, 404)

        elif path.startswith("/task/") and path.endswith("/incorrect"):
            item_id = path.split("/")[2]
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT box_level, subject, topic FROM review_index_current WHERE item_id = ?", (item_id,))
            row = cursor.fetchone()
            if row:
                curr_box, subject, topic = row
                new_box = max(1, curr_box - 2) if curr_box >= 4 else max(1, curr_box - 1)
                cursor.execute("UPDATE review_index_current SET box_level = ?, status = 'needs_review', updated_at = CURRENT_TIMESTAMP WHERE item_id = ?", (new_box, item_id))
                cursor.execute("INSERT INTO review_index_log (item_id, subject, topic, action, box_level) VALUES (?, ?, ?, 'demote', ?)", (item_id, subject, topic, new_box))
                conn.commit()
                conn.close()
                self.send_json({"status": "demoted", "new_box_level": new_box})
            else:
                conn.close()
                self.send_json({"error": "Item not found"}, 404)

        else:
            self.send_json({"error": "Not Found"}, 404)

def run(port=8000):
    server_address = ('127.0.0.1', port)
    httpd = HTTPServer(server_address, RDQHandler)
    print(f"RDQ Apple-Style Web Dashboard Server running on http://127.0.0.1:{port}")
    httpd.serve_forever()

if __name__ == '__main__':
    run()
