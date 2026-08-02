import os
import sqlite3
import yaml
import shutil
import uuid
import datetime
import asyncio
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List
from tenacity import retry, wait_exponential, stop_after_attempt

def load_config():
    with open("config.yaml", "r") as f:
        return yaml.safe_load(f)

config = load_config()
DB_PATH = os.path.expanduser(config.get("db_path", "~/.education_ecosystem/review_index.db"))
MEDIA_DIR = os.path.expanduser(config.get("MEDIA_SAVE_DIR", "~/.education_ecosystem/media"))
LAPLACE_K = config.get("LAPLACE_K", 1)
LAPLACE_PRIOR = config.get("LAPLACE_PRIOR", 0.5)
LLM_CONFIDENCE_THRESHOLD = config.get("LLM_CONFIDENCE_THRESHOLD", 0.6)
DAILY_LIMIT = config.get("DAILY_LIMIT", 30)

os.makedirs(MEDIA_DIR, exist_ok=True)
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

app = FastAPI(title="RDQ Minimalist Dashboard")
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

class ApproveRequest(BaseModel):
    priority: str

class SRSActionRequest(BaseModel):
    action: str

def gc_rejected_media(media_path: str):
    if media_path:
        full_path = os.path.join(MEDIA_DIR, os.path.basename(media_path))
        if os.path.exists(full_path):
            os.remove(full_path)

@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3))
async def mock_llm_parse(text: str = None, has_image: bool = False):
    await asyncio.sleep(1)
    confidence = 0.9 if (text and len(text) > 10) or has_image else 0.4
    return {
        "subject": "science" if "cell" in str(text).lower() else "math",
        "eds_x_code": "Bc-IV-3" if "cell" in str(text).lower() else "N-7-1",
        "priority": "yellow",
        "confidence": confidence
    }

@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    index_path = os.path.join("static", "dashboard.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Dashboard UI not found</h1>"

@app.post("/api/ingest")
async def ingest_external_error(
    extracted_text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None)
):
    media_path = None
    if file:
        if file.content_type not in ["image/jpeg", "image/png", "image/webp"]:
            raise HTTPException(status_code=400, detail="Only JPG, PNG and WEBP images are allowed")

        file.file.seek(0, 2)
        size = file.file.tell()
        file.file.seek(0)

        if size > 5 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File too large. Maximum size is 5MB")

        base_filename = os.path.basename(file.filename)
        filename = f"{uuid.uuid4()}_{base_filename}"
        save_path = os.path.join(MEDIA_DIR, filename)
        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        media_path = f"/media/{filename}"

    if not extracted_text and not file:
        raise HTTPException(status_code=400, detail="Must provide text or image")

    try:
        llm_result = await mock_llm_parse(text=extracted_text, has_image=bool(file))
    except Exception as e:
        llm_result = {"subject": "unknown", "eds_x_code": "unknown", "priority": "yellow", "confidence": 0.0}

    status = "approved" if llm_result["confidence"] >= LLM_CONFIDENCE_THRESHOLD else "pending"

    conn = get_db()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO ingestion_staging
        (image_path, extracted_text, subject, eds_x_code, priority, llm_confidence, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (media_path, extracted_text, llm_result["subject"], llm_result["eds_x_code"],
          llm_result["priority"], llm_result["confidence"], status))
    staging_id = cur.lastrowid
    conn.commit()

    if status == "approved":
        new_item_id = int(uuid.uuid4().int >> 64) % 2147483647
        cur.execute('''
            INSERT INTO review_index_log
            (item_id, subject, eds_x_code, source, media_path, llm_confidence, priority, box, status, next_review, action)
            VALUES (?, ?, ?, 'external', ?, ?, ?, 1, 'active', date('now', '+1 day'), 'initial')
        ''', (new_item_id, llm_result["subject"], llm_result["eds_x_code"], media_path,
              llm_result["confidence"], llm_result["priority"]))
        cur.execute('''
            UPDATE ingestion_staging SET promoted_item_id = ?, reviewed_at = CURRENT_TIMESTAMP WHERE id = ?
        ''', (new_item_id, staging_id))
        conn.commit()
        conn.close()
        return {"message": "Auto-approved and scheduled", "item_id": new_item_id}

    conn.close()
    return {"message": "Saved to pending zone for review", "staging_id": staging_id}

@app.post("/api/staging/{staging_id}/approve")
async def approve_staging(staging_id: int, req: ApproveRequest):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM ingestion_staging WHERE id = ? AND status = 'pending'", (staging_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Staging item not found or not pending")

    new_item_id = int(uuid.uuid4().int >> 64) % 2147483647
    priority = req.priority if req.priority else (row["priority"] or "yellow")

    cur.execute('''
        INSERT INTO review_index_log
        (item_id, subject, eds_x_code, source, media_path, llm_confidence, priority, box, status, next_review, action)
        VALUES (?, ?, ?, 'external', ?, ?, ?, 1, 'active', date('now', '+1 day'), 'initial')
    ''', (new_item_id, row["subject"], row["eds_x_code"], row["image_path"],
          row["llm_confidence"], priority))

    cur.execute('''
        UPDATE ingestion_staging SET status = 'approved', promoted_item_id = ?, reviewed_at = CURRENT_TIMESTAMP, priority = ? WHERE id = ?
    ''', (new_item_id, priority, staging_id))
    conn.commit()
    conn.close()
    return {"message": "Approved", "item_id": new_item_id}

