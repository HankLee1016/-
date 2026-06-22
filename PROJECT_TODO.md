# ABCDE 系統 — 專題補全與優化待辦清單

> 依據 `專題系統文件 最新.docx`、`專題系統手冊 一二張 終.docx` 與 `--main` 程式現況整理。  
> 建議由上而下依序執行；完成一項請將 `[ ]` 改為 `[x]`。

**目前綜合進度（估算）**：文件 ~55%｜一般功能 ~65%｜核心技術 ~15%｜資料庫 ~89%

---

## 階段 0：環境與基礎建設（先做）

- [ ] **0-1** 初始化 Git 倉庫，建立 `.gitignore`（排除 `.env`、`.venv`、`__pycache__`、`uploads/*`）
- [ ] **0-2** 建立 `requirements.txt`，鎖定 Flask、psycopg2-binary、python-dotenv、requests、openai 等依賴
- [ ] **0-3** 確認 `.env` 設定正確（`DATABASE_URL`、`OPENAI_API_KEY`、`SECRET_KEY`）
- [ ] **0-4** 執行 `python create_database.py` + `python init_database.py`，確認 17 張表可正常建立
- [ ] **0-5** 撰寫 `DEPLOY.md` 或補充 `README.md`：本機啟動、資料庫、爬蟲、常見錯誤排除

---

## 階段 1：專題核心技術（最高優先 — 文件與程式落差最大）

### 1-A 真實 AI 串接（取代虛擬模式）

> 本段優先目標：把企劃生成器從「可展示」提升為「可送件」等級。  
> 重點不是只接上模型，而是要讓輸出內容更正式、穩定、可重複生成，並符合補助申請文件的結構與語氣。

- [x] **1-A-1** 移除 `app.py` 中 `openai_client = None` 強制禁用，改為依 `.env` 的 `OPENAI_API_KEY` 啟用
- [x] **1-A-2** 建立穩定的 `request_openai_proposal()` 流程：統一輸入、固定輸出格式、錯誤處理、逾時與 fallback 機制
- [x] **1-A-3** 重整 `generate_chat_response()`，讓對話結果可作為企劃補強依據，而不是只做一般聊天回覆
- [ ] **1-A-4** 將企劃生成 prompt 改寫為正式送件版：明確分段產出「計畫緣起、執行目標、服務對象、執行方式、預期效益、經費概算、風險與因應」
- [x] **1-A-5** 加入固定格式約束：標題層級一致、段落語氣正式、數據與名詞前後一致、避免重複與口語化內容
- [ ] **1-A-6** 強化生成穩定性：加入輸出檢核、內容補齊規則、最小字數門檻與空值保護，避免產生破碎草稿
- [ ] **1-A-7** 驗證非功能需求：AI 回應時間控制在 15 秒內（文件要求）
- [ ] **1-A-8** 保留「開發/demo 模式」開關（如 `AI_MOCK_MODE=true`），方便無 API Key 時演示

### 1-B RAG 知識庫（文件核心亮點，目前 0%）

- [ ] **1-B-1** 選定技術方案（建議：LangChain + Chroma 或 pgvector；文件提及 LangChain）
- [ ] **1-B-2** 建立 `rag/` 模組：`ingest.py`（匯入 PDF/HTML）、`retriever.py`（檢索）、`pipeline.py`（RAG 問答）
- [ ] **1-B-3** 補助簡章匯入流程：上傳 PDF → 分段 → embedding → 寫入向量庫
- [ ] **1-B-4** 企劃生成時先 RAG 檢索相關補助條文，再餵給 LLM（降低幻覺）
- [ ] **1-B-5** 對話助理整合 RAG：依使用者選定補助方案檢索對應簡章
- [ ] **1-B-6** 管理員介面：知識庫文件列表、重新索引、刪除過期文件

### 1-C 補助資訊爬蟲（對齊文件「資訊端」目標）

