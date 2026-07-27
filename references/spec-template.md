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
  mode_used: "{L1 | L2 | L3}"

# ── 機器讀取層：Scheduler / Exam-Mock 直接吃這份陣列，不需 LLM 解析 ──
items:
  # - id:          知識點代碼（從 question-bank.md 的迷思代碼衍生，如 math_ch3_002）
  #   quadrant:    Ⅰ|Ⅱ|Ⅲ|Ⅳ
  #   status:      confirmed | uncertain
  #   source:      self | prompted    # self=✓自己說出，prompted=◇選項認出
  #   priority:    red | yellow | green
  #   last_reviewed: YYYY-MM-DD
  #   next_review:  YYYY-MM-DD       # self→+7d, prompted→+3d, uncertain→+1d
  #   mc_id:       迷思代碼（可選，如 mc_math_002）
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

next_review_date: "{YYYY-MM-DD}"
priority: "{high | medium | low}"

# ── 持久化索引契約 ──
# RDQ Phase 7 寫完本 md 檔案後，同時往索引表寫一筆記錄：
#   table: review_index
#   schema: (subject, topic, date, item_id, status, next_review_date)
# Scheduler 與 Exam-Mock 只讀索引表，不觸碰 markdown 本身。
# 索引表實作：SQLite (review_index.db) 或共享 JSON 索引檔，交由環境決定。
# 檔案路徑慣例：reviews/{subject}/{topic_slug}_{date}.md
---

> 📘 你的學習覆盤卡 — 全部在你的教材範圍內，不會跑出去。

## ✅ 你已經記住的（象限Ⅰ）

- 項目（L1 自己說出來）✅
- 項目（L2 選項提示後答對）✅

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
- ❓ 待確認項目：1 天後再看（{日期}）

## 📋 學習建議

- 一句鼓勵
- 一個具體的複習方向
- 若需要，補充一句「這個部分可以請老師再講一次，或翻課本 OO 頁」
