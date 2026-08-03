# server.py - RDQ v11.5 FastAPI 非同步伺服器
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3, os, json, datetime, uuid, asyncio, random, shutil

from reference_impl.config import (
    MAX_DAILY_TASKS, BOX_QUOTA_RATIO, BOX_INTERVAL_DAYS,
    OCR_CONFIDENCE_THRESHOLD, PRIORITY_WRONG_WEIGHT, PRIORITY_RECENT_MAX,
    MEDIA_STAGING_DIR, MEDIA_OFFICIAL_DIR
)
from reference_impl.db import (
    get_connection, init_db, now_utc_iso, execute_with_retry, maybe_cleanup
)
from reference_impl.backup import backup_db

app = FastAPI(title="RDQ Socratic Engine & Leitner Scheduler", version="11.5")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    init_db()

def compute_next_review(box_level: int):
    if box_level >= 5:
        return None
    days = BOX_INTERVAL_DAYS.get(box_level, 1)
    dt = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=days)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

def compute_priority(item: dict) -> int:
    score = 0
    score += min(item.get("wrong_count", 0) * PRIORITY_WRONG_WEIGHT, 60)
    if item.get("last_wrong_at"):
        try:
            iso_str = item["last_wrong_at"].replace('Z', '+00:00')
            days_since_last_wrong = (datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(iso_str)).days
            score += max(0, PRIORITY_RECENT_MAX - days_since_last_wrong * 2)
        except: pass
    return min(score, 100)

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
    return HTMLResponse(content="<h1>RDQ FastAPI Server v11.5 Running</h1>")

# API 1: /api/tasks (【Hard Quota + 動態名額釋出】演算法)
@app.get("/api/tasks")
async def get_tasks():
    conn = get_connection()
    maybe_cleanup(conn)
    now_str = now_utc_iso()

    all_due = conn.execute("""
        SELECT * FROM review_index_current
        WHERE status != 'mastered'
        AND (next_review_at <= ? OR next_review_at IS NULL)
    """, (now_str,)).fetchall()

    items = [dict(r) for r in all_due]
    for i in items:
        i["priority"] = compute_priority(i)

    due_by_box = {1: [], 2: [], 3: [], 4: [], 5: []}
    for i in items:
        b = i["box_level"]
        if b in due_by_box:
            due_by_box[b].append(i)

    for b in due_by_box:
        due_by_box[b].sort(key=lambda x: (-x["priority"], x["next_review_at"] or ""))

    reserved_quota = {b: int(MAX_DAILY_TASKS * r) for b, r in BOX_QUOTA_RATIO.items()}
    result = []
    for b, q in reserved_quota.items():
        result.extend(due_by_box[b][:q])

    used_ids = {x["item_id"] for x in result}
    if len(result) < MAX_DAILY_TASKS:
        remaining_pool = [i for i in items if i["item_id"] not in used_ids]
        remaining_pool.sort(key=lambda x: (x["box_level"], -x["priority"]))
        result.extend(remaining_pool[: MAX_DAILY_TASKS - len(result)])

    conn.close()
    return {"status": "success", "count": len(result), "total_due": len(items), "tasks": result[:MAX_DAILY_TASKS]}

# API 2: /api/radar (Laplace 平滑算分)
@app.get("/api/radar")
async def get_radar():
    conn = get_connection()
    subjects = ["國文", "英語", "數學", "自然", "社會"]
    radar = {}
    for s in subjects:
        total = conn.execute("SELECT COUNT(*) as c FROM review_index_current WHERE subject=?", (s,)).fetchone()["c"]
        mastered = conn.execute("SELECT COUNT(*) as c FROM review_index_current WHERE subject=? AND status='mastered'", (s,)).fetchone()["c"]
        radar[s] = round(((mastered + 1) / (total + 2)) * 100)
    conn.close()
    return {"status": "success", "radar": radar}

