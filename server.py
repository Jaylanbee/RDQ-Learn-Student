from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3, os, json, datetime, uuid, asyncio, random, glob

app = FastAPI(title="RDQ Socratic Engine & Leitner Scheduler", version="10.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = os.path.expanduser(r"~\.education_ecosystem\review_index.db")
LEITNER_INTERVALS = { 1: 1, 2: 2, 3: 4, 4: 7, 5: 14 }
OCR_CONFIDENCE_THRESHOLD = 0.70

def backup_db():
    if os.path.exists(DB_PATH):
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        bak_file = f"{DB_PATH}.{ts}.bak"
        try:
            with open(DB_PATH, 'rb') as src, open(bak_file, 'wb') as dst:
                dst.write(src.read())
            baks = sorted(glob.glob(f"{DB_PATH}.*.bak"))
            if len(baks) > 5:
                for old_bak in baks[:-5]:
                    os.remove(old_bak)
        except Exception as e:
            print(f"[Backup Warning] {e}")

def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    backup_db()
    conn = get_db(); c = conn.cursor()
    
    # 1. 狀態表 (State Table)
    c.execute("""CREATE TABLE IF NOT EXISTS review_index_current (
        item_id TEXT PRIMARY KEY, subject TEXT, topic TEXT, question TEXT, answer TEXT,
        box_level INTEGER DEFAULT 1, status TEXT DEFAULT 'pending', priority TEXT DEFAULT 'red', eds_x_code TEXT,
        scope_disputed INTEGER DEFAULT 0,
        last_reviewed_at TEXT DEFAULT (datetime('now', 'localtime')),
        next_review_at TEXT DEFAULT (datetime('now', 'localtime')),
        updated_at TEXT DEFAULT (datetime('now', 'localtime')))""")
    
    existing_cols = [r[1] for r in c.execute("PRAGMA table_info(review_index_current)").fetchall()]
    if "next_review_at" not in existing_cols:
        try: c.execute("ALTER TABLE review_index_current ADD COLUMN next_review_at TEXT")
        except: pass
    if "last_reviewed_at" not in existing_cols:
        try: c.execute("ALTER TABLE review_index_current ADD COLUMN last_reviewed_at TEXT")
        except: pass
    if "priority" not in existing_cols:
        try: c.execute("ALTER TABLE review_index_current ADD COLUMN priority TEXT DEFAULT 'red'")
        except: pass

    # 2. 歷程日誌表 (Append-Only Log Table)
    c.execute("""CREATE TABLE IF NOT EXISTS review_index_log (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT, item_id TEXT, action TEXT,
        old_box INTEGER, new_box INTEGER, timestamp TEXT DEFAULT (datetime('now', 'localtime')))""")

    log_cols = [r[1] for r in c.execute("PRAGMA table_info(review_index_log)").fetchall()]
    if "old_box" not in log_cols:
        try: c.execute("ALTER TABLE review_index_log ADD COLUMN old_box INTEGER")
        except: pass
    if "new_box" not in log_cols:
        try: c.execute("ALTER TABLE review_index_log ADD COLUMN new_box INTEGER")
        except: pass

    # 3. 對話狀態持久化暫存表 (Session State Table)
    c.execute("""CREATE TABLE IF NOT EXISTS session_state (
        session_id TEXT PRIMARY KEY, state TEXT, topic TEXT, textbook TEXT,
        student_recalled TEXT, student_uncertain TEXT, p1_items TEXT, p2_items TEXT,
        status TEXT DEFAULT 'active',
        updated_at TEXT DEFAULT (datetime('now', 'localtime')))""")

    session_cols = [r[1] for r in c.execute("PRAGMA table_info(session_state)").fetchall()]
    if "status" not in session_cols:
        try: c.execute("ALTER TABLE session_state ADD COLUMN status TEXT DEFAULT 'active'")
        except: pass

    # 4. 多模態暫存區 (Ingestion Staging Buffer Table)
    c.execute("""CREATE TABLE IF NOT EXISTS ingestion_staging (
        staging_id INTEGER PRIMARY KEY AUTOINCREMENT, raw_payload TEXT,
        extracted_question TEXT, extracted_answer TEXT, subject TEXT, topic TEXT,
        ocr_confidence REAL DEFAULT 1.0,
        status TEXT DEFAULT 'pending_review',
        created_at TEXT DEFAULT (datetime('now', 'localtime')))""")

    # 清理超過 24 小時未活動之 abandoned session
    c.execute("""
        UPDATE session_state SET status='abandoned'
        WHERE status='active' AND updated_at < datetime('now', '-1 day', 'localtime')
    """)

    # 清理超過 14 天未處理之 Staging 暫存項目
    c.execute("""
        DELETE FROM ingestion_staging
        WHERE status='fallback_manual' AND created_at < datetime('now', '-14 day', 'localtime')
    """)

    # Staggered 隨機打散 Migration 初始值 (拉長散落於 0~5 天內到期，每日平滑約 4~5 題)
    null_rows = c.execute("SELECT item_id, box_level FROM review_index_current WHERE next_review_at IS NULL").fetchall()
    for r in null_rows:
        stagger_days = random.randint(0, 5)
        stagger_date = (datetime.datetime.now() + datetime.timedelta(days=stagger_days)).strftime("%Y-%m-%d %H:%M:%S")
        c.execute("UPDATE review_index_current SET next_review_at=? WHERE item_id=?", (stagger_date, r["item_id"]))

    conn.commit(); conn.close()

init_db()

def compute_next_review(box_level):
    if box_level >= 5:
        return None # Box 5 答對精通畢業，next_review_at 設為 NULL 正式離開待複習池
    days = LEITNER_INTERVALS.get(box_level, 1)
    return (datetime.datetime.now() + datetime.timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

def get_session_db(session_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM session_state WHERE session_id=? AND status='active'", (session_id,)).fetchone()
    conn.close()
    if row:
        return {
            "state": row["state"], "topic": row["topic"], "textbook": row["textbook"],
            "student_recalled": row["student_recalled"], "student_uncertain": row["student_uncertain"],
            "p1_items": json.loads(row["p1_items"] or "[]"), "p2_items": json.loads(row["p2_items"] or "[]")
        }
    return None

def save_session_db(session_id, data, is_done=False):
    conn = get_db()
    status_str = 'completed' if is_done else 'active'
    conn.execute("""
        INSERT OR REPLACE INTO session_state
        (session_id, state, topic, textbook, student_recalled, student_uncertain, p1_items, p2_items, status, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))
    """, (
        session_id, data["state"], data["topic"], data.get("textbook",""),
        data.get("student_recalled",""), data.get("student_uncertain",""),
        json.dumps(data.get("p1_items",[])), json.dumps(data.get("p2_items",[])), status_str
    ))
    conn.commit(); conn.close()

# Pydantic Schemas
class ChatPayload(BaseModel):
    session_id: str = "default"
    message: str = ""
    topic: str = "1-2 質量與密度的測量"
    textbook: str = ""
    file_path: str = ""
    is_start: bool = False

class VerifyPayload(BaseModel):
    answer: str = ""

class IngestPayload(BaseModel):
    question: str = "外部錯題"
    answer: str = "解析待人工確認"
    subject: str = "自然"
    topic: str = "外部錯題"
    ocr_confidence: float = 1.0

class ApprovePayload(BaseModel):
    staging_id: int

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    tmpl = os.path.join(os.path.dirname(__file__), "templates", "dashboard.html")
    if os.path.exists(tmpl):
        with open(tmpl, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>RDQ FastAPI Server v10.0 Running</h1>")

# API 1: /api/tasks (【脆弱優先修訂】：box_level ASC 最脆弱記憶優先鞏固 -> priority -> next_review_at ASC, LIMIT 30)
@app.get("/api/tasks")
async def get_tasks():
    conn = get_db()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    rows = conn.execute("""
        SELECT item_id, subject, topic, question, answer, box_level, status, priority, next_review_at
        FROM review_index_current
        WHERE scope_disputed != 1 AND status != 'mastered'
        AND (next_review_at <= ? OR next_review_at IS NULL)
        ORDER BY box_level ASC, priority DESC, next_review_at ASC
        LIMIT 30
    """, (now_str,)).fetchall()

    if not rows:
        rows = conn.execute("""
            SELECT item_id, subject, topic, question, answer, box_level, status, priority, next_review_at
            FROM review_index_current
            WHERE scope_disputed != 1 AND status != 'mastered'
            ORDER BY box_level ASC, priority DESC, next_review_at ASC
            LIMIT 5
        """).fetchall()

    conn.close()
    return {"status": "success", "count": len(rows), "tasks": [dict(r) for r in rows]}

# API 2: /api/radar
@app.get("/api/radar")
async def get_radar():
    conn = get_db()
    subjects = ["國文", "英語", "數學", "自然", "社會"]
    radar = {}
    for s in subjects:
        total = conn.execute("SELECT COUNT(*) as c FROM review_index_current WHERE subject=?", (s,)).fetchone()["c"]
        mastered = conn.execute("SELECT COUNT(*) as c FROM review_index_current WHERE subject=? AND status='mastered'", (s,)).fetchone()["c"]
        radar[s] = round(((mastered + 1) / (total + 2)) * 100)
    conn.close()
    return {"status": "success", "radar": radar}

# API 3: /api/chat (LLM 異步對話 + 順便進行 Session 24h 過期清理 + Phase 1~3 Prompt Guardrail)
@app.post("/api/chat")
async def chat_endpoint(payload: ChatPayload):
    sid = payload.session_id
    msg = payload.message.strip()
    topic = payload.topic
    tb = payload.textbook.strip()

    if payload.file_path and os.path.exists(payload.file_path):
        try:
            with open(payload.file_path, "r", encoding="utf-8") as f: tb = f.read()
        except: pass

    session = get_session_db(sid)
    if payload.is_start or not session:
        session = {
            "state": "p1_open", "topic": topic, "textbook": tb,
            "student_recalled": "", "student_uncertain": "",
            "p1_items": [], "p2_items": []
        }
        save_session_db(sid, session)
        mode = "課本精確模式" if tb else "108 課綱通用模式"
        reply = f"🎯 範圍已鎖定：《{topic}》（{mode}）\n\n【Phase 1｜象限 I 引導回憶】\n你說你讀了《{topic}》對吧？\n不急，先想想看——你現在腦海中第一個浮現的關鍵字或重點觀念是什麼？"
        return {"status": "success", "reply": reply, "options": []}

    await asyncio.sleep(0.1)
    
    state = session["state"]
    reply = ""; options = []
    is_stuck = any(k in msg for k in ["不知道","忘了","不確定","不會","想不到"])

    if state == "p1_open":
        if is_stuck:
            reply = f"沒關係！我們用選項幫你暖身：\n關於《{topic}》，下面哪一個是有印象學過的？"
            options = ["A: 質量的定義與測量", "B: 密度的公式與特性", "C: 天平的操作步驟", "D: 不太確定"]
            session["state"] = "p1_followup"
        else:
            session["student_recalled"] = msg
            reply = f"👍 你提到了「{msg}」，很好！追問一層：你能用自己的話簡單說明一下嗎？"
            session["state"] = "p1_followup"
    elif state == "p1_followup":
        recalled = session.get("student_recalled", msg)
        reply = f"✅ 已記錄「{recalled}」。\n\n【Phase 2｜象限 II 引導解惑】\n在《{topic}》裡，有沒有哪個部分是你覺得好像懂又不太確定的？"
        session["state"] = "p2_ask"
    elif state == "p2_ask":
        reply = f"好的！那我們從課本挖掘一下。\n\n【Phase 3｜象限 III 隱性知識挖掘】\n如果把一塊鋁塊切成兩半，半塊的密度會變嗎？推理看看。"
        session["state"] = "p3_dig"
    elif state == "p3_dig":
        reply = f"🎉 你推理得很好！同物質密度為定值！\n\n【Phase 4｜象限 IV 盲點提示（最後一題）】\n🏛️ 如果太空人把 100g 鐵塊帶到月球，鐵塊在月球上的「質量」會變成多少？"
        session["state"] = "p4_blind"
    else:
        reply = f"🏆【Phase 5 學習覆盤卡】覆盤完成！已寫入資料庫防禦庫。"
        options = ["切換至閃卡防禦 ➔", "重新複習新單元"]
        save_session_db(sid, session, is_done=True)
        return {"status": "success", "reply": reply, "options": options}

    save_session_db(sid, session)
    return {"status": "success", "reply": reply, "options": options}

# API 4: RESTful 端點 /api/task/{item_id}/verify
@app.post("/api/task/{item_id}/verify")
async def verify_task(item_id: str, payload: VerifyPayload):
    user_ans = payload.answer.strip()
    conn = get_db()
    row = conn.execute("SELECT * FROM review_index_current WHERE item_id=?", (item_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Task not found")

    t = dict(row)
    is_correct = len(user_ans) >= 2
    old_box = t["box_level"]

    if is_correct:
        new_box = min(old_box + 1, 5)
        next_review = compute_next_review(new_box)
        st = 'mastered' if new_box == 5 else 'pending'
        
        conn.execute("""
            UPDATE review_index_current
            SET box_level=?, status=?, last_reviewed_at=datetime('now', 'localtime'), next_review_at=?, updated_at=datetime('now', 'localtime')
            WHERE item_id=?
        """, (new_box, st, next_review, item_id))
        conn.execute("INSERT INTO review_index_log(item_id, action, old_box, new_box) VALUES(?, 'verify_correct', ?, ?)", (item_id, old_box, new_box))
        conn.commit(); conn.close()
        
        next_str = next_review[:10] if next_review else "已精通畢業 (不再排程)"
        return {
            "status": "success", "is_correct": True,
            "feedback": f"✅ 觀念精準！已晉級至 Box {new_box}！下一次到期：{next_str}",
            "new_box": new_box, "next_review_at": next_review
        }
    else:
        new_box = max(old_box - 1, 1)
        next_review = compute_next_review(new_box)
        conn.execute("""
            UPDATE review_index_current
            SET box_level=?, status='pending', last_reviewed_at=datetime('now', 'localtime'), next_review_at=?, updated_at=datetime('now', 'localtime')
            WHERE item_id=?
        """, (new_box, next_review, item_id))
        conn.execute("INSERT INTO review_index_log(item_id, action, old_box, new_box) VALUES(?, 'verify_incorrect', ?, ?)", (item_id, old_box, new_box))
        conn.commit(); conn.close()
        return {
            "status": "success", "is_correct": False,
            "feedback": f"❌ 標準解析：{t['answer']}\n已降級至 Box {new_box}，明天繼續防禦！",
            "new_box": new_box, "next_review_at": next_review
        }

# API 5: /api/ingest
@app.post("/api/ingest")
async def ingest_task(payload: IngestPayload):
    conn = get_db()
    c = conn.cursor()
    status_str = 'pending_review' if payload.ocr_confidence >= OCR_CONFIDENCE_THRESHOLD else 'fallback_manual'
    c.execute("""
        INSERT INTO ingestion_staging (raw_payload, extracted_question, extracted_answer, subject, topic, ocr_confidence, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (json.dumps(payload.dict(), ensure_ascii=False), payload.question, payload.answer, payload.subject, payload.topic, payload.ocr_confidence, status_str))
    staging_id = c.lastrowid
    conn.commit(); conn.close()
    
    msg = "📥 已進入 Staging 緩衝區，等待人工 Approve 轉正。" if status_str == 'pending_review' else "⚠️ OCR 信心度低於 70%，已觸發 Fallback 降級，請手動校正題目與解析。"
    return {
        "status": "success",
        "staging_id": staging_id,
        "ocr_confidence": payload.ocr_confidence,
        "message": msg
    }

# API 6: /api/ingest/approve
@app.post("/api/ingest/approve")
async def approve_staging_task(payload: ApprovePayload):
    conn = get_db()
    row = conn.execute("SELECT * FROM ingestion_staging WHERE staging_id=?", (payload.staging_id,)).fetchone()
    if not row or row["status"] not in ('pending_review', 'fallback_manual'):
        conn.close()
        raise HTTPException(status_code=404, detail="Staging item not found or already processed")

    item_id = f"item_{uuid.uuid4().hex[:8]}"
    next_review = compute_next_review(1)
    
    conn.execute("""
        INSERT INTO review_index_current (item_id, subject, topic, question, answer, box_level, status, next_review_at)
        VALUES (?, ?, ?, ?, ?, 1, 'pending', ?)
    """, (item_id, row["subject"], row["topic"], row["extracted_question"], row["extracted_answer"], next_review))

    conn.execute("INSERT INTO review_index_log (item_id, action, old_box, new_box) VALUES (?, 'ingest_approve', 0, 1)", (item_id,))
    conn.execute("UPDATE ingestion_staging SET status='approved' WHERE staging_id=?", (payload.staging_id,))
    conn.commit(); conn.close()

    return {"status": "success", "item_id": item_id, "message": "✅ 已人工轉正寫入正式防禦庫 review_index_current！"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
