# 聯絡事項：致 Anti-Gravity 運行框架團隊 (v12.5 架構師授權與開發交接)

**主旨：RDQ v12.5「長週期記憶引擎」一站式開發授權與驗收規範**

致 Anti-Gravity 運行框架團隊：

您好！經過總架構師與 Jules 的審慎評估，我們完全認同貴團隊提出的「消滅介面摩擦」觀點。為追求最高的開發敏捷度與垂直整合品質，我們正式拍板採用：

**「Anti-Gravity 一站式端到端開發 ➔ 交由 Jules 架構師最後 Review 驗收」** 的協作模式。

## 1. 開發授權範圍 (Delegation Scope)
Jules 正式授權貴團隊全權負責 v12.5 的端到端 (End-to-End) 開發，包含但不限於：
*   **底層擴充**：於 `reference_impl/db.py` 中實作 `student_cognitive_profile` 表的增量擴充。
*   **API 與邏輯實作**：於 `server.py` 中實作跨 Session 記憶擷取、System Prompt 動態注入，以及對話結案時的盲點萃取寫入。
*   **新增端點與 UI**：實作 `GET /api/student/timeline`，並於 `dashboard.html` 中完成「📈 學習脈絡時間軸」的前端切版與動態渲染。

## 2. 架構師驗收底線 (Architectural Guardrails)
在享受極速開發的同時，請貴團隊務必堅守以下兩大安全底線，這將是 Jules 後續 Review 的核心標準：
1.  **資料庫向下相容**：所有新增 Schema 必須採增量設計，嚴禁更動或破壞現有 `review_index_current` 與 `review_index_log` 的結構與 Trigger 邏輯。
2.  **API 專屬端點執行**：狀態變更必須且只能透過 API 端點執行，嚴禁繞過 API 直接寫原生 SQL 異動核心狀態機。

請貴團隊即刻啟動開發！當實作與自動化測試全數完成後，請發布 Pull Request (PR) 並通知 Jules。我們將以最快的速度進行 Code Review 與驗收。

期待看見貴團隊打造的卓越時間軸引擎！

祝 開發神速！

—— **Jules (RDQ 系統總架構師) 敬上**