- [ ] **1-C-1** 釐清爬蟲範圍：衛福部、原民會、各縣市社會局（文件要求）vs 現有家扶捐款爬蟲
- [ ] **1-C-2** 新建 `subsidy_crawler.py`（或擴充 `crawler.py`），抓取政府補助公告
- [ ] **1-C-3** 設計 `subsidies` 資料表（或遷移現有 `subsidies.json` 至 PostgreSQL）
- [ ] **1-C-4** 定時任務或手動觸發：管理員一鍵更新補助資料
- [ ] **1-C-5** `/subsidies` 頁面改為讀取資料庫，支援分類、關鍵字、截止日期排序
- [ ] **1-C-6** 保留家扶捐款爬蟲為獨立模組（`donations` 表），與補助爬蟲分開命名

---

## 階段 2：資料層補全與一致性

- [ ] **2-1** 新增 T19 `service_applications` 表（文件有、程式缺）
- [ ] **2-2** 將 `applications.json` 補助申請遷移至 PostgreSQL `applications` 或專用表
- [ ] **2-3** 將 `subsidies.json` 遷移至資料庫（若 1-C 完成）
- [ ] **2-4** 統一 JSON 種子資料與 DB：users、cases、activities 等改為以 DB 為主、JSON 僅作初始化
- [ ] **2-5** 補齊 `users` 表欄位與 `profile` 表單同步（org_name、member_count、volunteer_count 等）
- [ ] **2-6** 企劃書 PDF 上傳路徑與 `files` 表關聯（success_pdf、subsidy_pdf）

---

## 階段 3：文件需求功能對齊（程序規格書逐項驗收）

| 編號 | 功能 | 待辦 |
|------|------|------|
| F01 | 登入功能 | [ ] 登入失敗訊息、密碼雜湊、session 過期處理 |
| F02 | 編輯團體背景設定 | [ ] 確認欄位與文件一致（字號、社員人數、志工人數、負責人、登記地址） |
| F03 | 公家機關補助查詢 | [ ] 即時統計總數、類別篩選、關鍵字搜尋（依 1-C 資料來源） |
| F04 | AI 個案企劃書產生器 | [ ] 串接真實 AI + RAG；支援 PDF 參考檔上傳 |
| F05 | 下載個案企劃書 | [ ] TXT 已有；確認 DOC/PDF 匯出品質與編碼 |
| F06 | 用對話優化企劃 | [ ] 真實 AI 對話；可從草稿帶入上下文 |
| F07 | 提交補助申請 | [ ] 申請列表、狀態、管理者備註；遷移 DB 後再驗收 |
| F08 | 捐款管理 | [ ] 表單寫入 DB；與爬蟲資料整合顯示 |

---

## 階段 4：非功能需求與安全

- [ ] **4-1** 角色權限：非管理員存取 `/admin/*` 一律攔截（文件要求）
- [ ] **4-2** 錯誤回報：全域 exception handler + 寫入 `system_logs`
- [ ] **4-3** 密碼改用 bcrypt（目前若為簡易雜湊需升級）
- [ ] **4-4** 檔案上傳：限制副檔名、大小、路徑遍歷防護
- [ ] **4-5** CSRF 保護（表單 POST 路由）
- [ ] **4-6** 敏感設定不入版控（`.env.example` 提供範本）

---

## 階段 5：專題文件補全（繳交用）

- [ ] **5-1** 第九章：軟體架構與程式清單（對照實際 `app.py`、`features.py`、`routes_features.py`）
- [ ] **5-2** 第十章：測試計畫 + 測試個案與結果（可參考 `WORKFLOW_TEST_GUIDE.md` 擴寫）
- [ ] **5-3** 第十一章：操作手冊（安裝、資料庫、爬蟲、環境變數）
- [ ] **5-4** 第十二章：使用手冊（各畫面操作流程、狀態轉換說明）
- [ ] **5-5** 第五章：補功能分解圖（Functional Decomposition Diagram）
- [ ] **5-6** 第六章：補資料流程圖 DFD（爬蟲 → DB → RAG → AI → 申請）
- [ ] **5-7** 第七章～第八章：ER 圖與實際 DB 同步（含新增 T19、subsidies 表）
- [ ] **5-8** 第四章：補 GitHub 上傳紀錄截圖（完成 0-1 後）

---

## 階段 6：可優化項目（提升品質，非阻擋上線但建議做）

### 6-A 程式架構