# API 3: /api/chat (四象限對話引擎 + 惰性清理)
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

    conn = get_connection()
    maybe_cleanup(conn)

    row = conn.execute("SELECT * FROM session_state WHERE session_id=? AND status='active'", (sid,)).fetchone()
    if payload.is_start or not row:
        execute_with_retry(conn, """
            INSERT OR REPLACE INTO session_state (session_id, phase, topic, textbook_content, status, updated_at)
            VALUES (?, 'phase1', ?, ?, 'active', ?)
        """, (sid, topic, tb, now_utc_iso()))
        conn.commit(); conn.close()
        mode = "課本精確模式" if tb else "108 課綱通用模式"
        reply = f"🎯 範圍已鎖定：《{topic}》（{mode}）\n\n【Phase 1｜象限 I 引導回憶】\n你說你讀了《{topic}》對吧？\n不急，先想想看——你現在腦海中第一個浮現的關鍵字或重點觀念是什麼？"
        return {"status": "success", "reply": reply, "options": []}

    phase = row["phase"]
    reply = ""; options = []; new_phase = phase
    is_stuck = any(k in msg for k in ["不知道","忘了","不確定","不會","想不到"])

    if phase == "phase1":
        if is_stuck:
            reply = f"沒關係！我們用選項幫你暖身：\n關於《{topic}》，下面哪一個是有印象學過的？"
            options = ["A: 質量的定義與測量", "B: 密度的公式與特性", "C: 天平的操作步驟", "D: 不太確定"]
            new_phase = "phase2"
        else:
            reply = f"👍 你提到了「{msg}」，很好！追問一層：你能用自己的話簡單說明一下嗎？"
            new_phase = "phase2"
    elif phase == "phase2":
        reply = f"✅ 已記錄。在《{topic}》裡，有沒有哪個部分是你覺得好像懂又不太確定的？"
        new_phase = "phase3"
    elif phase == "phase3":
        reply = f"好的！那我們從課本挖掘一下。\n\n【Phase 3｜象限 III 隱性知識挖掘】\n如果把一塊鋁塊切成兩半，半塊的密度會變嗎？推理看看。"
        new_phase = "phase4"
    elif phase == "phase4":
        reply = f"🎉 你推理得很好！同物質密度為定值！\n\n【Phase 4｜象限 IV 盲點提示（最後一題）】\n🏛️ 如果太空人把 100g 鐵塊帶到月球，鐵塊在月球上的「質量」會變成多少？"
        new_phase = "phase5"
    else:
        reply = f"🏆【Phase 5 學習覆盤卡】覆盤完成！已寫入資料庫防禦庫。"
        options = ["切換至閃卡防禦 ➔", "重新複習新單元"]
        new_phase = "phase5"

    execute_with_retry(conn, """
        UPDATE session_state SET phase=?, student_recalled=?, updated_at=? WHERE session_id=?
    """, (new_phase, msg, now_utc_iso(), sid))
    conn.commit(); conn.close()
    return {"status": "success", "reply": reply, "options": options}

