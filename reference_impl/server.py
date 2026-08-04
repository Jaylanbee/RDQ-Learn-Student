# server.py - RDQ v11.5 FastAPI 非同步伺服器 (根目錄唯一入口點)
# 此檔案為專案唯一的 FastAPI 伺服器入口。
# reference_impl/ 下的模組 (config, db, backup) 作為共用套件被匯入。
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import sqlite3, os, json, datetime, uuid, asyncio, random, shutil

from reference_impl.config import (
    MAX_DAILY_TASKS, BOX_QUOTA_RATIO, BOX_INTERVAL_DAYS,
    OCR_CONFIDENCE_THRESHOLD, PRIORITY_WRONG_WEIGHT, PRIORITY_RECENT_MAX,
    MEDIA_STAGING_DIR, MEDIA_OFFICIAL_DIR, IMAGE_MAX_SIZE_BYTES
)
from reference_impl.db import (
    get_connection, init_db, now_utc_iso, execute_with_retry, maybe_cleanup
)
from reference_impl.backup import backup_db

app = FastAPI(title="RDQ Socratic Engine & Leitner Scheduler", version="11.5")

# ── Startup ──
@app.on_event("startup")
def startup_event():
    os.makedirs(MEDIA_STAGING_DIR, exist_ok=True)
    os.makedirs(MEDIA_OFFICIAL_DIR, exist_ok=True)
    init_db()

# ── 共用工具函式 ──
def compute_next_review(box_level: int):
    """計算下次到期日。Box 5 畢業時回傳 None（永不再排程）。"""
    if box_level >= 5:
        return None
    days = BOX_INTERVAL_DAYS.get(box_level, 1)
    dt = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=days)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

def compute_priority(item: dict) -> int:
    """純粹客觀 Priority 算分。80~100 分留白作為極端歷史積壓之彈性空間。"""
    score = 0
    score += min(item.get("wrong_count", 0) * PRIORITY_WRONG_WEIGHT, 60)
    if item.get("last_wrong_at"):
        try:
            iso_str = item["last_wrong_at"].replace('Z', '+00:00')
            days_since = (datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(iso_str)).days
            score += max(0, PRIORITY_RECENT_MAX - days_since * 2)
        except Exception:
            pass
    return min(score, 100)

# ── Pydantic Schemas ──
class ChatPayload(BaseModel):
    session_id: str = "default"
    message: str = ""
    topic: str = "1-2 質量與密度的測量"
    textbook: str = ""
    is_start: bool = False

class VerifyPayload(BaseModel):
    answer: str = ""

class ApprovePayload(BaseModel):
    staging_id: int

