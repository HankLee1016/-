# 企劃書生成 - 檔案快速參考

## 🎯 核心檔案位置 Map

### 前端層次
```
templates/
├─ _proposal_builder.html          ⭐ 核心表單（4 步驟）
│  ├─ Step 1: 機構資料 (行 24-73)
│  ├─ Step 2: 補助與經費 (行 74-111)
│  ├─ Step 3: 計畫內容與時程 (行 112-161)
│  ├─ Step 4: 生成與提交 (行 162-204)
│  ├─ generateBtn.onclick → submitApplication() (行 593-615)
│  ├─ exportProposalDoc() (行 522)
│  ├─ exportProposalPdf() (行 529)
│  └─ gantt preview (行 405-483)
│
├─ user.html                       ← 嵌入 _proposal_builder.html (行 105)
│  └─ user_applications.html (查詢申請狀態)
│
├─ subsidy_application.html         ← 嵌入 _proposal_builder.html (行 21)
│  └─ 補助專案的企劃書生成器
│
├─ admin_applications.html          ← 管理員審核介面
│  ├─ 批准按鈕 → /admin/applications/<id>/approve
│  └─ 拒絕按鈕 → /admin/applications/<id>/reject
│
└─ case_workflow.html               ← 個案工作流時間軸
   └─ GET /cases/<case_id>/workflow-data
```

### 後端層次
```
app.py
├─ 應用程序管理
│  ├─ load_applications() (行 162)
│  ├─ create_application() (行 176)  ⭐ 保存應用程序
│  ├─ get_user_applications() (行 206)
│  ├─ update_application_status() (行 210)
│  └─ get_application() (行 199)
│
├─ 企劃書生成
│  ├─ @app.route('/api/generate-proposal', POST) (行 1163) ⭐ 主 API
│  │  └─ 處理流程
│  │     ├─ 驗證必填欄位
│  │     ├─ 解析 JSON (budget_items, timeline_items)
│  │     ├─ choose_ai_agent() (行 577)
│  │     ├─ generate_case_proposal() (行 702) ⭐ 內容生成
│  │     ├─ 組合預算表 HTML (行 1204)
│  │     ├─ 組合甘特圖 HTML (行 1215)
│  │     └─ 返回 {status, html_content, template_filename}
│  │
│  ├─ generate_case_proposal(title, bg, issues, goals, agent) (行 702)
│  │  ├─ request_openai_proposal() (行 605) [虛擬模式]
│  │  └─ 組合 7 個標準段落
│  │
│  └─ request_openai_proposal(title, bg, issues, goals) (行 605)
│     └─ 返回虛擬企劃書模板
│
├─ AI 代理系統
│  ├─ choose_ai_agent(background, issues) (行 577)
│  └─ AI_AGENTS 清單 (行 589-599)
│
└─ 審核路由
   ├─ @app.route('/user/application/submit', POST) (行 1025)
   ├─ @app.route('/user/applications') (行 1056)
   ├─ @app.route('/admin/applications') (行 1063)
   ├─ @app.route('/admin/applications/<id>/approve', POST) (行 1070)
   └─ @app.route('/admin/applications/<id>/reject', POST) (行 1078)

features.py
├─ WorkflowManager
│  ├─ update_case_status() (行 570)       ← 更新個案狀態
│  └─ get_case_history() (行 585)         ← 取得變更日誌
│
└─ (其他管理器: Stats, Notification, Search, File, Backup, Permission)
```

### 資料層次
```
JSON 檔案:
├─ applications.json                ⭐ 應用程序存儲
│  └─ [{id, username, case_title, background, proposal, status, admin_note, created_at, ...}]
│
├─ cases.json
│  └─ [{id, case_name, member_name, issue_description, status, ...}]
│
└─ (users.json, subsidies.json, ...)

PostgreSQL:
├─ case_logs                        ← WorkflowManager 寫入
│  └─ {case_id, action, description, changed_by, created_at}
│
└─ (cases, users, registrations, ...)
```

---

## 🔄 資料流向圖

### 从表單提交到企劃書生成

