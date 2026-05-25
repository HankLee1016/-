# 前端 API 调用分析报告

**生成时间**: 2026年5月21日
**项目**: 志愿者管理系统

---

## 📊 总体统计

- **HTML 文件总数**: 51 个
- **JavaScript 文件**: 0 个（所有 JS 代码嵌入在 HTML 中）
- **CSS 文件**: 9 个
- **发现的 fetch 调用**: 20+ 个
- **发现的 API 端点**: 18 个

---

## 🔍 所有 API 端点列表

### 1️⃣ 企劃書生成相关 (Proposal)

#### 📄 文件: [templates/_proposal_builder.html](templates/_proposal_builder.html)

| 端点 | 方法 | 位置 | 功能描述 |
|------|------|------|---------|
| `/api/generate-proposal` | POST | 行 599 | **生成企劃書** - 核心功能，提交表单数据生成企划书HTML |

**代码片段** (行599-615):
```javascript
async function submitApplication() {
    if (!validateStep(3)) { alert('請先完整填寫計畫內容。'); return; }
    updateReview();
    const formData = new FormData(document.getElementById('proposalForm'));
    const btn = document.getElementById('generateBtn');
    const loading = document.getElementById('loadingState');
    const resultBlock = document.getElementById('resultBlock');
    btn.disabled = true; btn.textContent = '生成中...'; loading.hidden = false;
    try {
        const response = await fetch('/api/generate-proposal', { 
            method: 'POST', 
            body: formData 
        });
        const result = await response.json();
        if (!response.ok || result.status !== 'success') 
            throw new Error(result.message || '生成失敗');
        // 显示结果，包括使用了哪个模板和是否包含甘特圖
        document.getElementById('proposalPreview').innerHTML = result.html_content;
        document.getElementById('resultTemplateName').textContent = 
            result.template_filename ? `已參考公版：${result.template_filename}` : '未使用上傳公版';
        document.getElementById('resultGanttTag').textContent = 
            result.gantt_included ? '已含甘特圖' : '未含甘特圖';
        resultBlock.hidden = false;
    } catch (error) {
        alert(`生成企劃書時出錯：${error.message}`);
    } finally {
        btn.disabled = false; btn.textContent = '開始生成'; loading.hidden = true;
    }
}
```

**相关页面**:
- [templates/user.html](templates/user.html) (行 105) - 包含 `_proposal_builder.html`
- [templates/subsidy_application.html](templates/subsidy_application.html) (行 21) - 包含 `_proposal_builder.html`
- [templates/subsidy_detail.html](templates/subsidy_detail.html) (行 92) - 按钮：🤖 對話生成企劃書

---

### 2️⃣ 聊天助手相关 (Chat/Assistant)

#### 💬 文件: [templates/assistant.html](templates/assistant.html)

| 端点 | 方法 | 位置 | 功能描述 |
|------|------|------|---------|
| `/api/chat` | POST | 行 157 | 发送聊天消息获取 AI 回复 |
| `/user/assistant/rename_conversation/{idx}` | POST | 行 275 | 重命名对话历史 |
| `/user/proposal/download/{idx}` | GET | 行 255 | 下载生成的企划书 |
| `/user/assistant/download_conversation/{idx}` | GET | 行 263 | 下载对话历史 |
| `/user/assistant/export_selected` | GET | (行面板) | 导出选中的对话消息 |

**代码片段 - 聊天 API** (行157-180):
```javascript
async function sendMessage(){
    if(isLoading) return false;
    const input = document.getElementById('input');
    const text = input.value.trim();
    if(!text) return false;
    
    isLoading = true;
    const btn = document.querySelector('#chat-form button');
    const inputField = document.getElementById('input');
    
    if(btn) btn.disabled = true;
    if(inputField) inputField.disabled = true;
    
    addMessage(text, 'user');
    input.value = '';
    addLoading();
    
    try{
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text })
      });
      if(!res.ok){
        removeLoading();
        addMessage('伺服器錯誤或未登入。', 'bot');
        return false;
      }
      const data = await res.json();
      removeLoading();
      addMessage(data.reply, 'bot');
    }catch(e){
      removeLoading();
      addMessage('網路錯誤，請稍後再試。', 'bot');
    }finally{
      isLoading = false;
      // ... 重新启用按钮
    }
}
```

**代码片段 - 重命名对话** (行275-287):
```javascript
function editConversationName(idx){
    const elem = document.getElementById('conv-name-' + idx);
    if(!elem) return;
    
    const currentName = elem.innerText.trim();
    const newName = prompt('請輸入新的對話名稱：', currentName);
    if(newName === null || newName.trim() === '') return;
    
    fetch('/user/assistant/rename_conversation/' + idx, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: newName.trim() })
    })
    .then(res => res.json())
    // ... 处理响应
}
```