# API 4: RESTful 端點 /api/task/{item_id}/verify
@app.post("/api/task/{item_id}/verify")
async def verify_task(item_id: str, payload: VerifyPayload):
    user_ans = payload.answer.strip()
    conn = get_connection()
    row = conn.execute("SELECT * FROM review_index_current WHERE item_id=?", (item_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail={"error_code": "ITEM_NOT_FOUND", "message": "Task not found"})

    t = dict(row)
    is_correct = len(user_ans) >= 2
    old_box = t["box_level"]
    now_str = now_utc_iso()

    if is_correct:
        new_box = min(old_box + 1, 5)
        next_review = compute_next_review(new_box)
        st = 'mastered' if new_box == 5 else 'active'
        m_at = now_str if new_box == 5 else t.get("mastered_at")

        execute_with_retry(conn, """
            UPDATE review_index_current
            SET box_level=?, status=?, last_reviewed_at=?, next_review_at=?, mastered_at=?, updated_at=?
            WHERE item_id=?
        """, (new_box, st, now_str, next_review, m_at, now_str, item_id))
        
        execute_with_retry(conn, """
            INSERT INTO review_index_log (item_id, action, from_box, to_box, created_at)
            VALUES (?, 'verify_correct', ?, ?, ?)
        """, (item_id, old_box, new_box, now_str))
        conn.commit(); conn.close()
        next_display = next_review[:10] if next_review else "已精通畢業"
        return {"status": "success", "is_correct": True, "feedback": f"✅ 觀念精準！已晉級至 Box {new_box}！下一次到期：{next_display}", "new_box": new_box}
    else:
        new_box = max(old_box - 1, 1)
        next_review = compute_next_review(new_box)
        new_wrong_count = t["wrong_count"] + 1

        execute_with_retry(conn, """
            UPDATE review_index_current
            SET box_level=?, status='active', wrong_count=?, last_wrong_at=?, last_reviewed_at=?, next_review_at=?, updated_at=?
            WHERE item_id=?
        """, (new_box, new_wrong_count, now_str, now_str, next_review, now_str, item_id))

        execute_with_retry(conn, """
            INSERT INTO review_index_log (item_id, action, from_box, to_box, created_at)
            VALUES (?, 'verify_wrong', ?, ?, ?)
        """, (item_id, old_box, new_box, now_str))
        conn.commit(); conn.close()
        return {"status": "success", "is_correct": False, "feedback": f"❌ 標準解析：{t['answer']}\n已降級至 Box {new_box}，明天繼續防禦！", "new_box": new_box}

# API 5: /api/ingest
@app.post("/api/ingest")
async def ingest_task(payload: IngestPayload):
    conn = get_connection()
    st_str = 'pending_review' if payload.ocr_confidence >= OCR_CONFIDENCE_THRESHOLD else 'fallback_manual'
    cur = execute_with_retry(conn, """
        INSERT INTO ingestion_staging (question, answer, subject, topic, ocr_confidence, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (payload.question, payload.answer, payload.subject, payload.topic, payload.ocr_confidence, st_str, now_utc_iso()))
    staging_id = cur.lastrowid
    conn.commit(); conn.close()

    msg = "📥 已進入 Staging 緩衝區，等待人工 Approve 轉正。" if st_str == 'pending_review' else "⚠️ OCR 信心度低於 70%，已觸發 Fallback 降級，請手動校正。"
    return {"status": "success", "staging_id": staging_id, "ocr_confidence": payload.ocr_confidence, "message": msg}

# API 6: /api/ingest/approve
@app.post("/api/ingest/approve")
async def approve_staging_task(payload: ApprovePayload):
    conn = get_connection()
    row = conn.execute("SELECT * FROM ingestion_staging WHERE staging_id=?", (payload.staging_id,)).fetchone()
    if not row or row["status"] == 'approved':
        conn.close()
        raise HTTPException(status_code=404, detail={"error_code": "STAGING_NOT_FOUND", "message": "Staging item not found or already approved"})

    new_uuid = f"item_{uuid.uuid4().hex[:8]}"
    now_str = now_utc_iso()
    next_at = compute_next_review(1)

    official_img = None
    if row["image_path"] and os.path.exists(row["image_path"]):
        os.makedirs(MEDIA_OFFICIAL_DIR, exist_ok=True)
        ext = os.path.splitext(row["image_path"])[1] or ".jpg"
        official_img = os.path.join(MEDIA_OFFICIAL_DIR, f"{new_uuid}{ext}")
        shutil.move(row["image_path"], official_img)

    execute_with_retry(conn, """
        INSERT INTO review_index_current (item_id, subject, topic, question, answer, image_path, box_level, status, next_review_at, created_at)
        VALUES (?, ?, ?, ?, ?, ?, 1, 'pending', ?, ?)
    """, (new_uuid, row["subject"], row["topic"], row["question"], row["answer"], official_img, next_at, now_str))

    execute_with_retry(conn, "INSERT INTO review_index_log (item_id, action, from_box, to_box, created_at) VALUES (?, 'ingest_approve', 0, 1, ?)", (new_uuid, now_str))
    execute_with_retry(conn, "UPDATE ingestion_staging SET status='approved' WHERE staging_id=?", (payload.staging_id,))
    conn.commit(); conn.close()

    return {"status": "success", "item_id": new_uuid, "message": "✅ 已人工轉正寫入正式防禦庫 review_index_current！"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
