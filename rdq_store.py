#!/usr/bin/env python3
"""
rdq_store.py

封裝 RDQ Phase 7 寫入邏輯的 CLI 工具。
接收 JSON 字串、呼叫 leitner 跳箱邏輯、寫入 SQLite。

用法：
  python rdq_store.py '<json_string>'

環境變數（選填）：
  ECOSYSTEM_DB_PATH  — 資料庫路徑，未設定則使用 constants.json 的預設值
"""

import sys
import json
import sqlite3
import os
from datetime import datetime

_BASE = os.path.dirname(os.path.abspath(__file__))

# ── 載入 Shared-Schema 常數 ──────────────────────────────
_CONST_PATH = os.path.join(_BASE, 'RDQ-Shared-Schema',
                           'config', 'constants.json')
if os.path.exists(_CONST_PATH):
    with open(_CONST_PATH, encoding='utf-8') as f:
        _CONST = json.load(f)
else:
    _CONST = {}

# 載入 leitner
sys.path.insert(0, os.path.join(_BASE, 'RDQ-Shared-Schema'))
try:
    import leitner
except ImportError:
    print("Error: 無法載入 leitner 模組，請確定 RDQ-Shared-Schema 存在。", file=sys.stderr)
    sys.exit(1)


def _get_db_path() -> str:
    """優先讀取 ECOSYSTEM_DB_PATH 環境變數，否則 fallback 到 constants.json 的預設值。"""
    env = os.environ.get('ECOSYSTEM_DB_PATH')
    if env:
        return os.path.expanduser(env)
    default = _CONST.get(
        'db_default_path', '~/.education_ecosystem/review_index.db')
    return os.path.expanduser(default)


def _valid_statuses():
    return set(_CONST.get('status', {}).keys()) or {'confirmed', 'uncertain', 'clarified'}


def _valid_loss_reasons():
    return _CONST.get('loss_reason', [
        '概念錯誤', '計算錯誤', '圖表判讀', '推理不足', '看錯題'
    ])


def write_to_db(data):
    db_path = _get_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 確保表格存在
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS review_index (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        subject       TEXT    NOT NULL,
        topic         TEXT    NOT NULL,
        item_id       TEXT    NOT NULL,
        quadrant      TEXT,
        status        TEXT    NOT NULL CHECK (status IN ('confirmed', 'uncertain', 'clarified')),
        source        TEXT    CHECK (source IN ('self', 'prompted')),
        priority      TEXT    NOT NULL CHECK (priority IN ('red', 'yellow', 'green')),
        box           INTEGER NOT NULL DEFAULT 1 CHECK (box BETWEEN 1 AND 5),
        mc_id         TEXT,
        mc_probe_count INTEGER DEFAULT 0,
        mc_probe_variant TEXT,
        date          TEXT    NOT NULL,
        last_reviewed TEXT    NOT NULL,
        next_review   TEXT    NOT NULL,
        scope_disputed INTEGER DEFAULT 0,
        scope_confirmed INTEGER DEFAULT 0,
        file_path     TEXT,
        eds_x_code    TEXT,
        loss_reason   TEXT,
        UNIQUE(subject, topic, item_id, date)
    )
    """)

    subject = data.get('subject')
    topic = data.get('topic')
    date_str = data.get('date', datetime.now().strftime('%Y-%m-%d'))
    items = data.get('items', [])
    valid_statuses = _valid_statuses()
    valid_loss = _valid_loss_reasons()

    for item in items:
        status = item.get('status')
        if status not in valid_statuses:
            print(
                f"Warning: 未知 status '{status}'，跳過 item {item.get('id')}", file=sys.stderr)
            continue

        loss = item.get('loss_reason')
        if loss and loss not in valid_loss:
            print(
                f"Warning: 未知 loss_reason '{loss}'，跳過 item {item.get('id')}", file=sys.stderr)
            continue

        # 查詢最近 box
        cursor.execute('''
            SELECT box FROM review_index
            WHERE subject = ? AND item_id = ?
            ORDER BY date DESC LIMIT 1
        ''', (subject, item['id']))
        row = cursor.fetchone()
        current_box = row[0] if row else 1

        source = item.get('source')
        priority = item.get('priority', 'green')
        next_box, next_review = leitner.next_box(
            current_box, status, priority, source)

        try:
            cursor.execute('''
                INSERT INTO review_index (
                    subject, topic, item_id, quadrant, status, source, priority, box,
                    mc_id, mc_probe_count, mc_probe_variant, date, last_reviewed, next_review,
                    scope_disputed, scope_confirmed, file_path, eds_x_code, loss_reason
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?
                )
            ''', (
                subject, topic, item['id'], item.get(
                    'quadrant'), status, source, priority, next_box,
                item.get('mc_id'), item.get('mc_probe_count',
                                            0), item.get('mc_probe_variant'),
                date_str, date_str, next_review,
                1 if item.get('scope_disputed') else 0,
                1 if item.get('scope_confirmed') else 0,
                data.get('file_path'), item.get('eds_x_code'), loss
            ))
        except sqlite3.IntegrityError:
            pass

    conn.commit()
    conn.close()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python rdq_store.py '<json_string>'", file=sys.stderr)
        sys.exit(1)

    try:
        data = json.loads(sys.argv[1])
        write_to_db(data)
        print("Data successfully stored.")
    except json.JSONDecodeError:
        print("Error: 傳入的不是合法的 JSON 字串。", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)