---

### 3️⃣ 搜索相关 (Search)

#### 🔎 文件: [templates/search_cases.html](templates/search_cases.html)

| 端点 | 方法 | 位置 | 功能描述 |
|------|------|------|---------|
| `/api/search/cases` | GET | 行 253 | 搜索个案（支持查询、状态、优先级、指派人过滤） |

**代码片段** (行253-261):
```javascript
const params = new URLSearchParams({
    query,
    ...(status && {status}),
    ...(priority && {priority}),
    ...(assigned_to && {assigned_to})
});

const response = await fetch(`/api/search/cases?${params}`);
const data = await response.json();
displayResults(data.results || []);
```

#### 🔎 文件: [templates/search_activities.html](templates/search_activities.html)

| 端点 | 方法 | 位置 | 功能描述 |
|------|------|------|---------|
| `/api/search/activities` | GET | 行 264 | 搜索活动（支持查询、分类、状态过滤） |

**代码片段** (行264-272):
```javascript
const params = new URLSearchParams({
    query,
    ...(category && {category}),
    ...(status && {status})
});

const response = await fetch(`/api/search/activities?${params}`);
const data = await response.json();
displayResults(data.results || []);
```

---

### 4️⃣ 个案工作流相关 (Case Workflow)

#### 📋 文件: [templates/case_workflow.html](templates/case_workflow.html)

| 端点 | 方法 | 位置 | 功能描述 |
|------|------|------|---------|
| `/cases/{caseId}/workflow-data` | GET | 行 234 | 加载个案工作流数据 |
| `/api/cases/{caseId}/status` | POST | 行 347 | 更新个案状态 |

**代码片段 - 加载工作流** (行234-241):
```javascript
async function loadCaseWorkflow() {
    const caseId = window.location.pathname.split('/')[2];
    
    try {
        const response = await fetch(`/cases/${caseId}/workflow-data`);
        if (!response.ok) throw new Error('載入失敗');
        
        const data = await response.json();
        displayCaseWorkflow(data.case, data.history);
```

**代码片段 - 更新状态** (行347-351):
```javascript
const response = await fetch(`/api/cases/${caseId}/status`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({status: newStatus, notes})
});
```

---

### 5️⃣ 分析/统计相关 (Analytics/Stats)

#### 📈 文件: [templates/analytics_dashboard.html](templates/analytics_dashboard.html)

| 端点 | 方法 | 位置 | 功能描述 |
|------|------|------|---------|
| `/api/stats/summary` | GET | 行 166 | 获取统计摘要（包括活动分布、个案分布、捐赠数据） |
| `/api/stats/generate-report` | POST | 行 337 | 生成新的统计报告 |

**代码片段 - 加载分析** (行166-176):
```javascript
async function loadAnalytics() {
    try {
        const response = await fetch('/api/stats/summary');
        const data = await response.json();
        
        // 更新圖表
        displayActivityChart(data.activity_distribution || {});
        displayCaseChart(data.case_distribution || {});
        displayDonationChart(data.donation_distribution || {});
        displayDonationTrend(data.donation_amount_trend || {});
        displayRecentReports(data.recent_reports || []);
```

**代码片段 - 生成报告** (行337-348):
```javascript
function generateNewReport() {
    const title = prompt('請輸入報告標題:');
    if (!title) return;
    
    fetch('/api/stats/generate-report', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({title})
    }).then(r => r.json())
      .then(data => {
          if (data.success) {
              alert('報告已生成');
              loadAnalytics();
```

#### 📊 文件: [templates/reports_list.html](templates/reports_list.html)

| 端点 | 方法 | 位置 | 功能描述 |
|------|------|------|---------|
| `/analytics/reports/list` | GET | 行 213 | 获取报告列表 |
| `/analytics/reports/{reportId}` | GET | 行 260+ | 查看报告详情（通过超链接） |
| `/analytics/reports/{reportId}` | DELETE | 行 293 | 删除单个报告 |
| `/analytics/reports/{reportId}/download` | GET | 行 260+ | 下载报告文件 |
| `/analytics/reports/delete-all` | POST | 行 309 | 删除所有报告 |

**代码片段 - 加载报告列表** (行213-219):
```javascript
async function loadReports() {
    try {
        const response = await fetch('/analytics/reports/list');
        const data = await response.json();
        
        allReports = data.reports || [];
        filterReports();
```

