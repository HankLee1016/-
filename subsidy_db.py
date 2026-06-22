"""補助資料的資料庫/檔案雙模式存取工具。

設計目標：
1. 先讓補助資料能穩定進 PostgreSQL。
2. 若資料庫尚未建立或連線失敗，仍可回退到 `subsidies.json`。
3. 上層程式只呼叫這個模組，不需要自己判斷資料來源。
"""

from __future__ import annotations

import json
from pathlib import Path

from db_config import get_db_connection

SUBSIDIES_JSON = Path(__file__).with_name("subsidies.json")


def _row_to_dict(row) -> dict:
    return {
        "id": row[0],
        "title": row[1],
        "category": row[2],
        "agency": row[3],
        "subsidy_number": row[4],
        "deadline": row[5].isoformat() if getattr(row[5], "isoformat", None) else row[5],
        "amount_range": row[6],
        "eligibility": row[7],
        "description": row[8],
        "source_url": row[9],
        "source_type": row[10],
    }


def load_subsidies_from_json() -> list[dict]:
    if not SUBSIDIES_JSON.exists():
        return []
    return json.loads(SUBSIDIES_JSON.read_text(encoding="utf-8")).get("subsidies", [])


def ensure_subsidies_table() -> None:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS subsidies (
            id BIGINT PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            category VARCHAR(100),
            agency VARCHAR(255),
            subsidy_number VARCHAR(255),
            deadline DATE,
            amount_range VARCHAR(255),
            eligibility TEXT,
            description TEXT,
            source_url TEXT,
            source_type VARCHAR(50) DEFAULT 'seed',
            raw_data JSONB,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_subsidies_category ON subsidies(category)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_subsidies_deadline ON subsidies(deadline)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_subsidies_agency ON subsidies(agency)")
    conn.commit()
    cur.close()
    conn.close()


def upsert_subsidies(records: list[dict]) -> int:
    if not records:
        return 0
    ensure_subsidies_table()
    conn = get_db_connection()
    cur = conn.cursor()
    inserted = 0
    for item in records:
        cur.execute(
            """
            INSERT INTO subsidies
                (id, title, category, agency, subsidy_number, deadline, amount_range, eligibility, description, source_url, source_type, raw_data, updated_at)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (id) DO UPDATE SET
                title = EXCLUDED.title,
                category = EXCLUDED.category,
                agency = EXCLUDED.agency,
                subsidy_number = EXCLUDED.subsidy_number,
                deadline = EXCLUDED.deadline,
                amount_range = EXCLUDED.amount_range,
                eligibility = EXCLUDED.eligibility,
                description = EXCLUDED.description,
                source_url = EXCLUDED.source_url,
                source_type = EXCLUDED.source_type,
                raw_data = EXCLUDED.raw_data,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                int(item.get("id") or 0),
                item.get("title", ""),
                item.get("category", ""),
                item.get("agency", ""),
                item.get("subsidy_number", ""),
                item.get("deadline") or None,
                item.get("amount_range", ""),
                item.get("eligibility", ""),
                item.get("description", ""),
                item.get("source_url", ""),
                item.get("source_type", "seed"),
                json.dumps(item, ensure_ascii=False),
            ),
        )
        inserted += 1
    conn.commit()
    cur.close()
    conn.close()
    return inserted


def sync_subsidies_from_json() -> int:
    return upsert_subsidies(load_subsidies_from_json())


def fetch_subsidies() -> list[dict]:
    try:
        ensure_subsidies_table()
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, title, category, agency, subsidy_number, deadline, amount_range, eligibility, description, source_url, source_type FROM subsidies ORDER BY COALESCE(deadline, DATE '9999-12-31') ASC, id DESC"
        )
        rows = [_row_to_dict(row) for row in cur.fetchall()]
        cur.close()
        conn.close()
        if rows:
            return rows
    except Exception:
        pass
    return load_subsidies_from_json()
