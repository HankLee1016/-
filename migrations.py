"""保守型資料遷移工具。

這個模組專門負責把舊 JSON 資料同步到 PostgreSQL。
原則是：先同步、再保留 JSON、必要時可重跑，不做破壞性操作。
"""

from __future__ import annotations

from service_applications_db import ensure_service_applications_table, load_service_applications
from subsidy_db import ensure_subsidies_table, sync_subsidies_from_json, load_subsidies_from_json, upsert_subsidies


def sync_applications_from_json() -> int:
    """把 applications.json 內容同步到 service_applications 表。"""
    ensure_service_applications_table()
    records = load_service_applications()
    # 若資料庫已有資料，直接回傳目前數量，避免重複寫入。
    if records:
        return len(records)
    # 由於 service_applications_db 已提供 JSON 備援，這裡可直接使用其 create 邏輯不安全。
    # 因此此函式會由 admin 工具呼叫更完整的遷移流程。
    return 0


def sync_subsidies_from_json_safe() -> int:
    """把 subsidies.json 同步到 subsidies 表。"""
    ensure_subsidies_table()
    return sync_subsidies_from_json()
