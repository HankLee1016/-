# 專案說明

「長者安心服務平台」是以 Flask 開發的里民長者關懷服務網站：里內長者與家屬可線上提出生活需求、查看服務媒合與申請進度、報名里民活動、查詢長者福利並詢問 AI 福利小幫手；里辦公處則於後台受理需求、管理在地服務資源、活動、公告、福利資訊，並使用 AI 企劃書產生器撰寫社區計畫企劃書。

## 主要檔案

- `app.py`：Flask 主程式，網站入口。
- `db_store.py`：資料存取層，負責讀寫 PostgreSQL 資料表。
- `migrate_json_to_db.py`：將 JSON 範例資料匯入資料庫。
- `*.json`：初始範例資料（匯入資料庫用）。
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
pip install flask werkzeug openai psycopg2-binary python-dotenv
```

如需使用 AI 功能，另需安裝 `openai` 套件並設定 `OPENAI_API_KEY`。

### 3. 建立 `.env`

先複製 `.env.example` 為 `.env`，並填入正確資料庫資訊。

### 4. 建立資料庫

```bash
python create_database.py
```

### 5. 建立資料表並匯入資料

```bash
python init_database.py
python migrate_json_to_db.py
```

`init_database.py` 會在 `elder` schema 建立 9 張資料表；`migrate_json_to_db.py` 將專案中的 JSON 範例資料（使用者、服務資源、活動、福利資訊等）匯入資料庫，只需執行一次。

### 6. 啟動 Flask 網站

```bash
python app.py
```

## 環境變數（選用）

- `OPENAI_API_KEY`：設定後，AI 福利小幫手與企劃書產生器會使用 OpenAI；未設定時改用內建規則回覆與範本。
- `ADMIN_REG_CODE`：註冊管理者帳號所需的驗證代碼。

## 測試

```bash
python -m unittest tests.test_system -v
```

測試在獨立的 `elder_test` schema 中進行，結束後自動刪除，不影響正式資料。
