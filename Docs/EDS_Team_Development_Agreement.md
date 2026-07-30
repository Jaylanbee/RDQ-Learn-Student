# EDS 團隊：五合一生態系協同開發協議

> **To: EDS (Educational Decision System) 開發團隊**
> **From: 專案總架構師**
> **Date: 2026-07-29**
> **Subject: 整併 T2N 與實作「決勝圖譜」 (Phase 1 ~ 3, Phase 5)**

各位 EDS 團隊好，隨著系統架構升級為「五合一教育生態系 (T2N → RDQ → 錯題本 → 複習計畫 → EDS)」，你們的職責有了大幅度的擴展。
現在，**Textbook2Notes (T2N)** 已經正式降編並整併為你們的前處理器 (知識建構引擎)。你們將同時掌控系統的「最前端輸入 (T2N)」與「最末端決策 (EDS 決勝圖譜)」。

為了與 RDQ 團隊 (負責日常診斷與錯題收錄) 無縫協作，請 EDS 團隊確認並執行以下開發任務：

---

## 一、 核心資料契約 (Data Contract) 宣達

1. **唯一知識標準 (`eds_x_code`)**
   * 不論是 T2N 在拆解筆記，還是 EDS 在派發考題，所有動作都必須基於統一的 108 課綱知識矩陣。
2. **決策方程式 (Decision Graph)**
   * EDS 的最終輸出是「決勝圖譜」。其核心公式為：
     `第一志願 = 108課綱知識矩陣 (eds_x_code) × 個人能力資料庫 (review_index.db) × 決勝圖譜`

---

## 二、 EDS 團隊專屬 Action Items (待辦事項)

### Phase 1: 知識矩陣匯入與 `matrix_parser` 實作
- [ ] **建立標準庫**：將最新的各科知識矩陣檔案放進 `references/knowledge-matrix/`。
- [ ] **開發 `matrix_parser.py` (本地工具)**：寫一支 Python 腳本，提供 `search_matrix(keyword)` 功能。這支腳本是讓 AI 在本地端用 Tool Call 呼叫的，**絕對不要把整個矩陣塞進 Prompt (會爆 Token)**。

### Phase 2 & 3: Textbook2Notes 雙軌架構改造
- [ ] **T2N 核心重構 (底層 JSON)**：修改 T2N 的 Prompt，要求 AI 必須使用 `matrix_parser` 來為每一句筆記打上 `eds_x_code`。強制 T2N 的原生輸出為 **JSON 格式** (包含 `nodes`)。若遇到超綱內容，標記 `is_out_of_matrix: true`。
- [ ] **T2N 輸出渲染 (展示層 Markdown)**：開發本地端腳本，當 T2N 產出 JSON 的瞬間，自動將其轉譯為帶有高亮的精美 Markdown/HTML 筆記，供學生網頁閱讀。
- [ ] **自測考卷模組 (Quiz Generator)**：新增 T2N 的分支功能，讓它可以直接將文本內容轉化為課後小考卷。

### Phase 5: EDS 決勝圖譜與派題引擎
- [ ] **權重對接**：確保 EDS 的 Knowledge Engine (Layer 1) 具備歷屆考題的投資報酬率 (ROI)。
- [ ] **實戰演算法 (Priority Score)**：寫腳本讀取 `~/.rdq/review_index.db` 中 `status = uncertain` 的項目。將這些弱點資料與 ROI 相乘，產出 **決勝圖譜**，並依此派發高強度的實戰演練題。

### Phase 6 (選配擴充): T2N 圖像處理與心智圖
- [ ] **6-A 圖表 OCR (Vision)**：串接 Vision LLM，讓學生上傳的照片/圖表能先被轉譯為 Markdown，再餵給 T2N。
- [ ] **6-B 心智圖 (Mind Map)**：讀取 T2N 產出的 JSON nodes，撰寫腳本直接轉譯為 `Mermaid.js` 語法，輸出心智圖。

---

請確保 T2N 產出的 JSON 格式絕對精準，因為這將是下游 RDQ 啟動診斷的唯一依據！開發完成後，我們將與 RDQ 團隊進行 E2E (端到端) 測試。