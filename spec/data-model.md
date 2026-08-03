# data-model.md - SQLite 5 大資料表 Schema 規格與 UTC 時間處理
# RDQ v11.5 資料模型規格書

## 核心 Table Schema (review_index_current)

```sql
CREATE TABLE review_index_current (
    item_id           TEXT PRIMARY KEY,
    subject           TEXT NOT NULL,
    topic             TEXT NOT NULL,
    question          TEXT NOT NULL,
    answer            TEXT NOT NULL,
    image_path        TEXT DEFAULT NULL,
    box_level         INTEGER NOT NULL DEFAULT 1 CHECK(box_level BETWEEN 1 AND 5),
    status            TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','active','mastered')),
    priority          INTEGER NOT NULL DEFAULT 0 CHECK(priority BETWEEN 0 AND 100),
    wrong_count       INTEGER NOT NULL DEFAULT 0,
    last_wrong_at     TEXT,
    next_review_at    TEXT,          -- NULL 代表已畢業
    last_reviewed_at  TEXT,          -- 每次 verify 答題均強制更新
    mastered_at       TEXT,          -- 僅 status='mastered' 時有值
    created_at        TEXT NOT NULL
);
```

包含 `review_index_log`, `session_state`, `ingestion_staging`, `system_metadata` 等 5 大資料表完整定義。