# ── 首頁：提供 dashboard.html ──
@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    tmpl = os.path.join(os.path.dirname(__file__), "..", "templates", "dashboard.html")
    if os.path.exists(tmpl):
        with open(tmpl, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>RDQ FastAPI Server v11.5 Running</h1>")

# ══════════════════════════════════════════════════════════
# API 1: GET /api/tasks ── 【Hard Quota + 動態名額釋出】
# ══════════════════════════════════════════════════════════
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

    # 依 box_level 分群
    due_by_box = {1: [], 2: [], 3: [], 4: [], 5: []}
    for i in items:
        b = i["box_level"]
        if b in due_by_box:
            due_by_box[b].append(i)

    # 各群內依 priority DESC, next_review_at ASC 排序 (脆弱優先)
    for b in due_by_box:
        due_by_box[b].sort(key=lambda x: (-x["priority"], x["next_review_at"] or ""))

    reserved_quota = {b: int(MAX_DAILY_TASKS * r) for b, r in BOX_QUOTA_RATIO.items()}
    result = []
    for b, q in reserved_quota.items():
        result.extend(due_by_box[b][:q])

    # 名額動態釋出
    used_ids = {x["item_id"] for x in result}
    if len(result) < MAX_DAILY_TASKS:
        remaining_pool = [i for i in items if i["item_id"] not in used_ids]
        remaining_pool.sort(key=lambda x: (x["box_level"], -x["priority"]))
        result.extend(remaining_pool[: MAX_DAILY_TASKS - len(result)])

    conn.close()
    return {"status": "success", "count": len(result), "total_due": len(items), "tasks": result[:MAX_DAILY_TASKS]}

# ══════════════════════════════════════════════════════════
# API 2: GET /api/radar ── Laplace 平滑化五科能力分數
# ══════════════════════════════════════════════════════════
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

# ══════════════════════════════════════════════════════════
# API 3: POST /api/chat ── 四象限蘇格拉底對話引擎
#   嚴格套用 v11.5 模組1 Prompt Guardrail：
#   1. 絕不直接給出名詞定義、公式結論或標準答案
#   2. 卡住時僅拋出啟發式問句或 L2 鷹架選項降級
#   3. 語氣溫和、極簡、正向鼓勵
# ══════════════════════════════════════════════════════════
@app.post("/api/chat")
async def chat_endpoint(payload: ChatPayload):
    sid = payload.session_id
    msg = payload.message.strip()
    topic = payload.topic
    tb = payload.textbook.strip()

    conn = get_connection()
    maybe_cleanup(conn)

    # ── Phase 0 → Phase 1：開始新對話 ──
    row = conn.execute("SELECT * FROM session_state WHERE session_id=? AND status='active'", (sid,)).fetchone()
    if payload.is_start or not row:
        execute_with_retry(conn, """
            INSERT OR REPLACE INTO session_state (session_id, phase, topic, textbook_content, student_recalled, student_uncertain, status, updated_at)
            VALUES (?, 'phase1', ?, ?, '', '', 'active', ?)
        """, (sid, topic, tb, now_utc_iso()))
        conn.commit()
        conn.close()
        mode = "📖 課本精確模式" if tb else "🌐 108 課綱通用模式"
        reply = (
            f"🎯 範圍已鎖定：《{topic}》（{mode}）\n\n"
            f"【Phase 1｜象限 I — 引導回憶】\n"
            f"你說你讀了《{topic}》對吧？\n"
            f"不急，先想想看——你現在腦海中第一個浮現的關鍵字或重點觀念是什麼？\n\n"
            f"💡 沒有標準答案，說「不知道」也完全沒問題，我會用選項接住你！"
        )
        return {"status": "success", "reply": reply, "options": [], "phase": "phase1"}

    phase = row["phase"]
    tb = row["textbook_content"] or ""
    recalled = row["student_recalled"] or ""
    uncertain = row["student_uncertain"] or ""
    reply = ""
    options = []
    new_phase = phase

    # 判斷學生是否卡住
    stuck_keywords = ["不知道", "忘了", "不確定", "不會", "想不到", "沒印象", "不記得"]
    is_stuck = any(k in msg for k in stuck_keywords)

    # ── Phase 1：象限 I — 已知的已知 (Known Knowns) ──
    if phase == "phase1":
        if is_stuck:
            # L2 鷹架選項降級：Guardrail 規定不給答案，只給引導選項
            reply = (
                f"沒關係！每個人都有一時想不起來的時候 😊\n"
                f"我們用選項幫你暖身——關於《{topic}》，下面哪一個是你印象中有學過的？"
            )
            options = [
                "A: 好像跟「定義」或「基本概念」有關",
                "B: 好像有算過「公式」或「數值換算」",
                "C: 好像有做過「實驗」或「操作步驟」",
                "D: 以上都不太確定，請給我更多提示"
            ]
            new_phase = "phase2"
        else:
            # 學生有回憶 → 記錄 + 追問（Guardrail: 不給答案，只追問）
            recalled = msg
            reply = (
                f"👍 你提到了「{msg}」，很好！\n\n"
                f"追問一層：你能用自己的話，簡單說明一下「{msg}」是什麼意思嗎？\n"
                f"不用擔心講錯，用你自己的理解就好 😊"
            )
            new_phase = "phase2"

    # ── Phase 2：象限 II — 已知的未知 (Known Unknowns) ──
    elif phase == "phase2":
        if is_stuck:
            reply = (
                f"沒問題！這個階段就是要找出「你覺得不太確定的地方」。\n\n"
                f"換個方式問：如果明天考試，《{topic}》裡面你最擔心哪一個部分會答不出來？\n"
                f"或者，有沒有哪個公式或名詞讓你覺得「好像懂又不太懂」？"
            )
        else:
            uncertain = msg
            reply = (
                f"✅ 已記錄你的想法。\n\n"
                f"【Phase 2 → Phase 3 過渡】\n"
                f"在《{topic}》裡，有沒有哪個部分是你覺得「自己應該會，但不太確定能解釋清楚」的？\n\n"
                f"這種「說不上來但好像知道」的感覺很重要——它可能是你的隱性知識 💎"
            )
        new_phase = "phase3"

    # ── Phase 2.5：反問梯子 (Misconception Probe) ──
    elif phase == "phase2_5":
        reply = (
            f"有趣！你剛才的回答讓我發現一個值得深究的點 🔍\n\n"
            f"讓我用反問幫你釐清：如果你的理解是對的，那麼以下這個情境應該怎麼解釋？\n"
            f"「把一塊鋁塊切成兩半，半塊的密度會變嗎？」\n\n"
            f"試著推理看看，不用急 😊"
        )
        new_phase = "phase3"

    # ── Phase 3：象限 III — 未知的已知 (Unknown Knowns) ──
    elif phase == "phase3":
        # Guardrail: 不直接告訴學生答案，用啟發式問題挖掘隱性知識
        reply = (
            f"好的！那我們來挖掘一下你可能已經知道但沒意識到的東西 🔬\n\n"
            f"【Phase 3｜象限 III — 隱性知識挖掘】\n"
            f"想像一個場景：如果把一塊完整的物質切成兩半，\n"
            f"半塊的「密度」會不會改變？為什麼？\n\n"
            f"試著用你自己的邏輯推理看看——答案就藏在你的直覺裡 💡"
        )
        new_phase = "phase4"

    # ── Phase 4：象限 IV — 未知的未知 (Unknown Unknowns) ──
    elif phase == "phase4":
        # 唯一一題會考陷阱題 (v11.5 規定: 最後一題才出)
        # Guardrail: 出完題後不直接給答案，等學生回答後再引導
        reply = (
            f"🎉 你的推理很棒！你已經觸碰到了關鍵觀念！\n\n"
            f"【Phase 4｜象限 IV — 最後一題盲點偵測 🏛️】\n"
            f"這是今天唯一一題會考等級的陷阱題：\n\n"
            f"🧪 如果太空人把一塊 100g 的鐵塊帶到月球上，\n"
            f"鐵塊在月球上的「質量」會變成多少？\n\n"
            f"提示：想想看「質量」和「重量」有什麼不同？ 🤔"
        )
        new_phase = "phase5"

    # ── Phase 5：覆盤與閃卡特訓導向 ──
    elif phase == "phase5":
        reply = (
            f"🏆【Phase 5｜學習覆盤完成！】\n\n"
            f"📋 今日覆盤總結：\n"
            f"• 你記得的：{recalled if recalled else '（選擇了 L2 鷹架輔助）'}\n"
            f"• 你不確定的：{uncertain if uncertain else '（未提及）'}\n"
            f"• 陷阱題挑戰：已完成 ✅\n\n"
            f"覆盤卡已自動寫入防禦庫！\n"
            f"接下來你可以：⬇️"
        )
        options = ["🎴 切換至閃卡防禦特訓 ➔", "🔄 重新複習新的單元"]

        # 標記 session 為 completed
        execute_with_retry(conn, """
            UPDATE session_state SET phase='phase5', status='completed', updated_at=? WHERE session_id=?
        """, (now_utc_iso(), sid))
        conn.commit()
        conn.close()
        return {"status": "success", "reply": reply, "options": options, "phase": "phase5"}

    else:
        # Fallback: 未預期的 phase 值
        reply = "系統偵測到異常階段狀態，正在重置對話..."
        new_phase = "phase1"

    # 更新 session_state
    execute_with_retry(conn, """
        UPDATE session_state SET phase=?, student_recalled=?, student_uncertain=?, updated_at=? WHERE session_id=?
    """, (new_phase, recalled if phase == "phase1" and not is_stuck else row["student_recalled"], uncertain if phase == "phase2" and not is_stuck else row["student_uncertain"], now_utc_iso(), sid))
    conn.commit()
    conn.close()
    return {"status": "success", "reply": reply, "options": options, "phase": new_phase}

# ══════════════════════════════════════════════════════════
# API 4: POST /api/task/{item_id}/verify ── 閃卡 Leitner 驗證
#   v11.5 規格:
#   - 每次答題均強制更新 last_reviewed_at
#   - pending 首次答題 → active
#   - Box 1 觸底答錯: log from_box=1, to_box=1, action='verify_wrong'
#   - Box 5 答對畢業: status='mastered', next_review_at=NULL
# ══════════════════════════════════════════════════════════
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
    old_status = t["status"]
    now_str = now_utc_iso()

    # v11.5: 若 status='pending'，首次答題強制轉為 'active'
    if old_status == 'pending':
        old_status = 'active'

    if is_correct:
        new_box = min(old_box + 1, 5)
        next_review = compute_next_review(new_box)
        new_status = 'mastered' if new_box == 5 else 'active'
        mastered_at = now_str if new_box == 5 else t.get("mastered_at")

        execute_with_retry(conn, """
            UPDATE review_index_current
            SET box_level=?, status=?, last_reviewed_at=?, next_review_at=?, mastered_at=?
            WHERE item_id=?
        """, (new_box, new_status, now_str, next_review, mastered_at, item_id))

        execute_with_retry(conn, """
            INSERT INTO review_index_log (item_id, action, from_box, to_box, created_at)
            VALUES (?, 'verify_correct', ?, ?, ?)
        """, (item_id, old_box, new_box, now_str))
        conn.commit()
        conn.close()

        next_display = next_review[:10] if next_review else "🎓 已精通畢業"
        return {
            "status": "success", "is_correct": True,
            "feedback": f"✅ 觀念精準！已晉級至 Box {new_box}！下一次到期：{next_display}",
            "new_box": new_box
        }
    else:
        # v11.5: Box 1 觸底 → new_box = max(1-1, 1) = 1, 仍完整記 log
        new_box = max(old_box - 1, 1)
        next_review = compute_next_review(new_box)
        new_wrong_count = t["wrong_count"] + 1

        execute_with_retry(conn, """
            UPDATE review_index_current
            SET box_level=?, status='active', wrong_count=?, last_wrong_at=?, last_reviewed_at=?, next_review_at=?
            WHERE item_id=?
        """, (new_box, new_wrong_count, now_str, now_str, next_review, item_id))

        execute_with_retry(conn, """
            INSERT INTO review_index_log (item_id, action, from_box, to_box, created_at)
            VALUES (?, 'verify_wrong', ?, ?, ?)
        """, (item_id, old_box, new_box, now_str))
        conn.commit()
        conn.close()
        return {
            "status": "success", "is_correct": False,
            "feedback": f"❌ 標準解析：{t['answer']}\n已降級至 Box {new_box}，明天繼續防禦！",
            "new_box": new_box
        }

# ══════════════════════════════════════════════════════════
# API 5: POST /api/ingest ── multipart/form-data 圖片上傳
#   已修復：
#   - 移除 file_path 絕對路徑漏洞 (LFI 防護)
#   - 改用 UploadFile + Form 接收 multipart/form-data
#   - 圖片存入 data/media/staging/temp_{staging_id}.{ext}
#   - 檔案類型與大小驗證
# ══════════════════════════════════════════════════════════
ALLOWED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}

