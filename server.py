# server.py - RDQ v11.5 FastAPI 非同步伺服器 (根目錄唯一入口點)
# 此檔案為專案唯一的 FastAPI 伺服器入口。
# reference_impl/ 下的模組 (config, db, backup) 作為共用套件被匯入。
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import sqlite3
import os
import json
import datetime
import uuid
import asyncio
import random
import shutil
from google import genai
from google.genai import types

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


# ── Mount Static Media ──
os.makedirs("data/media/staging", exist_ok=True)
os.makedirs("data/media/official", exist_ok=True)
app.mount(
    "/data/media/staging",
    StaticFiles(
        directory="data/media/staging"),
    name="staging_media")
app.mount(
    "/data/media/official",
    StaticFiles(
        directory="data/media/official"),
    name="official_media")

# ── 共用工具函式 ──

def get_student_cognitive_summary(subject: str) -> str:
    """查詢當前學科最近 5 筆未完全根治 (is_resolved=0) 的盲點摘要"""
    conn = get_connection()
    rows = conn.execute("""
        SELECT topic, weakness_summary, occurred_count
        FROM student_cognitive_profile
        WHERE subject = ? AND is_resolved = 0
        ORDER BY updated_at DESC LIMIT 5
    """, (subject,)).fetchall()
    conn.close()

    if not rows:
        return "尚無歷史盲點紀錄，請進行基礎觀念過場。"

    summary_lines = []
    for r in rows:
        summary_lines.append(f"- 《{r[0]}》：{r[1]} (累積發生 {r[2]} 次)")
    return "\n".join(summary_lines)


def compute_next_review(box_level: int):
    """計算下次到期日。Box 5 畢業時回傳 None（永不再排程）。"""
    if box_level >= 5:
        return None
    days = BOX_INTERVAL_DAYS.get(box_level, 1)
    dt = datetime.datetime.now(datetime.timezone.utc) + \
        datetime.timedelta(days=days)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def compute_priority(item: dict) -> int:
    """純粹客觀 Priority 算分。80~100 分留白作為極端歷史積壓之彈性空間。"""
    score = 0
    score += min(item.get("wrong_count", 0) * PRIORITY_WRONG_WEIGHT, 60)
    if item.get("last_wrong_at"):
        try:
            iso_str = item["last_wrong_at"].replace('Z', '+00:00')
            days_since = (
                datetime.datetime.now(
                    datetime.timezone.utc) -
                datetime.datetime.fromisoformat(iso_str)).days
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
    mode: str = "light"  # "light" or "full"


class VerifyPayload(BaseModel):
    answer: str = ""
    loss_reason: str = None
    mode: str = "light"  # "light" or "full"


class IncorrectPayload(BaseModel):
    loss_reason: str = None


class ApprovePayload(BaseModel):
    staging_id: int

# ── 首頁：提供 dashboard.html ──