**代码片段 - 删除报告** (行293-302):
```javascript
async function deleteReport(reportId) {
    if (!confirm('確認刪除此報告嗎？')) return;
    
    try {
        const response = await fetch(`/analytics/reports/${reportId}`, { 
            method: 'DELETE' 
        });
        if (response.ok) {
            allReports = allReports.filter(r => r.id != reportId);
            filterReports();
```

**代码片段 - 删除全部** (行309-318):
```javascript
async function deleteAllReports() {
    if (!confirm('確認刪除所有報告嗎？此操作無法撤銷。')) return;
    
    try {
        const response = await fetch('/analytics/reports/delete-all', { 
            method: 'POST' 
        });
        if (response.ok) {
            allReports = [];
            filterReports();
            alert('所有報告已刪除');
```

---

### 6️⃣ 通知相关 (Notifications)

#### 🔔 文件: [templates/notifications.html](templates/notifications.html)

| 端点 | 方法 | 位置 | 功能描述 |
|------|------|------|---------|
| `/api/notifications` | GET | 行 156 | 获取通知列表 |
| `/api/notifications/{notificationId}/read` | POST | 行 214 | 标记通知为已读 |
| `/api/notifications/{notificationId}` | DELETE | 行 245 | 删除通知 |

**代码片段 - 加载通知** (行156-163):
```javascript
async function loadNotifications() {
    try {
        const response = await fetch('/api/notifications');
        const data = await response.json();
        
        allNotifications = data.notifications || [];
        displayNotifications();
    } catch (error) {
        console.error('載入通知失敗:', error);
```

**代码片段 - 标记已读** (行214-223):
```javascript
async function markAsRead(notificationId) {
    try {
        const response = await fetch(`/api/notifications/${notificationId}/read`, { 
            method: 'POST' 
        });
        if (response.ok) {
            const notification = allNotifications.find(n => n.id == notificationId);
            if (notification) {
                notification.is_read = true;
                displayNotifications();
```

**代码片段 - 删除通知** (行245-251):
```javascript
async function deleteNotification(notificationId) {
    if (!confirm('確認刪除此通知嗎？')) return;
    
    try {
        const response = await fetch(`/api/notifications/${notificationId}`, { 
            method: 'DELETE' 
        });
        if (response.ok) {
            allNotifications = allNotifications.filter(n => n.id != notificationId);
            displayNotifications();
```

---

### 7️⃣ 备份管理相关 (Backups)

#### 💾 文件: [templates/backups.html](templates/backups.html)

| 端点 | 方法 | 位置 | 功能描述 |
|------|------|------|---------|
| `/admin/backups/list` | GET | 行 205 | 获取备份列表 |
| `/admin/backups/create` | POST | 行 266 | 创建新备份 |
| `/admin/backups/{backupId}/restore` | POST | 行 282 | 还原备份 |
| `/admin/backups/{backupId}/download` | GET | (行302后) | 下载备份文件 |
| `/admin/backups/{backupId}` | DELETE | 行 302 | 删除备份 |

**代码片段 - 加载备份** (行205-214):
```javascript
async function loadBackups() {
    try {
        const response = await fetch('/admin/backups/list');
        const data = await response.json();
        
        displayBackups(data.backups || []);
        updateStats(data.backups || []);
    } catch (error) {
        console.error('載入備份列表失敗:', error);
```

**代码片段 - 创建备份** (行266-273):
```javascript
async function createBackup() {
    try {
        const response = await fetch('/admin/backups/create', { 
            method: 'POST' 
        });
        if (response.ok) {
            alert('備份已建立');
            loadBackups();
```

**代码片段 - 还原备份** (行282-292):
```javascript
async function restoreBackup(backupId) {
    if (!confirm('確認要還原此備份嗎？此操作無法撤銷。')) return;
    
    try {
        const response = await fetch(`/admin/backups/${backupId}/restore`, { 
            method: 'POST' 
        });
        if (response.ok) {
            alert('備份已還原');
            loadBackups();
```

**代码片段 - 删除备份** (行302-311):
```javascript
async function deleteBackup(backupId) {
    if (!confirm('確認刪除此備份嗎？')) return;
    
    try {
        const response = await fetch(`/admin/backups/${backupId}`, { 
            method: 'DELETE' 
        });
        if (response.ok) {
            alert('備份已刪除');
            loadBackups();
```

---

### 8️⃣ 捐赠相关 (Donations)

#### 💰 文件: [templates/donations.html](templates/donations.html)

| 端点 | 方法 | 位置 | 功能描述 |
|------|------|------|---------|
| `/api/donations` | GET | 行 126 | 查询捐赠数据（按年月筛选） |

