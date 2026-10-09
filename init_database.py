"""
初始化 PostgreSQL 資料庫表結構
執行方式: python init_database.py

資料表建立於 DB_SCHEMA 環境變數指定之 schema（預設 elder），
不會影響資料庫中其他 schema 的既有資料表。
"""

import os
import sys
from db_config import get_db_connection
from psycopg2 import OperationalError, sql

SCHEMA = os.getenv("DB_SCHEMA", "elder")

TABLES = [
    # 1. 使用者表（里民與里辦公處管理者）
    """
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username VARCHAR(50) UNIQUE NOT NULL,
        password VARCHAR(64) NOT NULL,
        role VARCHAR(10) NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin')),
        contact_name VARCHAR(50),
        relation VARCHAR(20),
        phone VARCHAR(30),
        email VARCHAR(100),
        elder_name VARCHAR(50),
        age_group VARCHAR(20),
        district VARCHAR(20),
        address VARCHAR(200),
        household_status VARCHAR(20),
        care_level VARCHAR(20),
        care_notes TEXT,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    # 2. 服務資源表
    """
    CREATE TABLE IF NOT EXISTS services (
        id VARCHAR(64) PRIMARY KEY,
        username VARCHAR(50) REFERENCES users(username) ON DELETE SET NULL ON UPDATE CASCADE,
        service_name VARCHAR(100) NOT NULL,
        service_type VARCHAR(20) NOT NULL,
        description TEXT,
        target_group VARCHAR(100),
        contact VARCHAR(100),
        status VARCHAR(10) NOT NULL DEFAULT '開放申請' CHECK (status IN ('開放申請', '額滿', '停止申請')),
        district VARCHAR(20),
        service_scope VARCHAR(10) NOT NULL DEFAULT '全區',
        created_at TIMESTAMP
    )
    """,
    # 3. 長者需求表
    """
    CREATE TABLE IF NOT EXISTS help_requests (
        id VARCHAR(64) PRIMARY KEY,
        username VARCHAR(50) NOT NULL REFERENCES users(username) ON DELETE CASCADE ON UPDATE CASCADE,
        elder_name VARCHAR(50),
        age_group VARCHAR(20),
        district VARCHAR(20) NOT NULL,
        urgency VARCHAR(10) NOT NULL DEFAULT '一般',
        household_status VARCHAR(20),
        care_level VARCHAR(20),
        need_type VARCHAR(20) NOT NULL,
        need_when VARCHAR(100) NOT NULL,
        location VARCHAR(200) NOT NULL,
        duration VARCHAR(50),
        details TEXT,
        contact_name VARCHAR(50),
        contact_phone VARCHAR(30),
        status VARCHAR(10) NOT NULL DEFAULT '待處理'
            CHECK (status IN ('待處理', '已申請', '處理中', '已安排', '已完成')),
        matched_service VARCHAR(100),
        service_id VARCHAR(64) REFERENCES services(id) ON DELETE SET NULL,
        service_contact VARCHAR(100),
        assigned_unit VARCHAR(100),
        admin_note TEXT,
        history JSONB NOT NULL DEFAULT '[]',
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    # 4. 活動表
    """
    CREATE TABLE IF NOT EXISTS activities (
        id VARCHAR(64) PRIMARY KEY,
        username VARCHAR(50) REFERENCES users(username) ON DELETE SET NULL ON UPDATE CASCADE,
        activity_name VARCHAR(100) NOT NULL,
        description TEXT,
        category VARCHAR(20),
        start_date DATE,
        end_date DATE,
        location VARCHAR(200),
        max_capacity INTEGER NOT NULL DEFAULT 0 CHECK (max_capacity >= 0),
        registration_deadline DATE,
        status VARCHAR(10) NOT NULL DEFAULT '進行中' CHECK (status IN ('進行中', '已結束', '已取消')),
        created_at TIMESTAMP
    )
    """,
    # 5. 活動報名表
    """
    CREATE TABLE IF NOT EXISTS registrations (
        id VARCHAR(64) PRIMARY KEY,
        activity_id VARCHAR(64) NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
        username VARCHAR(50) NOT NULL REFERENCES users(username) ON DELETE CASCADE ON UPDATE CASCADE,
        email VARCHAR(100),
        phone VARCHAR(30),
        status VARCHAR(10) NOT NULL DEFAULT '待審核' CHECK (status IN ('待審核', '已通過', '已拒絕')),
        registered_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (activity_id, username)
    )
    """,
    # 6. 活動簽到表（僅限已通過報名之里民簽到，username 參照使用者）
    """
    CREATE TABLE IF NOT EXISTS attendances (
        id VARCHAR(64) PRIMARY KEY,
        activity_id VARCHAR(64) NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
        username VARCHAR(50) NOT NULL REFERENCES users(username) ON DELETE CASCADE ON UPDATE CASCADE,
        check_in_time TIMESTAMP NOT NULL,
        check_out_time TIMESTAMP,
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (activity_id, username)
    )
    """,
    # 7. 福利資訊表
    """
    CREATE TABLE IF NOT EXISTS welfare (
        id INTEGER PRIMARY KEY,
        title VARCHAR(100) NOT NULL,
        category VARCHAR(20),
        agency VARCHAR(100),
        eligibility TEXT NOT NULL,
        benefit TEXT,
        apply_method TEXT NOT NULL,
        contact VARCHAR(100),
        source_url VARCHAR(300),
        updated_at DATE,
        updated_by VARCHAR(50) REFERENCES users(username) ON DELETE SET NULL ON UPDATE CASCADE
    )
    """,
    # 8. 公告表
    """
    CREATE TABLE IF NOT EXISTS announcements (
        id VARCHAR(64) PRIMARY KEY,
        title VARCHAR(200) NOT NULL,
        content TEXT,
        priority VARCHAR(10) NOT NULL DEFAULT '普通',
        status VARCHAR(10) NOT NULL DEFAULT '已發佈',
        author VARCHAR(50) REFERENCES users(username) ON DELETE SET NULL ON UPDATE CASCADE,
        created_at TIMESTAMP
    )
    """,
    # 9. 網頁內容表
    """
    CREATE TABLE IF NOT EXISTS contents (
        id VARCHAR(64) PRIMARY KEY,
        title VARCHAR(200) NOT NULL,
        category VARCHAR(20),
        content TEXT,
        image_url VARCHAR(300),
        author VARCHAR(50) REFERENCES users(username) ON DELETE SET NULL ON UPDATE CASCADE,
        status VARCHAR(10) NOT NULL DEFAULT '已發佈',
        created_at TIMESTAMP
    )
    """,
]

# 既有資料庫升級：補上記錄建立者／維護者之外鍵（新建資料庫已於上方定義，重複執行不影響）
# (資料表, 欄位)：參照 users(username)，帳號刪除時設為 NULL；原本對應不到帳號之值先改為 NULL
CREATOR_FKS = [("services", "username"), ("activities", "username"), ("welfare", "updated_by"),
               ("announcements", "author"), ("contents", "author")]

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_help_requests_username ON help_requests(username)",
    "CREATE INDEX IF NOT EXISTS idx_help_requests_status ON help_requests(status)",
    "CREATE INDEX IF NOT EXISTS idx_services_type_status ON services(service_type, status)",
    "CREATE INDEX IF NOT EXISTS idx_registrations_activity ON registrations(activity_id)",
    "CREATE INDEX IF NOT EXISTS idx_attendances_activity ON attendances(activity_id)",
    "CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)",
]


