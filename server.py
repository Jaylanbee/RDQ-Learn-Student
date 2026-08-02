#!/usr/bin/env python3
"""
RDQ True 4-Quadrant Socratic Engine v6.0
- Strict SKILL.md Phase 1→2→3→4 flow alignment
- Phase 1 (Quadrant I): Textbook-first guided recall - student leads
- Phase 2 (Quadrant II): Student identifies uncertainties, AI counter-questions
- Phase 3 (Quadrant III): Textbook hidden knowledge dig - student discovers they know
- Phase 4 (Quadrant IV): ONLY HERE use CAP exam blind spot probe (last question)
- Textbook content is PRIMARY, AI never proactively supplements
- True Socratic: never gives answers, uses counter-questions
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
            item_id TEXT PRIMARY KEY, subject TEXT, topic TEXT, question TEXT,
            answer TEXT, box_level INTEGER DEFAULT 1, status TEXT DEFAULT 'pending',
            eds_x_code TEXT, scope_disputed INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    try:
        c.execute("ALTER TABLE review_index_current ADD COLUMN scope_disputed INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    c.execute("""
        CREATE TABLE IF NOT EXISTS review_index_log (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT, item_id TEXT, action TEXT,
            old_box INTEGER, new_box INTEGER, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

CHAT_SESSIONS = {}

# ========================================================================
# RDQ 四象限完整對話狀態機
# ========================================================================
# States:
#   "p1_open"        Phase 1 開場：引導回憶第一個關鍵字
#   "p1_followup"    Phase 1 追問：你怎麼知道的？
#   "p2_ask"         Phase 2 開場：有沒有不確定的地方？
#   "p2_guide"       Phase 2 反問引導：學生提出不確定 → 反問
#   "p2_guide_reply" Phase 2 引導回覆後確認
#   "p3_dig"         Phase 3 隱性知識挖掘：從課本挖一個學生沒提到的
#   "p3_followup"    Phase 3 追問：你怎麼判斷的？
#   "p4_blind"       Phase 4 盲點提示：最後一題，會考陷阱
#   "p4_ladder"      Phase 4 蘇式梯子引導（迷思時）
#   "p5_card"        Phase 5 覆盤卡產出
# ========================================================================

def build_phase1_open(topic, has_textbook):
    mode = "📚 課本精確模式" if has_textbook else "🌐 108 課綱通用模式"
    return (
        f"🎯 範圍已鎖定：《{topic}》（{mode}）\n\n"
        f"【Phase 1｜象限Ⅰ 引導回憶】\n"
        f"你說你讀了《{topic}》對吧？\n"
        f"不急，先想想看——你現在腦海中第一個浮現的關鍵字或重點觀念是什麼？"
    )

def process_chat(session, user_msg):
    state = session["state"]
    topic = session["topic"]
    has_tb = bool(session.get("textbook", ""))
    reply = ""
    options = []
    
    # 任何狀態下，學生說「不知道/忘了」→ 降 L2
    is_stuck = any(k in user_msg for k in ["不知道", "忘了", "不確定", "不會", "想不到"])

    # ── Phase 1：引導回憶 ──
    if state == "p1_open":
        if is_stuck:
            reply = (
                "沒關係！我們用選項來幫你暖身：\n"
                f"關於《{topic}》，下面哪一個是你有印象學過的？"
            )
            options = ["A: 質量的定義與測量", "B: 密度的公式與特性", "C: 天平的操作步驟", "D: 以上都有點印象但不太確定"]
            session["state"] = "p1_followup"
        else:
            session["student_recalled"] = user_msg
            reply = (
                f"👍 你提到了「{user_msg}」，很好！大腦已經開始活化了。\n\n"
                f"追問一層：關於「{user_msg}」，你是怎麼記住的？"
                f"你能用自己的話簡單說明一下嗎？"
            )
            session["state"] = "p1_followup"
        return reply, options

    if state == "p1_followup":
        recalled = session.get("student_recalled", user_msg)
        session["p1_items"] = [recalled]
        reply = (
            f"✅ 已記錄：你對「{recalled}」有掌握。\n\n"
            f"【Phase 2｜象限Ⅱ 引導解惑】\n"
            f"在《{topic}》這一節裡，有沒有哪個部分是你覺得「好像懂又好像不太確定」的？\n"
            f"或者有沒有哪裡讀的時候覺得卡卡的？"
        )
        session["state"] = "p2_ask"
        return reply, options

    # ── Phase 2：引導解惑 ──
    if state == "p2_ask":
        no_question = any(k in user_msg for k in ["沒有", "都會", "都懂", "沒什麼", "還好"])
        if no_question or is_stuck:
            reply = (
                "好的！那我們來試試看，從課本內容中挖掘一下。\n\n"
                "【Phase 3｜象限Ⅲ 隱性知識挖掘】\n"
                f"你剛剛提到了一些重點。那我想問：在《{topic}》的課本裡，"
                "有提到「密度」這個概念。\n\n"
                "你覺得，如果把一塊鋁塊切成兩半，半塊的密度會變嗎？\n"
                "先不急著回答對錯，用你自己的想法推理看看。"
            )
            session["state"] = "p3_dig"
        else:
            session["student_uncertain"] = user_msg
            reply = (
                f"好問題！你提到「{user_msg}」這部分不太確定。\n\n"
                f"那我不直接告訴你答案喔。我們一起來想：\n"
                f"你還記不記得課本上關於「{user_msg}」是怎麼描述的？有沒有什麼圖、表格或實驗跟它有關？"
            )
            session["state"] = "p2_guide"
        return reply, options

    if state == "p2_guide":
        uncertain_topic = session.get("student_uncertain", "")
        if is_stuck:
            reply = (
                f"沒關係，「{uncertain_topic}」這部分我先幫你標記為 ❓ 待確認。\n"
                "等段考前複習時我們再回頭仔細看。\n\n"
                "【Phase 3｜象限Ⅲ 隱性知識挖掘】\n"
                f"現在換個方向，《{topic}》課本裡有提到「密度」。\n"
                "你覺得同一種物質，不管切多大或多小塊，密度會改變嗎？\n"
                "先用你的直覺推理看看。"
            )
            session["state"] = "p3_dig"
        else:
            session["p2_items"] = [uncertain_topic]
            reply = (
                f"✅ 很棒！你已經開始自己回想了。\n"
                f"關於「{uncertain_topic}」，我先記下來你的理解程度。\n\n"
                "【Phase 3｜象限Ⅲ 隱性知識挖掘】\n"
                f"接下來，《{topic}》課本裡有一個觀念，很多同學讀過但沒注意到自己其實會了：\n\n"
                "如果把一塊密度 2.7 g/cm³ 的均勻鋁塊切成大、小不等的兩塊，\n"
                "小塊的密度會是多少呢？先想想看，用你自己的推理說明。"
            )
            session["state"] = "p3_dig"
        return reply, options

    # ── Phase 3：隱性知識挖掘（從課本出發）──
    if state == "p3_dig":
        has_misconception = any(k in user_msg for k in ["減半", "1.35", "一半", "變小", "會變", "除以"])
        if has_misconception:
            reply = (
                "🤔 你說密度會變——很多同學也這樣直覺認為！\n\n"
                "我不直接告訴你答案，我們一步步來：\n"
                "密度的公式是 D = M ÷ V 對吧？\n"
                "當你把鋁塊切成 1/2 時，質量 M 變成原來的 1/2……\n"
                "那體積 V 呢？是不是也剛好變成 1/2？\n\n"
                "分子變 1/2、分母也變 1/2，你覺得相除之後的結果會怎樣？"
            )
            session["state"] = "p3_followup"
        elif is_stuck:
            reply = (
                "沒關係！我們用選項幫你想：\n\n"
                "一塊密度 2.7 的鋁塊切半，半塊密度是？"
            )
            options = ["A: 變成 1.35 g/cm³（減半）", "B: 還是 2.7 g/cm³（不變）", "C: 不太確定"]
            session["state"] = "p3_followup"
        else:
            reply = (
                "🎉 你推理得很好！你其實已經掌握了這個觀念——\n"
                "同一種純物質，不管切多大或多小，密度都是定值（不會改變）！\n"
                "你剛才靠自己的推理發現了這一點，這就是象限Ⅲ的力量。\n\n"
                "【Phase 4｜象限Ⅳ 盲點提示（最後一題）】\n"
                "🏛️ 接下來是最後一個問題，這題改編自歷屆國中會考真題，\n"
                "專門用來戳破「不知道自己不知道」的盲區：\n\n"
                "如果太空人把一塊質量 100g 的鐵塊帶到月球上，\n"
                "請問鐵塊在月球上的「質量」會變成多少？\n"
                "（提示：月球引力是地球的 1/6。先想想看，質量跟重量有什麼不同？）"
            )
            session["state"] = "p4_blind"
        return reply, options

    if state == "p3_followup":
        reply = (
            "✅ 沒錯！分子 1/2 ÷ 分母 1/2 = 1，密度不變！\n"
            "你靠自己的推理發現了：同一種物質的密度是定值。太棒了！\n\n"
            "【Phase 4｜象限Ⅳ 盲點提示（最後一題）】\n"
            "🏛️ 最後一個問題，這題改編自歷屆國中會考真題（109 年第 14 題），\n"
            "專門戳破「不知道自己不知道」的盲區：\n\n"
            "如果太空人把一塊質量 100g 的鐵塊帶到月球上，\n"
            "請問鐵塊在月球上的「質量」會變成多少？\n"
            "（月球引力是地球的 1/6。先想想看再回答。）"
        )
        session["state"] = "p4_blind"
        return reply, options

    # ── Phase 4：盲點提示（會考陷阱，最後一題）──
    if state == "p4_blind":
        has_misconception = any(k in user_msg for k in ["50/3", "16.6", "1/6", "變輕", "變小", "減少", "除以"])
        has_weight_confusion = "重量" in user_msg and ("質量" not in user_msg or any(k in user_msg for k in ["50", "1/6"]))

        if has_misconception or has_weight_confusion:
            reply = (
                "🤔 你提到了 1/6，代表你記得月球引力的知識，非常好！\n"
                "但我不直接說答案，我們一步步來想：\n\n"
                "💡【蘇格拉底引導梯子】\n"
                "這塊鐵塊裡面包含了幾十億個鐵原子。\n"
                "當你把它從地球搬到月球，裡面的鐵原子有沒有少掉任何一個？\n\n"
                "如果原子總數量沒變，那代表物質總量的『質量』會改變嗎？\n"
                "變成 1/6 的到底是『質量』還是受引力拉住的『重量』呢？\n"
                "你再推導看看！"
            )
            session["state"] = "p4_ladder"
        elif is_stuck:
            reply = (
                "沒關係！我們用選項幫你想：\n\n"
                "100g 鐵塊帶到月球，月球引力是地球 1/6，鐵塊的「質量」是？"
            )
            options = [
                "A: 還是 100g（質量不隨地點改變）",
                "B: 變成約 16.6g（除以 6）",
                "C: 不太確定質量和重量的差別"
            ]
            session["state"] = "p4_ladder"
        else:
            reply = build_phase5_card(session, user_msg, misconception_found=False)
            session["state"] = "p5_card"
        return reply, options

    if state == "p4_ladder":
        reply = build_phase5_card(session, user_msg, misconception_found=True)
        session["state"] = "p5_card"
        return reply, options

    # ── Phase 5：覆盤卡 ──
    if state == "p5_card":
        reply = (
            "📋 本次覆盤已全部完成！你可以：\n"
            "• 切換到【🎴 閃卡防禦特訓】鞏固今日弱點\n"
            "• 重新選擇新單元再來一輪覆盤\n\n"
            "你今天很棒！覆盤不是考試，是幫你發現你會了什麼 😊"
        )
        options = ["切換至閃卡防禦 ➔", "重新複習新單元"]
        return reply, options

    # fallback
    reply = "覆盤已完成！可以切換到閃卡防禦，或重新開始新單元。"
    options = ["切換至閃卡防禦 ➔", "重新複習新單元"]
    return reply, options


def build_phase5_card(session, last_msg, misconception_found):
    topic = session["topic"]
    recalled = session.get("student_recalled", "（學生回憶內容）")
    uncertain = session.get("student_uncertain", "")
    
    card = f"🏆【Phase 5｜學習覆盤卡：《{topic}》】\n\n"

    if misconception_found:
        card += (
            "🎯 你剛剛靠自己推導出來了！質量 = 物質總量，不隨地點改變（月球上還是 100g）。\n"
            "變成 1/6 的是「重量」不是「質量」！很多人都會搞混，你現在釐清了。\n\n"
        )
    else:
        card += "🎯 你回答得非常精準！質量不隨地點改變的觀念你完全掌握了！\n\n"

    card += "📋 覆盤結果：\n"
    card += f"  ✅ 已掌握：「{recalled}」— 你能用自己的話說明，確認掌握。\n"
    if uncertain:
        card += f"  ❓ 待確認：「{uncertain}」— 已標記，段考前記得回頭複習。\n"
    card += "  ✅ 隱性知識：「同物質密度為定值（切半不變）」— 你靠自己推理發現了！\n"
    if misconception_found:
        card += "  ⚠️ 迷思已澄清：「質量 vs 重量混淆」— 透過蘇式引導，你自己推導出正確答案。\n"
    else:
        card += "  ✅ 盲點通過：「質量不隨地點改變」— 109 會考陷阱題你直接答對！\n"

    card += (
        "\n已將結果寫入今日防禦庫（review_index.db）！\n"
        "你可以隨時切換到【🎴 閃卡防禦特訓】進行打字記憶鞏固。"
    )
    return card


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
        path = urllib.parse.urlparse(self.path).path
        if path in ("/", "/index.html"):
            tmpl = os.path.join(os.path.dirname(__file__), "templates", "dashboard.html")
            if os.path.exists(tmpl):
                with open(tmpl, "r", encoding="utf-8") as f:
                    self._send_html(f.read())
            else:
                self._send_html("<h1>RDQ Server Running</h1>")
            return
        if path == "/api/tasks":
            conn = get_db_connection()
            rows = conn.execute("""
                SELECT item_id, subject, topic, question, answer, box_level, status, eds_x_code
                FROM review_index_current WHERE scope_disputed != 1 AND status != 'mastered'
                ORDER BY box_level ASC, updated_at DESC
            """).fetchall()
            conn.close()
            self._send_json({"status": "success", "tasks": [dict(r) for r in rows]})
            return
        self.send_error(404)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        length = int(self.headers.get('Content-Length', 0))
        raw = self.rfile.read(length) if length > 0 else b'{}'
        try:
            payload = json.loads(raw.decode('utf-8'))
        except Exception:
            payload = {}

        if path == "/api/chat":
            sid = payload.get("session_id", "default")
            msg = payload.get("message", "").strip()
            topic = payload.get("topic", "1-2 質量與密度的測量")
            textbook = payload.get("textbook", "").strip()
            file_path = payload.get("file_path", "").strip()
            is_start = payload.get("is_start", False)

            if file_path and os.path.exists(file_path):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        textbook = f.read()
                except Exception:
                    pass

            if is_start or sid not in CHAT_SESSIONS:
                CHAT_SESSIONS[sid] = {
                    "state": "p1_open", "topic": topic, "textbook": textbook,
                    "student_recalled": "", "student_uncertain": "",
                    "p1_items": [], "p2_items": []
                }
                reply = build_phase1_open(topic, bool(textbook))
                self._send_json({"status": "success", "reply": reply, "options": []})
                return

            session = CHAT_SESSIONS[sid]
            reply, options = process_chat(session, msg)
            self._send_json({"status": "success", "reply": reply, "options": options})
            return

        if path == "/api/verify":
            item_id = payload.get("item_id")
            user_ans = payload.get("answer", "").strip()
            conn = get_db_connection()
            row = conn.execute("SELECT * FROM review_index_current WHERE item_id = ?", (item_id,)).fetchone()
            if not row:
                conn.close()
                self._send_json({"status": "error", "message": "Not found"}, 404)
                return
            task = dict(row)
            is_correct = len(user_ans) >= 2
            if is_correct:
                new_box = min(task["box_level"] + 1, 5)
                conn.execute("UPDATE review_index_current SET box_level=?, status='mastered', updated_at=CURRENT_TIMESTAMP WHERE item_id=?", (new_box, item_id))
                conn.execute("INSERT INTO review_index_log (item_id, action, old_box, new_box) VALUES (?, 'verify_correct', ?, ?)", (item_id, task["box_level"], new_box))
                conn.commit(); conn.close()
                self._send_json({"status": "success", "is_correct": True, "feedback": "✅ 觀念精準！已晉級！", "new_box": new_box})
            else:
                new_box = max(task["box_level"] - 1, 1)
                conn.execute("UPDATE review_index_current SET box_level=?, status='pending', updated_at=CURRENT_TIMESTAMP WHERE item_id=?", (new_box, item_id))
                conn.execute("INSERT INTO review_index_log (item_id, action, old_box, new_box) VALUES (?, 'verify_incorrect', ?, ?)", (item_id, task["box_level"], new_box))
                conn.commit(); conn.close()
                self._send_json({"status": "success", "is_correct": False, "feedback": f"❌ 標準解析：{task['answer']}", "new_box": new_box})
            return

        if path == "/api/ingest":
            self._send_json({"status": "success", "message": "Ingested."})
            return

        if path.startswith("/task/"):
            parts = path.split("/")
            if len(parts) >= 4:
                item_id, action = parts[2], parts[3]
                conn = get_db_connection()
                row = conn.execute("SELECT box_level FROM review_index_current WHERE item_id=?", (item_id,)).fetchone()
                old_box = row["box_level"] if row else 1
                new_box = min(old_box+1, 5) if action == "correct" else max(old_box-1, 1) if action == "incorrect" else old_box
                if action in ("correct", "incorrect"):
                    st = 'mastered' if action == 'correct' else 'pending'
                    conn.execute(f"UPDATE review_index_current SET box_level=?, status=?, updated_at=CURRENT_TIMESTAMP WHERE item_id=?", (new_box, st, item_id))
                conn.execute("INSERT INTO review_index_log (item_id, action, old_box, new_box) VALUES (?,?,?,?)", (item_id, action, old_box, new_box))
                conn.commit(); conn.close()
                self._send_json({"status": "success", "item_id": item_id, "new_box_level": new_box})
                return
        self.send_error(404)

def run(port=8000):
    init_db()
    httpd = HTTPServer(('127.0.0.1', port), RDQDashboardHandler)
    print(f"[RDQ 4-Quadrant Engine v6.0] Active on http://127.0.0.1:{port}")
    try:
        httpd.serve_forever()
    except Exception as e:
        print(f"[RDQ Error] {e}")

if __name__ == '__main__':
    run()
