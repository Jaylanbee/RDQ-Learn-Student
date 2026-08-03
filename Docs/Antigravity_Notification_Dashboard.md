# 聯絡事項：致 Antigravity 運行環境設定團隊

**主旨：RDQ 極簡學習儀表板上線 - 工具鏈與 API 變更通知**

致 Antigravity Agent 維運團隊：

RDQ 技能即將迎來重大升級。我們在系統內建構了原生的 FastAPI 後端與極簡前端 (HTML/RWD)，這將改變 Antigravity Agent 與 RDQ 系統的互動模式。
請檢閱以下變更，並相應調整 Antigravity 的系統設定與 Prompt：

## 1. 職責轉移：從「對話渲染」轉向「Web 渲染」
*   **過去**：Antigravity Agent 負責讀取 `rdq_store.py` 的產出，並直接在聊天室內以 Markdown 渲染出「學習覆盤卡」。
*   **現在**：我們開發了獨立的 HTML 儀表板 (`dashboard.html`)。
*   **對 Antigravity 的要求**：
    *   在日常複習模式啟動時，Antigravity 不需再印出冗長的卡片清單。
    *   請改為**提供儀表板的 Local URL (例如 `http://localhost:8000`)** 給學生，引導他們點擊進入 Web 介面進行「今日防禦任務」。
    *   在 Web 介面中，學生必須完成「實體阻力 (Physical Friction)」(在 Canvas 畫圖或 Textarea 打字) 才能翻轉閃卡。這是對話介面無法做到的，請務必引導學生轉移至 Web 端操作。

## 2. 外部錯題匯入 (Ingestion API) 的串接
*   **過去**：外部考卷或錯題沒有標準化的匯入管道。
*   **現在**：系統提供了 `ingest_external_error.py` 與對應的 FastAPI 路由 (`POST /ingest`)。
*   **對 Antigravity 的要求**：
    *   當學生在對話中上傳一張考卷截圖，或貼上一段題目要求「把這個加入錯題本」時。
    *   Antigravity Agent 應具備呼叫此 FastAPI 端點的能力，將圖片路徑或文字 Payload 傳送至後端進行 LLM 萃取與 Staging 暫存。

## 3. Schema 變更與 `rdq_store.py` 的重構
*   **警告**：底層資料庫 `review_index.db` 已進行大規模 CQRS-lite 重構（拆分為 Log 表與 Current 表），並加入了 Trigger 邏輯。
*   **對 Antigravity 的要求**：
    *   請絕對避免讓 Agent 直接寫原生 SQL 來異動資料庫。
    *   所有狀態變更 (晉級、降級、報廢) 必須嚴格透過我們新提供的 FastAPI 端點 (例如 `POST /task/{item_id}/correct` 或 `/incorrect`) 來執行，以確保高壓降級演算法與 Trigger 能正確運作。

感謝您的配合！這套新架構將大幅降低學生的認知負荷，並提升系統的防呆能力。

—— RDQ 開發團隊 敬上
