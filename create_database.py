import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

try:
    import psycopg2
    from psycopg2 import OperationalError
except ImportError:
    print("❌ 尚未安裝 psycopg2，請執行：pip install psycopg2-binary")
    sys.exit(1)


def load_env():
    env_file = Path(__file__).parent / ".env"
    if load_dotenv and env_file.exists():
        load_dotenv(env_file)


def get_db_settings():
    return {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": os.getenv("DB_PORT", "5432"),
        "database": os.getenv("DB_ADMIN_DB", "postgres"),
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD", "postgres"),
        "target_db": os.getenv("DB_NAME", "volunteer_db"),
    }


def create_database():
    load_env()
    settings = get_db_settings()

    try:
        conn = psycopg2.connect(
            host=settings["host"],
            port=settings["port"],
            database=settings["database"],
            user=settings["user"],
            password=settings["password"],
        )
        conn.autocommit = True
        cursor = conn.cursor()

        cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (settings["target_db"],))
        exists = cursor.fetchone() is not None
        if exists:
            print(f"✓ 資料庫 {settings['target_db']} 已存在")
        else:
            cursor.execute(f"CREATE DATABASE \"{settings['target_db']}\"")
            print(f"✅ 已建立資料庫: {settings['target_db']}")

        cursor.close()
        conn.close()

    except OperationalError as e:
        print("❌ 無法連線至 PostgreSQL 伺服器")
        print(f"錯誤：{e}")
        print("請確認 PostgreSQL 已啟動，並檢查 .env 或環境變數中的連線設定。")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 建立資料庫失敗：{e}")
        sys.exit(1)


if __name__ == "__main__":
    create_database()
