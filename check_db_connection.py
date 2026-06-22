"""快速檢查 PostgreSQL 連線與 donations 表。

執行方式：
    python check_db_connection.py
"""

from __future__ import annotations

from db_config import get_db_connection


def main() -> None:
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        try:
            cur.execute("select 1")
            print("✅ 連線成功：select 1 =", cur.fetchone()[0])

            cur.execute("select to_regclass('public.donations')")
            regclass = cur.fetchone()[0]
            if regclass:
                print("✅ 表存在：donations")
            else:
                print("⚠️  找不到 donations 表：請先執行 python init_database.py")
        finally:
            cur.close()
    finally:
        conn.close()


if __name__ == "__main__":
    main()

