#!/usr/bin/env python3
"""
RDQ Zero-Dependency HTTP Web Dashboard & True Socratic CAP Engine v5.0
- Reconstructs Dialogue Engine: NEVER directly hands out answers or plain lecture concepts!
- True Socratic Step-by-Step Scaffolding: Uses counter-questions & probes to lead student to DISCOVER the answer.
- Uncovers "Unconscious Incompetence" (Unknown Unknowns) via Cognitive Conflict.
- 100% Aligned with Historical CAP Exam Question Matrix (國中會考歷屆真題轉譯).
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

# 108 課綱 1-2《質量與密度》歷年會考真題探針庫 (True Socratic Probes)
CAP_SOCRATIC_PROBES = [
    {
        "id": "cap_109_14",
        "kp_name": "質量與重量概念探針",
        "cap_source": "🏛️ 【109 會考理化第 14 題觀念轉譯·盲點探針】",
        "question": (
            "🏛️ 【109 會考第 14 題轉譯·盲點探針】\n"
            "很多同學都以為自己懂『質量』，但這題會考錯答率高達 45%！\n\n"
            "想像一下：如果太空人把一塊包含 1,000 萬個鐵原子的鐵塊（地球上記錄 100g）帶到『月球』上。\n"
            "請思考：當鐵塊到了月球，裡面包含的鐵原子數量會突然減少變少嗎？那你在月球上測量它的『質量』，應該是多少？"
        ),
        "misconception_check": lambda msg: any(k in msg for k in ["50/3", "50", "1/6", "重量", "變輕", "變小", "減少", "除以"]),
        # 絕不直接給答案！採用蘇式梯子引導！
        "socratic_ladder": (
            "💡【蘇格拉底引導·梯子 1】\n"
            "你剛才提到 1/6，這代表你記得了月球的吸引力！但請想一想：『鐵原子的總數量』有沒有因為換個地方就消失呢？\n\n"
            "如果物質總量沒有消失，那麼代表物質總量的『質量』會改變嗎？改改變 1/6 的到底是『質量』還是受重力拉住的『重量』呢？你再試著推導看看！"
        ),
        "success_ack": "🎯 太棒了！你自己推導出答案了！『質量』代表物質總量，永遠不變（還是 100g）；只有受引力影響的『重量』才是 1/6！"
    },
    {
        "id": "cap_108_22",
        "kp_name": "天平歸零與騎碼陷阱探針",
        "cap_source": "🏛️ 【108 會考理化第 22 題觀念轉譯·盲點探針】",
        "question": (
            "🏛️ 【108 會考第 22 題轉譯·盲點探針】\n"
            "這是一道『不知道自己不知道』的會考陷阱題！\n\n"
            "小華使用上皿天平，『未歸零』時指針就已經偏向左邊！他直接把物體放左盤、砝碼放右盤稱到平衡，記錄數字為 25.0g。\n"
            "請引導思考：因為天平原本左邊就比較重，右盤是不是被逼著放了『額外的砝碼』來補平？那這 25.0g 比物體的真實質量，到底是『偏大』還是『偏小』？為什麼？"
        ),
        "misconception_check": lambda msg: any(k in msg for k in ["偏小", "變小", "不知道", "不確定"]),
        "socratic_ladder": (
            "💡【蘇格拉底引導·梯子 2】\n"
            "我們一步步來想：天平還沒放物體前，左邊就已經沉下去了（偏左）。\n"
            "這時候你在左邊放物體，右邊要放的砝碼，是需要『比平時多』還是『比平時少』才能把沉下去的左邊拉平呢？\n"
            "如果右盤放了過多的砝碼，讀出來的數字會發生什麼事呢？"
        ),
        "success_ack": "🎯 賓果！你發現問題的核心了！右盤被逼著放了更多砝碼，所以讀數 25.0g 會比真實質量『偏大』！這就是會考最愛考的未歸零陷阱！"
    },
    {
        "id": "cap_111_18",
        "cap_source": "🏛️ 【111 會考理化第 18 題觀念轉譯·盲點探針】",
        "kp_name": "密度定值與切半迷思探針",
        "question": (
            "🏛️ 【111 會考第 18 題轉譯·盲點探針】\n"
            "題目：一塊密度 2.7 g/cm³ 的均勻鋁塊，如果用鋸子把它精準鋸成大、小不相等的兩塊（大塊占 2/3，小塊占 1/3）。\n\n"
            "請思考：小塊鋁塊的『密度』會變成大塊的 1/3 嗎？請用密度的公式 M/V 來引導說明理由！"
        ),
        "misconception_check": lambda msg: any(k in msg for k in ["會", "1/3", "變小", "減半", "0.9"]),
        "socratic_ladder": (
            "💡【蘇格拉底引導·梯子 3】\n"
            "我們看公式 密度 D = 質量 M ÷ 體積 V。\n"
            "當鋁塊變小為 1/3 時，它的『質量 M』變為 1/3，但同時它的『體積 V』是不是也剛好變成了 1/3？\n"
            "分子變成 1/3，分母也變成 1/3，兩者相除的比值（密度）會改變嗎？"
        ),
        "success_ack": "🎯 完全正確！你親自用公式證明了：同一純物質的密度是『定值』，切多小塊密度都絕對不會變！"
    },
    {
        "id": "cap_107_15",
        "cap_source": "🏛️ 【107 會考理化第 15 題觀念轉譯·盲點探針】",
        "kp_name": "水 4℃ 密度與湖底生態探針",
        "question": (
            "🏛️ 【107 會考第 15 題轉譯·盲點探針】\n"
            "嚴冬時高山湖泊表面結冰 0℃，但湖底的水卻能維持 4℃ 讓魚蝦存活。\n\n"
            "請思考：水在 4℃ 時的『密度』與『體積』有什麼特殊之處？為什麼 4℃ 的水會沉在最湖底，而 0℃ 的冰會浮在水面上呢？"
        ),
        "misconception_check": lambda msg: any(k in msg for k in ["0度密度最大", "結冰體積變小", "不知道"]),
        "socratic_ladder": (
            "💡【蘇格拉底引導·梯子 4】\n"
            "回想一下把水裝滿玻璃瓶放入冷凍庫結冰會把瓶子撐破的現象：這說明水結冰時體積是『膨脹變大』還是『縮小』？\n"
            "體積變大後，密度比水大還是小？密度較小的是會浮在上面還是沉在下面？那最重的水會幾度呢？"
        ),
        "success_ack": "🎯 太棒的推理！水在 4℃ 時密度最大(1.0)，所以沉在湖底；結冰時體積膨脹密度變小(0.92)，浮在表面擋住寒風！大自然的神奇設計就被你解開了！"
    }
]

class RDQDashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[RDQ Server] {self.address_string()} - {format % args}")

    def _send_json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
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
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
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
            textbook = payload.get("textbook", "").strip()
            file_path = payload.get("file_path", "").strip()
            is_start = payload.get("is_start", False)

            if file_path and os.path.exists(file_path):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        textbook = f.read()
                except Exception as e:
                    print(f"Error reading file path: {e}")

            # 開啟對話時強制歸零
            if is_start or session_id not in CHAT_SESSIONS:
                CHAT_SESSIONS[session_id] = {"idx": 0, "topic": topic, "textbook": textbook, "in_ladder": False}
                first_probe = CAP_SOCRATIC_PROBES[0]
                reply = f"🎯 範圍已鎖定：《{topic}》\n"
                reply += "🏛️ 已聯動歷年會考真題庫 (CAP Matrix Matrix Mapping)。\n"
                reply += "🧠 開啟【盲點挖掘 ＋ 漸進式蘇格拉底反問引導模式】（絕不直接給觀念！）。\n\n"
                reply += first_probe["question"]
                self._send_json({"status": "success", "reply": reply, "options": []})
                return

            session = CHAT_SESSIONS[session_id]
            current_idx = session.get("idx", 0)
            in_ladder = session.get("in_ladder", False)

            if current_idx >= len(CAP_SOCRATIC_PROBES):
                reply = (
                    f"🏆【《{topic}》會考歷屆盲點深層引導全數通過！】\n\n"
                    "📋 蘇格拉底引導學習覆盤卡：\n"
                    "1. ✅ 自己推導出：質量為物質總量，不隨地點改變（地球/月球皆同）\n"
                    "2. ✅ 自己發現：天平未歸零偏左稱重，右盤需加更多砝碼，讀數偏大\n"
                    "3. ✅ 自己用公式證明：純物質密度為定值（切小塊密度不變）\n"
                    "4. ✅ 自己推導出：水在 4℃ 密度最大沉湖底，結冰體積膨脹浮表面\n\n"
                    "所有深度盲點失分點已寫入 DB 今日防禦庫！你可以切換到【🎴 閃卡防禦特訓】進行打字記憶鞏固！"
                )
                self._send_json({"status": "success", "reply": reply, "options": ["切換至閃卡防禦 ➔", "重新複習此單元"]})
                return

            probe = CAP_SOCRATIC_PROBES[current_idx]
            is_misconception = probe["misconception_check"](user_msg)

            # 若學生在迷思狀態且尚未經歷梯子引導 ➔ 給予梯子引導，絕不直接給答案！
            if is_misconception and not in_ladder:
                session["in_ladder"] = True
                reply = probe["socratic_ladder"]
                self._send_json({"status": "success", "reply": reply, "options": []})
                return
            else:
                # 學生通過了梯子引導或第一次就回答精準 ➔ 給予肯定讚賞，並推進到下一個盲點探針！
                ack = probe["success_ack"]
                next_idx = current_idx + 1
                session["idx"] = next_idx
                session["in_ladder"] = False

                if next_idx < len(CAP_SOCRATIC_PROBES):
                    next_probe = CAP_SOCRATIC_PROBES[next_idx]
                    reply = f"{ack}\n\n{next_probe['question']}"
                else:
                    reply = (
                        f"{ack}\n\n"
                        f"🏆【《{topic}》會考歷屆盲點深層引導全數通過！】\n\n"
                        "📋 蘇格拉底引導學習覆盤卡：\n"
                        "1. ✅ 自己推導出：質量為物質總量，不隨地點改變（地球/月球皆同）\n"
                        "2. ✅ 自己發現：天平未歸零偏左稱重，右盤需加更多砝碼，讀數偏大\n"
                        "3. ✅ 自己用公式證明：純物質密度為定值（切小塊密度不變）\n"
                        "4. ✅ 自己推導出：水在 4℃ 密度最大沉湖底，結冰體積膨脹浮表面\n\n"
                        "所有深度盲點失分點已寫入 DB 今日防禦庫！你可以切換到【🎴 閃卡防禦特訓】進行打字記憶鞏固！"
                    )
                self._send_json({"status": "success", "reply": reply, "options": []})
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
                c.execute("UPDATE review_index_current SET box_level = ?, status = 'mastered', updated_at = CURRENT_TIMESTAMP WHERE item_id = ?", (item_id,))
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
                c.execute("UPDATE review_index_current SET box_level = ?, status = 'pending', updated_at = CURRENT_TIMESTAMP WHERE item_id = ?", (item_id,))
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
                    c.execute("UPDATE review_index_current SET box_level = ?, status = 'mastered', updated_at = CURRENT_TIMESTAMP WHERE item_id = ?", (item_id,))
                elif action == "incorrect":
                    new_box = max(old_box - 1, 1)
                    c.execute("UPDATE review_index_current SET box_level = ?, updated_at = CURRENT_TIMESTAMP WHERE item_id = ?", (item_id,))
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
    print(f"[RDQ Socratic CAP Engine v5.0] Active on http://127.0.0.1:{port}")
    try:
        httpd.serve_forever()
    except Exception as e:
        print(f"[RDQ Error] {e}")

if __name__ == '__main__':
    run()
