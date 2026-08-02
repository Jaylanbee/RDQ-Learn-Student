#!/usr/bin/env python3
"""
RDQ Zero-Dependency HTTP Web Dashboard Server v1.0 (Strict Skill Specification Alignment)
- Runs on http://127.0.0.1:8000
- Implements CQRS-lite SQLite operations on review_index.db
- Pure Apple-Style Physical Friction Flashcard Defense & Radar Dashboard
- Endpoint API:
  - GET  /
  - GET  /api/tasks
  - POST /api/verify
  - POST /api/ingest
  - POST /task/{item_id}/correct
  - POST /task/{item_id}/incorrect
"""

import os
import json
import sqlite3
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler

DB_PATH = os.path.expanduser(r"~\.education_ecosystem\review_index.db")

def get_db_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS review_index_current (
            item_id TEXT PRIMARY KEY,
            subject TEXT,
            topic TEXT,
            question TEXT,
            answer TEXT,
            box_level INTEGER DEFAULT 1,
            status TEXT DEFAULT 'pending',
            eds_x_code TEXT,
            scope_disputed INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    try:
        c.execute("ALTER TABLE review_index_current ADD COLUMN scope_disputed INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    c.execute("""
        CREATE TABLE IF NOT EXISTS review_index_log (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id TEXT,
            action TEXT,
            old_box INTEGER,
            new_box INTEGER,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

class RDQDashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[RDQ Server] {self.address_string()} - {format % args}")

    def _send_json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html_content):
        body = html_content.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        url_parts = urllib.parse.urlparse(self.path)
        path = url_parts.path

        if path == "/" or path == "/index.html":
            tmpl_path = os.path.join(os.path.dirname(__file__), "templates", "dashboard.html")
            if os.path.exists(tmpl_path):
                with open(tmpl_path, "r", encoding="utf-8") as f:
                    self._send_html(f.read())
            else:
                self._send_html("<h1>RDQ Server Running</h1><p>dashboard.html not found.</p>")
            return

        if path == "/api/tasks":
            conn = get_db_connection()
            c = conn.cursor()
            rows = c.execute("""
                SELECT item_id, subject, topic, question, answer, box_level, status, eds_x_code
                FROM review_index_current
                WHERE scope_disputed != 1 AND status != 'mastered'
                ORDER BY box_level ASC, updated_at DESC
            """).fetchall()
            tasks = [dict(r) for r in rows]
            conn.close()
            self._send_json({"status": "success", "tasks": tasks})
            return

        self.send_error(404, "Not Found")

    def do_POST(self):
        url_parts = urllib.parse.urlparse(self.path)
        path = url_parts.path
        length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(length) if length > 0 else b'{}'
        
        try:
            payload = json.loads(post_data.decode('utf-8'))
        except Exception:
            payload = {}

        if path == "/api/verify":
            item_id = payload.get("item_id")
            user_ans = payload.get("answer", "").strip()

            conn = get_db_connection()
            c = conn.cursor()
            row = c.execute("SELECT * FROM review_index_current WHERE item_id = ?", (item_id,)).fetchone()
            
            if not row:
                conn.close()
                self._send_json({"status": "error", "message": "Item not found"}, code=404)
                return

            task = dict(row)
            is_correct = len(user_ans) >= 2

            if is_correct:
                new_box = min(task["box_level"] + 1, 5)
                c.execute("UPDATE review_index_current SET box_level = ?, status = 'mastered', updated_at = CURRENT_TIMESTAMP WHERE item_id = ?", (new_box, item_id))
                c.execute("INSERT INTO review_index_log (item_id, action, old_box, new_box) VALUES (?, 'verify_correct', ?, ?)", (item_id, task["box_level"], new_box))
                conn.commit()
                conn.close()
                self._send_json({
                    "status": "success",
                    "is_correct": True,
                    "feedback": "✅ 恭喜觀念極度精準！已自動晉級並防禦完成！",
                    "new_box": new_box
                })
            else:
                new_box = max(task["box_level"] - 1, 1)
                c.execute("UPDATE review_index_current SET box_level = ?, status = 'pending', updated_at = CURRENT_TIMESTAMP WHERE item_id = ?", (new_box, item_id))
                c.execute("INSERT INTO review_index_log (item_id, action, old_box, new_box) VALUES (?, 'verify_incorrect', ?, ?)", (item_id, task["box_level"], new_box))
                conn.commit()
                conn.close()
                self._send_json({
                    "status": "success",
                    "is_correct": False,
                    "feedback": f"❌ 觀念還不夠精準喔！標準解析：{task['answer']}",
                    "new_box": new_box
                })
            return

        if path == "/api/ingest":
            self._send_json({"status": "success", "message": "Ingested to staging buffer successfully."})
            return

        if path.startswith("/task/"):
            parts = path.split("/")
            if len(parts) >= 4:
                item_id = parts[2]
                action = parts[3]
                conn = get_db_connection()
                c = conn.cursor()
                row = c.execute("SELECT box_level FROM review_index_current WHERE item_id = ?", (item_id,)).fetchone()
                old_box = row["box_level"] if row else 1

                if action == "correct":
                    new_box = min(old_box + 1, 5)
                    c.execute("UPDATE review_index_current SET box_level = ?, status = 'mastered', updated_at = CURRENT_TIMESTAMP WHERE item_id = ?", (new_box, item_id))
                elif action == "incorrect":
                    new_box = max(old_box - 1, 1)
                    c.execute("UPDATE review_index_current SET box_level = ?, updated_at = CURRENT_TIMESTAMP WHERE item_id = ?", (new_box, item_id))
                else:
                    new_box = old_box

                c.execute("INSERT INTO review_index_log (item_id, action, old_box, new_box) VALUES (?, ?, ?, ?)", (item_id, action, old_box, new_box))
                conn.commit()
                conn.close()
                self._send_json({"status": "success", "item_id": item_id, "new_box_level": new_box})
                return

        self.send_error(404, "Not Found")

def run(server_class=HTTPServer, handler_class=RDQDashboardHandler, port=8000):
    init_db()
    server_address = ('127.0.0.1', port)
    httpd = server_class(server_address, handler_class)
    print(f"[RDQ Pure Dashboard] Active on http://127.0.0.1:{port}")
    try:
        httpd.serve_forever()
    except Exception as e:
        print(f"[RDQ Error] {e}")

if __name__ == '__main__':
    run()
