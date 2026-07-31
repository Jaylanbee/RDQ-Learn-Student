# 雙系統共享後設資料協定 (Shared Metacognitive Schema Protocol)
**版本**：v2.0 (5-in-1 Ecosystem Integrated)  
**歸屬**：RDQ-Learn 與 EDS 雙系統共享協定  
**整合原 Skill**：#32 (紅綠燈自評標籤) & SCHEMA.md 規範

---

## 1. 核心職責與 SSOT

本文件定義 RDQ (上游探勘) 與 EDS (下游演練) 在共享資料庫 `~/.education_ecosystem/review_index.db` 上的資料寫入、讀取與狀態標籤標準。

---

## 2. 狀態標籤與紅綠燈 (Traffic Light System) 映射

| 燈號 / 狀態 | DB `status` | DB `traffic_light` | 定義與語義 | 雙系統處理邏輯 |
|---|---|---|---|---|
| 🟢 **Green** | `confirmed` | `GREEN` | 完全掌握，能白話流暢講出，無疑惑 | **RDQ**：拉長 Leitner 間隔<br>**EDS**：減少派題頻率 |
| 🟡 **Yellow** | `uncertain` | `YELLOW` | 大概懂，但細節模糊，講起來卡卡 | **RDQ**：標記 ❓，寫入 loss_reason<br>**EDS**：排入中優先級特訓 |
| 🔴 **Red** | `uncertain` / `clarified` | `RED` | 完全不確定、答錯或踩中迷思陷阱 | **RDQ**：標記 ⚠️/❓，觸發逃生引導<br>**EDS**：最高 Priority 考前特訓打擊 |

---

## 3. SQLite 表格拓展欄位規範

```sql
-- review_index 表格欄位擴充說明
ALTER TABLE review_index ADD COLUMN traffic_light TEXT DEFAULT 'YELLOW';
ALTER TABLE review_index ADD COLUMN mc_id TEXT;
ALTER TABLE review_index ADD COLUMN loss_reason TEXT;
ALTER TABLE review_index ADD COLUMN eds_x_code TEXT;
```

- `eds_x_code`：108 課綱 X 軸代碼 (如 `Bc-Ⅳ-3`, `N-7-1`)。
- `mc_id`：對應 `question-bank.md` 之迷思代碼 (如 `#mc_sci_006`)。
- `loss_reason`：`概念錯誤` | `計算錯誤` | `圖表判讀` | `推理不足` | `看錯題`。
- `traffic_light`：`GREEN` | `YELLOW` | `RED`。
