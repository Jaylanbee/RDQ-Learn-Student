# api-contract.md - RESTful API 與錯誤碼技術規格
# RDQ v11.5 API 規格書

## 端點清單

### 1. `POST /api/chat`
- **說明**：蘇格拉底對話狀態機進度推移（含 24h 惰性清理）。
- **Request Body**：
```json
{
  "session_id": "session_123",
  "message": "質量的定義",
  "topic": "1-2 質量與密度的測量",
  "textbook": "",
  "file_path": "",
  "is_start": false
}
```

### 2. `GET /api/tasks`
- **說明**：取得今日到期閃卡清單（【Hard Quota + 動態名額釋出】演算法）。
- **Response**：
```json
{
  "status": "success",
  "count": 23,
  "total_due": 23,
  "tasks": [...]
}
```

### 3. `POST /api/task/{item_id}/verify`
- **說明**：閃卡答案評定，更新 `last_reviewed_at`，並重算 Leitner 箱子層級。

### 4. `GET /api/radar`
- **說明**：取得 Laplace 平滑化五科能力分數。
- **Response**：
```json
{
  "status": "success",
  "radar": { "國文": 62, "英語": 55, "數學": 70, "自然": 68, "社會": 50 }
}
```

### 5. `POST /api/ingest` & `POST /api/ingest/approve`
- **說明**：多模態草稿寫入 Staging 與轉正移至 `./data/media/official/item_{uuid}.jpg`。
