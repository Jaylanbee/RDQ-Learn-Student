# 聯絡事項：致 Anti-Gravity 運行框架團隊 (PR 合併與部署指令)

**主旨：請協助將 `jules-v12-gemini-integration` 分支合併至 Master**

致 Anti-Gravity Agent 運行框架團隊：

您好！關於 RDQ v12 的核心架構升級 (Gemini 直連與 EDS 弱點圖譜匯出端點)，Jules 團隊已經將所有程式碼與相關交接文件提交完畢，並發布了對應的 Pull Request (PR)。

**需貴團隊立即協助執行的事項：**

1.  **審閱與合併 (Merge) PR**：
    目前的 v12 實作皆已安全提交至 `jules-v12-gemini-integration` 分支。請貴團隊的發布管理員 (Release Manager) 協助審閱該分支的程式碼變更，並將其正式合併 (Merge) 到 `master` 主分支中。
2.  **拉取與部署**：
    合併完成後，請貴團隊在正式營運環境中執行 `git pull origin master` 以拉取最新代碼，並確保在重啟 `uvicorn server:app` 前，已如前信所交代，將 `GEMINI_API_KEY` 注入環境變數中。

一旦合併與重啟完成，v12 架構即刻生效。感謝貴團隊的高效配合！

祝 部署順利！

—— **Jules (RDQ 系統核心開發) 敬上**
