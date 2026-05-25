# 企劃書生成功能分析報告
**生成日期**: 2026年5月25日  
**詳細程度**: Medium

---

## 📋 概述

該平台已實現了完整的**企劃書生成與審核工作流**，包括：
- ✅ AI 輔助的多步驟表單生成器
- ✅ 自動 HTML 預覽與甘特圖
- ✅ DOC/PDF 匯出功能
- ✅ 管理員審核與批准工作流
- ✅ 政府公版範本支持

---

## 🎯 1. 企劃書生成功能代碼位置

### 前端實現

| 檔案 | 位置 | 功能 |
|------|------|------|
| **_proposal_builder.html** | `templates/_proposal_builder.html` | 核心生成表單（4步驟） |
| **四步表單流程** | 行 1–350 | UI 架構與表單欄位 |
| **AI 生成按鈕** | 行 164 | 「AI 生成企劃書」 |
| **生成函數** | 行 593–615 | `submitApplication()` → POST `/api/generate-proposal` |
| **匯出功能** | 行 522–540 | `exportProposalDoc()` / `exportProposalPdf()` |
| **甘特圖生成** | 行 405–483 | 時程動態計算與展示 |

### 後端實現

| 函數 | 位置 | 功能 |
|------|------|------|
| **api_generate_proposal()** | `app.py` 行 1163–1260 | API 主端點 |
| **generate_case_proposal()** | `app.py` 行 702–755 | 企劃書內容生成 |
| **request_openai_proposal()** | `app.py` 行 605–681 | 虛擬 AI 回應 |
| **choose_ai_agent()** | `app.py` 行 594–599 | AI 代理選擇 |
| **create_application()** | `app.py` 行 176–197 | 保存應用程序 |

---

## 🔄 2. 四步表單工作流

### 步驟1：機構基本資料 (Step 1)
表單欄位（`_proposal_builder.html` 行 24–73）：
```
- org_name              → 機構名稱
- org_type              → 機構類型（下拉選項）
- project_name          → 計畫名稱
- target_people         → 服務對象
- template_outline      → 公版企劃章節架構提示
- template_file         → 上傳政府格式範本（.html/.txt/.md/.pdf）
```

### 步驟2：補助與經費規劃 (Step 2)
表單欄位（行 74–111）：
```
- subsidy_source        → 補助來源（衛生福利部、基金會等）
- subsidy_category      → 補助大類（社會救助、社區發展等）
- subsidy_program       → 補助方案名稱
- budget                → 申請總金額（數字，新台幣）
- budget_items_json     → 經費項目列表（JSON）
  └─ item 結構：
    {name, note, amount}
```

**經費項目編輯器**：
- 函數：`addBudgetItem()` 添加行項
- 函數：`updateBudgetItem(idx, key, val)` 更新內容
- 表格生成：後端自動轉成 HTML `<table>` (行 1204–1214)

### 步驟3：計畫內容與時程 (Step 3)
表單欄位（行 112–161）：
```
- background            → 計畫背景與問題描述
- goals                 → 計畫目標
- activities            → 主要活動/執行策略
- expected_benefit      → 預期效益
- milestones            → 整體重要里程碑
- start_date            → 計畫起日（日期欄）
- end_date              → 計畫迄日（日期欄）
- timeline_items_json   → 分項時程列表（JSON）
  └─ item 結構：
    {title, owner, start_date, end_date, progress}
```

**時程項目編輯器**（`_proposal_builder.html` 行 355–395）：
- 甘特圖實時預覽（行 399–450）
- 月尺度時間軸（支持 18 個月）
- 進度表示：已完成、進行中、未開始

### 步驟4：生成與提交 (Step 4)
表單欄位（行 162–204）：
```
- 摘要卡片（自動從前3步填充）
- 生成按鈕 → submitApplication() 
  └─ 發送 POST /api/generate-proposal
  └─ 等待結果
  └─ 顯示預覽
```

**匯出選項**（行 205–220）：
- 匯出 DOC
- 匯出 PDF（使用 print window）
- 複製甘特圖表格
- 複製預算表格

---

## 🔌 3. 後端 API 端點與資料流

