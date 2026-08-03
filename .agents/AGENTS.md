# RDQ 專案行為規範 (.agents/AGENTS.md)

## 🎓 RDQ 學習系統互動與 Web 儀表板導流規範 (RDQ Dashboard & API Integration)

當使用者（學生）說「幫我複習」、「用 RDQ 複習」、「課後複習」、「我要複習」或觸發 RDQ 學習系統時，請嚴格遵守以下規則：

### 1. Apple 風格 Web 渲染優先 (Web-First) 與實體阻力引導
- **過去方式**：直接在對話視窗中輸出冗長的 Markdown 學習覆盤卡清單與腳本操作。
- **新版規範**：**不得在對話中印出冗長卡片**。請以最簡短、最優雅的蘋果風格語氣給予 Web 儀表板連結，引導學生進入網頁端進行「今日防禦任務」與實體阻力（Canvas 畫圖 / Textarea 打字）閃卡挑戰。
- **標準優雅回應範例**：
  > 「請點擊這裡 [http://localhost:8000](http://localhost:8000) 進入您的 RDQ 極簡儀表板進行實體操作喔！」

### 2. 外部錯題匯入 API (`POST /api/ingest`)
- 當學生在對話中傳送考卷截圖或貼上題目文字，並要求「把這個加入錯題本」時：
- Agent **必須停止舊版 `rdq_store.py` 或手動 SQL 操作**，改為呼叫專屬 FastAPI 端點 `POST http://localhost:8000/api/ingest`，將圖片路徑或題目 Payload 傳送至後端進行 LLM 萃取與 Staging 暫存。

### 3. 狀態異動禁寫原生 SQL 與停用舊腳本 (CQRS-lite API 防呆)
- 底層 `review_index.db` 已完成 CQRS-lite 重構（`review_index_log` 歷史表與 `review_index_current` 狀態表分離，含神經元高壓軟性降級演算法與 Trigger）。
- **嚴禁 Agent 直接撰寫原生 SQL 操作數據庫，並全面停止使用舊版 `rdq_store.py`**。
- 所有狀態變更（晉級、降級、報廢）必須嚴格透由 FastAPI 專屬端點執行：
  - 答對晉級：`POST http://localhost:8000/task/{item_id}/correct`
  - 答錯降級：`POST http://localhost:8000/task/{item_id}/incorrect`
