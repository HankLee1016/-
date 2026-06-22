"""補助申請資料的 DB 版儲存層。

目標：
1. 先建立新的 `service_applications` 資料表，讓補助申請有正式資料結構。
2. 同時保留 `applications.json` 作為舊資料備援，避免遷移期把資料弄丟。
3. 上層 `app.py` 只需要呼叫這個模組，不必再自己判斷 DB / JSON。
"""

from __future__ import annotations

import datetime
import json
import uuid
from pathlib import Path

from db_config import get_db_connection

APPLICATIONS_JSON = Path(__file__).with_name("applications.json")


def ensure_service_applications_table() -> None:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS service_applications (
            id UUID PRIMARY KEY,
            username VARCHAR(255) NOT NULL,
            case_title VARCHAR(255) NOT NULL,
            background TEXT,
            issues TEXT,
            goals TEXT,
            proposal TEXT NOT NULL,
            subsidy_summary TEXT,
            success_pdf TEXT,
            subsidy_pdf TEXT,
            status VARCHAR(50) DEFAULT 'pending',
            admin_note TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (username) REFERENCES users(username)
        )
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_service_applications_status ON service_applications(status)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_service_applications_username ON service_applications(username)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_service_applications_created_at ON service_applications(created_at)")
    conn.commit()
    cur.close()
    conn.close()


def _load_json_applications() -> list[dict]:
    if not APPLICATIONS_JSON.exists():
        return []
    try:
        return json.loads(APPLICATIONS_JSON.read_text(encoding="utf-8")).get("applications", [])
    except json.JSONDecodeError:
        return []


def _save_json_applications(applications: list[dict]) -> None:
    APPLICATIONS_JSON.write_text(json.dumps({"applications": applications}, ensure_ascii=False, indent=2), encoding="utf-8")


def _row_to_dict(row) -> dict:
    return {
        "id": str(row[0]),
        "username": row[1],
        "case_title": row[2],
        "background": row[3] or "",
        "issues": row[4] or "",
        "goals": row[5] or "",
        "proposal": row[6] or "",
        "subsidy_summary": row[7] or "",
        "success_pdf": row[8],
        "subsidy_pdf": row[9],
        "status": row[10] or "pending",
        "admin_note": row[11] or "",
        "created_at": row[12].isoformat() if getattr(row[12], "isoformat", None) else row[12],
        "updated_at": row[13].isoformat() if getattr(row[13], "isoformat", None) else row[13],
    }


def create_service_application(username, case_title, background, issues, goals, proposal, subsidy_summary="", success_pdf=None, subsidy_pdf=None, status="pending") -> dict:
    ensure_service_applications_table()
    app_id = str(uuid.uuid4())
    now = datetime.datetime.utcnow()
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO service_applications
            (id, username, case_title, background, issues, goals, proposal, subsidy_summary, success_pdf, subsidy_pdf, status, admin_note, created_at, updated_at)
        VALUES
            (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (app_id, username, case_title, background, issues, goals, proposal, subsidy_summary, success_pdf, subsidy_pdf, status, "", now, now),
    )
    conn.commit()
    cur.close()
    conn.close()
    return {
        "id": app_id,
        "username": username,
        "case_title": case_title,
        "background": background,
        "issues": issues,
        "goals": goals,
        "proposal": proposal,
        "subsidy_summary": subsidy_summary,
        "success_pdf": success_pdf,
        "subsidy_pdf": subsidy_pdf,
        "status": status,
        "admin_note": "",
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }


def load_service_applications() -> list[dict]:
    try:
        ensure_service_applications_table()
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, username, case_title, background, issues, goals, proposal, subsidy_summary, success_pdf, subsidy_pdf, status, admin_note, created_at, updated_at FROM service_applications ORDER BY created_at DESC"
        )
        rows = [_row_to_dict(row) for row in cur.fetchall()]
        cur.close()
        conn.close()
        if rows:
            return rows
    except Exception:
        pass
    return _load_json_applications()


def sync_service_applications_from_json() -> int:
    """把 applications.json 內容保守地同步到 service_applications。"""
    items = _load_json_applications()
    if not items:
        return 0
    ensure_service_applications_table()
    conn = get_db_connection()
    cur = conn.cursor()
    count = 0
    for item in items:
        app_id = item.get("id") or str(uuid.uuid4())
        created_at = item.get("created_at") or datetime.datetime.utcnow().isoformat()
        updated_at = item.get("updated_at") or created_at
        cur.execute(
            """
            INSERT INTO service_applications
                (id, username, case_title, background, issues, goals, proposal, subsidy_summary, success_pdf, subsidy_pdf, status, admin_note, created_at, updated_at)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                username = EXCLUDED.username,
                case_title = EXCLUDED.case_title,
                background = EXCLUDED.background,
                issues = EXCLUDED.issues,
                goals = EXCLUDED.goals,
                proposal = EXCLUDED.proposal,
                subsidy_summary = EXCLUDED.subsidy_summary,
                success_pdf = EXCLUDED.success_pdf,
                subsidy_pdf = EXCLUDED.subsidy_pdf,
                status = EXCLUDED.status,
                admin_note = EXCLUDED.admin_note,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                app_id,
                item.get("username", ""),
                item.get("case_title", ""),
                item.get("background", ""),
                item.get("issues", ""),
                item.get("goals", ""),
                item.get("proposal", ""),
                item.get("subsidy_summary", ""),
                item.get("success_pdf"),
                item.get("subsidy_pdf"),
                item.get("status", "pending"),
                item.get("admin_note", ""),
                created_at,
                updated_at,
            ),
        )
        count += 1
    conn.commit()
    cur.close()
    conn.close()
    return count


def get_service_application(application_id: str) -> dict | None:
    for app in load_service_applications():
        if app.get("id") == application_id:
            return app
    return None


def get_user_service_applications(username: str) -> list[dict]:
    return [app for app in load_service_applications() if app.get("username") == username]


def update_service_application_status(application_id: str, status: str, admin_note: str = "") -> dict | None:
    try:
        ensure_service_applications_table()
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE service_applications
            SET status = %s, admin_note = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING id, username, case_title, background, issues, goals, proposal, subsidy_summary, success_pdf, subsidy_pdf, status, admin_note, created_at, updated_at
            """,
            (status, admin_note, application_id),
        )
        row = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        return _row_to_dict(row) if row else None
    except Exception:
        applications = _load_json_applications()
        for app in applications:
            if app.get("id") == application_id:
                app["status"] = status
                app["admin_note"] = admin_note
                app["updated_at"] = datetime.datetime.utcnow().isoformat()
                _save_json_applications(applications)
                return app
        return None
