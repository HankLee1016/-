"""將原本的 JSON 資料檔匯入 PostgreSQL（只需執行一次）。

執行方式: python migrate_json_to_db.py
會先建立資料表（init_database），再依參照順序匯入資料；
參照不存在之資料（例如報名對應的活動已刪除）會略過並列出。
"""
import json
from pathlib import Path

import db_store
from init_database import init_database

ROOT = Path(__file__).parent


def read(name):
    p = ROOT / f"{name}.json"
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8")).get(name, [])


def known_creator(rows, field, names):
    """建立者／維護者帳號對應不到使用者時（如舊資料之 "admin"）改為空值，以符合外鍵限制。"""
    for r in rows:
        if r.get(field) not in names:
            r[field] = ""
    return rows


def main():
    init_database(db_store.SCHEMA)
    skipped = []

    users = [{"username": u["username"], "password": u["password"], "role": u.get("role", "user"),
              "profile": u.get("profile") or {}} for u in read("users")]
    db_store.save("users", users)
    names = {u["username"] for u in users}

    services = known_creator(read("services"), "username", names)
    db_store.save("services", services)
    service_ids = {s["id"] for s in services}

    db_store.save("welfare", known_creator(read("welfare"), "updated_by", names))

    activities = known_creator(read("activities"), "username", names)
    db_store.save("activities", activities)
    activity_ids = {a["id"] for a in activities}

    regs, seen = [], set()
    for r in read("registrations"):
        key = (r.get("activity_id"), r.get("username"))
        if r.get("activity_id") not in activity_ids or r.get("username") not in names or key in seen:
            skipped.append(("registrations", r.get("id")))
            continue
        seen.add(key)
        regs.append(r)
    db_store.save("registrations", regs)

    atts, seen = [], set()
    for a in read("attendances"):
        key = (a.get("activity_id"), a.get("username"))
        if a.get("activity_id") not in activity_ids or a.get("username") not in names or key in seen:
            skipped.append(("attendances", a.get("id")))
            continue
        seen.add(key)
        atts.append(a)
    db_store.save("attendances", atts)

    reqs = []
    for r in read("help_requests"):
        if r.get("username") not in names:
            skipped.append(("help_requests", r.get("id")))
            continue
        if r.get("service_id") not in service_ids:
            r["service_id"] = ""
        reqs.append(r)
    db_store.save("help_requests", reqs)

    db_store.save("announcements", known_creator(read("announcements"), "author", names))
    db_store.save("contents", known_creator(read("contents"), "author", names))

    for t in db_store.TABLES:
        print(f"  {t:<15} {len(db_store.load(t))} 筆")
    if skipped:
        print("略過（參照之資料不存在或重複）：", skipped)


if __name__ == "__main__":
    main()
