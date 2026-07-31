# 【水循環學習法 (RDQ × EDS)】工作流程 specification (WorkFlow Specification)

> **版本**：v2.0  
> **發布者**：Antigravity Agent Team & 專案總架構師  

---

## 1. 全局工作流程概覽 (Global Workflow Architecture)

```
[Phase 0: 靜默判定] ➔ [Phase 0.5: 認知快照 / T2N 讀取] ➔ [Phase 1: 象限Ⅰ 引導回憶]
                                                                 │
[Phase 4: 象限Ⅳ 盲點提示]  [Phase 3: 象限Ⅲ 隱性知識挖掘]  [Phase 2: 象限Ⅱ 引導解惑]
       │
       ▼
[Phase 5: 產出覆盤卡] ➔ [Phase 6: 學生確認] ➔ [Phase 7: 寫入 review_index.db] ➔ [Phase 8: 移交下游 EDS]
```

---

## 2. 階段詳細作業流程與 If-Then 狀態轉移

### Phase 0｜靜默判定 (Silent Diagnosis)
- 判斷科目、單元範圍、Lite/Full 互動預算。
- **預設不主動要求課本** (延遲索取原則)。

### Phase 0.5｜認知快照與選配輸入 (Snapshot & Optional Input)
- 若有 T2N JSON 或照片，讀取對齊；若無，進行 30 秒認知快照問答，0 秒開局。

### Phase 1 & 2｜象限Ⅰ與象限Ⅱ (Recall & Explanation)
- **L1 蘇式開局**：開放式問句與 10 歲小孩費曼白話測試。
- **降級觸發**：學生回答字數 $<5$ 或說「不知道」➔ **無條件強制降至 L2 選項**。
- **迷思處理**：自信答錯 ➔ 以非評判語氣澄清，進行微型驗證，成功上記 ⚠️迷思已澄清 (`status: clarified`)。

### Phase 3 & 4｜象限Ⅲ與象限Ⅳ (Deep Digging & Blind Spot)
- 參照 `eds_roi_weights.csv` 挑選高 ROI / 低通過率之盲區進行挖掘與提示。

### Phase 5 & 6｜覆盤卡呈現與學生確認 (Artifact & Confirmation)
- 使用 `write_to_file` 工具以 Artifact (UserFacing: true) 展示覆盤卡。
- 學生選擇：✅ 確認 / ✏️ 修改 / 🔁 再問一輪。

### Phase 7｜SQLite 資料庫自動寫入 (DB Store)
- 呼叫 `rdq_store.py` 寫入 `~/.education_ecosystem/review_index.db`。
- 背景執行 `leitner.py` 計算 Ebbinghaus 跳箱與 `next_review` (Day 1, 3, 7, 14, 30)。

### Phase 8｜移交下游 EDS (Handover to EDS)
- 若卡關比例 $\ge 50\%$ 或提到大考，引導啟動 EDS 進行高強度實戰演練與 5x 損失對賭。

---

## 3. 外圈通用選配插件調用流程 (Plugins Invocation)

在 Phase 1~4 過程中，可隨時插隊調用 `Docs/skills/plugins/` 下之選配模組：
- **M02 迷走降壓**：焦慮時暫停對話 ➔ 引導 3 次生理嘆息 ➔ 返回主流程。
- **M09 門神過濾**：遇到伸手牌指令 ➔ 啟動第 7 條驗證門神 ➔ 切換為教練引導。