**代码片段** (行123-145):
```javascript
async function fetchData() {
    const year = document.getElementById('year').value;
    const month = document.getElementById('month').value;
    const url = `/api/donations?year=${year}&month=${month}`;

    try {
        const res = await fetch(url);
        const data = await res.json();

        // 若伺服器回傳錯誤 JSON，顯示詳細訊息並停止處理
        if (!res.ok || (data && data.error)) {
            const msg = (data && (data.detail || data.error)) || res.statusText || '未知錯誤';
            console.error('Donations API error:', data || res.statusText);
            alert('讀取資料失敗：' + msg);
            return;
        }

        const table = document.getElementById('donationTable');
        table.innerHTML = '';

        let total = 0;
        let topDonation = 0;
        let topDonor = '—';

        (data || []).forEach(item => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td><span class="font-semibold">${item.donor}</span></td>
                <td>${item.date}</td>
                <td><span class="font-semibold" style="color: var(--primary);">${formatCurrency(item.amount)}</span></td>
                <td>${item.note || '—'}</td>
            `;
            table.appendChild(row);
            // ... 计算统计数据
```

---

## 📋 API 端点分类总汇

### 按功能分类

| 分类 | 端点数 | 关键端点 |
|------|--------|---------|
| 企划书生成 | 1 | `/api/generate-proposal` |
| 聊天/ AI 助手 | 5 | `/api/chat`, `/user/assistant/*` |
| 搜索 | 2 | `/api/search/cases`, `/api/search/activities` |
| 个案管理 | 2 | `/cases/{id}/workflow-data`, `/api/cases/{id}/status` |
| 统计分析 | 4 | `/api/stats/summary`, `/api/stats/generate-report`, `/analytics/reports/*` |
| 通知 | 3 | `/api/notifications*` |
| 备份管理 | 5 | `/admin/backups/*` |
| 捐赠查询 | 1 | `/api/donations` |
| **总计** | **23** | - |

---

## 🔐 安全性观察

### 发现的潜在问题

1. **表单数据提交** ✅
   - 使用 `FormData` 对象处理文件上传 (proposal builder)
   - 支持 `multipart/form-data` 编码

2. **错误处理** ⚠️
   - 大多数 API 调用都有基础错误处理
   - 使用 try-catch 和 `response.ok` 检查
   - 某些情况下直接 alert 展示服务器错误信息

3. **认证** 🔒
   - 聊天 API 检查"伺服器錯誤或未登入"
   - POST 请求中没有显式的 CSRF token

4. **加载状态** ✅
   - 按钮禁用机制防止重复提交
   - Loading 指示器显示进行中的操作

---

## 📁 前端代码文件位置总结

### 包含 API 调用的 HTML 文件 (20+ 处)

1. **_proposal_builder.html** - 核心企划书生成功能
   - 生成 (1 个 API)

2. **assistant.html** - AI 聊天助手
   - 聊天、对话管理 (4 个 API)

3. **search_cases.html** - 个案搜索
   - 搜索 (1 个 API)

4. **search_activities.html** - 活动搜索
   - 搜索 (1 个 API)

5. **analytics_dashboard.html** - 分析仪表板
   - 统计数据加载、报告生成 (2 个 API)

6. **case_workflow.html** - 个案工作流
   - 工作流加载、状态更新 (2 个 API)

7. **notifications.html** - 通知中心
   - 通知管理 (3 个 API)

8. **backups.html** - 备份管理
   - 备份操作 (5 个 API)

9. **reports_list.html** - 报告列表
   - 报告管理 (3 个 API)

10. **donations.html** - 捐赠查询
    - 捐赠数据查询 (1 个 API)

---

## 🎯 关键发现

### 主要功能流程

```
用户流程：
1. [生成企劃書] → POST /api/generate-proposal
   ↓
2. [AI 聊天助手] → POST /api/chat
   ↓
3. [下載企劃書] → GET /user/proposal/download/{idx}
   ↓
4. [查看統計] → GET /api/stats/summary
   ↓
5. [搜尋個案/活動] → GET /api/search/cases/activities
```

### 管理员工作流程

```
管理流程：
1. [管理備份] → POST/GET/DELETE /admin/backups/*
   ↓
2. [生成報告] → POST /api/stats/generate-report
   ↓
3. [查看報告] → GET /analytics/reports/list
   ↓
4. [個案狀態管理] → POST /api/cases/{id}/status
```

---

## 📝 建议

1. ✅ 所有 API 调用都使用 `fetch` API（现代标准）
2. ⚠️ 建议添加 CSRF token 保护
3. ⚠️ 建议隐藏具体错误信息，使用用户友好的提示
4. ✅ 使用异步/等待处理异步操作
5. ⚠️ 某些长时间操作建议添加超时机制

---

**报告末尾** - 所有 API 端点已完整列出