@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    tmpl = os.path.join(
        os.path.dirname(__file__),
        "templates",
        "dashboard.html")
    if os.path.exists(tmpl):
        with open(tmpl, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>RDQ FastAPI Server v11.5 Running</h1>")

# ══════════════════════════════════════════════════════════
# API 0: GET /api/staging ── 取得 Pending 狀態的待審核資料
# ══════════════════════════════════════════════════════════


@app.get("/api/staging")
async def get_staging():
    conn = get_connection()
    maybe_cleanup(conn)
    rows = conn.execute("""
        SELECT * FROM ingestion_staging
        WHERE status = 'pending_review' OR status = 'fallback_manual'
        ORDER BY created_at DESC
    """).fetchall()
    conn.close()
    return {"status": "success", "tasks": [dict(r) for r in rows]}

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
        due_by_box[b].sort(
            key=lambda x: (-x["priority"], x["next_review_at"] or ""))

    reserved_quota = {b: int(MAX_DAILY_TASKS * r)
                      for b, r in BOX_QUOTA_RATIO.items()}
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
    return {"status": "success",
            "count": len(result),
            "total_due": len(items),
            "tasks": result[:MAX_DAILY_TASKS]}

# ══════════════════════════════════════════════════════════
# API 2: GET /api/radar ── Laplace 平滑化五科能力分數
# ══════════════════════════════════════════════════════════


@app.get("/api/radar")
async def get_radar():
    conn = get_connection()
    subjects = ["國文", "英語", "數學", "自然", "社會"]
    radar = {}
    for s in subjects:
        total = conn.execute(
            "SELECT COUNT(*) as c FROM review_index_current WHERE subject=?",
            (s,
             )).fetchone()["c"]
        mastered = conn.execute(
            "SELECT COUNT(*) as c FROM review_index_current WHERE subject=? AND status='mastered'",
            (s,
             )).fetchone()["c"]
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
    row = conn.execute(
        "SELECT * FROM session_state WHERE session_id=? AND status='active'",
        (sid,
         )).fetchone()
    if payload.is_start or not row:
        execute_with_retry(conn, """
            INSERT OR REPLACE INTO session_state (session_id, phase, topic, textbook_content, student_recalled, student_uncertain, status, updated_at)
            VALUES (?, 'phase1', ?, ?, '', '', 'active', ?)
        """, (sid, topic, tb, now_utc_iso()))
        conn.commit()
        conn.close()
        mode_str = "📖 課本精確模式" if tb else "🌐 108 課綱通用模式"
        reply = (
            f"🎯 範圍已鎖定：《{topic}》（{mode_str}）\n\n"
            f"【Phase 1｜象限 I — 引導回憶】\n"
            f"你說你讀了《{topic}》對吧？\n"
            f"不急，先想想看——你現在腦海中第一個浮現的關鍵字或重點觀念是什麼？\n\n"
            f"💡 沒有標準答案，說「不知道」也完全沒問題，我會用選項接住你！"
        )
        return {
            "status": "success",
            "reply": reply,
            "options": [],
            "phase": "phase1"}

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

    if payload.mode == "full":
        # Full Mode: 真實 LLM 呼叫 (Gemini)
        gemini_api_key = os.environ.get("GEMINI_API_KEY")
        if gemini_api_key:
            client = genai.Client(api_key=gemini_api_key)

            # v12.5 長週期記憶注入
            subject_to_query = "自然" # fallback
            if "數學" in topic: subject_to_query = "數學"
            elif "自然" in topic: subject_to_query = "自然"

            history_summary = get_student_cognitive_summary(subject_to_query)
            history_context = f"💡 【RDQ Jules 架構師長週期記憶注入】過去未完全解決的盲點如下：\n{history_summary}"

            prompt = f"""
你是一位嚴格、溫和且極具啟發力的國中會考導師（100% 遵照 RDQ 蘇格拉底教學法）。
學生的複習主題是：{topic}
{history_context}
學生已回憶的內容：{recalled}
學生覺得不懂的地方：{uncertain}
[學生最新回答]: {msg}

請拋出一個啟發式的追問，引導他發現自己的迷思概念。
如果學生當前的表現與過去未解決的盲點有關，請在引導中巧妙地融入並提示。
請以 JSON 格式回傳，包含 `reply` (你的引導) 和 `options` (一個包含2~4個選項的陣列，如果不需要選項可以給空陣列)。
"""

            class ChatResult(BaseModel):
                reply: str = Field(description="給學生的不直接破題的引導")
                options: list[str] = Field(description="選項陣列")
            try:
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=ChatResult,
                    )
                )
                result_json = json.loads(response.text)
                reply = result_json.get(
                    "reply", "🤖 (LLM 深度追問) 這是一個很有趣的觀點！讓我們再深入想想看。")
                options = result_json.get("options", [])
            except Exception as e:
                print(f"Gemini API 呼叫失敗: {e}")
                reply = (
                    f"🤖 (Fallback 深度追問)\n"
                    f"這是一個很有趣的觀點！你提到「{msg if len(msg) < 10 else msg[:10] + '...'}」。\n"
                    f"我們再深入想想看，這和《{topic}》的核心概念有什麼關聯？如果我們換個角度來看，結果會不會不一樣？"
                )
        else:
            reply = (
                f"🤖 (Fallback 深度追問)\n"
                f"這是一個很有趣的觀點！你提到「{msg if len(msg) < 10 else msg[:10] + '...'}」。\n"
                f"我們再深入想想看，這和《{topic}》的核心概念有什麼關聯？如果我們換個角度來看，結果會不會不一樣？"
            )

        # Phase 5: 在完整 LLM 模式下，判斷對話是否已完成並進行總結
        new_phase = "phase5"
        execute_with_retry(conn, """
            UPDATE session_state SET phase=?, updated_at=? WHERE session_id=?
        """, (new_phase, now_utc_iso(), sid))

        # v12.5 紀錄盲點到 cognitive profile
        if new_phase == "phase5":
             try:
                summary_prompt = f"""
學生的複習主題：{topic}
學生已回憶的內容：{recalled}
學生覺得不懂的地方：{uncertain}
學生最後的回答：{msg}

請評估這段對話中學生展現的「盲點」或「迷思概念」。
如果學生已經完全理解，回傳空字串。
否則，回傳一個簡短的摘要描述學生的盲點（例如："-(a-b)² 負號分配律變號陷阱"）及可能的 loss_reason ("概念錯誤", "計算錯誤", "看錯題目", "圖表判讀")，以 JSON 格式回傳：
{{
  "weakness_summary": "盲點描述摘要",
  "loss_reason": "對應的錯因分類"
}}
"""
                class SummaryResult(BaseModel):
                    weakness_summary: str = Field(description="盲點描述摘要")
                    loss_reason: str = Field(description="對應的錯因分類 (概念錯誤, 計算錯誤, 看錯題目, 圖表判讀)")

                summary_resp = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=summary_prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=SummaryResult,
                    )
                )

                summary_json = json.loads(summary_resp.text)
                weakness_summary = summary_json.get("weakness_summary", "").strip()
                loss_reason = summary_json.get("loss_reason", "概念錯誤")
                if loss_reason not in ["計算錯誤", "概念錯誤", "看錯題目", "圖表判讀"]:
                    loss_reason = "概念錯誤"

                if weakness_summary:
                    subject_to_save = "自然" # fallback
                    if "數學" in topic: subject_to_save = "數學"
                    elif "自然" in topic: subject_to_save = "自然"

                    # 檢查是否已有類似紀錄 (簡單處理：用主題與科目找最近的一筆)
                    existing_row = conn.execute(
                        "SELECT profile_id, weakness_summary, occurred_count FROM student_cognitive_profile WHERE subject=? AND topic=? AND is_resolved=0 ORDER BY updated_at DESC LIMIT 1",
                        (subject_to_save, topic)
                    ).fetchone()

                    now_str = now_utc_iso()
                    if existing_row:
                        execute_with_retry(conn, """
                            UPDATE student_cognitive_profile
                            SET occurred_count = occurred_count + 1, weakness_summary = ?, loss_reason = ?, updated_at = ?
                            WHERE profile_id = ?
                        """, (weakness_summary, loss_reason, now_str, existing_row["profile_id"]))
                    else:
                        execute_with_retry(conn, """
                            INSERT INTO student_cognitive_profile (subject, topic, weakness_summary, loss_reason, occurred_count, is_resolved, created_at, updated_at)
                            VALUES (?, ?, ?, ?, 1, 0, ?, ?)
                        """, (subject_to_save, topic, weakness_summary, loss_reason, now_str, now_str))
             except Exception as e:
                print(f"盲點摘要儲存失敗: {e}")

        conn.commit()
        conn.close()
        return {
            "status": "success",
            "reply": reply,
            "options": options,
            "phase": new_phase}

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
        return {
            "status": "success",
            "reply": reply,
            "options": options,
            "phase": "phase5"}

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
    return {
        "status": "success",
        "reply": reply,
        "options": options,
        "phase": new_phase}

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
    row = conn.execute(
        "SELECT * FROM review_index_current WHERE item_id=?",
        (item_id,
         )).fetchone()
    if not row:
        conn.close()
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "ITEM_NOT_FOUND",
                "message": "Task not found"})

    t = dict(row)

    is_correct = False
    loss_reason = payload.loss_reason
    feedback_msg = ""

    if payload.mode == "full":
        # Full Mode: 真實 LLM 呼叫 (Gemini)
        gemini_api_key = os.environ.get("GEMINI_API_KEY")
        if not gemini_api_key:
            # 如果沒有設定 API Key，退回 Light Mode
            is_correct = len(user_ans) >= 2
            feedback_msg = "✅ (Fallback) 觀念精準！" if is_correct else "❌ (Fallback) 答案太短或無效。"
            if not is_correct and not loss_reason:
                loss_reason = "概念錯誤"
        else:
            client = genai.Client(api_key=gemini_api_key)
            prompt = f"""
你是一位嚴格但溫和的蘇格拉底導師。
學生正在回答以下問題：
【題目】：{t['question']}
【標準答案】：{t['answer']}
【學生的回答】：{user_ans}

請根據學生的回答判斷是否正確，並提供一段啟發式的回饋訊息(Socratic feedback)。
如果學生的回答不完全或有錯誤，請找出錯誤的原因 (loss_reason)。
loss_reason 只能是以下四種之一：["計算錯誤", "概念錯誤", "看錯題目", "圖表判讀"]。如果無法歸類，請預設為 "概念錯誤"。
"""

            class VerifyResult(BaseModel):
                is_correct: bool = Field(description="學生是否答對")
                loss_reason: str = Field(
                    default=None, description="若答錯，失分的原因分類 (計算錯誤/概念錯誤/看錯題目/圖表判讀)")
                feedback_msg: str = Field(description="給學生的蘇格拉底引導回饋，絕不直接給答案")

            try:
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=VerifyResult,
                    ),
                )

                result_json = json.loads(response.text)
                is_correct = result_json.get("is_correct", False)
                feedback_msg = result_json.get("feedback_msg", "無法解析 LLM 回饋")
                if not is_correct:
                    loss_reason = result_json.get("loss_reason")
                    if loss_reason not in ["計算錯誤", "概念錯誤", "看錯題目", "圖表判讀"]:
                        loss_reason = "概念錯誤"
            except Exception as e:
                print(f"Gemini API 呼叫失敗: {e}")
                is_correct = len(user_ans) >= 2
                feedback_msg = "✅ (Fallback) 觀念精準！" if is_correct else "❌ (Fallback) 答案太短或無效。"
                if not is_correct and not loss_reason:
                    loss_reason = "概念錯誤"
    else:
        # Light Mode: 快速規則引擎
        is_correct = len(user_ans) >= 2
        feedback_msg = "✅ 觀念精準！" if is_correct else "❌ 答案太短或無效。"

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
            "status": "success",
            "is_correct": True,
            "feedback": f"{feedback_msg} 已晉級至 Box {new_box}！下一次到期：{next_display}",
            "new_box": new_box}
    else:
        # 若是 light 模式，且缺少 loss_reason，則先回傳要求前端補齊 (這已由前端 handle，但後端亦可再擋)
        if payload.mode == "light" and not loss_reason:
            return {
                "status": "success",
                "is_correct": False,
                "feedback": f"{feedback_msg} 標準解析：{
                    t['answer']}\n請選擇失分原因後再次送出。",
                "new_box": old_box}

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
            INSERT INTO review_index_log (item_id, action, from_box, to_box, loss_reason, created_at)
            VALUES (?, 'verify_wrong', ?, ?, ?, ?)
        """, (item_id, old_box, new_box, loss_reason, now_str))
        conn.commit()
        conn.close()
        return {
            "status": "success", "is_correct": False,
            "feedback": f"❌ 標準解析：{t['answer']}\n已降級至 Box {new_box}，明天繼續防禦！",
            "new_box": new_box
        }

# ══════════════════════════════════════════════════════════
# API 4.1: POST /api/task/{item_id}/correct ── EDS / Agent 專用正確端點
# ══════════════════════════════════════════════════════════


@app.post("/api/task/{item_id}/correct")
async def correct_task(item_id: str):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM review_index_current WHERE item_id=?",
        (item_id,
         )).fetchone()
    if not row:
        conn.close()
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "ITEM_NOT_FOUND",
                "message": "Task not found"})

    t = dict(row)
    old_box = t.get("box_level", 1) or 1
    old_status = t.get("status", "pending")
    now_str = now_utc_iso()

    if old_status == 'pending':
        old_status = 'active'

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

    return {"status": "success", "action": "correct", "new_box": new_box}

# ══════════════════════════════════════════════════════════
# API 4.1.5: GET /api/eds/export-weaknesses ── EDS 弱點圖譜匯出端點
# ══════════════════════════════════════════════════════════


@app.get("/api/eds/export-weaknesses")
async def export_weaknesses():
    conn = get_connection()
    # 撈取可能需要考前特訓的題目：
    # 1. 狀態為 active 且 box_level 較低 (例如 <= 2)
    # 2. 或者 wrong_count 較高的題目
    rows = conn.execute("""
        SELECT item_id, subject, topic, question, answer, box_level, wrong_count, priority, status
        FROM review_index_current
        WHERE (box_level <= 2 AND status = 'active') OR wrong_count >= 3
        ORDER BY wrong_count DESC, priority DESC
    """).fetchall()

    weaknesses = []
    for r in rows:
        item = dict(r)
        # 查詢這題最近常錯的原因 (loss_reason)
        log_rows = conn.execute("""
            SELECT loss_reason, created_at
            FROM review_index_log
            WHERE item_id = ? AND action = 'verify_wrong' AND loss_reason IS NOT NULL
            ORDER BY created_at DESC LIMIT 3
        """, (item["item_id"],)).fetchall()

        recent_loss_reasons = [dict(lr) for lr in log_rows]
        item["recent_loss_reasons"] = recent_loss_reasons
        weaknesses.append(item)

    conn.close()

    return {
        "status": "success",
        "exported_at": now_utc_iso(),
        "total_weaknesses": len(weaknesses),
        "data": weaknesses
    }

# ══════════════════════════════════════════════════════════
# API 4.2: POST /api/task/{item_id}/incorrect ── EDS / Agent 專用錯誤端點
# ══════════════════════════════════════════════════════════


@app.post("/api/task/{item_id}/incorrect")
async def incorrect_task(item_id: str, payload: IncorrectPayload = None):
    loss_reason = payload.loss_reason if payload else None
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM review_index_current WHERE item_id=?",
        (item_id,
         )).fetchone()
    if not row:
        conn.close()
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "ITEM_NOT_FOUND",
                "message": "Task not found"})

    t = dict(row)
    old_box = t.get("box_level", 1) or 1
    now_str = now_utc_iso()

    new_box = max(old_box - 1, 1)
    next_review = compute_next_review(new_box)
    new_wrong_count = (t.get("wrong_count") or 0) + 1

    execute_with_retry(conn, """
        UPDATE review_index_current
        SET box_level=?, status='active', wrong_count=?, last_wrong_at=?, last_reviewed_at=?, next_review_at=?
        WHERE item_id=?
    """, (new_box, new_wrong_count, now_str, now_str, next_review, item_id))

    execute_with_retry(conn, """
        INSERT INTO review_index_log (item_id, action, from_box, to_box, loss_reason, created_at)
        VALUES (?, 'verify_wrong', ?, ?, ?, ?)
    """, (item_id, old_box, new_box, loss_reason, now_str))
    conn.commit()
    conn.close()

    return {"status": "success", "action": "incorrect", "new_box": new_box}

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
    answer: str = Form(""),
    subject: str = Form("自然"),
    topic: str = Form(""),
    ocr_confidence: float = Form(1.0),
    image: UploadFile = File(None)
):
    conn = get_connection()
    maybe_cleanup(conn)

    gemini_api_key = os.environ.get("GEMINI_API_KEY")

    final_answer = answer.strip()
    final_topic = topic.strip()

    if (not final_answer or not final_topic or final_topic == "外部錯題") and gemini_api_key:
        try:
            client = genai.Client(api_key=gemini_api_key)
            prompt = f"""
