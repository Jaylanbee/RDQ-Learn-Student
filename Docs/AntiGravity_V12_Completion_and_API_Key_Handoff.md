# 聯絡事項：致 Anti-Gravity 運行框架團隊 (v12 升級完工與 API Key 管理交接)

**主旨：RDQ v12 架構升級完工報告與 API Key 維運交接指令**

致 Anti-Gravity Agent 運行框架團隊：

您好！向貴團隊報告，RDQ 生態系的 v12 核心架構升級已經由 Jules 團隊順利開發、測試並提交完畢。

## 1. 核心實作進度報告 (已完工)
*   **真實 Gemini 串接與結構化輸出**：`server.py` 已全面載入 `google-genai` SDK。在 `POST /api/chat` 與 `POST /api/task/{item_id}/verify` 的 `mode="full"` 分支中，系統已能向 `gemini-2.5-flash` 發送請求，並透過強制 JSON Schema (`response_mime_type="application/json"`) 精準提取 `is_correct`、`loss_reason` 與蘇格拉底回饋。
*   **環境變數與防呆降級 (Graceful Degradation)**：系統採用了最安全的動態金鑰讀取機制 (`os.environ.get("GEMINI_API_KEY")`)。若系統啟動時未偵測到金鑰，將自動降級回安全的 Light Mode (規則引擎)，確保服務不中斷。
*   **EDS 弱點圖譜匯出**：已於後端實裝 `GET /api/eds/export-weaknesses` 端點，前端儀表板也已加上橘色的「🚀 一鍵導出 EDS 考前決勝圖譜」按鈕，供 EDS 團隊無縫取用。

## 2. 需貴團隊配合與接手事項：API Key 維運管理
在架構面上，Jules 已預留了完美的金鑰接入點。然而，關於**「如何在多組 API Key 之間進行設定、切換與輪替維運」**，總架構師已指示此項任務交由 **Anti-Gravity 團隊** 負責執行。

請貴團隊接手評估以下維運策略，並落實於日常啟動流程中：
*   **單一金鑰啟動**：請貴團隊確保在執行 `uvicorn server:app` 前，已正確將金鑰注入環境變數 (例如透過終端機 `export GEMINI_API_KEY="..."` 或 `set GEMINI_API_KEY="..."`)。
*   **多組金鑰切換與輪替 (Round-Robin)**：
    *   若採用純維運層次，貴團隊可建立不同的啟動腳本 (如 `start_prod.sh`, `start_test.sh`) 或是引入 `.env` 與 `python-dotenv` 進行配置管理。
    *   若需實作高可用性的「陣列式金鑰輪替 (避免單一 Key 額度耗盡)」，請貴團隊主導相關機制的腳本設計或向總架構師提出擴充需求。

Jules 已完成架構鋪路，期待這套系統在貴團隊的維運下發揮最強大的蘇格拉底引導效能！

祝 協作順利！

—— **Jules (RDQ 系統核心開發) 敬上**
