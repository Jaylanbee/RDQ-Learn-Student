# 10 大 Skills 重構對照索引與稽查清單 (Skills Refactoring & Audit Log)
**發布日期**：2026-07-31  
**維護者**：Antigravity Agent Team & 專案總架構師  
**狀態**：✅ 已完成 10 合 4 精煉重構並正式發布至 `Docs/skills/`

---

## 📋 1. 重構背景與減法原則

為避免 LLM 在執行時因讀取過多重複科普文章而造成 Context Overload 與角色語氣內耗，我們將原始 10 個散落的 AI Skills 進行了「去冗餘、統一對話角色、轉化為 If-Then 指令鏈」的深度優化，精煉重構為 **4 大標準化模組**。

---

## 🔍 2. 原始 10 大 Skills ➔ 4 大精煉模組稽查對照表

| 原始桌面 Skill 檔案 | 稽查精髓與硬參數 | 整合後對應模組路徑 (`Docs/skills/`) | 模組歸屬 |
|---|---|---|---|
| **`#17 認知快照模板-AI-Skill.md`** | 寫保留 71% vs 只想 45%；30秒/3分鐘快照；戳破 30% 知識幻覺 | `RDQ_Socratic_Feynman.md` (Phase 0.5 快照) | RDQ 獨佔 |
| **`#20 蘇格拉底教練-AI-Skill.md`** | ONLY問問題不給答案；「我猜」代替「不知道」；先想 30 秒 | `RDQ_Socratic_Feynman.md` (我猜引導機制) | RDQ 獨佔 |
| **`#30 費曼技巧練習台-AI-Skill.md`** | 簡化即理解；生成效應 (+20-40%保留)；找出卡關點 | `RDQ_Socratic_Feynman.md` (白話診斷引擎) | RDQ 獨佔 |
| **`#31 費曼技巧-AI-Skill.md`** | 扮演 10 歲好奇小孩追問；禁止使用專業術語；雙階段評估 | `RDQ_Socratic_Feynman.md` (10歲小孩追問 Mode) | RDQ 獨佔 |
| **`#27 間隔重複排程器-AI-Skill.md`** | Ebbinghaus 遺忘曲線；最優復習時間 (1, 3, 7, 14, 30 天)；沙灘防浪堤 | `EDS_Deliberate_Practice.md` (間隔重測排程) | EDS 交付 |
| **`#28 主動提取題庫-AI-Skill.md`** | 出題即學習；7 種實戰題型派發；背到會用轉化流程 | `EDS_Deliberate_Practice.md` (7種實戰題型) | EDS 交付 |
| **`#29 刻意練習設計師-AI-Skill.md`** | 三區模型；**50-70% 成功率甜頭區**；髓鞘質增厚；3分鐘掙扎原則 | `EDS_Deliberate_Practice.md` (50-70%難度控制) | EDS 交付 |
| **`#21 PME三階段檢查表-AI-Skill.md`** | Plan-Monitor-Evaluate 流程；防止流暢性幻覺 | `EDS_PME_System.md` (考前 Plan-Monitor) | EDS 交付 |
| **`#22 PME-Skill-AI-Skill.md`** | PME 強制執行系統；三不原則 (無法跳過/作弊/逃避) | `EDS_PME_System.md` (考前強制執行) | EDS 交付 |
| **`#32 後設認知監控儀表板-AI-Skill.md`** | 紅綠燈自評 (🟢/🟡/🔴)；**5x 損失趨避公開對賭承諾 (損失痛苦 2.25x)** | `EDS_PME_System.md` (5x損失對賭承諾)<br>`Shared_Metacognitive_Schema.md` (紅綠燈) | EDS 交付 / 共享 |

---

## 🛠️ 3. 模組維護與稽查指引

日後若有新的學習科學理論或 Skill 欲加入系統，請遵照以下稽查原則：
1. **不要新增獨立單一檔案**，優先評估歸屬於 RDQ 診斷端還是 EDS 演練端。
2. 剔除科普性敘述，將其提煉為硬參數與 **If-Then 條件觸發鏈**。
3. 更新本對照表 (`Skills_Audit_Index.md`)，維持 SSOT (Single Source of Truth) 版本追蹤。