請協助處理這道來自學生的錯題。
科目：{subject}
題目內容：{question}

請根據上述資訊，提供以下兩項：
1. `answer`: 詳細的標準答案、推導步驟與關聯推理過程。
2. `topic`: 這道題目對應到台灣 108 課綱的年級與章節（例如：國二上 2-1 平方根與近似值）。如果無法精確判斷，請給出最可能的知識點主題。
"""
            class IngestResult(BaseModel):
                answer: str = Field(description="標準答案與詳細推導步驟")
                topic: str = Field(description="對應的 108 課綱年級與章節")

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=IngestResult,
                )
            )
            result_json = json.loads(response.text)
            if not final_answer:
                final_answer = result_json.get("answer", "解析待人工確認")
            if not final_topic or final_topic == "外部錯題":
                final_topic = result_json.get("topic", "外部錯題")
        except Exception as e:
            print(f"Gemini API 呼叫失敗 (Ingest): {e}")
            if not final_answer:
                final_answer = "解析待人工確認"
            if not final_topic:
                final_topic = "外部錯題"
    else:
        if not final_answer:
             final_answer = "解析待人工確認"
        if not final_topic:
             final_topic = "外部錯題"

    st_str = 'pending_review' if ocr_confidence >= OCR_CONFIDENCE_THRESHOLD else 'fallback_manual'

    # 先建立 staging 記錄取得 staging_id
    cur = execute_with_retry(conn, """
        INSERT INTO ingestion_staging (question, answer, subject, topic, ocr_confidence, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (question, final_answer, subject, final_topic, ocr_confidence, st_str, now_utc_iso()))
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
                "message": f"檔案大小超過上限 {IMAGE_MAX_SIZE_BYTES // (1024 * 1024)}MB"
            })

        os.makedirs(MEDIA_STAGING_DIR, exist_ok=True)
        image_path = os.path.join(MEDIA_STAGING_DIR, f"temp_{staging_id}{ext}")
        with open(image_path, "wb") as f:
            f.write(content)

        execute_with_retry(
            conn,
            "UPDATE ingestion_staging SET image_path=? WHERE staging_id=?",
            (image_path,
             staging_id))

    conn.commit()
    conn.close()

    msg = "📥 已進入 Staging 緩衝區，等待人工 Approve 轉正。" if st_str == 'pending_review' else "⚠️ OCR 信心度低於 70%，已觸發 Fallback 降級，請手動校正。"
    return {
        "status": "success",
        "staging_id": staging_id,
        "ocr_confidence": ocr_confidence,
        "image_path": image_path,
        "message": msg}

