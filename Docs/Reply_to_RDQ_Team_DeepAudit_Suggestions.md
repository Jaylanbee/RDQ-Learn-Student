# 官方信件：致 RDQ 開發團隊與總架構師

**主旨：RDQ 學習系統全方位深度診斷報告 — 5 大體驗與架構改善建議清單**

**發信人**：Antigravity Agent 運行框架團隊 (代表家長、學生與架構診斷組)
**收信人**：RDQ 系統總架構師 & 開發團隊
**日期**：2026 年 8 月 2 日

---

致 RDQ 系統總架構師與開發團隊：

您好！為了確保全新的 RDQ Web Dashboard (`dashboard.html`) 與 FastAPI 後端在學生日常使用與大考衝刺時達到最完美的穩定度與教學效果，Antigravity 團隊針對系統進行了全方位的深度模擬與情境探索。

特此整理 **5 大關鍵潛在問題與對應改善建議** 供貴團隊排程優化：

---

### 🚨 1. 【高優先級 P0】SQLite 併發寫入鎖定防護 (`database is locked`)
- **問題**：當對話框發起 `POST /api/ingest` 的同時，若 Web 端亦點擊晉級/降級，SQLite 可能觸發 `database is locked` 錯誤。
- **改善建議**：
  - 後端連線預設開啟 WAL 模式 (`PRAGMA journal_mode=WAL;`)。
  - FastAPI 處理連線時加入 Exponential Backoff 交易重試與鎖定逾時時間。

---

### 🚨 2. 【高優先級 P1】Web 實體阻力解題區草稿自動暫存 (`localStorage`)
- **問題**：學生在 Web 端的實體阻力區（Textarea / Canvas）認真打字寫下思考時，若網頁意外重新整理或跳出，輸入內容會完全丟失。
- **改善建議**：
  - 在 `dashboard.html` 加入 `localStorage` auto-save，離線或跳出時自動保留草稿，重新開啟網頁時自動復原。

---

### 🚨 3. 【中優先級 P2】卡關降級時收集「失分原因 (`loss_reason`)」
- **問題**：目前 Web 端點擊「卡關降級 ↩」無追問，導致資料庫 `review_index_log` 中的 `loss_reason` 欄位數據缺失。
- **改善建議**：
  - 點擊卡關時，跳出極簡標籤（`計算錯誤` | `觀念不熟` | `看錯題` | `推理不足`），學生點選後再提交 API。

---

### 🚨 4. 【中優先級 P2】EDS 決勝圖譜一鍵匯出與對接端點 (`GET /api/eds/export-weaknesses`)
- **問題**：當學生在 Box 1 滯留題目過多或大考前夕，缺少一鍵匯出弱點資料至下游 EDS 系統的實體端點與按鈕。
- **改善建議**：
  - 開放 `GET /api/eds/export-weaknesses` 端點。
  - 在 Web 儀表板頂部新增「🚀 一鍵導出 EDS 考前決勝圖譜」按鈕。

---

### 🚨 5. 【優化級 P3】數理化公式 LaTeX / KaTeX 動態美化渲染
- **問題**：數理科題目與解析中的數學公式（如 `ax^2 + bx + c = 0`）與化學式直接以純文字呈現，排版較硬。
- **改善建議**：
  - 在 `dashboard.html` 引入輕量級 KaTeX 庫，自動渲染 LaTeX 格式之公式。

---

### 📊 建議改善優先級排程表

| 改善項目 | 診斷維度 | 建議優先級 |
|---|---|---|
| **SQLite WAL 模式與鎖定重試** | 系統穩定度 | **P0 (緊急修復)** |
| **實體阻力草稿 localStorage Auto-Save** | 用戶體驗 (UX) | **P1 (優先優化)** |
| **卡關點選 loss_reason 失分原因** | 教學與數據分析 | **P2** |
| **GET /api/eds/export-weaknesses 匯出端點** | 生態系銜接 | **P2** |
| **KaTeX 數理化公式動態渲染** | 視覺體驗 (UI) | **P3** |

期待貴團隊在下一階段的版本疊代中納入考量！如有任何對接技術問題，Antigravity 團隊隨時提供支援！

—— **Antigravity Agent 運行框架團隊 敬上**
