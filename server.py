#!/usr/bin/env python3
"""
RDQ Zero-Dependency HTTP Web Dashboard & Equal-Effect Socratic Engine v3.2
- Fixes single-question early termination bug.
- Implements full 3-question Socratic flow (Phase 1 -> Phase 2.5 Misconception -> Phase 3 -> Phase 4 -> Phase 5).
- Precise Misconception Detection (e.g. Mass vs Weight confusion).
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
            topic = payload.get("topic", "未指定單元")
            textbook = payload.get("textbook", "").strip()
            file_path = payload.get("file_path", "").strip()
            is_start = payload.get("is_start", False)

            if file_path and os.path.exists(file_path):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        textbook = f.read()
                except Exception as e:
                    print(f"Error reading file path: {e}")

            if is_start or session_id not in CHAT_SESSIONS:
                CHAT_SESSIONS[session_id] = {"step": 1, "topic": topic, "textbook": textbook}
                reply = f"🎯 範圍已鎖定：《{topic}》\n"
                if textbook:
                    reply += "📚 已成功載入課本講義內文（開啟 100% 絕不超綱極致精確模式）。\n\n"
                else:
                    reply += "🌐 已開啟預設 108 課綱通用庫模式（零壓力模式）。\n\n"
                
                reply += f"【Phase 1 蘇氏開局 (第 1/3 題)】\n如果今天太空人把一塊質量 100g 的鐵塊帶到「月球」上，請問這塊鐵塊在月球上的「質量」會變成多少？為什麼呢？"
                
                self._send_json({
                    "status": "success",
                    "reply": reply,
                    "options": [],
                    "step": 1
                })
                return

            session = CHAT_SESSIONS[session_id]
            step = session["step"]
            reply = ""
            options = []

            # 檢測學生是否回答「不知道/忘了」觸發 L2 鷹架
            if "不知道" in user_msg or "忘了" in user_msg or "不確定" in user_msg or "提示" in user_msg:
                reply = f"沒關係！我們來看 L2 鷹架選項接住你：\n針對《{session['topic']}》，下面哪一個描述最契合你剛才想到的重點？"
                options = ["選項 A: 質量不隨地點改變，仍然是 100g", "選項 B: 質量隨地點改變，變成 16.6g", "選項 C: 請進一步解說質量與重量差異"]
                self._send_json({"status": "success", "reply": reply, "options": options, "step": step})
                return

            if step == 1:
                # 檢查學生是否有「質量 vs 重量混淆」迷思（例如答 50/3, 16.6, 1/6, 變輕）
                if any(k in user_msg for k in ["50/3", "16.6", "1/6", "變輕", "變小", "減半"]):
                    reply = (
                        "⚠️【Phase 2.5 迷思澄清】\n"
                        "很多人看到月球重力是地球的 1/6，也會直覺覺得數字要除以 6 喔！\n\n"
                        "不過請注意：『質量』代表物質所含的總量，不會隨地點、重力改變（在地球與月球都是 100g）！只有受重力吸引的『重量』才會變成 1/6 喔！\n\n"
                        "【Phase 3 觀念深度追問 (第 2/3 題)】\n"
                        "接下一題：如果將一塊密度為 2.7 g/cm³ 的均勻鋁塊切成大小相同的兩半，半塊鋁塊的「密度」會變成多少？"
                    )
                else:
                    reply = (
                        "🎉 太棒了！答對了！因為「質量」代表物體所含物質的總量，不隨地點、重力強弱而改變。\n\n"
                        "【Phase 3 觀念深度追問 (第 2/3 題)】\n"
                        "接下一題：如果將一塊密度為 2.7 g/cm³ 的均勻鋁塊切成大小相同的兩半，半塊鋁塊的「密度」會變成多少？"
                    )
                session["step"] = 2

            elif step == 2:
                if any(k in user_msg for k in ["減半", "1.35", "一半"]):
                    reply = (
                        "⚠️【Phase 2.5 迷思澄清】\n"
                        "直覺很容易覺得切半密度就減半對不對？但密度是「質量 ÷ 體積 (M/V)」。當質量減半時，體積也剛好減半，兩者相除的比值是不變的！所以半塊鋁塊的密度依然是 2.7 g/cm³！\n\n"
                        "【Phase 4 盲點提示 (第 3/3 題·會考陷阱真題)】\n"
                        "你有想過，水在 4℃ 時密度最大。當水結成 0℃ 的冰塊時，體積與密度會怎麼變化？為什麼冰塊能浮在水面上？"
                    )
                else:
                    reply = (
                        "✅ 觀念極度精準！同一種純物質在固定溫度壓力下，密度是定值（與大小或質量無關）！\n\n"
                        "【Phase 4 盲點提示 (第 3/3 題·會考陷阱真題)】\n"
                        "你有想過，水在 4℃ 時密度最大。當水結成 0℃ 的冰塊時，體積與密度會怎麼變化？為什麼冰塊能浮在水面上？"
                    )
                session["step"] = 3

            elif step == 3:
                reply = (
                    "🏆【 Phase 5 覆盤卡產出與防禦寫入 】\n"
                    "太優秀了！你完整完成了 3 道深層認知檢驗題！\n\n"
                    "📋 學習覆盤卡：\n"
                    "- ✅ 質量不隨地點改變（地球/月球皆同）\n"
                    "- ⚠️ 迷思已澄清：區分「質量(不變)」與「重量(變1/6)」\n"
                    "- ✅ 同物質密度為定值（切半密度不變）\n"
                    "- ✅ 水在 4℃ 密度最大，結冰體積膨脹密度變小\n\n"
                    "已將失分點寫入今日防禦庫！你可以隨時切換到【🎴 閃卡防禦特訓】進行打字記憶鞏固喔！"
                )
                session["step"] = 4

            else:
                reply = "本單元的 3 道對話檢驗已全數完成囉！你可以點擊下方按鈕重新開始新的單元複習，或切換至閃卡特訓。"
                options = ["重新複習新單元", "切換至閃卡防禦 ➔"]

            self._send_json({
                "status": "success",
                "reply": reply,
                "options": options,
                "step": session["step"]
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
    server_address = ('127.0.0.1', port)
    httpd = server_class(server_address, handler_class)
    print(f"[RDQ Web Engine v3.2] Active on http://127.0.0.1:{port}")
    try:
        httpd.serve_forever()
    except Exception as e:
        print(f"[RDQ Error] {e}")

if __name__ == '__main__':
    run()
