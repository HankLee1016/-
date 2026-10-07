"""
初始化 PostgreSQL 資料庫表結構
執行方式: python init_database.py
"""

import os
import sys
from db_config import get_db_connection
from psycopg2 import OperationalError

def init_database():
    """初始化所有必需的表"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. 用戶表（已存在）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(255) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                role VARCHAR(50) NOT NULL DEFAULT 'user',
                contact_name VARCHAR(100),
                relation VARCHAR(20),
                phone VARCHAR(30),
                email VARCHAR(255),
                elder_name VARCHAR(100),
                age_group VARCHAR(20),
                district VARCHAR(20),
                address TEXT,
                household_status VARCHAR(20),
                care_level VARCHAR(20),
                care_notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✓ users 表已建立")
        
        # 2. 活動表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS activities (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                username VARCHAR(255) NOT NULL,
                activity_name VARCHAR(255) NOT NULL,
                description TEXT,
                category VARCHAR(100),
                start_date DATE,
                end_date DATE,
                location VARCHAR(255),
                max_capacity INTEGER,
                registration_deadline DATE,
                status VARCHAR(50) DEFAULT '進行中',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (username) REFERENCES users(username)
            )
        """)
        print("✓ activities 表已建立")
        
        # 3. 活動報名表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS registrations (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                activity_id UUID NOT NULL,
                username VARCHAR(255) NOT NULL,
                status VARCHAR(50) DEFAULT '待審核',
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reviewed_by VARCHAR(255),
                reviewed_at TIMESTAMP,
                rejection_reason TEXT,
                FOREIGN KEY (activity_id) REFERENCES activities(id),
                FOREIGN KEY (username) REFERENCES users(username)
            )
        """)
        print("✓ registrations 表已建立")
        
        # 4. 活動簽到表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS attendances (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                activity_id UUID NOT NULL,
                username VARCHAR(255) NOT NULL,
                check_in_time TIMESTAMP,
                check_out_time TIMESTAMP,
                status VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (activity_id) REFERENCES activities(id),
                FOREIGN KEY (username) REFERENCES users(username)
            )
        """)
        print("✓ attendances 表已建立")
        
        # 5. 個案表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cases (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                case_name VARCHAR(255) NOT NULL,
                member_name VARCHAR(255),
                issue_description TEXT,
                status VARCHAR(50) DEFAULT '待處理',
                priority VARCHAR(50) DEFAULT '普通',
                assigned_to VARCHAR(255),
                progress INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                closed_at TIMESTAMP,
                FOREIGN KEY (assigned_to) REFERENCES users(username)
            )
        """)
        print("✓ cases 表已建立")
        
        # 6. 個案進度日誌表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS case_logs (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                case_id UUID NOT NULL,
                action VARCHAR(255),
                description TEXT,
                changed_by VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (case_id) REFERENCES cases(id),
                FOREIGN KEY (changed_by) REFERENCES users(username)
            )
        """)
        print("✓ case_logs 表已建立")
        
        # 7. 公告表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS announcements (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                title VARCHAR(255) NOT NULL,
                content TEXT NOT NULL,
                priority VARCHAR(50) DEFAULT '普通',
                status VARCHAR(50) DEFAULT '已發佈',
                author VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                published_at TIMESTAMP,
                FOREIGN KEY (author) REFERENCES users(username)
            )
        """)
        print("✓ announcements 表已建立")
        
        # 8. 服務表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS services (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                service_name VARCHAR(255) NOT NULL,
                service_type VARCHAR(100),
                target_group VARCHAR(255),
                description TEXT,
                contact VARCHAR(255),
                status VARCHAR(50) DEFAULT '開放申請',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✓ services 表已建立")
        
        # 9. 內容表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contents (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                title VARCHAR(255) NOT NULL,
                content TEXT,
                category VARCHAR(100),
                author VARCHAR(255),
                status VARCHAR(50) DEFAULT '已發佈',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (author) REFERENCES users(username)
            )
        """)
        print("✓ contents 表已建立")

        # 10. 系統日誌表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_logs (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id VARCHAR(255),
                action VARCHAR(255) NOT NULL,
                resource_type VARCHAR(100),
                resource_id VARCHAR(255),
                details TEXT,
                ip_address VARCHAR(45),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(username)
            )
        """)
        print("✓ system_logs 表已建立")
        
        # 11. 通知表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id VARCHAR(255) NOT NULL,
                title VARCHAR(255) NOT NULL,
                message TEXT,
                type VARCHAR(50),
                status VARCHAR(50) DEFAULT '未讀',
                related_resource_type VARCHAR(100),
                related_resource_id VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                read_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(username)
            )
        """)
        print("✓ notifications 表已建立")
        
        # 12. 備份表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS backups (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                backup_name VARCHAR(255) NOT NULL,
                backup_type VARCHAR(50),
                backup_size BIGINT,
                status VARCHAR(50),
                created_by VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                restored_at TIMESTAMP,
                FOREIGN KEY (created_by) REFERENCES users(username)
            )
        """)
        print("✓ backups 表已建立")
        
        # 13. 用戶權限表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_permissions (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id VARCHAR(255) NOT NULL,
                permission VARCHAR(255) NOT NULL,
                granted_by VARCHAR(255),
                granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(username),
                FOREIGN KEY (granted_by) REFERENCES users(username),
                UNIQUE(user_id, permission)
            )
        """)
        print("✓ user_permissions 表已建立")
        
        # 14. 檔案表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                filename VARCHAR(255) NOT NULL,
                file_path TEXT NOT NULL,
                file_size BIGINT,
                file_type VARCHAR(50),
                uploaded_by VARCHAR(255),
                related_resource_type VARCHAR(100),
                related_resource_id VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (uploaded_by) REFERENCES users(username)
            )
        """)
        print("✓ files 表已建立")
        
        # 15. 統計報表表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                report_name VARCHAR(255) NOT NULL,
                report_type VARCHAR(100),
                report_data JSONB,
                generated_by VARCHAR(255),
                start_date DATE,
                end_date DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (generated_by) REFERENCES users(username)
            )
        """)
        print("✓ reports 表已建立")
        
        # 建立索引以提升查詢效率
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_activities_status ON activities(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cases_status ON cases(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_registrations_status ON registrations(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_announcements_status ON announcements(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_status ON notifications(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_system_logs_created ON system_logs(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)")
        print("✓ 所有索引已建立")
        
        conn.commit()
        print("\n✅ 資料庫初始化成功！")
        cursor.close()
        conn.close()
        
    except OperationalError as e:
        print(f"❌ 資料庫連接失敗: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 執行失敗: {e}")
        sys.exit(1)

if __name__ == "__main__":
    init_database()
