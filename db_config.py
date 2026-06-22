"""資料庫連線設定。

這個模組只負責一件事：根據環境變數建立 PostgreSQL 連線。
爬蟲與其他腳本都應該透過這裡取得連線，而不要把帳密硬寫在程式碼裡。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None

import psycopg2
from psycopg2 import OperationalError


# 讀取同層級 .env，方便本機開發與 Supabase 設定切換
_ENV_PATH = Path(__file__).parent / ".env"
if load_dotenv and _ENV_PATH.exists():
    load_dotenv(_ENV_PATH)

_ENV_LOCAL_PATH = Path(__file__).parent / ".env.local"
# 只有在 .env 不存在時，才使用 .env.local 作為本機預設（避免占位值覆蓋真實設定）
if load_dotenv and (not _ENV_PATH.exists()) and _ENV_LOCAL_PATH.exists():
    load_dotenv(_ENV_LOCAL_PATH)


def _build_dsn_from_env() -> Optional[str]:
    """優先支援連線字串（Supabase / Heroku 常見）。"""
    database_url = os.getenv("DATABASE_URL") or os.getenv("DB_URL")
    if database_url and database_url.strip():
        return database_url.strip()
    return None


def _connect_error_hint(host: str, port: str, dbname: str, user: str, exc: Exception) -> str:
    msg = str(exc)
    if "Connection refused" in msg or "could not connect to server" in msg:
        return (
            f"❌ 無法連上 PostgreSQL（{host}:{port}）。看起來伺服器未啟動或未監聽該連接埠。\n"
            f"- DB={dbname} USER={user}\n"
            "- 請先確認 PostgreSQL 服務已啟動，或把 .env 改成正確的遠端/Supabase 連線。\n"
        )
    if "password authentication failed" in msg:
        return (
            "❌ 帳號密碼驗證失敗。\n"
            f"- DB={dbname} USER={user}\n"
            "- 請檢查 .env 的 DB_USER / DB_PASSWORD（或 DATABASE_URL）。\n"
        )
    return f"❌ 資料庫連線失敗：{exc}\n"


def get_db_connection():
    """建立並回傳 PostgreSQL 連線。

    回傳值:
        psycopg2.connection: 已連線的資料庫連線物件。

    環境變數:
        DB_HOST: 資料庫主機位址
        DB_PORT: 資料庫連接埠
        DB_USER: 使用者名稱
        DB_PASSWORD: 密碼
        DB_NAME: 目標資料庫名稱
    """
    dsn = _build_dsn_from_env()
    if dsn:
        try:
            return psycopg2.connect(dsn)
        except OperationalError as exc:
            raise OperationalError(f"❌ 以 DATABASE_URL/DB_URL 連線失敗：{exc}") from exc

    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "postgres")
    dbname = os.getenv("DB_NAME", "volunteer_db")
    sslmode = os.getenv("DB_SSLMODE")

    try:
        return psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            dbname=dbname,
            sslmode=sslmode if sslmode else None,
        )
    except OperationalError as exc:
        raise OperationalError(_connect_error_hint(host, port, dbname, user, exc)) from exc
