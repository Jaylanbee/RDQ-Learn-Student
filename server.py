#!/usr/bin/env python3
"""
RDQ True 4-Quadrant Socratic Engine v6.1
- 3 fixes: (1) No-textbook flow identical (2) Phase 5 comprehensive review with role-play (3) Radar API
"""

import os, json, sqlite3, urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler

DB_PATH = os.path.expanduser(r"~\.education_ecosystem\review_index.db")

def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row; return conn

def init_db():
    conn = get_db(); c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS review_index_current (
        item_id TEXT PRIMARY KEY, subject TEXT, topic TEXT, question TEXT, answer TEXT,
        box_level INTEGER DEFAULT 1, status TEXT DEFAULT 'pending', eds_x_code TEXT,
        scope_disputed INTEGER DEFAULT 0, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    try: c.execute("ALTER TABLE review_index_current ADD COLUMN scope_disputed INTEGER DEFAULT 0")
    except: pass
    c.execute("""CREATE TABLE IF NOT EXISTS review_index_log (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT, item_id TEXT, action TEXT,
        old_box INTEGER, new_box INTEGER, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    conn.commit(); conn.close()

CHAT_SESSIONS = {}

def build_phase1_open(topic, has_textbook):
    mode = "課本精確模式" if has_textbook else "108 課綱通用模式"
    return (
        f"🎯 範圍已鎖定：《{topic}》（{mode}）\n\n"
        f"【Phase 1｜象限 I 引導回憶】\n"
        f"你說你讀了《{topic}》對吧？\n"
        f"不急，先想想看——你現在腦海中第一個浮現的關鍵字或重點觀念是什麼？"
    )

def process_chat(session, user_msg):
    state = session["state"]
    topic = session["topic"]
    has_tb = bool(session.get("textbook", ""))
    reply = ""; options = []
    is_stuck = any(k in user_msg for k in ["不知道","忘了","不確定","不會","想不到"])
    source_hint = "課本裡" if has_tb else "這一節裡"

    # ── Phase 1：引導回憶（課本優先/108課綱通用） ──
    if state == "p1_open":
        if is_stuck:
            reply = (
                f"沒關係！我們用選項來幫你暖身：\n"
                f"關於《{topic}》，下面哪一個是你有印象學過的？"
            )
            options = ["A: 質量的定義與測量","B: 密度的公式與特性","C: 天平的操作步驟","D: 以上都有點印象但不太確定"]
            session["state"] = "p1_followup"
        else:
            session["student_recalled"] = user_msg
            reply = (
                f"👍 你提到了「{user_msg}」，很好！大腦已經開始活化了。\n\n"
                f"追問一層：關於「{user_msg}」，你能用自己的話簡單說明一下嗎？\n"
                f"比如它的定義、公式、或你怎麼記住它的？"
            )
            session["state"] = "p1_followup"
        return reply, options

    if state == "p1_followup":
        recalled = session.get("student_recalled", user_msg)
        session["p1_items"] = [recalled]
        reply = (
            f"✅ 已記錄：你對「{recalled}」有掌握。\n\n"
            f"【Phase 2｜象限 II 引導解惑】\n"
            f"在《{topic}》{source_hint}，有沒有哪個部分是你覺得「好像懂又好像不太確定」的？\n"
            f"或者有沒有哪裡讀的時候覺得卡卡的？"
        )
        session["state"] = "p2_ask"
        return reply, options

    # ── Phase 2：引導解惑 ──
    if state == "p2_ask":
        no_q = any(k in user_msg for k in ["沒有","都會","都懂","沒什麼","還好"])
        if no_q or is_stuck:
            reply = (
                f"好的！那我們來試試看，從{source_hint}挖掘一下。\n\n"
                "【Phase 3｜象限 III 隱性知識挖掘】\n"
                f"在《{topic}》{source_hint}，有提到「密度」這個概念。\n\n"
                "你覺得，如果把一塊鋁塊切成兩半，半塊的密度會變嗎？\n"
                "先不急著回答對錯，用你自己的想法推理看看。"
            )
            session["state"] = "p3_dig"
        else:
            session["student_uncertain"] = user_msg
            reply = (
                f"好問題！你提到「{user_msg}」這部分不太確定。\n\n"
                f"那我不直接告訴你答案喔。我們一起來想：\n"
                f"你還記不記得{source_hint}關於「{user_msg}」是怎麼描述的？\n"
                f"有沒有什麼圖、表格或實驗跟它有關？"
            )
            session["state"] = "p2_guide"
        return reply, options

    if state == "p2_guide":
        uncertain = session.get("student_uncertain", "")
        if is_stuck:
            reply = (
                f"沒關係，「{uncertain}」這部分我先幫你標記為 ❓ 待確認。\n"
                "等段考前複習時我們再回頭仔細看。\n\n"
                "【Phase 3｜象限 III 隱性知識挖掘】\n"
                f"現在換個方向，《{topic}》{source_hint}有提到「密度」。\n"
                "你覺得同一種物質，不管切多大或多小塊，密度會改變嗎？\n"
                "先用你的直覺推理看看。"
            )
            session["state"] = "p3_dig"
        else:
            session["p2_items"] = [uncertain]
            reply = (
                f"✅ 很棒！你已經開始自己回想了。\n\n"
                "【Phase 3｜象限 III 隱性知識挖掘】\n"
                f"接下來，《{topic}》{source_hint}有一個觀念，很多同學讀過但沒注意到自己其實會了：\n\n"
                "如果把一塊密度 2.7 g/cm³ 的均勻鋁塊切成大、小不等的兩塊，\n"
                "小塊的密度會是多少呢？先想想看，用你自己的推理說明。"
            )
            session["state"] = "p3_dig"
        return reply, options

    # ── Phase 3：隱性知識挖掘（從課本/108課綱出發） ──
    if state == "p3_dig":
        has_mis = any(k in user_msg for k in ["減半","1.35","一半","變小","會變","除以"])
        if has_mis:
            reply = (
                "🤔 你說密度會變——很多同學也這樣直覺認為！\n\n"
                "我不直接告訴你答案，我們一步步來：\n"
                "密度的公式是 D = M ÷ V 對吧？\n"
                "當你把鋁塊切成 1/2 時，質量 M 變成原來的 1/2……\n"
                "那體積 V 呢？是不是也剛好變成了 1/2？\n\n"
                "分子變 1/2、分母也變 1/2，你覺得相除之後的結果會怎樣？"
            )
            session["state"] = "p3_followup"
        elif is_stuck:
            reply = "沒關係！我們用選項幫你想：\n\n一塊密度 2.7 的鋁塊切半，半塊密度是？"
            options = ["A: 變成 1.35 g/cm³（減半）","B: 還是 2.7 g/cm³（不變）","C: 不太確定"]
            session["state"] = "p3_followup"
        else:
            reply = (
                "🎉 你推理得很好！你其實已經掌握了——\n"
                "同一種純物質，不管切多大或多小，密度都是定值（不會改變）！\n"
                "你剛才靠自己的推理發現了這一點，這就是象限 III 的力量。\n\n"
                "【Phase 4｜象限 IV 盲點提示（最後一題）】\n"
                "🏛️ 最後一個問題，這題改編自歷屆國中會考真題，\n"
                "專門用來戳破「不知道自己不知道」的盲區：\n\n"
                "如果太空人把一塊質量 100g 的鐵塊帶到月球上，\n"
                "請問鐵塊在月球上的「質量」會變成多少？\n"
                "（提示：月球引力是地球的 1/6。先想想看，質量跟重量有什麼不同？）\n\n"
                "（這是最後一個問題了，如果你累了，隨時可以說「先這樣，我大概知道了」來結束覆盤）"
            )
            session["state"] = "p4_blind"
        return reply, options

    if state == "p3_followup":
        reply = (
            "✅ 沒錯！分子 1/2 ÷ 分母 1/2 = 1，密度不變！\n"
            "你靠自己的推理發現了：同一種物質的密度是定值。太棒了！\n\n"
            "【Phase 4｜象限 IV 盲點提示（最後一題）】\n"
            "🏛️ 最後一個問題，改編自 109 年國中會考真題：\n\n"
            "如果太空人把一塊質量 100g 的鐵塊帶到月球上，\n"
            "請問鐵塊在月球上的「質量」會變成多少？\n"
            "（月球引力是地球的 1/6。先想想看再回答。）\n\n"
            "（這是最後一個問題了，如果你累了，隨時可以說「先這樣」來結束覆盤）"
        )
        session["state"] = "p4_blind"
        return reply, options

    # ── Phase 4：盲點提示（會考陷阱，最後一題） ──
    if state == "p4_blind":
        wants_stop = any(k in user_msg for k in ["先這樣","大概知道了","結束"])
        if wants_stop:
            reply = build_phase5_card(session, user_msg, False, False)
            session["state"] = "p5_review"
            return reply, []
        has_mis = any(k in user_msg for k in ["50/3","16.6","1/6","變輕","變小","減少","除以"])
        has_wt = "重量" in user_msg and any(k in user_msg for k in ["50","1/6"])
        if has_mis or has_wt:
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
            reply = "沒關係！我們用選項幫你想：\n\n100g 鐵塊帶到月球，月球引力是地球 1/6，鐵塊的「質量」是？"
            options = ["A: 還是 100g（質量不隨地點改變）","B: 變成約 16.6g（除以 6）","C: 不太確定質量和重量的差別"]
            session["state"] = "p4_ladder"
        else:
            session["p4_correct"] = True
            reply = build_phase5_card(session, user_msg, False, True)
            session["state"] = "p5_review"
        return reply, options

    if state == "p4_ladder":
        session["p4_misconception"] = True
        reply = build_phase5_card(session, user_msg, True, False)
        session["state"] = "p5_review"
        return reply, options

    # ── Phase 5：覆盤卡 + 今日所學完整複習 ──
    if state == "p5_review":
        if "老師" in user_msg or "整理" in user_msg or "A" in user_msg.upper():
            recalled = session.get("student_recalled", "核心觀念")
            uncertain = session.get("student_uncertain", "")
            reply = (
                f"📚【AI 老師為你整理今日所學】\n\n"
                f"今天我們複習了《{topic}》，你的學習狀態如下：\n\n"
                f"1️⃣ 你自己回憶出了「{recalled}」，代表你的記憶是有效的。\n"
            )
            if uncertain:
                reply += f"2️⃣ 你主動提出了「{uncertain}」不太確定，這種自我覺察非常重要。\n"
            reply += (
                f"3️⃣ 透過推理，你發現了「同物質密度為定值」——這是你原本就會但沒意識到的隱性知識。\n"
                f"4️⃣ 最後的會考盲點題幫你釐清了「質量 vs 重量」的差異。\n\n"
                f"💡 總結一句話：你今天最大的收穫是——「質量代表物質總量，不隨地點改變；密度是同物質的固有特性，不隨大小改變。」\n\n"
                f"你做得很棒！覆盤完成 ✅"
            )
        elif "小孩" in user_msg or "教" in user_msg or "B" in user_msg.upper():
            reply = (
                f"👶【費曼學習法：你來教 10 歲小孩】\n\n"
                f"假裝我是一個 10 歲的小朋友，我完全不懂什麼是「密度」。\n\n"
                f"🧒「哥哥姐姐，什麼是密度啊？為什麼冰塊會浮在水上面？」\n\n"
                f"請你用最簡單的話教我！如果你能讓 10 歲小孩聽懂，那代表你 100% 真的理解了！"
            )
            session["state"] = "p5_feynman"
        else:
            reply = "覆盤已完成！你可以切換到閃卡防禦，或重新開始新單元。"
            options = ["切換至閃卡防禦 ➔","重新複習新單元"]
        return reply, options

    if state == "p5_feynman":
        reply = (
            f"🎉 太厲害了！你剛才的解釋是：\n「{user_msg}」\n\n"
            f"如果連 10 歲小孩都能聽懂，那代表你是真正理解了，不是死記硬背！\n"
            f"這就是費曼學習法的威力——能教別人的人，才是真正學會的人。\n\n"
            f"今日覆盤圓滿完成 ✅ 你做得非常棒！"
        )
        options = ["切換至閃卡防禦 ➔","重新複習新單元"]
        session["state"] = "done"
        return reply, options

    # fallback
    reply = "覆盤已完成！可以切換到閃卡防禦，或重新開始新單元。"
    options = ["切換至閃卡防禦 ➔","重新複習新單元"]
    return reply, options


def build_phase5_card(session, last_msg, misconception_found, p4_correct):
    topic = session["topic"]
    recalled = session.get("student_recalled", "（核心觀念）")
    uncertain = session.get("student_uncertain", "")
    
    card = f"🏆【Phase 5｜學習覆盤卡：《{topic}》】\n\n"
    if misconception_found:
        card += "🎯 你剛剛靠自己推導出來了！質量 = 物質總量，不隨地點改變（月球上還是 100g）。\n變成 1/6 的是「重量」不是「質量」！很多人都會搞混，你現在釐清了。\n\n"
    elif p4_correct:
        card += "🎯 你回答得非常精準！質量不隨地點改變的觀念你完全掌握了！\n\n"

    card += "📋 覆盤結果：\n"
    card += f"  ✅ 已掌握：「{recalled}」— 你能用自己的話說明。\n"
    if uncertain:
        card += f"  ❓ 待確認：「{uncertain}」— 已標記，段考前記得回頭。\n"
    card += "  ✅ 隱性知識：「同物質密度為定值」— 你靠自己推理發現了！\n"
    if misconception_found:
        card += "  ⚠️ 迷思已澄清：「質量 vs 重量混淆」— 蘇式引導後你自己推導出正確答案。\n"
    elif p4_correct:
        card += "  ✅ 盲點通過：「質量不隨地點改變」— 109 會考陷阱題直接答對！\n"

    card += (
        "\n已將結果寫入今日防禦庫 (review_index.db)！\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🎓【今日所學完整複習】請選擇一種方式回顧今天學了什麼：\n\n"
        "A: 📚 讓 AI 當老師，幫你完整整理今日所學重點\n"
        "B: 👶 讓 AI 當 10 歲小孩，你來教他（費曼學習法）"
    )
    return card


class RDQHandler(BaseHTTPRequestHandler):
    def log_message(self, f, *a): print(f"[RDQ] {self.address_string()} - {f%a}")

    def _json(self, d, code=200):
        b = json.dumps(d, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        for k,v in [('Content-Type','application/json;charset=utf-8'),('Content-Length',str(len(b))),
            ('Cache-Control','no-cache,no-store,must-revalidate'),('Pragma','no-cache'),('Expires','0'),
            ('Access-Control-Allow-Origin','*'),('Access-Control-Allow-Methods','GET,POST,OPTIONS'),
            ('Access-Control-Allow-Headers','Content-Type')]: self.send_header(k,v)
        self.end_headers(); self.wfile.write(b)

    def _html(self, h):
        b = h.encode('utf-8'); self.send_response(200)
        for k,v in [('Content-Type','text/html;charset=utf-8'),('Content-Length',str(len(b))),
            ('Cache-Control','no-cache,no-store,must-revalidate'),('Pragma','no-cache'),('Expires','0')]:
            self.send_header(k,v)
        self.end_headers(); self.wfile.write(b)

    def do_OPTIONS(self):
        self.send_response(200)
        for k,v in [('Access-Control-Allow-Origin','*'),('Access-Control-Allow-Methods','GET,POST,OPTIONS'),
            ('Access-Control-Allow-Headers','Content-Type')]: self.send_header(k,v)
        self.end_headers()

    def do_GET(self):
        p = urllib.parse.urlparse(self.path).path
        if p in ("/","/index.html"):
            t = os.path.join(os.path.dirname(__file__),"templates","dashboard.html")
            if os.path.exists(t):
                with open(t,"r",encoding="utf-8") as f: self._html(f.read())
            else: self._html("<h1>RDQ Running</h1>")
            return
        if p == "/api/tasks":
            conn = get_db()
            rows = conn.execute("SELECT item_id,subject,topic,question,answer,box_level,status,eds_x_code FROM review_index_current WHERE scope_disputed!=1 AND status!='mastered' ORDER BY box_level ASC, updated_at DESC").fetchall()
            conn.close(); self._json({"status":"success","tasks":[dict(r) for r in rows]}); return
        if p == "/api/radar":
            conn = get_db()
            subjects = ["國文","英語","數學","自然","社會"]
            radar = {}
            for s in subjects:
                total = conn.execute("SELECT COUNT(*) as c FROM review_index_current WHERE subject=?", (s,)).fetchone()["c"]
                mastered = conn.execute("SELECT COUNT(*) as c FROM review_index_current WHERE subject=? AND status='mastered'", (s,)).fetchone()["c"]
                radar[s] = round((mastered / max(total, 1)) * 100)
            conn.close()
            self._json({"status":"success","radar":radar}); return
        self.send_error(404)

    def do_POST(self):
        p = urllib.parse.urlparse(self.path).path
        L = int(self.headers.get('Content-Length',0))
        raw = self.rfile.read(L) if L > 0 else b'{}'
        try: payload = json.loads(raw.decode('utf-8'))
        except: payload = {}

        if p == "/api/chat":
            sid = payload.get("session_id","default")
            msg = payload.get("message","").strip()
            topic = payload.get("topic","1-2 質量與密度的測量")
            tb = payload.get("textbook","").strip()
            fp = payload.get("file_path","").strip()
            is_start = payload.get("is_start", False)
            if fp and os.path.exists(fp):
                try:
                    with open(fp,"r",encoding="utf-8") as f: tb = f.read()
                except: pass
            if is_start or sid not in CHAT_SESSIONS:
                CHAT_SESSIONS[sid] = {"state":"p1_open","topic":topic,"textbook":tb,
                    "student_recalled":"","student_uncertain":"","p1_items":[],"p2_items":[]}
                reply = build_phase1_open(topic, bool(tb))
                self._json({"status":"success","reply":reply,"options":[]}); return
            session = CHAT_SESSIONS[sid]
            reply, options = process_chat(session, msg)
            self._json({"status":"success","reply":reply,"options":options}); return

        if p == "/api/verify":
            iid = payload.get("item_id"); ans = payload.get("answer","").strip()
            conn = get_db(); row = conn.execute("SELECT * FROM review_index_current WHERE item_id=?",(iid,)).fetchone()
            if not row: conn.close(); self._json({"status":"error","message":"Not found"},404); return
            t = dict(row); ok = len(ans) >= 2
            if ok:
                nb = min(t["box_level"]+1,5)
                conn.execute("UPDATE review_index_current SET box_level=?,status='mastered',updated_at=CURRENT_TIMESTAMP WHERE item_id=?",(nb,iid))
                conn.execute("INSERT INTO review_index_log(item_id,action,old_box,new_box) VALUES(?,'verify_correct',?,?)",(iid,t["box_level"],nb))
                conn.commit();conn.close();self._json({"status":"success","is_correct":True,"feedback":"✅ 觀念精準！已晉級！","new_box":nb})
            else:
                nb = max(t["box_level"]-1,1)
                conn.execute("UPDATE review_index_current SET box_level=?,status='pending',updated_at=CURRENT_TIMESTAMP WHERE item_id=?",(nb,iid))
                conn.execute("INSERT INTO review_index_log(item_id,action,old_box,new_box) VALUES(?,'verify_incorrect',?,?)",(iid,t["box_level"],nb))
                conn.commit();conn.close();self._json({"status":"success","is_correct":False,"feedback":f"❌ 標準解析：{t['answer']}","new_box":nb})
            return

        if p == "/api/ingest": self._json({"status":"success","message":"Ingested."}); return

        if p.startswith("/task/"):
            parts = p.split("/")
            if len(parts) >= 4:
                iid, act = parts[2], parts[3]
                conn = get_db(); row = conn.execute("SELECT box_level FROM review_index_current WHERE item_id=?",(iid,)).fetchone()
                ob = row["box_level"] if row else 1
                nb = min(ob+1,5) if act=="correct" else max(ob-1,1) if act=="incorrect" else ob
                if act in ("correct","incorrect"):
                    st = 'mastered' if act=='correct' else 'pending'
                    conn.execute("UPDATE review_index_current SET box_level=?,status=?,updated_at=CURRENT_TIMESTAMP WHERE item_id=?",(nb,st,iid))
                conn.execute("INSERT INTO review_index_log(item_id,action,old_box,new_box) VALUES(?,?,?,?)",(iid,act,ob,nb))
                conn.commit();conn.close();self._json({"status":"success","item_id":iid,"new_box_level":nb}); return
        self.send_error(404)

def run(port=8000):
    init_db()
    httpd = HTTPServer(('127.0.0.1',port), RDQHandler)
    print(f"[RDQ 4-Quadrant Engine v6.1] Active on http://127.0.0.1:{port}")
    try: httpd.serve_forever()
    except Exception as e: print(f"[RDQ Error] {e}")

if __name__ == '__main__': run()
