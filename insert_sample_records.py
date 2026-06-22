import uuid
import datetime
import hashlib
from db_config import get_db_connection

sample_activities = [
    {
        'id': str(uuid.uuid4()),
        'username': 'admin',
        'activity_name': '社區關懷巡迴',
        'description': '前往社區訪視高齡長者並提供生活協助。',
        'category': '社區',
        'start_date': '2026-05-05',
        'end_date': '2026-05-05',
        'location': '大安區社區中心',
        'max_capacity': 20,
        'registration_deadline': '2026-05-01',
        'status': '進行中'
    },
    {
        'id': str(uuid.uuid4()),
        'username': 'admin',
        'activity_name': '青少年才藝班',
        'description': '提供青少年免費才藝課程與團體支持。',
        'category': '教育',
        'start_date': '2026-04-10',
        'end_date': '2026-06-15',
        'location': '光復國小活動中心',
        'max_capacity': 15,
        'registration_deadline': '2026-04-05',
        'status': '進行中'
    },
    {
        'id': str(uuid.uuid4()),
        'username': 'admin',
        'activity_name': '長者陪伴服務',
        'description': '定期陪伴獨居長者，提供關懷與生活協助。',
        'category': '志工',
        'start_date': '2026-03-20',
        'end_date': '2026-03-20',
        'location': '中正區社區照護站',
        'max_capacity': 12,
        'registration_deadline': '2026-03-15',
        'status': '已結束'
    }
]

sample_cases = [
    {
        'id': str(uuid.uuid4()),
        'case_name': '家庭經濟支持',
        'member_name': '張小姐',
        'issue_description': '單親家庭面臨生活費不足與子女教育經費壓力。',
        'status': '待處理',
        'priority': '高',
        'assigned_to': 'admin',
        'progress': 10
    },
    {
        'id': str(uuid.uuid4()),
        'case_name': '失智長者關懷',
        'member_name': '陳先生',
        'issue_description': '長者罹患失智症，需要定期陪伴與生活協助。',
        'status': '進行中',
        'priority': '中',
        'assigned_to': 'admin',
        'progress': 60
    },
    {
        'id': str(uuid.uuid4()),
        'case_name': '兒少輔導',
        'member_name': '李同學',
        'issue_description': '家庭變動導致情緒困擾、學習壓力與社交退縮。',
        'status': '已結案',
        'priority': '普通',
        'assigned_to': 'admin',
        'progress': 100,
        'closed_at': datetime.datetime(2026, 4, 1)
    }
]

sample_announcements = [
    {
        'id': str(uuid.uuid4()),
        'title': '社區服務招募',
        'announcement_text': '本週末將舉辦社區關懷活動，歡迎志工報名參加。',
        'priority': '一般',
        'status': '已發佈'
    }
]

def hash_password(password):
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

try:
    conn = get_db_connection()
    cur = conn.cursor()

    # 確保 admin 使用者也存在於資料庫中
    cur.execute(
        "INSERT INTO users (username, password, role, created_at, updated_at) VALUES (%s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) ON CONFLICT (username) DO NOTHING",
        ('admin', hash_password('Admin2026!'), 'admin')
    )

    for act in sample_activities:
        cur.execute(
            "INSERT INTO activities (id, username, activity_name, description, category, start_date, end_date, location, max_capacity, registration_deadline, status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING",
            (act['id'], act['username'], act['activity_name'], act['description'], act['category'], act['start_date'], act['end_date'], act['location'], act['max_capacity'], act['registration_deadline'], act['status'])
        )

    for case in sample_cases:
        cur.execute(
            "INSERT INTO cases (id, case_name, member_name, issue_description, status, priority, assigned_to, progress, closed_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING",
            (case['id'], case['case_name'], case['member_name'], case['issue_description'], case['status'], case['priority'], case['assigned_to'], case['progress'], case.get('closed_at'))
        )

    for ann in sample_announcements:
        cur.execute(
            "INSERT INTO announcements (id, title, content, priority, status) VALUES (%s,%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING",
            (ann['id'], ann['title'], ann['announcement_text'], ann['priority'], ann['status'])
        )

    conn.commit()
    cur.close()
    conn.close()
    print('✅ 已插入範例活動、個案與公告資料')
except Exception as e:
    print('❌ 插入失敗:', e)
