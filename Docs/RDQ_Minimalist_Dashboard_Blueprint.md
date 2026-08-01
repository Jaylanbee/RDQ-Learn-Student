# 🚀 RDQ 極簡學習儀表板：完整開發計畫書 (Final Blueprint)

## 🎯 一、系統總體目標
在現有 RDQ 專案內建構基於 **FastAPI + HTML/RWD** 的 Web SPA 儀表板。收斂日常與外部錯題，以嚴格的資料隔離、Append-Only 寫入與高壓 SRS 演算法，提供無延遲、零阻塞的學習檢傷體驗。

---

## 🧱 二、四大核心架構規範 (防禦底線)

### 1. 效能底線：FastAPI 原生非同步與 CQRS-lite 讀寫分離
*   **後端框架**：全面採用 **FastAPI**，以 `async/await` 處理 LLM 圖片解析，維持前端圖表與閃卡的零阻塞體驗。
*   **讀寫分離設計 (DB 架構)**：
    *   **寫入 (Write)**：歷史表 `review_index_log` 嚴格遵守 Append-Only (`INSERT`)。
    *   **讀取 (Read)**：新增實體表 `review_index_current`。利用 SQLite `TRIGGER`，當 Log 寫入時自動 `UPSERT` 該題的最新狀態至 Current 表。前端所有高頻查詢 (雷達圖、今日任務) 僅掃描 Current 表。

### 2. 算力底線：高壓階梯式降級與排序策略
*   **Box 狀態轉移矩陣 (SSOT)**：

| 狀態 / 動作 | Box 1 | Box 2 | Box 3 | Box 4 | Box 5 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **✅ 邏輯正確** | → Box 2 (+3天) | → Box 3 (+7天) | → Box 4 (+14天) | → Box 5 (+30天) | → **Confirmed** (歸檔) |
| **🔄 降級懲罰** | → Box 1 (+1天) | → Box 1 (+1天) | → **Box 2** (+3天) | → **Box 2** (+3天) | → **Box 2** (+3天) |

*   **每日排序與截斷策略**：
    *   設定每日複習上限（預設 30 題）。
    *   排序權重 (Order By)：① `box` 升冪 ➔ ② `priority` (紅>黃>綠) ➔ ③ `next_review` 升冪。命中上限即截斷。

### 3. 資料底線：Shared-Schema, LLM 容錯與參數化
*   **Schema 升級與回填腳本**：撰寫 `migration_script.sql`。擴充 `source`, `media_path`, `llm_confidence` 等欄位，新增 `rejected` 狀態，並完成舊 Log 數據向 Current 表的回填。
*   **參數抽離 (`config.yaml`)**：抽出 `LAPLACE_K`, `LAPLACE_PRIOR`, `LLM_CONFIDENCE_THRESHOLD`, `DAILY_LIMIT`。
*   **LLM 容錯防線 (Pending/Reject GC)**：
    *   使用 `Tenacity` 實作指數退避重試。
    *   **Pending 區 (`ingestion_staging`)**：`llm_confidence < 0.6` 或 API 異常時，存入暫存表，待人工確認後才寫入 Log (轉正)。
    *   **Reject GC**：人工判定無效後，標記 `'rejected'` 並從 Current 表刪除，背景清理本地圖檔。

### 4. 認知底線：實體阻力 UI (Physical Friction)
*   卡片翻轉前，強制要求學生在 `<textarea>` 或 `<canvas>` 產生實體輸出行為，解鎖「看答案 👉」按鈕，杜絕流暢性幻覺。

---

## 🛠️ 三、資料庫 DDL 實作規格 (Pre-Phase 1)

```sql
-- 1. 新增暫存表
CREATE TABLE ingestion_staging (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    image_path TEXT,
    extracted_text TEXT,
    subject TEXT,
    eds_x_code TEXT,
    priority TEXT CHECK(priority IN ('red','yellow','green')),
    llm_confidence REAL,
    status TEXT CHECK(status IN ('pending', 'approved', 'rejected')),
    promoted_item_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TIMESTAMP
);

-- 2. 歷史表 (Append-Only)
CREATE TABLE review_index_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    subject TEXT NOT NULL,
    eds_x_code TEXT,
    source TEXT CHECK(source IN ('daily','external')) NOT NULL,
    media_path TEXT,
    llm_confidence REAL,
    priority TEXT CHECK(priority IN ('red','yellow','green')) NOT NULL DEFAULT 'yellow',
    box INTEGER NOT NULL CHECK(box BETWEEN 1 AND 5),
    status TEXT CHECK(status IN ('active','confirmed','rejected')) NOT NULL,
    next_review DATE,
    action TEXT CHECK(action IN ('initial','correct','incorrect','manual_reject')) NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_log_item ON review_index_log(item_id, timestamp);

-- 3. 狀態表 (Current View)
CREATE TABLE review_index_current (
    item_id INTEGER PRIMARY KEY,
    subject TEXT NOT NULL,
    eds_x_code TEXT,
    priority TEXT CHECK(priority IN ('red','yellow','green')),
    box INTEGER NOT NULL,
    status TEXT CHECK(status IN ('active','confirmed')),
    next_review DATE,
    updated_at TIMESTAMP
);
CREATE INDEX idx_current_schedule ON review_index_current(next_review, box, priority);
CREATE INDEX idx_current_subject ON review_index_current(subject, status);

-- 4. 維護 Current 表的 Trigger
CREATE TRIGGER trg_update_current_state
AFTER INSERT ON review_index_log
BEGIN
    DELETE FROM review_index_current WHERE item_id = NEW.item_id AND NEW.status = 'rejected';

    INSERT INTO review_index_current (item_id, subject, eds_x_code, priority, box, status, next_review, updated_at)
    SELECT NEW.item_id, NEW.subject, NEW.eds_x_code, NEW.priority, NEW.box, NEW.status, NEW.next_review, NEW.timestamp
    WHERE NEW.status != 'rejected'
    ON CONFLICT(item_id) DO UPDATE SET
        priority = excluded.priority,
        box = excluded.box,
        status = excluded.status,
        next_review = excluded.next_review,
        updated_at = excluded.updated_at;
END;
```

---

## 👣 四、階段執行順序 (Milestones)

*   **Phase 1：基礎建設與單元測試先行**
    *   執行 DDL Schema Migration (包含資料回填腳本)。
    *   建置 `config.yaml`。
    *   **[Test]** 撰寫轉移矩陣與降級演算法的 Unit Test (測試先行)。
*   **Phase 2：LLM 可靠性與圖文匯入 (Ingestion)**
    *   實作 FastAPI 後端骨架與 `ingest_external_error.py`。
    *   實作 `/staging/{id}/approve` 轉正端點 (應用層生成 `item_id`)。
*   **Phase 3：核心演算法與 API 實作 (Backend)**
    *   實作拉普拉斯平滑 API (`total` 限定為 Current 表內數據) 與排序截斷 API。
*   **Phase 4：前端 UI 實作與端到端測試 (Frontend)**
    *   刻出 HTML/CSS/JS (雷達圖、實體阻力、兩段式翻轉卡片)。
    *   **[Test]** E2E 端到端測試。