### POST `/api/generate-proposal`

**請求資料** (FormData)：
```javascript
{
  // Step 1
  org_name: "○○社會福利基金會",
  org_type: "財團法人基金會",
  project_name: "弱勢家庭支持計畫",
  target_people: "低收家庭",
  template_file: File,          // 可選 (政府公版)
  
  // Step 2
  subsidy_source: "衛生福利部",
  subsidy_category: "社會救助",
  subsidy_program: "弱勢家庭支持方案",
  budget: 800000,
  budget_items_json: "[{name:'人事費', note:'督導', amount:200000}, ...]",
  budget_key: "budget_v1",      // 隱藏欄位
  
  // Step 3
  background: "服務缺口分析...",
  goals: "服務 50 位長者...",
  activities: "訪視、課程...",
  expected_benefit: "提升參與率",
  milestones: "招募、執行、評估",
  start_date: "2026-06-01",
  end_date: "2026-12-31",
  timeline_json: "[{title:'前期準備', owner:'社工', start_date:'2026-06-01', end_date:'2026-06-15', progress:60}, ...]"
}
```

**處理流程** (app.py 行 1163–1260)：
```python
1. 驗證必填欄位 (project_name, background)
2. 解析 JSON (budget_items, timeline_items)
3. 選擇 AI 代理 → choose_ai_agent(background, issues)
4. 調用 generate_case_proposal() → 生成企劃文本
5. 組合預算表 HTML (1204–1214)
6. 組合甘特圖 HTML (1215–1250)
7. 返回 JSON:
   {
     "status": "success",
     "html_content": "<div>企劃書 HTML</div>",
     "template_filename": "template.html" (如有上傳)
     "gantt_included": true
   }
```

**回應結構**：
```json
{
  "status": "success",
  "html_content": "<h4>預算表...</h4><table>...</table>",
  "template_filename": "government_template_v1.html",
  "gantt_included": true
}
```

---

## 📊 4. 審核系統與工作流

### 現有審核系統

**應用程序狀態轉移**：
```
pending (待審核)
  ↓
  ├─→ approved (已批准) [管理員按鈕批准]
  └─→ rejected (已拒絕) [管理員按鈕拒絕]
```

### 審核工作流程

#### 4.1 提交階段（用戶端）

**路由** (app.py 行 1025–1055)：
- **POST** `/user/application/submit`
- **GET** `/user/applications` (查看自己申請)

**提交數據結構**：
```python
create_application(
    username=session.username,
    case_title=request.form.get("case_title"),
    background=request.form.get("background"),
    issues=request.form.get("issues"),
    goals=request.form.get("goals"),
    proposal=request.form.get("proposal"),  # AI 生成的企劃書
    subsidy_summary="",
    success_pdf=None,
    subsidy_pdf=None
    # status 預設為 "pending"
)
```

**模板** (templates/user_applications.html)：
- 表格顯示用戶所有申請
- 狀態：待審核 / 已批准 / 已拒絕
- 顯示管理員備註

#### 4.2 審核階段（管理員端）

**路由** (app.py 行 1063–1088)：
- **GET** `/admin/applications` (查看全部待審核列表)
- **POST** `/admin/applications/<id>/approve` (批准)
- **POST** `/admin/applications/<id>/reject` (拒絕)

**模板** (templates/admin_applications.html)：
```html
<table>
  <tr>
    <td>申請時間</td>
    <td>使用者</td>
    <td>案名</td>
    <td>狀態</td>
    <td>
      <button onclick="批准">批准</button>
      <button onclick="拒絕">拒絕</button>
    </td>
  </tr>
</table>
```

**數據結構** (app.py 行 210–219)：
```python
def update_application_status(application_id, status, admin_note=""):
    # status ∈ {"pending", "approved", "rejected"}
    # admin_note: 管理員備註
    # 更新 applications.json
```

### 儲存位置

| 資料 | 檔案位置 | 格式 |
|------|---------|------|
| 應用程序 | `applications.json` | JSON (內存檔案) |
| 個案日誌 | PostgreSQL `case_logs` | 資料庫表 |
| 工作流日誌 | PostgreSQL `workflow_history` | 資料庫表 |