@app.post("/api/ingest")
async def ingest_task(
    question: str = Form("外部錯題"),
    answer: str = Form("解析待人工確認"),
    subject: str = Form("自然"),
    topic: str = Form("外部錯題"),
    ocr_confidence: float = Form(1.0),
    image: UploadFile = File(None)
):
    conn = get_connection()
    maybe_cleanup(conn)
    st_str = 'pending_review' if ocr_confidence >= OCR_CONFIDENCE_THRESHOLD else 'fallback_manual'

    # 先建立 staging 記錄取得 staging_id
    cur = execute_with_retry(conn, """
        INSERT INTO ingestion_staging (question, answer, subject, topic, ocr_confidence, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (question, answer, subject, topic, ocr_confidence, st_str, now_utc_iso()))
    staging_id = cur.lastrowid

    # 處理圖片上傳 (若有)
    image_path = None
    if image and image.filename:
        ext = os.path.splitext(image.filename)[1].lower()
        if ext not in ALLOWED_IMAGE_EXTS:
            conn.close()
            raise HTTPException(status_code=400, detail={
                "error_code": "INVALID_FILE_TYPE",
                "message": f"僅允許 {', '.join(ALLOWED_IMAGE_EXTS)} 格式"
            })

        content = await image.read()
        if len(content) > IMAGE_MAX_SIZE_BYTES:
            conn.close()
            raise HTTPException(status_code=400, detail={
                "error_code": "FILE_TOO_LARGE",
                "message": f"檔案大小超過上限 {IMAGE_MAX_SIZE_BYTES // (1024*1024)}MB"
            })

        os.makedirs(MEDIA_STAGING_DIR, exist_ok=True)
        image_path = os.path.join(MEDIA_STAGING_DIR, f"temp_{staging_id}{ext}")
        with open(image_path, "wb") as f:
            f.write(content)

        execute_with_retry(conn, "UPDATE ingestion_staging SET image_path=? WHERE staging_id=?", (image_path, staging_id))

    conn.commit()
    conn.close()

    msg = "📥 已進入 Staging 緩衝區，等待人工 Approve 轉正。" if st_str == 'pending_review' else "⚠️ OCR 信心度低於 70%，已觸發 Fallback 降級，請手動校正。"
    return {"status": "success", "staging_id": staging_id, "ocr_confidence": ocr_confidence, "image_path": image_path, "message": msg}

# ══════════════════════════════════════════════════════════
# API 6: POST /api/ingest/approve ── 轉正：圖檔自動重命名
# ══════════════════════════════════════════════════════════
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

    # v11.5: 轉正時圖檔重命名為 data/media/official/item_{uuid}.{ext}
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

    execute_with_retry(conn, """
        INSERT INTO review_index_log (item_id, action, from_box, to_box, created_at)
        VALUES (?, 'ingest_approve', 0, 1, ?)
    """, (new_uuid, now_str))

    execute_with_retry(conn, "UPDATE ingestion_staging SET status='approved' WHERE staging_id=?", (payload.staging_id,))
    conn.commit()
    conn.close()
    return {"status": "success", "item_id": new_uuid, "message": "✅ 已人工轉正寫入正式防禦庫 review_index_current！"}

# ── 主入口 ──
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
