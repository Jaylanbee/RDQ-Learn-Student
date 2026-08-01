# 聯絡事項：致 EDS 團隊 (Educational Decision System)

**主旨：RDQ 極簡學習儀表板上線通知與系統協作說明**

致 EDS 決策團隊：

為了提升學生的每日複習動機並消除「流暢性幻覺」，RDQ 團隊即將在系統第一線部署「極簡學習儀表板 (Minimalist Learning Dashboard)」。
此儀表板將成為學生每日錯題管理的單一入口，並涵蓋日常 RDQ 覆盤與外部手拍錯題。

我們了解 EDS 團隊負責考前的高強度實戰特訓與全局弱點分析，因此特別在此說明我們的架構更動，確保兩端系統 (RDQ 檢傷端 ↔ EDS 決策端) 的無縫接軌：

## 1. 資料庫讀寫分離 (CQRS-lite) 實作
我們已對共用的 `review_index.db` 進行了重構：
*   新增 `review_index_current` 表：此表僅包含活躍與已歸檔 (Confirmed) 卡片的「最新狀態」。
*   **對 EDS 的影響**：強烈建議 EDS 團隊在撈取學生即時弱點以計算 ROI 或生成考前特訓 (Re-test) 清單時，**直接讀取 `review_index_current` 表**。這將大幅提升您的 SQL 查詢效能，免去每次都在 Log 表中使用 `MAX(timestamp)` 聚合的負擔。

## 2. 嚴格的 Append-Only Log 與 Staging 隔離
*   `review_index_log` 現在受到嚴格保護，僅支援 `INSERT`。
*   所有低信心度的 LLM 解析錯題，會先暫存於全新的 `ingestion_staging` 表，轉正後才會進入 Log 表。
*   **對 EDS 的影響**：您可以確保 Log 表中的資料絕對乾淨，不會被未經驗證的垃圾資料污染，有利於您後續建立「學生學習軌跡深度分析」模型。

## 3. 高壓軟性降級演算法
*   我們修改了錯題降級機制：Box 5/4 答錯退回 Box 2；Box 3 退回 Box 2；Box 2/1 退回 Box 1。
*   **對 EDS 的影響**：這意味著學生的中長期記憶即使出錯，也不會被一鍵清零，而是維持在 3 天後複習的短週期。請確保 EDS 的派題演算法在讀取 `box` 數值時，理解這套新的階梯式轉移邏輯。

## 4. `confirmed` 狀態的語意定調
*   當學生通過 Box 5，狀態將轉為 `confirmed` (永久歸檔)。在 Current 表中，其 `next_review` 會被設為 `NULL`。
*   **對 EDS 的影響**：這代表該知識點 (`eds_x_code` 對應之具體題目) 已被徹底掌握。EDS 若要進行高強度盲點打擊，請直接過濾掉這些 `next_review IS NULL` 的紀錄。

期待我們雙系統的協同作戰，能為學生打造最堅固的記憶防護網！

—— RDQ 開發團隊 敬上
