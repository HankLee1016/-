"""資料存取層：以 PostgreSQL 儲存系統資料。

提供 load(table) 與 save(table, rows) 兩個函式，回傳／接收之資料格式
與原本 JSON 檔案相同（字典串列），讓 app.py 的業務邏輯不需更動：
    - load：讀取整張資料表，日期時間轉為字串、空值轉為空字串。
    - save：在同一交易中新增或更新每一筆資料，並刪除串列中已不存在的資料。
資料表位於 DB_SCHEMA 環境變數指定之 schema（預設 elder）。
"""
from __future__ import annotations

import datetime
import os
import queue

from psycopg2 import DatabaseError, sql
from psycopg2.extras import Json, RealDictCursor

from db_config import get_db_connection

SCHEMA = os.getenv("DB_SCHEMA", "elder")
PROFILE_FIELDS = ["contact_name", "relation", "phone", "email", "elder_name", "age_group", "district",
                  "address", "household_status", "care_level", "care_notes"]

# 各資料表欄位型態：text、int、date、ts（時間戳記）、json、fk（外鍵，空字串存為 NULL）
TABLES = {
    "users": {"key": "username", "order": "id",
              "cols": {"username": "text", "password": "text", "role": "text",
                       **{f: "text" for f in PROFILE_FIELDS}}},
    "services": {"key": "id", "order": "created_at NULLS FIRST, id",
                 "cols": {"id": "text", "username": "fk", "service_name": "text", "service_type": "text",
                          "description": "text", "target_group": "text", "contact": "text", "status": "text",
                          "district": "text", "service_scope": "text", "created_at": "ts"}},
    "help_requests": {"key": "id", "order": "created_at DESC, id",
                      "cols": {"id": "text", "username": "text", "elder_name": "text", "age_group": "text",
                               "district": "text", "urgency": "text", "household_status": "text",
                               "care_level": "text", "need_type": "text", "need_when": "text", "location": "text",
                               "duration": "text", "details": "text", "contact_name": "text",
                               "contact_phone": "text", "status": "text", "matched_service": "text",
                               "service_id": "fk", "service_contact": "text", "assigned_unit": "text",
                               "admin_note": "text", "history": "json", "created_at": "ts"}},
    "activities": {"key": "id", "order": "created_at NULLS FIRST, id",
                   "cols": {"id": "text", "username": "fk", "activity_name": "text", "description": "text",
                            "category": "text", "start_date": "date", "end_date": "date", "location": "text",
                            "max_capacity": "int", "registration_deadline": "date", "status": "text",
                            "created_at": "ts"}},
    "registrations": {"key": "id", "order": "registered_at, id",
                      "cols": {"id": "text", "activity_id": "text", "username": "text", "email": "text",
                               "phone": "text", "status": "text", "registered_at": "ts"}},
    "attendances": {"key": "id", "order": "check_in_time, id",
                    "cols": {"id": "text", "activity_id": "text", "username": "text", "check_in_time": "ts",
                             "check_out_time": "ts", "created_at": "ts"}},
    "welfare": {"key": "id", "order": "id",
                "cols": {"id": "int", "title": "text", "category": "text", "agency": "text",
                         "eligibility": "text", "benefit": "text", "apply_method": "text", "contact": "text",
                         "source_url": "text", "updated_at": "date", "updated_by": "fk"}},
    "announcements": {"key": "id", "order": "created_at NULLS FIRST, id",
                      "cols": {"id": "text", "title": "text", "content": "text", "priority": "text",
                               "status": "text", "author": "fk", "created_at": "ts"}},
    "contents": {"key": "id", "order": "created_at NULLS FIRST, id",
                 "cols": {"id": "text", "title": "text", "category": "text", "content": "text",
                          "image_url": "text", "author": "fk", "status": "text", "created_at": "ts"}},
}

# ------------------------------------------------------------------ 連線池
_pool: "queue.LifoQueue" = queue.LifoQueue(maxsize=8)


def _acquire():
    while True:
        try:
            conn = _pool.get_nowait()
        except queue.Empty:
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(SCHEMA)))
            conn.commit()
            return conn
        if not conn.closed:
            return conn


def _release(conn, ok=True):
    if conn.closed:
        return
    if not ok:
        try:
            conn.rollback()
        except DatabaseError:  # 連線已中斷：直接丟棄，下次重新連線
            conn.close()
            return
    try:
        _pool.put_nowait(conn)
    except queue.Full:
        conn.close()


# ------------------------------------------------------------------ 型態轉換
def _to_db(kind, value):
    if kind == "json":
        return Json(value if value is not None else [])
    if value in (None, ""):
        return None if kind in ("date", "ts", "int", "fk") else value
    if kind == "int":
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
    if kind == "date":
        try:
            return datetime.date.fromisoformat(str(value)[:10])
        except ValueError:
            return None
    if kind == "ts":
        text = str(value).replace("T", " ").replace(" UTC", "")[:19]
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                return datetime.datetime.strptime(text, fmt)
            except ValueError:
                pass
        return None
    return value


def _from_db(kind, value):
    if value is None:
        return [] if kind == "json" else (0 if kind == "int" else "")
    if kind == "date":
        return value.isoformat()
    if kind == "ts":
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return value


# ------------------------------------------------------------------ 讀寫
def load(table):
    spec = TABLES[table]
    cols = list(spec["cols"])
    conn = _acquire()
    ok = False
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql.SQL("SELECT {} FROM {} ORDER BY " + spec["order"]).format(
                sql.SQL(", ").join(map(sql.Identifier, cols)), sql.Identifier(table)))
            rows = cur.fetchall()
        conn.commit()
        ok = True
    finally:
        _release(conn, ok)
    result = [{c: _from_db(spec["cols"][c], r[c]) for c in cols} for r in rows]
    if table == "users":
        result = [{"username": r["username"], "password": r["password"], "role": r["role"],
                   "profile": {f: r[f] for f in PROFILE_FIELDS}} for r in result]
    return result


def save(table, rows):
    spec = TABLES[table]
    cols = list(spec["cols"])
    key = spec["key"]
    if table == "users":
        rows = [{"username": u["username"], "password": u["password"], "role": u.get("role", "user"),
                 **{f: (u.get("profile") or {}).get(f, "") for f in PROFILE_FIELDS}} for u in rows]
    upsert = sql.SQL("INSERT INTO {t} ({c}) VALUES ({v}) ON CONFLICT ({k}) DO UPDATE SET {u}").format(
        t=sql.Identifier(table), c=sql.SQL(", ").join(map(sql.Identifier, cols)),
        v=sql.SQL(", ").join(sql.Placeholder() * len(cols)), k=sql.Identifier(key),
        u=sql.SQL(", ").join(sql.SQL("{0} = EXCLUDED.{0}").format(sql.Identifier(c)) for c in cols if c != key))
    keys = [_to_db(spec["cols"][key], r.get(key)) for r in rows]
    conn = _acquire()
    ok = False
    try:
        with conn.cursor() as cur:
            for r in rows:
                cur.execute(upsert, [_to_db(spec["cols"][c], r.get(c)) for c in cols])
            if keys:
                cur.execute(sql.SQL("DELETE FROM {} WHERE NOT ({} = ANY(%s))").format(
                    sql.Identifier(table), sql.Identifier(key)), (keys,))
            else:
                cur.execute(sql.SQL("DELETE FROM {}").format(sql.Identifier(table)))
        conn.commit()
        ok = True
    finally:
        _release(conn, ok)
