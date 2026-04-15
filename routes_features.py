# ==========================================
# 功能路由：統計、通知、搜尋、檔案、工作流、備份、權限
# ==========================================

from flask import Blueprint, jsonify, request, render_template, redirect, url_for, session
from features import (
    StatsReportManager, NotificationManager, SearchFilterManager,
    FileManager, WorkflowManager, BackupManager, PermissionManager
)
from db_config import get_db_connection
from psycopg2.extras import RealDictCursor
import datetime

# 建立 Blueprint
bp = Blueprint('features', __name__)


# ==========================================
# 1. 統計與報表系統
# ==========================================

@bp.route('/analytics/dashboard')
def analytics_dashboard():
    """統計儀表板"""
    if session.get('role') != 'admin':
        return redirect(url_for('home'))
    
    stats = StatsReportManager.get_dashboard_stats()
    return render_template('analytics_dashboard.html', stats=stats)


@bp.route('/api/stats/summary')
def api_stats_summary():
    """API: 取得統計摘要"""
    stats = StatsReportManager.get_dashboard_stats()
    return jsonify(stats) if stats else jsonify({}), 200


@bp.route('/reports')
def reports_list():
    """報表列表"""
    if session.get('role') != 'admin':
        return redirect(url_for('home'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute('SELECT * FROM reports ORDER BY created_at DESC')
        reports = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template('reports_list.html', reports=reports)
    except Exception as e:
        return str(e), 500


@bp.route('/reports/generate', methods=['POST'])
def generate_report():
    """生成報表"""
    if session.get('role') != 'admin':
        return jsonify({'error': '無權限'}), 403
    
    data = request.get_json()
    report_type = data.get('report_type')
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    
    result = StatsReportManager.generate_report(report_type, start_date, end_date, session.get('username'))
    return jsonify({'success': True, 'report_id': str(result['id'])}) if result else jsonify({'error': '生成失敗'}), 500


# ==========================================
# 2. 通知與提醒系統
# ==========================================

@bp.route('/notifications')
def notifications_page():
    """通知頁面"""
    username = session.get('username')
    if not username:
        return redirect(url_for('login'))
    
    notifications = NotificationManager.get_user_notifications(username)
    return render_template('notifications.html', notifications=notifications)


@bp.route('/api/notifications')
def api_get_notifications():
    """API: 取得通知"""
    username = session.get('username')
    if not username:
        return jsonify({'error': '未登入'}), 401
    
    notifications = NotificationManager.get_user_notifications(username)
    notif_dicts = []
    if notifications:
        for notif in notifications:
            if hasattr(notif, 'keys'):
                notif_dicts.append(dict(notif))
            elif isinstance(notif, dict):
                notif_dicts.append(notif)
            else:
                notif_dicts.append({'error': 'invalid'})
    return jsonify({'notifications': notif_dicts}), 200


@bp.route('/api/notifications/<notification_id>/read', methods=['POST'])
def mark_notification_read(notification_id):
    """API: 標記通知為已讀"""
    success = NotificationManager.mark_as_read(notification_id)
    return jsonify({'success': success}), 200 if success else 500


# ==========================================
# 3. 進階搜尋與篩選
# ==========================================

@bp.route('/search/cases')
def search_cases():
    """搜尋個案"""
    if session.get('role') != 'admin':
        return redirect(url_for('home'))
    
    query = request.args.get('q', '')
    status = request.args.get('status')
    priority = request.args.get('priority')
    assigned_to = request.args.get('assigned_to')
    
    results = SearchFilterManager.search_cases(query, status, priority, assigned_to)
    return render_template('search_cases.html', results=results, query=query)


@bp.route('/api/search/cases')
def api_search_cases():
    """API: 搜尋個案"""
    query = request.args.get('q', '')
    status = request.args.get('status')
    priority = request.args.get('priority')
    assigned_to = request.args.get('assigned_to')
    
    results = SearchFilterManager.search_cases(query, status, priority, assigned_to)
    return jsonify({'results': [dict(r) for r in results] if results else []}), 200


@bp.route('/search/activities')
def search_activities():
    """搜尋活動"""
    query = request.args.get('q', '')
    category = request.args.get('category')
    status = request.args.get('status')
    
    results = SearchFilterManager.search_activities(query, category, status)
    return render_template('search_activities.html', results=results, query=query)


@bp.route('/api/search/activities')
def api_search_activities():
    """API: 搜尋活動"""
    query = request.args.get('q', '')
    category = request.args.get('category')
    status = request.args.get('status')
    
    results = SearchFilterManager.search_activities(query, category, status)
    return jsonify({'results': [dict(r) for r in results] if results else []}), 200


# ==========================================
# 4. 檔案管理系統
# ==========================================

@bp.route('/api/upload', methods=['POST'])
def upload_file():
    """API: 上傳檔案"""
    username = session.get('username')
    if not username:
        return jsonify({'error': '未登入'}), 401
    
    if 'file' not in request.files:
        return jsonify({'error': '未選擇檔案'}), 400
    
    file = request.files['file']
    resource_type = request.form.get('resource_type')
    resource_id = request.form.get('resource_id')
    
    if file.filename == '':
        return jsonify({'error': '檔案名稱為空'}), 400
    
    file_id = FileManager.upload_file(file, resource_type, resource_id, username)
    return jsonify({'success': True, 'file_id': str(file_id)}) if file_id else jsonify({'error': '上傳失敗'}), 500


@bp.route('/api/files/<resource_type>/<resource_id>')
def get_resource_files(resource_type, resource_id):
    """API: 取得資源檔案"""
    files = FileManager.get_resource_files(resource_type, resource_id)
    return jsonify({'files': [dict(f) for f in files] if files else []}), 200


# ==========================================
# 5. 審核工作流程
# ==========================================

@bp.route('/cases/<case_id>/workflow')
def case_workflow(case_id):
    """個案工作流程"""
    if session.get('role') != 'admin':
        return redirect(url_for('home'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute('SELECT * FROM cases WHERE id = %s', (case_id,))
        case = cursor.fetchone()
        
        history = WorkflowManager.get_case_history(case_id)
        
        cursor.close()
        conn.close()
        
        return render_template('case_workflow.html', case=case, history=history)
    except Exception as e:
        return str(e), 500


@bp.route('/api/cases/<case_id>/status', methods=['POST'])
def update_case_status(case_id):
    """API: 更新個案狀態"""
    username = session.get('username')
    if not username:
        return jsonify({'error': '未登入'}), 401
    
    data = request.get_json()
    new_status = data.get('status')
    description = data.get('description', '')
    
    success = WorkflowManager.update_case_status(case_id, new_status, username, description)
    return jsonify({'success': success}), 200 if success else 500


# ==========================================
# 6. 數據備份與恢復
# ==========================================

@bp.route('/admin/backups')
def backups_list():
    """備份列表"""
    if session.get('role') != 'admin':
        return redirect(url_for('home'))
    
    backups = BackupManager.get_backups()
    return render_template('backups.html', backups=backups)


@bp.route('/admin/backups/create', methods=['POST'])
def create_backup():
    """建立備份"""
    if session.get('role') != 'admin':
        return jsonify({'error': '無權限'}), 403
    
    backup_name = f"backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
    backup_id = BackupManager.create_backup(backup_name, 'full', session.get('username'))
    
    return jsonify({'success': True, 'backup_id': str(backup_id)}) if backup_id else jsonify({'error': '備份失敗'}), 500


# ==========================================
# 7. 用戶權限管理
# ==========================================

@bp.route('/admin/permissions')
def permissions_management():
    """權限管理"""
    if session.get('role') != 'admin':
        return redirect(url_for('home'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute('SELECT * FROM users WHERE role != "admin" ORDER BY username')
        users = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return render_template('permissions_management.html', users=users)
    except Exception as e:
        return str(e), 500


@bp.route('/api/permissions/<user_id>', methods=['GET'])
def get_user_permissions(user_id):
    """API: 取得用戶權限"""
    if session.get('role') != 'admin':
        return jsonify({'error': '無權限'}), 403
    
    permissions = PermissionManager.get_user_permissions(user_id)
    return jsonify({'permissions': permissions}), 200


@bp.route('/api/permissions/<user_id>', methods=['POST'])
def grant_permission(user_id):
    """API: 授予權限"""
    if session.get('role') != 'admin':
        return jsonify({'error': '無權限'}), 403
    
    data = request.get_json()
    permission = data.get('permission')
    
    success = PermissionManager.grant_permission(user_id, permission, session.get('username'))
    return jsonify({'success': success}), 200 if success else 500


# ==========================================
# 額外數據獲取端點
# ==========================================

@bp.route('/analytics/reports/list')
def get_reports_list():
    """取得報告列表"""
    if session.get('role') != 'admin':
        return jsonify({'error': '無權限'}), 403
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute('SELECT * FROM reports ORDER BY created_at DESC LIMIT 50')
        reports = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify({'reports': [dict(r) for r in reports] if reports else []}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/analytics/reports/<report_id>')
def view_report(report_id):
    """查看報告"""
    if session.get('role') != 'admin':
        return redirect(url_for('home'))
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute('SELECT * FROM reports WHERE id = %s', (report_id,))
        report = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if report:
            return render_template('report_detail.html', report=dict(report))
        return 'Not Found', 404
    except Exception as e:
        return str(e), 500


@bp.route('/analytics/reports/<report_id>/download')
def download_report(report_id):
    """下載報告"""
    if session.get('role') != 'admin':
        return jsonify({'error': '無權限'}), 403
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute('SELECT * FROM reports WHERE id = %s', (report_id,))
        report = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if report and report.get('file_path'):
            return redirect(f'/uploads/{report_id}')
        return 'Not Found', 404
    except Exception as e:
        return str(e), 500


@bp.route('/analytics/reports/<report_id>', methods=['DELETE'])
def delete_report(report_id):
    """刪除報告"""
    if session.get('role') != 'admin':
        return jsonify({'error': '無權限'}), 403
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM reports WHERE id = %s', (report_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'success': True}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/analytics/reports/delete-all', methods=['POST'])
def delete_all_reports():
    """刪除所有報告"""
    if session.get('role') != 'admin':
        return jsonify({'error': '無權限'}), 403
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM reports')
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'success': True}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/api/stats/generate-report', methods=['POST'])
def api_generate_report():
    """API: 生成報告"""
    if session.get('role') != 'admin':
        return jsonify({'error': '無權限'}), 403
    
    data = request.get_json()
    title = data.get('title', '新報告')
    
    try:
        result = StatsReportManager.generate_report(title, None, None, session.get('username'))
        if result:
            return jsonify({'success': True, 'report_id': str(result.get('id'))}), 200
        return jsonify({'error': '生成失敗'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/admin/backups/list')
def get_backups_list():
    """取得備份列表"""
    if session.get('role') != 'admin':
        return jsonify({'error': '無權限'}), 403
    
    try:
        backups = BackupManager.get_backups()
        return jsonify({'backups': [dict(b) for b in backups] if backups else []}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/admin/backups/<backup_id>/restore', methods=['POST'])
def restore_backup(backup_id):
    """還原備份"""
    if session.get('role') != 'admin':
        return jsonify({'error': '無權限'}), 403
    
    try:
        success = BackupManager.restore_backup(backup_id)
        return jsonify({'success': success}), 200 if success else 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/admin/backups/<backup_id>/download')
def download_backup(backup_id):
    """下載備份"""
    if session.get('role') != 'admin':
        return jsonify({'error': '無權限'}), 403
    
    try:
        return redirect(f'/uploads/backups/{backup_id}')
    except Exception as e:
        return str(e), 500


@bp.route('/admin/backups/<backup_id>', methods=['DELETE'])
def delete_backup(backup_id):
    """刪除備份"""
    if session.get('role') != 'admin':
        return jsonify({'error': '無權限'}), 403
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM backups WHERE id = %s', (backup_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'success': True}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/admin/permissions/list')
def get_permissions_list():
    """取得權限列表"""
    if session.get('role') != 'admin':
        return jsonify({'error': '無權限'}), 403
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute('SELECT * FROM users ORDER BY username')
        users = cursor.fetchall()
        cursor.close()
        conn.close()
        
        result = []
        for user in users:
            permissions = PermissionManager.get_user_permissions(str(user['id']))
            result.append({
                **dict(user),
                'permissions': permissions
            })
        
        return jsonify({'users': result}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/cases/<case_id>/workflow-data')
def get_case_workflow_data(case_id):
    """取得個案工作流程數據"""
    if session.get('role') != 'admin':
        return jsonify({'error': '無權限'}), 403
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute('SELECT * FROM cases WHERE id = %s', (case_id,))
        case = cursor.fetchone()
        cursor.close()
        conn.close()
        
        history = WorkflowManager.get_case_history(case_id)
        
        return jsonify({
            'case': dict(case) if case else None,
            'history': [dict(h) for h in history] if history else []
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/api/notifications/<notification_id>', methods=['DELETE'])
def delete_notification(notification_id):
    """刪除通知"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM notifications WHERE id = %s', (notification_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'success': True}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
