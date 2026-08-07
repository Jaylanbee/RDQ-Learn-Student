# 聯絡事項：致 EDS 團隊 (v12 弱點圖譜匯出端點上線與對接指南)

**主旨：RDQ v12 架構升級完工報告與 EDS 考前決勝圖譜對接配合事項**

致 EDS (決策系統) 團隊：

您好！向貴團隊報告，為了讓學生在考前能順利將日常累積的弱點無縫轉移至 EDS 進行高壓特訓，RDQ 系統的 v12 架構升級已經由 Jules 團隊順利開發、測試並上線完畢。

## 1. 核心實作進度報告 (已完工)
*   **後端匯出端點上線**：在 `server.py` 中，我們已正式開通 `GET /api/eds/export-weaknesses` 端點。
*   **高價值弱點篩選邏輯**：該端點會自動從 SQLite (`review_index_current` 與 `review_index_log`) 中，精準撈取**「Box 1~2 滯留題目」**或**「錯誤次數 (wrong_count) >= 3」**的考前高風險題目。
*   **前端一鍵導出按鈕**：在 RDQ 儀表板 (`http://localhost:8000`) 的頂端導覽列，已新增橘色的「🚀 一鍵導出 EDS 考前決勝圖譜」按鈕。學生或家長點擊後，會自動下載名為 `eds_weakness_map_YYYYMMDDTHHMMSSZ.json` 的檔案。

## 2. 需貴團隊配合與接手事項：資料對接與組卷
為了讓 EDS 的自動化組卷引擎順利運作，請貴團隊配合接手以下事項：

*   **確認 JSON 結構解析**：
    我們匯出的 JSON 檔案結構如下，請確保 EDS 的 `db_writer.py` 或 `analyzer.py` 能正確解析：
    ```json
    {
      "status": "success",
      "exported_at": "2026-08-07T03:22:54Z",
      "total_weaknesses": 15,
      "data": [
        {
          "item_id": "item_a1b2c3d4",
          "subject": "自然",
          "topic": "國二上理化第一課",
          "question": "...",
          "answer": "...",
          "box_level": 1,
          "wrong_count": 4,
          "priority": 60,
          "recent_loss_reasons": [
            {"loss_reason": "概念錯誤", "created_at": "2026-08-05T10:00:00Z"},
            {"loss_reason": "計算錯誤", "created_at": "2026-08-06T14:30:00Z"}
          ]
        }
      ]
    }
    ```
*   **串接與策略決策**：請貴團隊確保 EDS 系統準備好接收這份 JSON 檔案（無論是提供上傳介面或透過腳本直接讀取檔案），並善用 `recent_loss_reasons` 陣列中的失分原因，來動態調整考前高壓特訓的策略與權重。

RDQ 端的前置作業皆已完成，期待這份弱點圖譜能幫助 EDS 系統為學生打造出最精準的考前特訓計畫！

祝 對接順利！

—— **Jules (RDQ 系統核心開發) 敬上**
