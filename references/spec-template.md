---
learner: "{學生名稱}"
subject: "{科目}"
topic: "{單元名稱}"
date: "{YYYY-MM-DD}"
mode: "{Lite | Full}"

interaction_log:
  total_questions: int
  l1_count: int
  l2_count: int
  l3_skipped: int
  fallback_count: int

# ── 機器讀取層：Scheduler / Exam-Mock 直接吃這份陣列，不需 LLM 解析 ──
items:
  # - id:          知識點代碼（從 question-bank.md 的迷思代碼衍生，如 math_ch3_002）
  #   quadrant:    Ⅰ|Ⅱ|Ⅲ|Ⅳ
  #   status:      confirmed | uncertain | clarified
  #   source:      self | prompted | null   # self=✓自己說出，prompted=◇選項認出
  #                                          # null=uncertain 或 clarified（排程只讀 status）
  #   priority:    red | yellow | green
  #   last_reviewed: YYYY-MM-DD
  #   next_review:  YYYY-MM-DD       # self→+7d, prompted→+3d, uncertain→+1d, clarified→+3d(box2固定)
  #   mc_id:       迷思代碼（可選，如 mc_math_002）
  #   mc_probe_count: 0              # 此 mc_id 被當作迷思探測題問過的次數（防題目老化）
  #   mc_probe_variant: "{此次使用的變體代號，如 'a'，無則 null}"
  #   scope_disputed: false          # true=學生認為在範圍內但AI無法確認
  #   scope_confirmed: false         # true=範圍爭議經L1確認後學生答對
  #
  # 範例：
  # - id: "math_ch3_002"
  #   quadrant: "III"
  #   status: "confirmed"
  #   source: "self"
  #   priority: "red"
  #   last_reviewed: "2026-07-27"
  #   next_review: "2026-08-03"
  #   mc_id: null
  #   mc_probe_count: 0
  #   scope_disputed: false
  #   scope_confirmed: false
  # - id: "sci_intro_005"
  #   status: "clarified"
  #   source: null
  #   priority: "red"
  #   last_reviewed: "2026-07-27"
  #   next_review: "2026-07-30"       # ⚠️ 固定 box 2 (+3天)
  #   mc_id: "mc_sci_006"
  #   mc_probe_count: 1
  #   scope_disputed: false
  #   scope_confirmed: false

# 以下欄位由 Phase 7 自動計算，不手動填寫：
# next_review_summary = min(items[].next_review)
# priority_summary = max(items[].priority) (red>yellow>green)

# ── 持久化索引契約（完整 schema 見 RDQ-Shared-Schema/SCHEMA.md） ──
# RDQ Phase 7 寫入 ~/.rdq/review_index.db，呼叫 leitner.next_box() 計算 box。
# 檔案路徑慣例：reviews/{subject}/{topic_slug}_{date}.md
# Scheduler 與 Exam-Mock 只讀 SQLite，不解析 markdown。
---

> 📘 你的學習覆盤卡 — 全部在你的教材範圍內，不會跑出去。

## ✅ 你已經記住的（象限Ⅰ）

- 項目（L1 自己說出來）✅
- 項目（L2 選項提示後答對）✅

## ⚠️ 迷思已澄清

- 項目（學生自信但錯誤，已補充正確資訊），附迷思代碼（如 mc_sci_006）

## ❓ 還能再確認一下的（象限Ⅱ、Ⅲ）

- 具體說明還不太確定的部分，附迷思代碼（如 mc_math_002）

## 🔍 沒想過的關聯（象限Ⅳ，非必填）

- 這個需要更多資料才能確認，下次可以問老師或翻課本。

## 💡 今天的覆盤心得

- 你做得好的地方：
- 下次可以注意的地方：

## ⏰ 下次複習提醒

- ✅ 自己說出來的：7 天後再看（{日期}）
- ✅ 選項認出來的：3 天後再看（{日期}）
- ⚠️ 迷思已澄清：3 天後再看（{日期}）— 迷思復發率高，需比一般項目更早回訪
- ❓ 待確認項目：1 天後再看（{日期}）

## 📋 學習建議

- 一句鼓勵
- 一個具體的複習方向
- 若需要，補充一句「這個部分可以請老師再講一次，或翻課本 OO 頁」
