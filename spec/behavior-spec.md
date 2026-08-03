# behavior-spec.md - Leitner 演算法、四象限狀態機與 Prompt Guardrail
# RDQ v11.5 行為規格書

## 1. Leitner 排程與動態名額釋出演算法
- `ORDER BY box_level ASC (脆弱優先) -> priority DESC -> next_review_at ASC`
- 某 Box 配額不足時，自動釋放名額給最脆弱且優先度高之卡片。

## 2. 蘇格拉底四象限對話 Guardrail
- Phase 1~3 嚴禁直接給出定義或答案。
- 遇不知自動降級 L2 選擇題鷹架。