@app.post("/api/staging/{staging_id}/reject")
async def reject_staging(staging_id: int, background_tasks: BackgroundTasks):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT image_path FROM ingestion_staging WHERE id = ? AND status = 'pending'", (staging_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Staging item not found or not pending")

    cur.execute("UPDATE ingestion_staging SET status = 'rejected', reviewed_at = CURRENT_TIMESTAMP WHERE id = ?", (staging_id,))
    conn.commit()
    conn.close()
    if row["image_path"]:
        background_tasks.add_task(gc_rejected_media, row["image_path"])
    return {"message": "Rejected"}

@app.get("/api/dashboard/stats")
async def get_dashboard_stats():
    conn = get_db()
    cur = conn.cursor()
    subjects = ["math", "science", "chinese", "english", "social"]
    stats = {}
    for subj in subjects:
        cur.execute("SELECT COUNT(*) as total FROM review_index_current WHERE subject = ?", (subj,))
        total = cur.fetchone()["total"]
        cur.execute("SELECT COUNT(*) as confirmed FROM review_index_current WHERE subject = ? AND status = 'confirmed'", (subj,))
        confirmed = cur.fetchone()["confirmed"]
        smoothed_rate = (confirmed + LAPLACE_K * LAPLACE_PRIOR) / (total + LAPLACE_K)
        stats[subj] = {"total": total, "confirmed": confirmed, "kill_rate": smoothed_rate}

    cur.execute("SELECT COUNT(*) as pending_count FROM ingestion_staging WHERE status = 'pending'")
    pending_count = cur.fetchone()["pending_count"]
    conn.close()
    return {"radar": stats, "pending_count": pending_count}

@app.get("/api/dashboard/tasks")
async def get_daily_tasks():
    conn = get_db()
    cur = conn.cursor()
    cur.execute('''
        SELECT c.*,
               (CASE priority WHEN 'red' THEN 3 WHEN 'yellow' THEN 2 WHEN 'green' THEN 1 ELSE 0 END) as priority_score,
               (SELECT media_path FROM review_index_log l WHERE l.item_id = c.item_id AND l.media_path IS NOT NULL ORDER BY timestamp ASC LIMIT 1) as media_path,
               (SELECT extracted_text FROM ingestion_staging s WHERE s.promoted_item_id = c.item_id LIMIT 1) as extracted_text
        FROM review_index_current c
        WHERE c.next_review <= date('now') AND c.status != 'confirmed'
        ORDER BY c.box ASC, priority_score DESC, c.next_review ASC LIMIT ?
    ''', (DAILY_LIMIT,))
    tasks = [dict(row) for row in cur.fetchall()]
    conn.close()
    return {"tasks": tasks}

@app.get("/api/dashboard/pending")
async def get_pending_tasks():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM ingestion_staging WHERE status = 'pending'")
    tasks = [dict(row) for row in cur.fetchall()]
    conn.close()
    return {"pending": tasks}

@app.post("/api/task/{item_id}/action")
async def update_task_status(item_id: int, req: SRSActionRequest, background_tasks: BackgroundTasks):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM review_index_current WHERE item_id = ?", (item_id,))
    current = cur.fetchone()
    if not current:
        conn.close()
        raise HTTPException(status_code=404, detail="Task not found in current view")

    current_box = current["box"]
    subject = current["subject"]
    eds_x_code = current["eds_x_code"]
    priority = current["priority"]

    if req.action == "reject":
        cur.execute('''
            INSERT INTO review_index_log (item_id, subject, eds_x_code, source, priority, box, status, action)
            VALUES (?, ?, ?, 'external', ?, ?, 'rejected', 'manual_reject')
        ''', (item_id, subject, eds_x_code, priority, current_box))
        cur.execute("SELECT media_path FROM review_index_log WHERE item_id = ? AND media_path IS NOT NULL ORDER BY timestamp ASC LIMIT 1", (item_id,))
        media_row = cur.fetchone()
        if media_row and media_row["media_path"]:
            background_tasks.add_task(gc_rejected_media, media_row["media_path"])

    elif req.action == "correct":
        next_intervals = {1: 3, 2: 7, 3: 14, 4: 30}
        if current_box >= 5:
            cur.execute('''
                INSERT INTO review_index_log (item_id, subject, eds_x_code, source, priority, box, status, next_review, action)
                VALUES (?, ?, ?, 'daily', ?, ?, 'confirmed', NULL, 'correct')
            ''', (item_id, subject, eds_x_code, priority, current_box))
        else:
            new_box = current_box + 1
            interval = next_intervals[current_box]
            cur.execute(f'''
                INSERT INTO review_index_log (item_id, subject, eds_x_code, source, priority, box, status, next_review, action)
                VALUES (?, ?, ?, 'daily', ?, ?, 'active', date('now', '+{interval} day'), 'correct')
            ''', (item_id, subject, eds_x_code, priority, new_box))

    elif req.action == "incorrect":
        if current_box in (5, 4): new_box, interval = 2, 3
        elif current_box == 3: new_box, interval = 2, 3
        else: new_box, interval = 1, 1
        cur.execute(f'''
            INSERT INTO review_index_log (item_id, subject, eds_x_code, source, priority, box, status, next_review, action)
            VALUES (?, ?, ?, 'daily', ?, ?, 'active', date('now', '+{interval} day'), 'incorrect')
        ''', (item_id, subject, eds_x_code, priority, new_box))
    else:
        conn.close()
        raise HTTPException(status_code=400, detail="Invalid action")

    conn.commit()
    conn.close()
    return {"message": "Success"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