```
_proposal_builder.html 表單
    ↓ (enctype="multipart/form-data")
submitApplication()
    ↓
fetch('POST /api/generate-proposal', FormData)
    ↓
app.py: api_generate_proposal()
    ├─ 驗證 (project_name, background)
    ├─ 解析 JSON (budget_items, timeline_items)
    ├─ 選擇 AI 代理 → choose_ai_agent()
    ├─ 生成內容 → generate_case_proposal()
    ├─ 組合預算表 (預算項目 → HTML <table>)
    ├─ 組合甘特圖 (時程項目 → 月尺度表格)
    └─ 反回 JSON {status: "success", html_content, ...}
    ↓
前端 resultBlock.hidden = false
    ├─ proposalPreview.innerHTML = result.html_content
    ├─ 顯示匯出按鈕 (DOC, PDF, 複製表格)
    └─ 用戶可複製/下載
```

### 從提交到審核

```
用戶點擊「提交申請」
    ↓
/user/application/submit (POST)
    ├─ 提取表單數據 (case_title, background, proposal, ...)
    ├─ create_application() 
    │  └─ 寫入 applications.json {status: "pending"}
    └─ 重導至 /user/applications
    ↓
管理員訪問 /admin/applications
    ├─ 查詢 applications.json (status="pending")
    ├─ 顯示列表表格
    └─ 按鈕: 批准 | 拒絕
    ↓
管理員選擇 [批准]
    ├─ POST /admin/applications/<id>/approve
    ├─ update_application_status(id, "approved")
    ├─ 更新 applications.json
    └─ 寫入 WorkflowManager 日誌
    ↓
用戶再次訪問 /user/applications
    └─ 看到 status="已批准"
```

---

## 📝 表單欄位速查

### Step 1 - 機構基本資料
| 欄位 ID | 類型 | 必填 | 備註 |
|---------|------|------|------|
| org_name | text | ✓ | 機構名稱 |
| org_type | select | — | 下拉：財團/協會/NPO/等 |
| project_name | text | ✓ | 計畫名稱 → 用於企劃書標題 |
| target_people | text | — | 服務對象 |
| template_outline | textarea | — | 公版架構提示 |
| template_file | file | — | 上傳政府格式範本 |

### Step 2 - 補助與經費
| 欄位 ID | 類型 | 必填 | 備註 |
|---------|------|------|------|
| subsidy_source | text | — | 補助來源 |
| subsidy_category | text | — | 補助大類 |
| subsidy_program | text | — | 補助方案名稱 |
| budget | number | — | 申請總金額 |
| budget_items_json | hidden | — | 經費列表 (JSON) |
| budget_key | hidden | — | 版本控制 |

**預算項目結構**：
```json
[
  {"name": "人事費", "note": "督導工資", "amount": 200000},
  {"name": "辦理費", "note": "活動物資", "amount": 100000}
]
```

### Step 3 - 計畫內容與時程
| 欄位 ID | 類型 | 必填 | 備註 |
|---------|------|------|------|
| background | textarea | ✓ | 計畫背景 → 用於企劃書內容 |
| goals | textarea | — | 計畫目標 |
| activities | textarea | — | 執行策略 |
| expected_benefit | text | — | 預期效益 |
| milestones | text | — | 里程碑 |
| start_date | date | — | 計畫起日 |
| end_date | date | — | 計畫迄日 |
| timeline_json | hidden | — | 時程列表 (JSON) |

**時程項目結構**：
```json
[
  {
    "title": "前期準備",
    "owner": "社工督導",
    "start_date": "2026-06-01",
    "end_date": "2026-06-15",
    "progress": 60
  }
]
```

### Step 4 - 生成與提交
無特殊欄位，顯示摘要並生成企劃書

---

## ⚙️ 後端函數快速參考

### 資料庫操作
```python
# 應用程序
load_applications()                          # → List[dict]
create_application(username, case_title, ...) # → dict (新應用)
get_user_applications(username)              # → List[dict]
get_application(application_id)              # → dict
update_application_status(app_id, status)    # → dict (更新後)

# 個案
create_case(case_name, ...)                 # → dict
load_cases()                                # → List[dict]
save_cases(cases)                           # → None
```