---

## 📁 5. 相關 HTML 模板檔案

| 模板 | 路徑 | 用途 |
|------|------|------|
| **企劃書生成器主體** | `templates/_proposal_builder.html` | 包含所有步驟、表單、生成邏輯 |
| **使用者頁面** | `templates/user.html` (行 105) | 嵌入 _proposal_builder.html |
| **補助申請頁面** | `templates/subsidy_application.html` (行 21) | 嵌入 _proposal_builder.html |
| **用戶申請列表** | `templates/user_applications.html` | 顯示用戶自己的申請狀態 |
| **管理員審核列表** | `templates/admin_applications.html` | 管理員批准/拒絕介面 |
| **個案工作流** | `templates/case_workflow.html` | 個案同步狀態變更日誌 |

---

## 🔑 6. AI 代理與企劃書內容生成

### AI 代理選擇系統

**代理清單** (app.py 行 589–599)：
```python
[
  {"name": "社工實踐家", "description": "...實踐社會工作核心價值..."},
  {"name": "企劃師小智", "description": "...專注策略、落地執行..."},
  {"name": "計畫評估導師", "description": "...評估指標、成效測量..."}
]
```

**選擇邏輯** (app.py 行 577–602)：
```python
def choose_ai_agent(background, issues):
    # 根據背景、議題自動選擇最適合代理
    # 使用關鍵字匹配
```

### 虛擬企劃書結構

**生成函數** (app.py 行 702–755)：
```
generate_case_proposal(title, background, issues, goals, agent_name)
  ↓
  request_openai_proposal() [虛擬模式]
  ↓
  mock_proposal 返回 [7 個標準段落]
```

**企劃書標準章節**（app.py 行 607–680）：
```
壹、宗旨（計畫緣起）
貳、計劃目標
參、計畫執行期程
肆、企劃內容及實行方法
伍、預期成果與效益
陸、可能風險與因應措施
柒、建議經費概算方向
```

**每個段落包含**：
- 標準化文本範本
- 用戶提供的背景/目標內容
- 建議事項
- 備註與提示

---

## 📝 7. 主要及相關函數速查表

### 對應前端操作的後端函數

| 前端動作 | 觸發函數 | 功能 |
|---------|---------|------|
| 點擊「下一步」 | `goStep(n)` | 切換表單步驟 |
| 新增經費項目 | `addBudgetItem()` | 向預算列表添加行 |
| 新增時程項目 | `addTimelineItem()` | 向時程列表添加行 |
| 點擊「開始生成」 | `submitApplication()` | POST `/api/generate-proposal` |
| 点击「匯出 DOC」 | `exportProposalDoc()` | 生成 .doc 檔案 |
| 点击「匯出 PDF」 | `exportProposalPdf()` | 開啟列印視窗 |
| 管理員批准 | `admin_approve_application()` | POST `/admin/applications/<id>/approve` |
| 管理員拒絕 | `admin_reject_application()` | POST `/admin/applications/<id>/reject` |

### 核心後端函數

```python
# 應用程序生命週期
create_application()              # 創建新應用
get_user_applications()           # 用戶查詢自己的申請
get_application()                 # 獲取單筆申請詳情
update_application_status()       # 更新審核狀態

# 生成流程
api_generate_proposal()           # API 主端點（POST）
generate_case_proposal()          # 企劃書內容生成
request_openai_proposal()         # AI 虛擬回應
choose_ai_agent()                 # 代理選擇

# 工作流管理
WorkflowManager.update_case_status()    # 更新個案狀態
WorkflowManager.get_case_history()      # 取得變更日誌
```

---

## 📋 8. 現有系統缺口與建議

### 當前實現的功能 ✅
- ✅ 4 步驟表單設計
- ✅ 預算表自動生成  
- ✅ 甘特圖動態計算與展示
- ✅ DOC/PDF 匯出
- ✅ 管理員批准/拒絕工作流
- ✅ 政府公版範本支持
- ✅ AI 代理選擇

### 可能需要強化的功能 ⚠️
1. **審核流程完整性**
   - 目前狀態只有 3 種 (pending → approved/rejected)
   - 未來可追加：draft → review → approved/rejected → implemented
   
