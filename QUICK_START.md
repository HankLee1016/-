# 🚀 快速開始指南

## 系統需求
- Python 3.8+
- PostgreSQL 12+
- Flask
- psycopg2

## 安装和啟動

### 1️⃣ 初始化資料庫
```bash
cd c:\Users\88691\-
python init_database.py
```

### 2️⃣ 啟動應用
```bash
python app.py
```

應用程式將在 `http://localhost:5000` 上運行

## 🔐 登入

使用管理員賬戶登入以訪問所有新功能：
```
用戶名: admin
密碼: [根據您的系統設置]
```

## 📍 功能路由

### 分析與報告
- 📊 **分析儀表板**: `http://localhost:5000/analytics/dashboard`
- 📋 **報告列表**: `http://localhost:5000/analytics/reports`
- 📄 **報告詳情**: `http://localhost:5000/analytics/reports/<report_id>`

### 通知與溝通
- 🔔 **通知中心**: `http://localhost:5000/notifications`
- 📣 **標記為已讀**: API POST `/api/notifications/<id>/read`

### 搜尋與篩選
- 🔍 **搜尋個案**: `http://localhost:5000/search/cases`
- 🔍 **搜尋活動**: `http://localhost:5000/search/activities`

### 工作流管理
- 📝 **個案工作流**: `http://localhost:5000/cases/<case_id>/workflow`
- 🔄 **更新狀態**: API POST `/api/cases/<case_id>/status`

### 系統管理
- 💾 **備份管理**: `http://localhost:5000/admin/backups`
- 🔐 **權限管理**: `http://localhost:5000/admin/permissions`

### 管理儀表板
- 🎛️ **管理面板**: `http://localhost:5000/admin`

## 🧪 測試各功能

### 1. 測試分析儀表板
1. 訪問 `/analytics/dashboard`
2. 查看實時統計
3. 點擊「生成報告」按鈕
4. 查看報告列表中的新報告

### 2. 測試通知系統
1. 訪問 `/notifications`
2. 查看所有通知
3. 標記通知為已讀
4. 刪除通知

### 3. 測試搜尋功能
1. 訪問 `/search/cases`
2. 輸入搜尋條件
3. 點擊「搜尋」按鈕
4. 過濾結果

### 4. 測試工作流
1. 訪問 `/cases/<case_id>/workflow`
2. 查看個案詳情和歷史
3. 更新個案狀態
4. 查看更新日誌

### 5. 測試備份管理
1. 訪問 `/admin/backups`
2. 點擊「建立備份」按鈕
3. 查看備份列表
4. 下載或還原備份

### 6. 測試權限管理
1. 訪問 `/admin/permissions`
2. 選擇用戶
3. 授予或撤銷權限
4. 查看權限更新

## 📊 數據庫表

### 新增表格
- `reports` - 生成的報告
- `notifications` - 系統通知
- `backups` - 資料備份
- `user_permissions` - 用戶權限
- `files` - 上傳的檔案
- `system_logs` - 系統日誌
- `case_logs` - 個案變更歷史

### 修改的表格
- `users` - 用於權限查詢
- `cases` - 用於工作流追蹤

## 🎨 CSS 樣式文件

所有新樣式都組織在 4 個文件中：
- `static/css/admin-forms.css` - 表單元素
- `static/css/status-badges.css` - 狀態指示器
- `static/css/admin-pages.css` - 頁面卡片
- `static/css/pages.css` - 通用樣式

## 🛠️ 故障排除

### 問題：資料庫連接失敗
**解決方案**:
- 確認 PostgreSQL 正在運行
- 檢查 `db_config.py` 中的連接參數
- 驗證資料庫存在並可訪問

### 問題：缺少模塊錯誤
**解決方案**:
```bash
pip install flask psycopg2-binary
```

### 問題：藍圖未註冊
**解決方案**:
- 確認 `routes_features.py` 在 `app.py` 中導入
- 確認 blueprint 在創建 Flask app 後註冊

### 問題：範本未找到
**解決方案**:
- 確認所有 HTML 文件在 `templates/` 目錄中
- 檢查文件名拼寫

## 📝 日誌

### 應用日誌位置
- `logs/` 目錄（如果配置）
- 控制台輸出

### 數據庫日誌
- 系統操作記錄在 `system_logs` 表中
- 個案變更記錄在 `case_logs` 表中

## 🔒 安全檢查清單

- ✅ 所有管理路由都有 `role` 檢查
- ✅ 所有 API 都有會話驗證
- ✅ 所有數據庫查詢都使用參數化
- ✅ 檔案上傳使用 `secure_filename`
- ✅ 敏感操作需要確認

## 📞 支援

遇到問題？檢查：
1. `IMPLEMENTATION_SUMMARY.md` - 完整功能列表
2. 代碼註釋 - 每個函數都有文檔
3. 錯誤日誌 - 檢查控制台輸出
4. 資料庫日誌 - 檢查 `system_logs` 表

## ✨ 下一步

1. **自定義不同組織的權限**
2. **設置自動每日備份**
3. **配置電郵通知**
4. **查看並分析系統日誌**
5. **建立自定義報告**

---

**提示**: 在生產環境中，確保：
- 更改所有默認密碼
- 啟用 HTTPS
- 設置定期備份
- 監控系統日誌
- 配置防火牆規則

祝賀🎉 您的社福平台現在具有完整的企業級功能！
