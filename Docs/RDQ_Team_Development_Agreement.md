# RDQ-Learn 團隊：五合一生態系協同開發協議

> **To: RDQ-Learn-Student 開發團隊**
> **From: 專案總架構師**
> **Date: 2026-07-29**
> **Subject: RDQ 升級為五合一閉環中繼站 (Phase 3 ~ Phase 5)**

各位 RDQ 團隊好，隨著系統架構升級為「五合一教育生態系 (T2N → RDQ → 錯題本 → 複習計畫 → EDS)」，RDQ 的定位有了重大的提升。
你們現在不僅是「覆盤提問機」，更是承接上游筆記 (T2N) 並精準餵資料給下游 (EDS) 的**核心檢傷分類樞紐**。

為了與 EDS 團隊 (負責 T2N, EDS 派題) 無縫協作，請 RDQ 團隊確認並執行以下開發任務：

---

## 一、 核心資料契約 (Data Contract) 變更

1. **唯一資料庫 (`review_index.db`)**
   * 你們在 Phase 7 結束時的資料寫入，**嚴禁讓 AI 直接寫 SQL**。
   * **(已完成)** 必須強制 AI 呼叫本地端工具 `rdq_store.py` 並傳遞 JSON。該腳本會自動處理 Leitner 的 `next_box` 與資料庫寫入。
2. **唯一知識標準 (`eds_x_code`)**
   * 你們寫入的每一筆弱點 (`uncertain`, `clarified`)，都必須帶有精準的 108 課綱代碼 (`eds_x_code`)。這個代碼將決定下游 EDS 決勝圖譜的準確度。

---

## 二、 RDQ 團隊專屬 Action Items (待辦事項)

### Phase 0.5: 串接 T2N 輸出 (改用 JSON 作為提問範圍)
- [ ] **啟動邏輯升級**：修改 `SKILL.md`，當 RDQ 啟動時，優先尋找本地端由 T2N 產生的 JSON 筆記檔（例如 `notes/{subject}/{topic}.json`）。
- [ ] **自動提取**：AI 直接讀取 JSON 中的 `nodes` 作為「絕對提問範圍」。不再需要學生手動打字解釋「我今天讀了第一單元」。
- [ ] **防超綱**：如果讀到的 Node 帶有 `is_out_of_matrix: true`，RDQ 必須主動跳過該知識點，不進行蘇格拉底式提問。

### Phase 4: 錯題本與複習計畫的聯動 (Study Plan)
- [ ] **開發 `generate_error_book.py` (API 介接層)**：寫一支腳本，能從 `review_index.db` 中撈取過去一週 `status = uncertain` 或 `clarified` 的項目，並打包成 JSON 格式。
- [ ] **開發「今日任務清單 (Daily Task)」展示腳本**：讀取 `review_index.db` 中 `next_review <= 今天` 的項目，並將其清單拋給前端或是 T2N/EDS 進行下一步處理。

### Phase 6 (選配擴充): ELI5 模式支援
- [ ] **Prompt 參數化**：當系統傳遞 `--mode=eli5` 參數給 RDQ 時，AI 在進行 L1 (蘇式開局) 提問與 L2 (降級選項) 解釋時，必須額外使用生活化、國中生易懂的比喻 (`analogy`) 來進行引導。

---

請確保上述開發任務都在本地端腳本中完成，以最大化節省 Token 消耗。開發完成後，我們將與 EDS 團隊進行 E2E (端到端) 測試！