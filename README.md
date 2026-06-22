# 專案說明

這個專案目前包含兩個主要部分：

1. 一個 Flask 網站後台，負責資料展示、功能模組與管理操作。
2. 一個 Python 爬蟲 `crawler.py`，負責抓取家扶基金會捐款資料並寫入 PostgreSQL / Supabase。

## 主要檔案

- `app.py`：Flask 主程式，網站入口。
- `routes_features.py`：額外功能路由。
- `features.py`：功能模組集合，例如報表、通知、搜尋、權限等。
- `crawler.py`：家扶捐款資料爬蟲。
- `db_config.py`：資料庫連線設定。
- `create_database.py`：建立資料庫。
- `init_database.py`：建立資料表。
- `.env.example`：環境變數範本。

## 本機啟動步驟

### 1. 建立虛擬環境

```bash
python -m venv .venv
.venv\Scripts\activate
```

### 2. 安裝套件

```bash
pip install requests psycopg2-binary python-dotenv flask werkzeug
```

如果專案還有其他相依套件，請依 `app.py` 與 `features.py` 實際 import 的模組補裝。

### 3. 建立 `.env`

先複製 `.env.example` 為 `.env`，並填入正確資料庫資訊。

### 4. 建立資料庫

```bash
python create_database.py
```

### 5. 建立資料表

```bash
python init_database.py
```

### 6. 執行爬蟲

```bash
python crawler.py
```

### 7. 啟動 Flask 網站

```bash
python app.py
```

## 爬蟲 API 行為說明

爬蟲目前使用：

- `https://donate.ccf.org.tw/donation/`
- `https://donate.ccf.org.tw/donation/ajax/ajax_check_month.php`
- `https://donate.ccf.org.tw/donation/ajax/ajax_get_funds_list.php`

為了提高成功率，`crawler.py` 已加入：

- `requests.Session()` 保存 Cookie
- 初始 `GET` 頁面拿 Cookie
- 完整 `Headers`
- 使用 `data=` 送出表單型 POST

## 資料庫欄位

`crawler.py` 會寫入 `donations` 表，欄位包含：

- `id`
- `donor`
- `funds_no`
- `amount`
- `donation_date`
- `note`
- `category`
- `unit_data_id`
- `show_flag`
- `last_user`
- `last_date`
- `build_date`

## 備註

如果你目前抓不到資料，最常見原因是：

1. 只用單次 `requests.post()`，沒有保存 Cookie。
2. 缺少 `Referer` 或 AJAX 標頭。
3. 沒有先 GET 主頁，導致伺服器沒有發初始 Session。
4. `year` / `month` / `category` 參數與網站實際邏輯不一致。

如果網站未來再調整驗證流程，可以再進一步加上更完整的瀏覽器行為模擬。
