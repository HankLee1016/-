## 專案簡介
這個專案使用 Python 爬蟲抓取家扶基金會捐款資料，並將資料存入 PostgreSQL (Supabase) 資料庫中。  

爬蟲功能：
- 按年份抓取每個月份有資料的捐款紀錄
- 支援分頁抓取
- 將資料存入 `donations` 表格
- 透過 `execute_values` 高效率批次存入資料庫

## 資料庫設定（Supabase）

本專案使用 Supabase 的 PostgreSQL 作為資料庫。  
組員可以使用自己 Supabase 帳號，或依照以下方式建立連線設定：

1. 在專案資料夾建立 `config_py.py` 檔案
2. 範例內容如下（請用自己的 Supabase 專案資訊替換）：

```python
import psycopg2
from psycopg2.extras import Json

def get_db_connection():
    return psycopg2.connect(
        host="你的Supabase host",   # 例如 aws-1-ap-northeast-2.pooler.supabase.com
        port=5432,
        user="你的使用者名稱",     # 例如 postgres.xxxxx
        password="你的密碼",       # Supabase DB 密碼
        dbname="postgres"
    )


先利用了家扶基金會的網站嘗試用爬蟲抓取數據，爬蟲的檔案以及資料庫連接檔案為：crawler.py, db_config.py

##目前程式狀態 / 問題
抓取不到資料
使用的 API：
年月檢查：https://donate.ccf.org.tw/donation/ajax/ajax_check_month.php
捐款清單：https://donate.ccf.org.tw/donation/ajax/ajax_get_funds_list.php

對應 POST 資料：

year=2026
month=2
category=1
page=1
limit=30

執行程式後，印出：

2026 無資料月份
2025 無資料月份
2024 無資料月份
2023 無資料月份
抓取完成，總筆數：0
也就是說，即使網站上 2026-2 有資料，程式仍抓不到任何資料。

推測原因：網站需要特定的 Session / Cookie 才能返回資料（到時候可根據我們使用的網站做修改，程式大致是沒有問題，不會報錯，只是提取不到資料

目前我所使用的資料庫為Supabase網站上可用的，建立了可存儲捐贈人 時間 金額 用途等備註問題
No newline at end of file