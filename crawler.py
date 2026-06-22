import requests
from psycopg2.extras import execute_values
import time

# 假設你已有 conn, cursor
# from config_py import conn, cursor

session = requests.Session()
headers = {
    "X-Requested-With": "XMLHttpRequest",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Origin": "https://donate.ccf.org.tw",
    "Referer": "https://donate.ccf.org.tw/94/donation-funds/"
}

# 先 GET 主頁取得 cookie
session.get("https://donate.ccf.org.tw/94/donation-funds/", headers=headers)

years = ["2026", "2025", "2024", "2023"]
category = "1"  # 收入

total_count = 0

for year in years:
    # -------------------- 取得有資料的月份 --------------------
    check_month_url = "https://donate.ccf.org.tw/donation/ajax/ajax_check_month.php"
    try:
        resp_month = session.post(check_month_url, data={"year": year}, headers=headers)
        months_data = resp_month.json()
        months = months_data.get("months", [])
    except Exception as e:
        print(f"解析月份失敗 {year}, 錯誤：{e}")
        print(resp_month.text)
        continue

    if not months:
        print(f"{year} 無資料月份")
        continue

    for month in months:
        page = 1
        while True:
            get_funds_url = "https://donate.ccf.org.tw/donation/ajax/ajax_get_funds_list.php"
            payload = {
                "year": str(year),
                "month": str(month),
                "category": category,
                "page": str(page),
                "limit": "30"
            }
            try:
                resp = session.post(get_funds_url, data=payload, headers=headers)
                data_json = resp.json()
            except Exception as e:
                print(f"JSON 解析失敗 {year}-{month}, page {page}, 錯誤：{e}")
                print(resp.text)
                break

            data_list = data_json.get("Data", [])
            if not data_list:
                print(f"{year}-{month}, page {page} 無資料")
                break

            # -------------------- 印出資料檢查 --------------------
            for d in data_list:
                print(d)
            total_count += len(data_list)

            # -------------------- 存入 PostgreSQL --------------------
            sql = """
            INSERT INTO donations (id, name, funds_no, money, donation_date, content, category, unit_data_id, show_flag, last_user, last_date, build_date)
            VALUES %s
            ON CONFLICT (id) DO NOTHING
            """
            values = []
            for d in data_list:
                values.append((
                    int(d["ID"]),
                    d["Name"],
                    d["Funds_No"],
                    d["Money"].replace(",", ""),
                    d["Donation_Date"],
                    d["Content"],
                    int(d["Category"]),
                    int(d["Unit_Data_ID"]),
                    int(d["Show_Flag"]),
                    int(d["Last_User"]),
                    d["Last_Date"],
                    d["Build_Date"]
                ))
            execute_values(cursor, sql, values)
            conn.commit()

            # 分頁
            if page >= int(data_json.get("Total_Page", 0)):
                break
            page += 1
            time.sleep(0.5)  # 避免過快請求

print(f"抓取完成，總筆數：{total_count}")