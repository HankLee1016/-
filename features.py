"""
功能模塊：統計報表、通知、搜尋、檔案、工作流、備份、權限
"""

import os
import json
import uuid
import datetime
from pathlib import Path
from db_config import get_db_connection
import psycopg2
from psycopg2.extras import RealDictCursor


class StatsReportManager:
    """統計與報表系統"""
    
    @staticmethod
    def get_dashboard_stats(start_date=None, end_date=None):
        """取得儀表板統計"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # 活動統計
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN status = '進行中' THEN 1 ELSE 0 END) as ongoing,
                    SUM(CASE WHEN status = '已結束' THEN 1 ELSE 0 END) as completed
                FROM activities
            """)
            activity_stats = cursor.fetchone()
            
            # 個案統計
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN status = '待處理' THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN status = '進行中' THEN 1 ELSE 0 END) as ongoing,
                    SUM(CASE WHEN status = '已結案' THEN 1 ELSE 0 END) as closed
                FROM cases
            """)
            case_stats = cursor.fetchone()
            
            # 成員統計
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN role = 'admin' THEN 1 ELSE 0 END) as admins,
                    SUM(CASE WHEN role = 'user' THEN 1 ELSE 0 END) as users
                FROM users
            """)
            user_stats = cursor.fetchone()
            
            # 活動報名統計
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN status = '待審核' THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN status = '已通過' THEN 1 ELSE 0 END) as approved
                FROM registrations
            """)
            registration_stats = cursor.fetchone()
            
            cursor.close()
            conn.close()
            
            return {
                'activities': activity_stats,
                'cases': case_stats,
                'users': user_stats,
                'registrations': registration_stats,
                'timestamp': datetime.datetime.now().isoformat()
            }
        except Exception as e:
            print(f"統計取得失敗: {e}")
            return None
    
    @staticmethod
    def generate_report(report_type, start_date, end_date, user_id):
        """生成報表"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            report_data = {}
            
            if report_type == 'activities':
                cursor.execute("""
                    SELECT 
                        activity_name, status, 
                        COUNT(DISTINCT username) as participants,
                        created_at
                    FROM activities a
                    LEFT JOIN registrations r ON a.id = r.activity_id
                    WHERE a.created_at >= %s AND a.created_at <= %s
                    GROUP BY a.id, activity_name, status
                """, (start_date, end_date))
                report_data = cursor.fetchall()
            
            elif report_type == 'cases':
                cursor.execute("""
                    SELECT 
                        case_name, status, priority, assigned_to,
                        created_at, closed_at
                    FROM cases
                    WHERE created_at >= %s AND created_at <= %s
                    ORDER BY created_at DESC
                """, (start_date, end_date))
                report_data = cursor.fetchall()
            
            # 保存報表
            cursor.execute("""
                INSERT INTO reports (report_name, report_type, report_data, generated_by, start_date, end_date)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (f"{report_type}_report", report_type, json.dumps(report_data, default=str), 
                  user_id, start_date, end_date))
            
            report_id = cursor.fetchone()['id']
            conn.commit()
            cursor.close()
            conn.close()
            
            return {'id': report_id, 'data': report_data}
        except Exception as e:
            print(f"報表生成失敗: {e}")
            return None


class NotificationManager:
    """通知與提醒系統"""
    
    @staticmethod
    def create_notification(user_id, title, message, notification_type, resource_type=None, resource_id=None):
        """建立通知"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO notifications (user_id, title, message, type, related_resource_type, related_resource_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (user_id, title, message, notification_type, resource_type, resource_id))
            
            notification_id = cursor.fetchone()[0]
            conn.commit()
            cursor.close()
            conn.close()
            
            return notification_id
        except Exception as e:
            print(f"通知建立失敗: {e}")
            return None
    
    @staticmethod
    def get_user_notifications(user_identifier, limit=20):
        """取得用戶通知"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT * FROM notifications
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s
            """, (user_identifier, limit))
            
            notifications = cursor.fetchall()
            cursor.close()
            conn.close()
            
            return notifications if notifications else []
        except Exception as e:
            print(f"通知取得失敗: {e}")
            return []
    
    @staticmethod
    def mark_as_read(notification_id):
        """標記為已讀"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE notifications
                SET status = '已讀', read_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (notification_id,))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return True
        except Exception as e:
            print(f"標記失敗: {e}")
            return False


class SearchFilterManager:
    """進階搜尋與篩選"""
    
    @staticmethod
    def search_cases(query, status=None, priority=None, assigned_to=None):
        """搜尋個案"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            sql = "SELECT * FROM cases WHERE 1=1"
            params = []
            
            if query:
                sql += " AND (case_name ILIKE %s OR issue_description ILIKE %s)"
                params.extend([f"%{query}%", f"%{query}%"])
            
            if status:
                sql += " AND status = %s"
                params.append(status)
            
            if priority:
                sql += " AND priority = %s"
                params.append(priority)
            
            if assigned_to:
                sql += " AND assigned_to = %s"
                params.append(assigned_to)
            
            sql += " ORDER BY created_at DESC"
            cursor.execute(sql, params)
            results = cursor.fetchall()
            cursor.close()
            conn.close()
            
            return results
        except Exception as e:
            print(f"搜尋失敗: {e}")
            return []
    
    @staticmethod
    def search_activities(query, category=None, status=None):
        """搜尋活動"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            sql = "SELECT * FROM activities WHERE 1=1"
            params = []
            
            if query:
                sql += " AND (activity_name ILIKE %s OR description ILIKE %s)"
                params.extend([f"%{query}%", f"%{query}%"])
            
            if category:
                sql += " AND category = %s"
                params.append(category)
            
            if status:
                sql += " AND status = %s"
                params.append(status)
            
            sql += " ORDER BY created_at DESC"
            cursor.execute(sql, params)
            results = cursor.fetchall()
            cursor.close()
            conn.close()
            
            return results
        except Exception as e:
            print(f"搜尋失敗: {e}")
            return []


class FileManager:
    """檔案管理系統"""
    
    @staticmethod
    def upload_file(uploaded_file, resource_type, resource_id, uploaded_by):
        """上傳檔案"""
        try:
            from werkzeug.utils import secure_filename
            
            UPLOAD_FOLDER = Path(__file__).parent / "uploads"
            UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
            
            filename = secure_filename(uploaded_file.filename)
            unique_name = f"{uuid.uuid4().hex}_{filename}"
            file_path = UPLOAD_FOLDER / unique_name
            uploaded_file.save(file_path)
            
            file_size = os.path.getsize(file_path)
            file_type = filename.rsplit('.', 1)[1].upper() if '.' in filename else 'UNKNOWN'
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO files (filename, file_path, file_size, file_type, uploaded_by, related_resource_type, related_resource_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (filename, str(file_path), file_size, file_type, uploaded_by, resource_type, resource_id))
            
            file_id = cursor.fetchone()[0]
            conn.commit()
            cursor.close()
            conn.close()
            
            return file_id
        except Exception as e:
            print(f"檔案上傳失敗: {e}")
            return None
    
    @staticmethod
    def get_resource_files(resource_type, resource_id):
        """取得資源相關檔案"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT * FROM files
                WHERE related_resource_type = %s AND related_resource_id = %s
                ORDER BY created_at DESC
            """, (resource_type, resource_id))
            
            files = cursor.fetchall()
            cursor.close()
            conn.close()
            
            return files
        except Exception as e:
            print(f"取得檔案失敗: {e}")
            return []


class WorkflowManager:
    """審核工作流程"""
    
    @staticmethod
    def update_case_status(case_id, new_status, changed_by, description=""):
        """更新個案狀態"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # 更新個案狀態
            cursor.execute("""
                UPDATE cases
                SET status = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (new_status, case_id))
            
            # 記錄日誌
            cursor.execute("""
                INSERT INTO case_logs (case_id, action, description, changed_by)
                VALUES (%s, %s, %s, %s)
            """, (case_id, f"狀態已變更為: {new_status}", description, changed_by))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return True
        except Exception as e:
            print(f"狀態更新失敗: {e}")
            return False
    
    @staticmethod
    def get_case_history(case_id):
        """取得個案歷史"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT * FROM case_logs
                WHERE case_id = %s
                ORDER BY created_at DESC
            """, (case_id,))
            
            logs = cursor.fetchall()
            cursor.close()
            conn.close()
            
            return logs
        except Exception as e:
            print(f"歷史取得失敗: {e}")
            return []


class BackupManager:
    """數據備份與恢復"""
    
    @staticmethod
    def create_backup(backup_name, backup_type, created_by):
        """建立備份"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO backups (backup_name, backup_type, status, created_by)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """, (backup_name, backup_type, '已完成', created_by))
            
            backup_id = cursor.fetchone()[0]
            conn.commit()
            cursor.close()
            conn.close()
            
            return backup_id
        except Exception as e:
            print(f"備份建立失敗: {e}")
            return None
    
    @staticmethod
    def get_backups(limit=10):
        """取得備份清單"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT * FROM backups
                ORDER BY created_at DESC
                LIMIT %s
            """, (limit,))
            
            backups = cursor.fetchall()
            cursor.close()
            conn.close()
            
            return backups
        except Exception as e:
            print(f"備份清單取得失敗: {e}")
            return []


class PermissionManager:
    """用戶權限管理"""
    
    @staticmethod
    def grant_permission(user_id, permission, granted_by):
        """授予權限"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO user_permissions (user_id, permission, granted_by)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id, permission) DO NOTHING
            """, (user_id, permission, granted_by))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return True
        except Exception as e:
            print(f"權限授予失敗: {e}")
            return False
    
    @staticmethod
    def get_user_permissions(user_id):
        """取得用戶權限"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT permission FROM user_permissions
                WHERE user_id = %s
            """, (user_id,))
            
            permissions = [row['permission'] for row in cursor.fetchall()]
            cursor.close()
            conn.close()
            
            return permissions
        except Exception as e:
            print(f"權限取得失敗: {e}")
            return []
    
    @staticmethod
    def has_permission(user_id, required_permission):
        """檢查是否有權限"""
        permissions = PermissionManager.get_user_permissions(user_id)
        return required_permission in permissions or 'admin' in permissions