### 生成邏輯
```python
choose_ai_agent(background, issues)         # → {name, description}
generate_case_proposal(title, bg, issues, goals, agent) # → str (企劃文本)
request_openai_proposal(title, bg, issues, goals)       # → str (虛擬內容)
api_generate_proposal()                     # 路由處理函數

# 輔助
polish_text(text)                          # 文本清理
choose_ai_response_template(label, content) # 範本相應
```

### 工作流
```python
WorkflowManager.update_case_status(case_id, status, user, desc) # 更新狀態
WorkflowManager.get_case_history(case_id)                       # 查詢日誌
```

---

## 🌐 前端 JavaScript 函數速查

### 表單控制
```javascript
goStep(n)                          // 切換到第 n 步 (1-4)
submitApplication()                // 提交生成請求 → /api/generate-proposal
validateStep(n)                    // 驗證第 n 步欄位
updateReview()                     // 更新步驟 4 摘要

// 經費項目
addBudgetItem()                    // 添加預算行
updateBudgetItem(idx, key, val)   // 更新預算項
removeBudgetItem(idx)              // 刪除預算行
renderBudgetEditor()               // 重繪預算表

// 時程項目
addTimelineItem()                  // 添加時程行
updateTimelineItem(idx, key, val) // 更新時程項
removeTimelineItem(idx)            // 刪除時程行
renderTimelineEditor()             // 重繪時程表
buildGanttPreview()                // 生成甘特預覽
```

### 匯出與複製
```javascript
buildExportDocumentHtml()          // 組合 HTML
exportProposalDoc()                // 匯出 .doc
exportProposalPdf()                // 開啟列印
copyResultTable(selector, label)   // 複製表格到剪貼板
```

---

## 📊 API 端點速查表

### 企劃書生成
| 端點 | 方法 | 請求 | 回應 |
|------|------|------|------|
| `/api/generate-proposal` | POST | FormData (org_name, ..., timeline_json) | {status, html_content, template_filename, gantt_included} |

### 應用程序管理
| 端點 | 方法 | 請求 | 回應 |
|------|------|------|------|
| `/user/application/submit` | POST | case_title, background, proposal, ... | 302 → /user/applications |
| `/user/applications` | GET | — | user_applications.html 頁面 |
| `/admin/applications` | GET | — | admin_applications.html 頁面 |
| `/admin/applications/<id>/approve` | POST | admin_note | 302 → /admin/applications |
| `/admin/applications/<id>/reject` | POST | admin_note | 302 → /admin/applications |

### 個案工作流
| 端點 | 方法 | 回應 |
|------|------|------|
| `/cases/<id>/workflow` | GET | case_workflow.html 頁面 |
| `/cases/<id>/workflow-data` | GET | {case, history} (JSON) |

---

## 🔑 重要常數與配置

```python
# app.py
APPLICATIONS_FILE = "applications.json"
AI_MODEL_NAME = "GPT-4"
AI_MODEL_ENGINE = "OpenAI"

# 應用程序狀態
STATUS = ["pending", "approved", "rejected"]

# AI 代理數量
AI_AGENTS_COUNT = 3

# 預算項目欄位
BUDGET_FIELDS = ["name", "note", "amount"]

# 時程項目欄位
TIMELINE_FIELDS = ["title", "owner", "start_date", "end_date", "progress"]

# 甘特圖配置
MAX_TIMELINE_MONTHS = 24  # 最大 24 個月
MIN_TIMELINE_MONTHS = 6
```

---

## 测试檢查清單

- [ ] 完成 Step 1 表單
- [ ] 完成 Step 2 預算 (添加至少 1 項)
- [ ] 完成 Step 3 時程 (添加至少 1 項)
- [ ] 點擊「開始生成」
- [ ] 查看企劃書預覽
- [ ] 點擊「匯出 DOC」
- [ ] 登出，用管理員帳號登入
- [ ] 訪問 `/admin/applications`
- [ ] 點擊「批准」
- [ ] 登回用戶帳號，訪問 `/user/applications`
- [ ] 確認狀態更新為「已批准」