- [ ] **6-A-1** 拆分 `app.py`（~1800 行）：`routes/auth.py`、`routes/subsidy.py`、`routes/proposal.py`、`routes/admin.py`
- [ ] **6-A-2** 統一 API 回應格式：`{ "status": "ok"|"error", "data": ..., "message": ... }`
- [ ] **6-A-3** 抽出 `services/proposal_service.py`、`services/subsidy_service.py` 業務邏輯
- [ ] **6-A-4** 新增 `config.py` 集中讀取環境變數

### 6-B 前端與 UX

- [ ] **6-B-1** `_proposal_builder.html` 表單驗證：必填欄位、日期邏輯、預算合計檢查
- [ ] **6-B-2** 企劃生成中 loading 狀態與 15 秒逾時提示
- [ ] **6-B-3** `assistant.html` 對話紀錄持久化至 DB（目前僅 session）
- [ ] **6-B-4** 補助列表 RWD / 平板友善（文件要求外訪使用）
- [ ] **6-B-5** 統一錯誤 toast / flash 訊息樣式

### 6-C 資料與效能

- [ ] **6-C-1** 補助、申請、捐款列表分頁（避免一次載入過多）
- [ ] **6-C-2** 常用查詢加 index（subsidies.deadline、applications.status 等）
- [ ] **6-C-3** 爬蟲結果去重與增量更新（避免重複寫入）

### 6-D 測試與 CI

- [ ] **6-D-1** 新增 `tests/test_auth.py`、`tests/test_proposal_api.py` 基本 pytest
- [ ] **6-D-2** 爬蟲 API 煙霧測試（已有 `_test_crawler_api.py`，可納入 pytest）
- [ ] **6-D-3** GitHub Actions：push 時跑 lint + 測試（選做）

### 6-E 與文件技術棧對齊（選做）

- [ ] **6-E-1** 文件寫 React.js，目前為 Jinja；評估是否改前端或更新文件為「Flask + Jinja」
- [ ] **6-E-2** 評估 Gemini API 作為 OpenAI 備援（文件提及）

### 6-F 範圍釐清（避免專題失焦）

- [ ] **6-F-1** 盤點「額外功能」：活動、志工、個案、七大模組 — 哪些要保留、哪些寫入文件附錄
- [ ] **6-F-2** 首頁與導覽突出專題主軸：補助查詢 → AI 企劃 → 申請（弱化次要入口或收進管理員）

---

## 建議執行順序（本週可開始）

```
週次 1：0-x 環境 → 1-A 真實 AI → F04/F06 驗收
週次 2：1-B RAG 基礎 → 1-C 補助爬蟲規劃與第一個來源
週次 3：2-x 資料遷移 → F03/F07 驗收
週次 4：4-x 安全 → 5-x 文件補齊 → 6-x 依時間擇項優化
```

---

## 快速參考：關鍵檔案

| 用途 | 路徑 |
|------|------|
| 主程式 | `app.py` |
| 企劃書 UI | `templates/_proposal_builder.html` |
| AI 對話 | `templates/assistant.html` |
| 補助列表 | `templates/subsidies.html`、`subsidies.json` |
| 家扶爬蟲 | `crawler.py` |
| 資料庫初始化 | `init_database.py` |
| 功能模組 | `features.py`、`routes_features.py` |
| 專題文件 | `專題系統文件 最新.docx`、`專題系統手冊 一二張 終.docx` |

---

## 變更紀錄

| 日期 | 說明 |
|------|------| ##待測試##
| 2026-06-17 | 初版建立，依文件與程式差距分析產出 |
| 2026-06-17 | 1-A-1 已完成：解除 OpenAI 強制禁用，啟用依環境變數控制 |
| 2026-06-17 | 1-A-2 已完成：補上正式企劃生成流程、固定章節與 fallback 機制 |
| 2026-06-20 | 1-A-3 已完成：對話回覆改為企劃補強導向並加入正式語氣處理 |
| 2026-06-20 | 1-A-4 已完成：企劃生成 prompt 已改為送件版結構 |
| 2026-06-21 | 1-A-5 已完成：加入固定格式與正式語氣約束 |
