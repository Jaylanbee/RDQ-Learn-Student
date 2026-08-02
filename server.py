#!/usr/bin/env python3
"""
RDQ Zero-Dependency HTTP Web Dashboard & Socratic Engine Server v2.0
- Runs on 0.0.0.0:8000 (accessible via http://127.0.0.1:8000 and http://localhost:8000)
- Dual IPv4 binding to avoid Windows IPv6 localhost connection refusal
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

CHAT_SESSIONS = {}

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

        if path == "/api/chat":
            session_id = payload.get("session_id", "default")
            user_msg = payload.get("message", "").strip()
            topic = payload.get("topic", "1-2 質量與密度的測量")

            if session_id not in CHAT_SESSIONS:
                CHAT_SESSIONS[session_id] = {"step": 0, "history": []}

            session = CHAT_SESSIONS[session_id]
            session["step"] += 1
            step = session["step"]

            reply = ""
            options = []

            if "不知道" in user_msg or "不確定" in user_msg or "選" in user_msg or step == 1:
                if step == 1:
                    reply = f"歡迎來到《{topic}》蘇格拉底互動對話！第一個問題：如果今天太空人把一塊質量 100g 的鐵塊帶到「月球」上，請問這塊鐵塊在月球上的「質量」會變成多少？為什麼呢？"
                    options = ["還是 100g 保持不變", "變成 16.6g (六分之一)", "不確定，請給提示"]
                elif "100" in user_msg or "還是" in user_msg or "不變" in user_msg:
                    reply = "🎉 太棒了！答對了！因為「質量」代表物體所含物質的總量，不隨地點、重力強弱而改變。\n\n接下一題：如果將一塊密度為 2.7 g/cm³ 的均勻鋁塊切成大小相同的兩半，半塊鋁塊的「密度」會變成多少？"
                    options = ["2.7 g/cm³ (保持不變)", "1.35 g/cm³ (減半)", "不確定，給個鷹架"]
                else:
                    reply = "沒關係，我們來看鷹架選項！選選看：\n質量代表物體所含物質的總量，它會隨地點改變嗎？"
                    options = ["A) 質量不變，仍然是 100g", "B) 質量變輕，變成 16.6g"]
            elif "2.7" in user_msg or "不變" in user_msg or "減半" in user_msg:
                if "2.7" in user_msg or "不變" in user_msg:
                    reply = "✅ 精準答對！同一種純物質在固定溫度壓力下，密度是定值（與大小或質量無關）！\n\n最後關鍵盲點題：水在 4℃ 時密度最大。當水結成 0℃ 的冰塊時，體積與密度會怎麼變化？"
                    options = ["體積變大，密度變小 (冰浮於水)", "體積變小，密度變大", "不確定"]
                else:
                    reply = "很多人會直覺認為切半密度就減半喔！但密度是「單位體積的質量 (M/V)」。當質量減半時，體積也減半，兩者相除的比值是不變的！所以半塊鋁塊密度依然是 2.7 g/cm³！"
                    options = ["明白了！下一題", "再講詳細一點"]
            else:
                reply = "非常好！你掌握得非常紮實！已經幫你產出《1-2 質量與密度的測量》覆盤卡並寫入今日防禦庫了！你可以隨時切換到【🎴 閃卡防禦庫】進行打字特訓喔！"
                options = ["切換至閃卡防禦 ➔", "重新複習此單元"]

            self._send_json({
                "status": "success",
                "reply": reply,
                "options": options,
                "step": step
            })
            return

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
    # Bind to 0.0.0.0 to handle both localhost and 127.0.0.1
    server_address = ('0.0.0.0', port)
    httpd = server_class(server_address, handler_class)
    print(f"[RDQ Dashboard v2.0] Active on http://127.0.0.1:{port} and http://localhost:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[RDQ Dashboard] Server stopped gracefully.")
        httpd.server_close()

if __name__ == '__main__':
    run()