2. **草稿保存**
   - 目前只支持「待審核」狀態直接提交
   - 可考慮添加「草稿」狀態供用戶中途編輯

3. **動態表單驗證**
   - 目前只驗證 `project_name` 和 `background`
   - 可強化：日期範圍、預算上限、欄位相依性

4. **甘特圖交互**
   - 目前為靜態展示
   - 可考慮：拖放調整、進度進行中更新

5. **審核意見回覆**
   - 目前 admin_note 為單向
   - 可考慮：二次修改、往返溝通

---

## 📦 9. 需要創建或修改的文件清單

### 立即可實現的改進

#### Level 1: 增強現有功能（低風險）

1. **`features.py`** - 強化 WorkflowManager
   - [ ] 新增 `get_application_with_history()` - 取得申請完整日誌
   - [ ] 新增 `add_approval_workflow_log()` - 記錄審核日誌

2. **`app.py`** - 擴展審核路由
   - [ ] 新增 `/api/applications/<id>` - 返回申請詳情（JSON）
   - [ ] 新增 `/api/applications` - 列表 API（便於前端統計）

3. **`templates/_proposal_builder.html`**
   - [ ] 添加「保存草稿」按鈕 → 新狀態 "draft"
   - [ ] 添加欄位必填驗證提示

#### Level 2: 新增工作流功能（中等複雜）

4. **`templates/admin_applications.html`**
   - [ ] 添加「審核意見」文本區（允許詳細反饋）
   - [ ] 分頁顯示（支援大量申請）
   - [ ] 篩選功能（按狀態、日期、使用者）

5. **`app.py` - 新增路由**
   - [ ] `POST /admin/applications/<id>/request-revision` - 要求修改
   - [ ] `POST /admin/applications/<id>/add-comment` - 添加審核意見

#### Level 3: 完整功能擴展（高複雜度）

6. **`database/` - 審核歷史表**
   - [ ] 建立 `approval_history` 表（記錄每次審核）
   - [ ] 新增欄位：reviewer_id, review_date, decision, feedback

7. **前端交互增強**
   - [ ] 甘特圖拖放編輯
   - [ ] 實時預覽更新
   - [ ] 草稿自動保存

---

## 🎯 10. 快速開始 - 測試流程

### 測試企劃書生成

1. **訪問表單**  
   ```
   http://localhost:5000/user
   ```

2. **填填表單**  
   - 機構名稱：○○社會福利基金會
   - 計畫名稱：弱勢家庭支持計畫
   - 背景：服務 50 位低收家庭...
   - 時程：2026-06-01 至 2026-12-31

3. **生成企劃書**  
   點擊「開始生成」→ 等待 AI 回應 → 看預覽

4. **測試審核流程**  
   - 管理員訪問：`/admin/applications`
   - 點擊「批准」或「拒絕」
   - 用戶重新訪問 `/user/applications` 檢查狀態

---

## 📞 附錄：API 端點完整列表

| 端點 | 方法 | 認證 | 功能說明 |
|------|------|------|---------|
| `/api/generate-proposal` | POST | user | 生成企劃書 HTML |
| `/user/application/submit` | POST | user | 提交應用程序至待審核 |
| `/user/applications` | GET | user | 查詢自己的申請列表 |
| `/admin/applications` | GET | admin | 查詢所有待審核申請 |
| `/admin/applications/<id>/approve` | POST | admin | 批准應用程序 |
| `/admin/applications/<id>/reject` | POST | admin | 拒絕應用程序 |
| `/cases/<case_id>/workflow` | GET | user | 查看個案工作流 |
| `/cases/<case_id>/workflow-data` | GET | — | 返回個案狀態 JSON |

---

## 💾 總結

當前系統已實現了**完整的企劃書生成與基礎審核工作流**。建議優先實現以下改進以提升用戶體驗：

1. **添加草稿保存** - 允許用戶保存未完成的企劃書
2. **強化審核意見** - 支持管理員詳細反饋與修改要求
3. **完善驗證** - 增加表單欄位驗證和提示
4. **日誌追蹤** - 記錄完整的審核歷史時間軸

