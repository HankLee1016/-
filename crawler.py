"""家扶基金會捐款資料爬蟲。

功能：
1. 先進入捐款查詢頁面，取得網站核發的初始 Cookie。
2. 使用同一個 requests.Session 送出後續 AJAX 請求。
3. 逐年、逐月、逐頁抓取捐款清單。
4. 將抓到的資料批次寫入 PostgreSQL 的 donations 表。

欄位與 init_database / app.py 一致：donor、amount、note。
API 格式對應網站 /19/donation-funds/ 頁面目前使用的 ajax 介面。
"""

from __future__ import annotations

import time
import os
from typing import Any, Dict, Iterable, List

import requests
from psycopg2.extras import execute_values

from db_config import get_db_connection


BASE_URL = "https://donate.ccf.org.tw"
DONATION_PAGE_URL = f"{BASE_URL}/19/donation-funds/"
CHECK_MONTH_URL = f"{BASE_URL}/donation/ajax/ajax_check_month.php"
GET_FUNDS_LIST_URL = f"{BASE_URL}/donation/ajax/ajax_get_funds_list.php"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "X-Requested-With": "XMLHttpRequest",
    "Origin": BASE_URL,
    "Referer": DONATION_PAGE_URL,
    "Connection": "keep-alive",
}

YEARS = ["2026", "2025", "2024", "2023"]
CATEGORY = "1"  # 1=收入, 2=支出
PAGE_SIZE = 30
REQUEST_TIMEOUT = 30
MAX_PAGES_PER_MONTH = int(os.getenv("CRAWLER_MAX_PAGES_PER_MONTH", "0") or 0)  # 0=不限制
MAX_MONTHS_PER_YEAR = int(os.getenv("CRAWLER_MAX_MONTHS_PER_YEAR", "0") or 0)  # 0=不限制


def create_session() -> requests.Session:
    """建立已預設好 Headers 的 Session。"""
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    return session


def warm_up_session(session: requests.Session) -> None:
    """先訪問捐款查詢頁，讓伺服器發放初始 Cookie。"""
    session.get(DONATION_PAGE_URL, timeout=REQUEST_TIMEOUT)


def post_form(session: requests.Session, url: str, payload: Dict[str, str]) -> Dict[str, Any]:
    """送出表單型 POST 並回傳 JSON。"""
    response = session.post(url, data=payload, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.json()


def get_available_years_and_months(session: requests.Session, probe_year: str) -> tuple[List[str], List[str]]:
    """取得目前介面可查詢的年/月清單。

    注意：網站的 `ajax_check_month.php` 回傳的是「可選擇的年/月」，不一定代表該月有資料。
    """
    payload = {
        "donationType": "funds",
        "type": CATEGORY,
        "year": str(probe_year),
        "changeType": "2",
        "unit_data_id": "1",
    }
    data = post_form(session, CHECK_MONTH_URL, payload)

    years_raw = data.get("years", [])
    months_raw = data.get("months", [])

    years: List[str] = [str(y) for y in years_raw] if isinstance(years_raw, list) else []
    months: List[str] = [str(m) for m in months_raw] if isinstance(months_raw, list) else []
    return years, months


def get_funds_page(session: requests.Session, year: str, month: str, page: int) -> Dict[str, Any]:
    """取得某年某月某頁的捐款清單。"""
    payload = {
        "act": "list",
        "page": str(page),
        "data_rows": str(PAGE_SIZE),
        "search_param[category]": CATEGORY,
        "search_param[search-year]": str(year),
        "search_param[search-month]": str(month),
    }
    return post_form(session, GET_FUNDS_LIST_URL, payload)


def normalize_donation_row(row: Dict[str, Any]) -> tuple:
    """把單筆 API 資料轉成 donations 表可寫入的 tuple。"""
    donation_date = row.get("Donation_Date")
    if donation_date and " " in str(donation_date):
        donation_date = str(donation_date).split(" ", 1)[0]

    return (
        int(row["ID"]),
        row.get("Name"),
        row.get("Funds_No"),
        str(row.get("Money", "0")).replace(",", ""),
        donation_date,
        row.get("Content"),
        int(row.get("Category", 0) or 0),
        int(row.get("Unit_Data_ID", 0) or 0),
        int(row.get("Show_Flag", 0) or 0),
        int(row.get("Last_User", 0) or 0),
        row.get("Last_Date"),
        row.get("Build_Date"),
    )


def save_donations(cursor, conn, rows: Iterable[tuple]) -> int:
    """將資料批次寫入 donations 表。"""
    rows = list(rows)
    if not rows:
        return 0

    sql = """
        INSERT INTO donations (
            id, donor, funds_no, amount, donation_date, note,
            category, unit_data_id, show_flag, last_user, last_date, build_date
        )
        VALUES %s
        ON CONFLICT (id) DO NOTHING
    """
    execute_values(cursor, sql, rows)
    conn.commit()
    return len(rows)


def main() -> None:
    """爬蟲主流程。"""
    session = create_session()
    warm_up_session(session)

    total_count = 0
    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        probe_year = YEARS[0] if YEARS else "2025"
        try:
            years, months = get_available_years_and_months(session, probe_year)
        except Exception as exc:
            print(f"取得可查詢年/月失敗：{exc}")
            years, months = YEARS, [str(m) for m in range(1, 13)]

        years_to_fetch = years or YEARS
        months_to_fetch = months or [str(m) for m in range(1, 13)]

        for year in years_to_fetch:
            for month_idx, month in enumerate(months_to_fetch, start=1):
                if MAX_MONTHS_PER_YEAR > 0 and month_idx > MAX_MONTHS_PER_YEAR:
                    break
                page = 1
                while True:
                    try:
                        data_json = get_funds_page(session, year, month, page)
                    except Exception as exc:
                        print(f"{year}-{month} 第 {page} 頁抓取失敗：{exc}")
                        break

                    data_list = data_json.get("Data", [])
                    if not data_list:
                        if page == 1:
                            print(f"{year}-{month} 無資料")
                        break

                    rows = [normalize_donation_row(row) for row in data_list]
                    written = save_donations(cursor, conn, rows)
                    total_count += written
                    print(f"{year}-{month} 第 {page} 頁：抓到 {len(data_list)} 筆，寫入 {written} 筆")

                    total_page = int(data_json.get("Total_Page", 0) or 0)
                    if total_page <= 0 or page >= total_page:
                        break
                    if MAX_PAGES_PER_MONTH > 0 and page >= MAX_PAGES_PER_MONTH:
                        print(f"{year}-{month} 已達頁數上限（CRAWLER_MAX_PAGES_PER_MONTH={MAX_PAGES_PER_MONTH}），停止該月")
                        break
                    page += 1
                    time.sleep(0.5)

        print(f"抓取完成，總筆數：{total_count}")

    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    main()