def init_database(schema=SCHEMA):
    """建立 schema 與所有資料表（已存在者略過）。"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema)))
        cursor.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
        for ddl in TABLES:
            cursor.execute(ddl)
        for table, col in CREATOR_FKS:
            name = f"{table}_{col}_fkey"
            cursor.execute(sql.SQL("ALTER TABLE {} ADD COLUMN IF NOT EXISTS {} VARCHAR(50)").format(
                sql.Identifier(table), sql.Identifier(col)))
            cursor.execute("SELECT 1 FROM pg_constraint c JOIN pg_namespace n ON n.oid = c.connamespace "
                           "WHERE n.nspname = %s AND c.conname = %s", (schema, name))
            if cursor.fetchone() is None:
                cursor.execute(sql.SQL("UPDATE {t} SET {c} = NULL WHERE {c} IS NOT NULL AND {c} NOT IN "
                                       "(SELECT username FROM users)").format(t=sql.Identifier(table), c=sql.Identifier(col)))
                cursor.execute(sql.SQL("ALTER TABLE {t} ADD CONSTRAINT {n} FOREIGN KEY ({c}) REFERENCES users(username) "
                                       "ON DELETE SET NULL ON UPDATE CASCADE").format(
                    t=sql.Identifier(table), n=sql.Identifier(name), c=sql.Identifier(col)))
        # 既有資料庫升級：活動簽到改為參照使用者（簽到者須為已報名之里民）
        cursor.execute("SELECT 1 FROM pg_constraint c JOIN pg_namespace n ON n.oid = c.connamespace "
                       "WHERE n.nspname = %s AND c.conname = 'attendances_username_fkey'", (schema,))
        if cursor.fetchone() is None:
            cursor.execute("ALTER TABLE attendances ADD CONSTRAINT attendances_username_fkey FOREIGN KEY (username) "
                           "REFERENCES users(username) ON DELETE CASCADE ON UPDATE CASCADE")
        for ddl in INDEXES:
            cursor.execute(ddl)
        conn.commit()
        cursor.close()
        conn.close()
        print(f"[完成] 已於 schema「{schema}」建立 {len(TABLES)} 張資料表與 {len(INDEXES)} 個索引")
    except OperationalError as e:
        print(f"[錯誤] 資料庫連線失敗: {e}")
        sys.exit(1)


if __name__ == "__main__":
    init_database()
