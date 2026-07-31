# 🌊 水循環學習法 (RDQ × EDS) — RDQ 課後無壓檢傷與診斷系統

> **專案名稱**：【水循環學習法 (RDQ × EDS)】五合一教育生態系 — RDQ 診斷端  
> **版本**：v2.0 (5-in-1 Ecosystem Integrated)  
> **維護團隊**：Antigravity Agent Team & 專案總架構師  

---

## 🎯 1. 專案用途 (Purpose)

本專案為【水循環學習法 (RDQ × EDS)】教育生態系中的 **RDQ (Student Learning Review Quadrant) 課後無壓檢傷與診斷系統**。

### 核心哲學：
- **戰略定位**：作為教育決策系統 (EDS) 的先鋒探勘兵，負責在**最低壓力與零輸入負擔**下，探勘學生的知識盲點與迷思，並記錄於 `review_index.db`。
- **神經科學依據**：結合 Ebbinghaus 遺忘曲線防浪堤、費曼白話化測試、蘇格拉底「我猜代替不知道」以及後設認知紅綠燈自評，戳破學生的「流暢性幻覺 (Fluency Illusion)」。

---

## 🚀 2. 目前功能 (Current Features)

### 🟢 內圈：個人學習水循環 Core 模組 (`Docs/skills/`)
1. **`RDQ_Socratic_Feynman.md`**：Phase 0.5 認知快照、10 歲小孩費曼白話測試、蘇格拉底 L1/L2 鷹架降級。
2. **`EDS_Deliberate_Practice.md`**：交付 EDS 之 7 種考前實戰題型派發與 50-70% 難度甜頭區控制。
3. **`EDS_PME_System.md`**：交付 EDS 之考前 Plan-Monitor-Evaluate 強制執行與 5x 損失趨避對賭承諾。
4. **`Shared_Metacognitive_Schema.md`**：雙端共享 SQLite DB Schema 與 🟢/🟡/🔴 燈號協定。

### 🔵 外圈：水環境生態防護通用選配工具箱 (`Docs/skills/plugins/`)
1. **`Plugin_M02_Vagus_Ignition.md`**：🧘 30 秒生理嘆息/盒式呼吸急救與 90 分鐘心流發動。
2. **`Plugin_M08_Dopamine_Reset.md`**：🛡️ 三層摩擦力改造 (物理/數位/社交) 與 5 分鐘無聊罐抽籤。
3. **`Plugin_M09_Boundary_Gate.md`**：🛑 7 大門神外包過濾器 (防伸手牌/認知債務) 與 Prompt 鍛造。
4. **`Plugin_M10_Elementary_Care.md`**：國小親子護腦、家庭 AI 紅黃綠燈協議與床前 3 分鐘小小老師。
5. **`Plugin_M11_Junior_Epoch.md`**：國中親子雙向手機使用契約與 EPOCH 身份宣言。
6. **`Plugin_M12_EPOCH_Journal.md`**：EPOCH 靈魂五力、49 項持久技能自評與 90 天未來信。

---

## 💻 3. 啟動方式 (Getting Started)

### Antigravity Agent 環境觸發：
在 Antigravity 聊天室中，使用者只需輸入以下關鍵字即可 0 秒啟動：
- *「用 RDQ 複習」* / *「課後複習」* / *「幫我複習國文」* / *「學習覆盤」*

### 本地測試腳本執行：
```powershell
# 執行 Phase 7 測試寫入 review_index.db
python "$env:USERPROFILE\.config\opencode\skills\rdq\rdq_store.py" '{"subject":"science","topic":"光合作用","date":"2026-07-31","items":[{"item_id":"sci_ch3_001","status":"uncertain","priority":"red","mc_id":"mc_sci_006"}]}'
```

---

## 🛠️ 4. 部署方式 (Deployment)

1. **技能檔部署**：複製或 Git Sync 至本地 Agent 技能目錄 `~/.config/opencode/skills/rdq/`。
2. **資料庫部署**：執行期 SQLite 資料庫會自動建立於 `~/.education_ecosystem/review_index.db`。

---

## 🔑 5. 環境變數 (Environment Variables)

| 環境變數 | 預設值 | 說明 |
|---|---|---|
| `ECOSYSTEM_DB_PATH` | `~/.education_ecosystem/review_index.db` | 跨 Agent 共享 SQLite 資料庫檔案路徑 |
| `PAGER` | `cat` | 控制 CLI 命令輸出格式 |

---

## ⚠️ 6. 已知問題 (Known Issues)

1. **PowerShell 字符與 UTF-8 路徑**：Windows PowerShell 下傳遞包含單引號 `'` 的 JSON 字串至 `rdq_store.py` 時，需留意字符轉義。
2. **語音辨識同音字**：使用者透過語音輸入時，「RDQ」常被誤轉寫為「阿滴Q」、「R滴Q」、「二滴Q」，系統以全域善意還原原則處理。

---

## 🎯 7. 下一步計畫 (Next Steps)

1. 配合 EDS 開發團隊完成下游 `EDS_Deliberate_Practice.md` 的 SQL 抽樣實戰對接。
2. 在 UI 介面整合 `Docs/skills/plugins/` 下的 6 大外圈通用選配按鈕。
