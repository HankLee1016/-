"""管理員同步工具。

這裡集中放後台會用到的資料同步功能：
- 補助資料同步
- 申請資料同步

這樣 app.py 只負責路由，不負責遷移細節。
"""

from __future__ import annotations

from service_applications_db import sync_service_applications_from_json
from subsidy_db import sync_subsidies_from_json


def refresh_subsidies() -> int:
    """把 `subsidies.json` 同步到資料庫。"""
    return sync_subsidies_from_json()


def refresh_service_applications() -> int:
    """把 `applications.json` 同步到 service_applications。"""
    return sync_service_applications_from_json()
