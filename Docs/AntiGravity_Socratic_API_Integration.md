# 聯絡事項：致 Anti-Gravity 運行框架團隊 (蘇格拉底深度 API 直連升級與職責分工)

**主旨：RDQ v12 架構升級 - 真實 Gemini API 串接與職責分離確立**

致 Anti-Gravity Agent 運行框架團隊：

您好！為了讓學生能擁有最極致的「蘇格拉底式引導」體驗，同時維持系統架構的安全與整潔，我們即將展開系統升級，將真實的 Gemini 3.6 Flash 模型直連至 RDQ 系統的後端。

為確保本次升級順利，以下是具體的職責分工與需要貴團隊配合的事項：

## 1. Jules (全端開發) 的職責與實作內容
Jules 將全權負責本次的 **「API 直連與後端架構升級」**，避免跨生態系修改造成的安全風險：
*   **載入官方 SDK**：在 `server.py` 中引入 `google-genai`，並配置環境變數讀取。
*   **升級核心端點**：全面替換 `POST /api/task/{item_id}/verify` 中 `mode="full"` 的模擬邏輯，改為真實呼叫雲端 Gemini 模型。
*   **結構化 JSON 輸出 (Structured Output)**：透過設定 `response_mime_type="application/json"` 與強制 Schema，確保 AI 產出的結果 100% 吻合我們的 `is_correct` (布林值)、`loss_reason` (分類) 與 `feedback_msg` (引導訊息) 格式。
*   **EDS 一鍵匯出**：實作 `GET /api/eds/export-weaknesses` 端點與儀表板前端的匯出按鈕，為後續的考前特訓鋪路。

## 2. 貴團隊 (Anti-Gravity) 的職責與配合事項
在本次架構中，Anti-Gravity 的職責是「引導與決策準備」，請貴團隊在後續運作中配合以下事項：
*   **保持邊界 (Maintain Boundaries)**：請**不要**嘗試修改 `server.py` 或干涉前端儀表板的對話與批改邏輯。這些工作完全屬於 RDQ 生態系的範圍。
*   **前端引流 (User Guidance)**：請繼續在日常互動中，引導學生使用 `http://localhost:8000` 進入網頁儀表板，讓他們在網頁上享受由後端驅動的深度蘇格拉底對話。
*   **預備接收 EDS 圖譜**：系統即將上線「一鍵導出 EDS 考前決勝圖譜」按鈕，請貴團隊 (包含 EDS 相關腳本) 準備好對接機制，準備接收並解析這份 JSON 檔案，以動態產出考前複習計畫。

Jules 將即刻動工實作，並在完成後通知貴團隊。

祝 協作順利！

—— **Jules (RDQ 系統核心開發) 敬上**