# ══════════════════════════════════════════════════════════
# API 6: POST /api/ingest/approve ── 轉正：圖檔自動重命名
# ══════════════════════════════════════════════════════════


@app.post("/api/ingest/approve")
async def approve_staging_task(payload: ApprovePayload):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM ingestion_staging WHERE staging_id=?",
        (payload.staging_id,
         )).fetchone()
    if not row or row["status"] == 'approved':
        conn.close()
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "STAGING_NOT_FOUND",
                "message": "Staging item not found or already approved"})

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

    execute_with_retry(
        conn,
        "UPDATE ingestion_staging SET status='approved' WHERE staging_id=?",
        (payload.staging_id,
         ))
    conn.commit()
    conn.close()
    return {"status": "success", "item_id": new_uuid,
            "message": "✅ 已人工轉正寫入正式防禦庫 review_index_current！"}

# ══════════════════════════════════════════════════════════
# API 10: GET /api/student/timeline ── 長週期學習脈絡時間軸
# ══════════════════════════════════════════════════════════

@app.get("/api/student/timeline")
async def get_student_timeline():
    conn = get_connection()
    rows = conn.execute("""
        SELECT profile_id, subject, topic, weakness_summary, loss_reason, occurred_count, is_resolved, updated_at
        FROM student_cognitive_profile
        ORDER BY updated_at DESC LIMIT 20
    """).fetchall()
    conn.close()

    timeline = [dict(r) for r in rows]
    return {"status": "success", "timeline": timeline}

# ── 主入口 ──
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
