import os
import json
import hashlib
import random
import uuid
import datetime
from html import escape
from pathlib import Path
from flask import Flask, request, jsonify, render_template, send_from_directory, redirect, url_for, session, Response, flash
from werkzeug.utils import secure_filename

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from psycopg2 import OperationalError
from db_config import get_db_connection
from features import (
    StatsReportManager, NotificationManager, SearchFilterManager,
    FileManager, WorkflowManager, BackupManager, PermissionManager
)

app = Flask(__name__, template_folder="templates")
app.secret_key = os.getenv("SECRET_KEY", "dev_secret_key")

# 導入功能路由
from routes_features import bp as features_bp
app.register_blueprint(features_bp)

# ==========================================
# 檔案路徑與全域設定 (融合雙方設定)
# ==========================================
USERS_FILE = Path(app.root_path) / "users.json"
WELFARE_FILE = Path(app.root_path) / "welfare.json"
CASES_FILE = Path(app.root_path) / "cases.json"
ACTIVITIES_FILE = Path(app.root_path) / "activities.json"
SERVICES_FILE = Path(app.root_path) / "services.json"
CONTENTS_FILE = Path(app.root_path) / "contents.json"
ANNOUNCEMENTS_FILE = Path(app.root_path) / "announcements.json"
REGISTRATIONS_FILE = Path(app.root_path) / "registrations.json"
ATTENDANCES_FILE = Path(app.root_path) / "attendances.json"
HELP_REQUESTS_FILE = Path(app.root_path) / "help_requests.json"

UPLOAD_FOLDER = Path(app.root_path) / "uploads"
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
ALLOWED_EXTENSIONS = {"pdf"}

ADMIN_REG_CODE = os.getenv("ADMIN_REG_CODE", "ADMIN2026")

# 長者需求類型與服務類型共用同一組分類，媒合時以此比對
NEED_TYPES = [
    "餐食協助", "居家照顧", "交通接送", "就醫陪伴", "陪伴聊天", "3C／數位協助",
    "社會福利申請", "活動／社交參與", "居家整理", "緊急協助"
]
DISTRICTS = ["中山區", "大安區", "信義區", "士林區", "北投區", "內湖區", "中正區", "萬華區", "板橋區", "桃園區", "其他"]
CITYWIDE_SCOPES = {"全區", "全縣市", "全國"}
AGE_GROUPS = ["65-74", "75-84", "85歲以上"]
HOUSEHOLD_STATUSES = ["獨居", "與家人同住", "雙老同住", "低收入", "其他"]
CARE_LEVELS = ["自理", "部分協助", "需長期照護"]
RELATIONS = ["本人", "子女", "配偶", "其他親屬", "照顧者"]
PROFILE_FIELDS = ["contact_name", "relation", "phone", "email", "elder_name", "age_group", "district",
                  "address", "household_status", "care_level", "care_notes"]
PROFILE_REQUIRED = ["contact_name", "phone", "elder_name", "district"]
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
AI_MOCK_MODE = os.getenv("AI_MOCK_MODE", "false").strip().lower() in {"1", "true", "yes", "on"}
AI_TIMEOUT_SECONDS = int(os.getenv("AI_TIMEOUT_SECONDS", "15"))
AI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# 依環境變數決定是否啟用真實 OpenAI；開發/展示時可用 mock mode 保持穩定
openai_client = None
if OpenAI and OPENAI_API_KEY and not AI_MOCK_MODE:
    openai_client = OpenAI(api_key=OPENAI_API_KEY, timeout=AI_TIMEOUT_SECONDS)

# ==========================================
# 基礎輔助函式 (檔案處理、密碼雜湊等)
# ==========================================
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def save_uploaded_file(uploaded_file, prefix):
    if uploaded_file and uploaded_file.filename and allowed_file(uploaded_file.filename):
        filename = secure_filename(uploaded_file.filename)
        unique_name = f"{prefix}_{uuid.uuid4().hex}_{filename}"
        dest = UPLOAD_FOLDER / unique_name
        uploaded_file.save(dest)
        return unique_name
    return None

def hash_password(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

# ==========================================
# JSON 資料庫操作函式 (使用者、補助、管理模組)
# ==========================================

# --- Users ---
def load_users():
    if not USERS_FILE.exists(): return []
    try:
        with USERS_FILE.open("r", encoding="utf-8") as f:
            return json.load(f).get("users", [])
    except json.JSONDecodeError:
        return []

def save_users(users):
    with USERS_FILE.open("w", encoding="utf-8") as f:
        json.dump({"users": users}, f, ensure_ascii=False, indent=2)

def find_user(username):
    for user in load_users():
        if user["username"] == username: return user
    return None

def create_user(username, password, role="user", profile=None):
    profile = profile or {k: "" for k in PROFILE_FIELDS}
    users = load_users()
    users.append({
        "username": username, "password": hash_password(password),
        "role": role, "profile": profile
    })
    save_users(users)

def delete_user(username):
    users = [user for user in load_users() if user["username"] != username]
    save_users(users)

def update_user_role(username, role):
    users = load_users()
    for user in users:
        if user["username"] == username: user["role"] = role
    save_users(users)

def get_user_profile(username):
    user = find_user(username) or {}
    profile = {k: "" for k in PROFILE_FIELDS}
    profile.update({k: v for k, v in (user.get("profile") or {}).items() if k in PROFILE_FIELDS})
    return profile

def update_user_profile(username, profile):
    users = load_users()
    for user in users:
        if user["username"] == username: user["profile"] = profile
    save_users(users)

def update_user_password(username, new_password):
    users = load_users()
    for user in users:
        if user["username"] == username: user["password"] = hash_password(new_password)
    save_users(users)

# --- Subsidies ---
WELFARE_CATEGORIES = ["經濟補助", "長期照顧", "醫療保健", "生活照顧", "交通與優待", "其他"]
WELFARE_FIELDS = ["title", "category", "agency", "eligibility", "benefit", "apply_method", "contact", "source_url"]

def load_welfare():
    if not WELFARE_FILE.exists(): return []
    try:
        with WELFARE_FILE.open("r", encoding="utf-8") as f:
            return json.load(f).get("welfare", [])
    except json.JSONDecodeError: return []

def save_welfare(items):
    with WELFARE_FILE.open("w", encoding="utf-8") as f:
        json.dump({"welfare": items}, f, ensure_ascii=False, indent=2)

def search_welfare(category, keyword):
    items = load_welfare()
    if category: items = [w for w in items if w.get("category") == category]
    if keyword:
        items = [w for w in items if keyword in " ".join(str(w.get(k, "")) for k in WELFARE_FIELDS)]
    return items

def get_welfare(welfare_id):
    for item in load_welfare():
        if item.get("id") == welfare_id: return item
    return None

def welfare_from_form(form):
    return {k: form.get(k, "").strip() for k in WELFARE_FIELDS}

# --- Cases ---
def load_cases():
    if not CASES_FILE.exists(): return []
    try:
        with CASES_FILE.open("r", encoding="utf-8") as f: return json.load(f).get("cases", [])
    except json.JSONDecodeError: return []

def save_cases(cases):
    with CASES_FILE.open("w", encoding="utf-8") as f:
        json.dump({"cases": cases}, f, ensure_ascii=False, indent=2)

# --- Help Requests / Elderly Service Needs ---
def load_help_requests():
    if not HELP_REQUESTS_FILE.exists():
        save_help_requests([])
        return []
    try:
        with HELP_REQUESTS_FILE.open("r", encoding="utf-8") as f:
            return json.load(f).get("help_requests", [])
    except json.JSONDecodeError:
        return []


def save_help_requests(help_requests):
    with HELP_REQUESTS_FILE.open("w", encoding="utf-8") as f:
        json.dump({"help_requests": help_requests}, f, ensure_ascii=False, indent=2)


def create_help_request(username, need_type, need_when, location, duration, details="", status="待處理", contact_name="", contact_phone="", elder_name="", age_group="", district="", urgency="一般", household_status="", care_level="", assigned_unit="", assigned_service=""):
    help_requests = load_help_requests()
    new_request = {
        "id": str(uuid.uuid4()),
        "username": username,
        "elder_name": elder_name,
        "age_group": age_group,
        "district": district,
        "urgency": urgency,
        "household_status": household_status,
        "care_level": care_level,
        "need_type": need_type,
        "need_when": need_when,
        "location": location,
        "duration": duration,
        "details": details,
        "contact_name": contact_name,
        "contact_phone": contact_phone,
        "status": status,
        "matched_service": assigned_service,
        "service_id": "",
        "service_contact": "",
        "assigned_unit": assigned_unit,
        "admin_note": "",
        "history": [{
            "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "message": "需求已送出，等待里辦公處確認"
        }],
        "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    help_requests.insert(0, new_request)
    save_help_requests(help_requests)
    return new_request


def get_help_request(request_id):
    for request in load_help_requests():
        if request.get("id") == request_id:
            return request
    return None


def get_user_help_requests(username):
    requests = load_help_requests()
    return [req for req in requests if req.get("username") == username]


def update_help_request_status(request_id, status, admin_note="", assigned_service="", assigned_unit=""):
    requests = load_help_requests()
    for request in requests:
        if request.get("id") == request_id:
            request["status"] = status
            if assigned_service:
                request["matched_service"] = assigned_service
            if assigned_unit:
                request["assigned_unit"] = assigned_unit
            if admin_note:
                request["admin_note"] = admin_note

            history = request.setdefault("history", [])
            message = f"管理者更新狀態為 {status}"
            if assigned_service:
                message += f"；指派服務：{assigned_service}"
            if assigned_unit:
                message += f"；服務單位：{assigned_unit}"
            if admin_note:
                message += f"；備註：{admin_note}"
            history.insert(0, {
                "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "message": message
            })
            if len(history) > 10:
                history = history[:10]
            request["history"] = history
            save_help_requests(requests)
            return request
    return None


def apply_help_request_service(request_id, service_id):
    request_item = get_help_request(request_id)
    service = get_service(service_id)
    if not request_item or not service or service.get("status") != "開放申請":
        return None
    requests = load_help_requests()
    for req in requests:
        if req.get("id") == request_id:
            req["matched_service"] = service.get("service_name", "")
            req["service_id"] = service_id
            req["service_contact"] = service.get("contact", "")
            req["assigned_unit"] = service.get("service_name", "")
            req["status"] = "已申請"
            history = req.setdefault("history", [])
            history.insert(0, {
                "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "message": f"已選擇服務：{service.get('service_name', '')}，請等待管理者確認"
            })
            req["history"] = history[:10]
            break
    save_help_requests(requests)
    return request_item


def get_help_request_matches(request_item):
    """只推薦服務類型與需求相符、且服務範圍涵蓋長者所在區域的開放服務，同區服務優先。"""
    if not request_item:
        return []
    need_type = str(request_item.get("need_type", "")).strip()
    district = str(request_item.get("district", "")).strip()
    if not need_type:
        return []

    matches = []
    for service in load_services():
        if service.get("status") != "開放申請":
            continue
        text = f"{service.get('service_name', '')} {service.get('description', '')} {service.get('target_group', '')}"
        if service.get("service_type") != need_type and need_type not in text:
            continue

        service_district = str(service.get("district", "")).strip()
        citywide = str(service.get("service_scope", "")).strip() in CITYWIDE_SCOPES or not service_district
        if district and service_district == district:
            score, area = 2, "同區服務"
        elif citywide:
            score, area = 1, "全區皆可服務"
        else:
            continue  # 服務範圍不涵蓋長者所在區域，不推薦
        matches.append({"service": service, "score": score, "area": area, "reason": f"需求類型相符・{area}"})

    matches.sort(key=lambda m: m["score"], reverse=True)
    return matches


def create_case(case_name, member_name, issue_description, status="進行中"):
    cases = load_cases()
    new_case = {
        "id": str(uuid.uuid4()), "case_name": case_name, "member_name": member_name,
        "issue_description": issue_description, "status": status,
        "created_at": str(uuid.uuid4().hex[:8]), "created_date": str(uuid.uuid4().hex[:8])
    }
    cases.append(new_case)
    save_cases(cases)
    return new_case

def delete_case(case_id):
    cases = [case for case in load_cases() if case["id"] != case_id]
    save_cases(cases)

def get_case(case_id):
    for case in load_cases():
        if case["id"] == case_id: return case
    return None

def update_case(case_id, case_name=None, member_name=None, issue_description=None, status=None):
    cases = load_cases()
    for case in cases:
        if case["id"] == case_id:
            if case_name is not None: case["case_name"] = case_name
            if member_name is not None: case["member_name"] = member_name
            if issue_description is not None: case["issue_description"] = issue_description
            if status is not None: case["status"] = status
            break
    save_cases(cases)

# --- Activities ---
def load_activities(username=None):
    if not ACTIVITIES_FILE.exists(): return []
    try:
        with ACTIVITIES_FILE.open("r", encoding="utf-8") as f:
            all_activities = json.load(f).get("activities", [])
            if username: return [a for a in all_activities if a.get("username") == username]
            return all_activities
    except json.JSONDecodeError: return []

def save_activities(activities):
    with ACTIVITIES_FILE.open("w", encoding="utf-8") as f:
        json.dump({"activities": activities}, f, ensure_ascii=False, indent=2)

def create_activity(username, activity_name, description, category, start_date="", end_date="", location="", max_capacity=0, registration_deadline="", status="進行中"):
    activities = load_activities()
    new_activity = {
        "id": str(uuid.uuid4()), "username": username, "activity_name": activity_name,
        "description": description, "category": category, "start_date": start_date,
        "end_date": end_date, "location": location, "max_capacity": int(max_capacity) if max_capacity else 0,
        "registration_deadline": registration_deadline, "status": status, "created_at": str(uuid.uuid4().hex[:8])
    }
    activities.append(new_activity)
    save_activities(activities)
    return new_activity

def update_activity(activity_id, activity_name=None, description=None, category=None, start_date=None, end_date=None, location=None, max_capacity=None, registration_deadline=None, status=None):
    activities = load_activities()
    for activity in activities:
        if activity["id"] == activity_id:
            if activity_name is not None: activity["activity_name"] = activity_name
            if description is not None: activity["description"] = description
            if category is not None: activity["category"] = category
            if start_date is not None: activity["start_date"] = start_date
            if end_date is not None: activity["end_date"] = end_date
            if location is not None: activity["location"] = location
            if max_capacity is not None: activity["max_capacity"] = int(max_capacity) if max_capacity else 0
            if registration_deadline is not None: activity["registration_deadline"] = registration_deadline
            if status is not None: activity["status"] = status
            break
    save_activities(activities)

def delete_activity(activity_id):
    activities = [a for a in load_activities() if a["id"] != activity_id]
    save_activities(activities)

def get_activity(activity_id):
    for activity in load_activities():
        if activity["id"] == activity_id: return activity
    return None

# --- Registrations ---
def load_registrations():
    if not REGISTRATIONS_FILE.exists(): return []
    try:
        with REGISTRATIONS_FILE.open("r", encoding="utf-8") as f: return json.load(f).get("registrations", [])
    except json.JSONDecodeError: return []

def save_registrations(registrations):
    with REGISTRATIONS_FILE.open("w", encoding="utf-8") as f:
        json.dump({"registrations": registrations}, f, ensure_ascii=False, indent=2)

def create_registration(activity_id, username, email, phone, status="待審核"):
    registrations = load_registrations()
    new_reg = {
        "id": str(uuid.uuid4()), "activity_id": activity_id, "username": username,
        "email": email, "phone": phone, "status": status,
        "registered_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    registrations.append(new_reg)
    save_registrations(registrations)
    return new_reg

def get_activity_registrations(activity_id):
    return [r for r in load_registrations() if r["activity_id"] == activity_id]

def update_registration_status(registration_id, status):
    registrations = load_registrations()
    for reg in registrations:
        if reg["id"] == registration_id: reg["status"] = status; break
    save_registrations(registrations)

def delete_registration(registration_id):
    registrations = [r for r in load_registrations() if r["id"] != registration_id]
    save_registrations(registrations)

# --- Attendances ---
def load_attendances():
    if not ATTENDANCES_FILE.exists(): return []
    try:
        with ATTENDANCES_FILE.open("r", encoding="utf-8") as f: return json.load(f).get("attendances", [])
    except json.JSONDecodeError: return []

def save_attendances(attendances):
    with ATTENDANCES_FILE.open("w", encoding="utf-8") as f:
        json.dump({"attendances": attendances}, f, ensure_ascii=False, indent=2)

def create_attendance(activity_id, username, check_in_time, check_out_time=None):
    attendances = load_attendances()
    new_att = {
        "id": str(uuid.uuid4()), "activity_id": activity_id, "username": username,
        "check_in_time": check_in_time, "check_out_time": check_out_time,
        "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    attendances.append(new_att)
    save_attendances(attendances)
    return new_att

def update_check_out(activity_id, username, check_out_time):
    attendances = load_attendances()
    for att in attendances:
        if att["activity_id"] == activity_id and att["username"] == username:
            att["check_out_time"] = check_out_time; break
    save_attendances(attendances)

def get_activity_attendances(activity_id):
    return [a for a in load_attendances() if a["activity_id"] == activity_id]

def get_user_registration(activity_id, username):
    for reg in load_registrations():
        if reg["activity_id"] == activity_id and reg["username"] == username: return reg
    return None

def get_user_attendance(activity_id, username):
    for att in load_attendances():
        if att["activity_id"] == activity_id and att["username"] == username: return att
    return None

def registration_block_reason(activity, username):
    """回傳無法報名的原因；可報名時回傳 None。"""
    if activity.get("status") != "進行中": return "此活動目前不開放報名。"
    if get_user_registration(activity["id"], username): return "您已報名此活動。"
    deadline = activity.get("registration_deadline")
    if deadline and deadline < datetime.date.today().isoformat(): return "已超過報名截止日。"
    capacity = int(activity.get("max_capacity") or 0)
    if capacity:
        taken = [r for r in get_activity_registrations(activity["id"]) if r.get("status") != "已拒絕"]
        if len(taken) >= capacity: return "報名人數已額滿。"
    return None

# --- Services ---
def load_services(username=None):
    if not SERVICES_FILE.exists(): return []
    try:
        with SERVICES_FILE.open("r", encoding="utf-8") as f:
            all_services = json.load(f).get("services", [])
            if username: return [s for s in all_services if s.get("username") == username]
            return all_services
    except json.JSONDecodeError: return []

def save_services(services):
    with SERVICES_FILE.open("w", encoding="utf-8") as f:
        json.dump({"services": services}, f, ensure_ascii=False, indent=2)

def create_service(username, service_name, description, service_type, target_group="", contact="", status="開放申請", district="", service_scope="全區"):
    services = load_services()
    new_service = {
        "id": str(uuid.uuid4()), "username": username, "service_name": service_name,
        "description": description, "service_type": service_type, "target_group": target_group,
        "contact": contact, "status": status, "district": district, "service_scope": service_scope,
        "created_at": str(uuid.uuid4().hex[:8])
    }
    services.append(new_service)
    save_services(services)
    return new_service

def delete_service(service_id):
    services = [s for s in load_services() if s["id"] != service_id]
    save_services(services)

def get_service(service_id):
    for service in load_services():
        if service["id"] == service_id: return service
    return None

def update_service(service_id, service_name=None, description=None, service_type=None, target_group=None, contact=None, status=None, district=None, service_scope=None):
    services = load_services()
    for service in services:
        if service["id"] == service_id:
            if service_name is not None: service["service_name"] = service_name
            if description is not None: service["description"] = description
            if service_type is not None: service["service_type"] = service_type
            if target_group is not None: service["target_group"] = target_group
            if contact is not None: service["contact"] = contact
            if status is not None: service["status"] = status
            if district is not None: service["district"] = district
            if service_scope is not None: service["service_scope"] = service_scope
            break
    save_services(services)

# --- Contents ---
def load_contents():
    if not CONTENTS_FILE.exists(): return []
    try:
        with CONTENTS_FILE.open("r", encoding="utf-8") as f: return json.load(f).get("contents", [])
    except json.JSONDecodeError: return []

def save_contents(contents):
    with CONTENTS_FILE.open("w", encoding="utf-8") as f:
        json.dump({"contents": contents}, f, ensure_ascii=False, indent=2)

def create_content(title, category, content_text, image_url="", author="admin", status="已發佈"):
    contents = load_contents()
    new_content = {
        "id": str(uuid.uuid4()), "title": title, "category": category,
        "content": content_text, "image_url": image_url, "author": author,
        "status": status, "created_at": str(uuid.uuid4().hex[:8])
    }
    contents.append(new_content)
    save_contents(contents)
    return new_content

def delete_content(content_id):
    contents = [c for c in load_contents() if c["id"] != content_id]
    save_contents(contents)

def get_content(content_id):
    for content in load_contents():
        if content["id"] == content_id: return content
    return None

def update_content(content_id, title=None, category=None, content_text=None, image_url=None, status=None):
    contents = load_contents()
    for content in contents:
        if content["id"] == content_id:
            if title is not None: content["title"] = title
            if category is not None: content["category"] = category
            if content_text is not None: content["content"] = content_text
            if image_url is not None: content["image_url"] = image_url
            if status is not None: content["status"] = status
            break
    save_contents(contents)

# --- Announcements ---
def load_announcements():
    if not ANNOUNCEMENTS_FILE.exists(): return []
    try:
        with ANNOUNCEMENTS_FILE.open("r", encoding="utf-8") as f: return json.load(f).get("announcements", [])
    except json.JSONDecodeError: return []

def save_announcements(announcements):
    with ANNOUNCEMENTS_FILE.open("w", encoding="utf-8") as f:
        json.dump({"announcements": announcements}, f, ensure_ascii=False, indent=2)

def create_announcement(title, announcement_text, priority="普通", status="已發佈"):
    announcements = load_announcements()
    new_announcement = {
        "id": str(uuid.uuid4()), "title": title, "content": announcement_text,
        "priority": priority, "status": status, "created_at": str(uuid.uuid4().hex[:8])
    }
    announcements.append(new_announcement)
    save_announcements(announcements)
    return new_announcement

def delete_announcement(announcement_id):
    announcements = [a for a in load_announcements() if a["id"] != announcement_id]
    save_announcements(announcements)

def get_announcement(announcement_id):
    for announcement in load_announcements():
        if announcement["id"] == announcement_id: return announcement
    return None

def update_announcement(announcement_id, title=None, announcement_text=None, priority=None, status=None):
    announcements = load_announcements()
    for announcement in announcements:
        if announcement["id"] == announcement_id:
            if title is not None: announcement["title"] = title
            if announcement_text is not None: announcement["content"] = announcement_text
            if priority is not None: announcement["priority"] = priority
            if status is not None: announcement["status"] = status
            break
    save_announcements(announcements)

# ==========================================
# AI 模型與輔助功能
# ==========================================
AI_MODEL_NAME = "ChatAssist GPT"
AI_MODEL_ENGINE = "GPT-Assist-2.0"
WELFARE_BUDGET_REFERENCE = {
    "個人補助": "依據各地方社會局公告標準",
    "團體申請": "年度預算上限 50-100 萬元",
    "特殊個案": "由審議委員會推案至年度追加預算"
}

AI_AGENTS = [
    {"name": "企劃師小智", "description": "專注策略、落地執行與協調資源，適合需要具體方案的個案。"},
    {"name": "社服諮詢官", "description": "擅長需求分析與風險檢視，適合有情緒、家庭或心理層面議題的個案。"},
    {"name": "資源協調員", "description": "側重整合在地支持與長期追蹤，適合希望建立持續支持網絡的個案。"}
]

def choose_ai_agent(background, issues):
    combined = (background + " " + issues).lower()
    if any(keyword in combined for keyword in ["家庭", "親子", "孩童", "青少", "情緒", "心理"]): return AI_AGENTS[1]
    if any(keyword in combined for keyword in ["工作", "就業", "收入", "經濟", "社區"]): return AI_AGENTS[2]
    return AI_AGENTS[0]

def polish_text(text):
    if not text: return ""
    cleaned = " ".join(text.replace("\n", " ").replace("　", " ").split())
    replacements = {"很": "非常", "有點": "稍微", "幫忙": "協助", "要": "應", "可以": "可", "就": "", "會": "將", "還有": "此外", "如果": "若", "這樣": "如此", "問題": "議題", "成果": "成效", "影響": "影響因素", "比較": "較", "但": "然而", "而且": "並且", "不是": "非", "所需": "需要"}
    for old, new in replacements.items(): cleaned = cleaned.replace(old, new)
    cleaned = cleaned.strip()
    if cleaned and cleaned[-1] not in "。！？": cleaned += "。"
    return cleaned

def is_informal(text):
    informal_tokens = ["就", "很", "有點", "超", "ok", "haha", "哈哈", "ㄎ", "差不多", "隨便", "可能", "大概"]
    return any(token in text.lower() for token in informal_tokens)

def summarize_input(label, content):
    if not content: return ""
    templates = ["{label}重點為：{content}", "{label}描述了：{content}", "此段說明了{content}", "本段內容指出：{content}"]
    return random.choice(templates).format(label=label, content=content)


def _normalize_text(value):
    return " ".join(str(value or "").split())


def _build_chat_system_prompt(subsidy_summary=""):
    prompt = (
        "你是社區計畫補助企劃書的對話優化助理，協助里辦公處人員修改社區照顧與長者活動計畫的企劃書內容。"
        "請以正式、公文式、可送件的語氣回覆，內容具體、分段清楚，避免口語化與重複。"
        "企劃書章節依序為：一、計畫緣起；二、問題分析；三、計畫目標；四、服務對象；"
        "五、執行方式；六、預期效益；七、經費概算；八、風險與因應。"
        "使用者提供草稿時，請直接給出修改後的段落；資訊不足時，請具體指出需補充的項目（如服務人數、期程、成效指標、經費項目）。"
        "不可捏造統計數據、法規條文或補助金額。"
    )
    summary = _normalize_text(subsidy_summary)
    if summary:
        prompt += f"\n\n本次申請之補助資訊如下，請讓建議內容符合其補助目的與申請資格：{summary}"
    return prompt


def _fallback_proposal(title, background, issues, goals):
    sections = [
        f"計畫名稱：{_normalize_text(title) or '未命名計畫'}",
        "一、計畫緣起",
        _normalize_text(background) or "請補充組織背景、服務脈絡與本計畫推動原因。",
        "二、問題分析",
        _normalize_text(issues) or "請補充服務對象目前面臨的主要問題與需求。",
        "三、計畫目標",
        _normalize_text(goals) or "請補充本計畫欲達成的具體目標與預期成效。",
        "四、服務對象",
        "請補充年齡層、身份背景、服務規模與選案依據。",
        "五、執行方式",
        "請依服務流程、分工、資源配置與期程進一步撰寫。",
        "六、預期效益",
        "請補充量化與質化成果指標。",
        "七、經費概算",
        "請依實際補助規定拆分人事費、業務費與雜支。",
        "八、風險與因應",
        "請補充可能風險與對應措施。",
    ]
    return "\n".join(sections)


def request_openai_proposal(title, background, issues, goals):
    if openai_client is None:
        return None

    system_prompt = (
        "你是政府補助計畫書撰寫助手。請以正式、公文式、可送件的語氣撰寫，"
        "內容需穩定、分段清楚、避免口語化、避免重複，並優先使用使用者提供的資訊。"
        "請嚴格遵守下列格式要求：\n"
        "1. 以標題列出各章節，章節名稱需固定且一致。\n"
        "2. 每一章需有具體段落，避免只列點不說明。\n"
        "3. 內容必須補足計畫可送件所需的基本要素，不可留下空白章節。\n"
        "4. 語氣需正式、穩定、客觀，避免宣傳式、聊天式或推測式語句。"
    )
    user_prompt = (
        f"計畫名稱：{_normalize_text(title)}\n"
        f"計畫背景：{_normalize_text(background)}\n"
        f"主要問題：{_normalize_text(issues)}\n"
        f"計畫目標：{_normalize_text(goals)}\n\n"
        "請輸出完整企劃草案，並嚴格依下列章節順序撰寫：\n"
        "一、計畫緣起\n"
        "二、問題分析\n"
        "三、計畫目標\n"
        "四、服務對象\n"
        "五、執行方式\n"
        "六、預期效益\n"
        "七、經費概算\n"
        "八、風險與因應\n\n"
        "請保持章節順序固定、標題格式一致、每段內容完整且可直接作為送件初稿。"
    )

    try:
        completion = openai_client.chat.completions.create(
            model=AI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=1400,
        )
        content = completion.choices[0].message.content
        return content.strip() if content else None
    except Exception:
        return None


def generate_case_proposal(title, background, issues, goals, agent_name):
    response = request_openai_proposal(title, background, issues, goals)
    if response:
        return response
    return _fallback_proposal(title, background, issues, goals)

def build_assistant_messages(user_input, history, subsidy_summary=""):
    messages = [{"role": "system", "content": _build_chat_system_prompt(subsidy_summary)}]
    for item in history:
        role = item.get("role", "user")
        content = _normalize_text(item.get("content", ""))
        if content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": _normalize_text(user_input)})
    return messages


def _chat_fallback_response(user_input, history):
    lower_text = _normalize_text(user_input).lower()
    if any(token in lower_text for token in ["服務對象", "族群", "對象", "受眾"]):
        return "請先明確列出服務對象的年齡層、身份背景與目前面臨的困難，這樣後續目標與服務方法會更精準。"
    if any(token in lower_text for token in ["目標", "預期", "成效", "成果", "指標"]):
        return "成果指標建議分成數量、品質與時程三類，例如服務人次、滿意度、改善率與完成期限。"
    if any(token in lower_text for token in ["預算", "經費", "費用", "成本"]):
        return "經費規劃可先拆成人事費、業務費與雜支，再依補助規定補上金額與比例。"
    if any(token in lower_text for token in ["風險", "困難", "挑戰", "問題"]):
        return "風險可先從人力、經費、對象參與與執行期程四個面向整理，再為每項安排對應措施。"
    if any(token in lower_text for token in ["時程", "期程", "多久", "期限"]):
        return "常見做法是分成籌備期、執行期與評估期三段，並標示每一階段的月數與主要工作。"
    if any(token in lower_text for token in ["補助", "申請", "案件", "方案"]):
        return "請提供補助名稱、申請期限與服務重點，我可以幫您把內容整理成更接近正式送件格式。"
    if len(history) < 4:
        return "您好，請先簡單說明組織背景、服務族群與申請目的，我會依序幫您補齊企劃內容。"
    return "請補充目前可運用的資源、服務方式與期望成效，我會協助整理成更完整的企劃書。"


def generate_chat_response(user_input, history, subsidy_summary=""):
    normalized_input = _normalize_text(user_input)
    if not normalized_input:
        return "請先輸入要優化的內容，我會協助整理成正式企劃語氣。"

    if openai_client is None:
        return _chat_fallback_response(normalized_input, history)

    try:
        completion = openai_client.chat.completions.create(
            model=AI_MODEL,
            messages=build_assistant_messages(normalized_input, history, subsidy_summary),
            temperature=0.35,
            max_tokens=900,
        )
        content = completion.choices[0].message.content
        if not content:
            return _chat_fallback_response(normalized_input, history)
        return polish_text(content.strip())
    except Exception:
        return _chat_fallback_response(normalized_input, history)

# ==========================================
# 路由 (Routes) - 基礎認證與個人設定
# ==========================================
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/services")
def service_introduction():
    services = load_services()
    return render_template("services.html", services=services)

@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        role = request.form.get("role", "user")
        admin_code = request.form.get("admin_code", "")

        if not username or not password: error = "請輸入帳號與密碼。"
        elif password != confirm_password: error = "密碼與確認密碼不一致。"
        elif find_user(username): error = "此帳號已存在，請改用其他帳號名稱。"
        elif role == "admin" and admin_code != ADMIN_REG_CODE: error = "管理者註冊代碼不正確。"
        else:
            create_user(username, password, role)
            session["username"] = username
            session["role"] = role
            if role == "admin": return redirect(url_for("admin_dashboard"))
            return redirect(url_for("user_dashboard"))
    return render_template("register.html", error=error)

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = find_user(username)

        if not username or not password: error = "請輸入帳號與密碼。"
        elif not user: error = "使用者不存在，請先註冊。"
        elif user["password"] != hash_password(password): error = "帳號或密碼錯誤。"
        else:
            session["username"] = username
            session["role"] = user["role"]
            if user["role"] == "admin": return redirect(url_for("admin_dashboard"))
            return redirect(url_for("user_dashboard"))
    return render_template("login.html", error=error)

@app.route("/select/<role>")
def select_role(role):
    if role not in ("user", "admin"): return render_template("unauthorized.html"), 400
    session["role"] = role
    if role == "admin": return redirect(url_for("admin_dashboard"))
    return redirect(url_for("user_dashboard"))

@app.route("/logout")
def logout():
    session.pop("role", None)
    session.pop("username", None)
    return redirect(url_for("home"))

@app.route("/user/profile", methods=["GET", "POST"])
def user_profile():
    if session.get("role") != "user": return redirect(url_for("home"))
    username = session.get("username")
    user = find_user(username)
    if not user: return redirect(url_for("home"))

    error = None; success = None
    profile = get_user_profile(username)
    if request.method == "POST" and request.form.get("action") == "password":
        current = request.form.get("current_password", "")
        new = request.form.get("new_password", "")
        if user["password"] != hash_password(current): error = "目前密碼不正確。"
        elif len(new) < 6: error = "新密碼至少需 6 個字元。"
        elif new != request.form.get("confirm_password", ""): error = "兩次輸入的新密碼不一致。"
        else:
            update_user_password(username, new)
            success = "密碼已更新。"
    elif request.method == "POST":
        profile = {k: request.form.get(k, "").strip() for k in PROFILE_FIELDS}
        missing = [k for k in PROFILE_REQUIRED if not profile[k]]
        if missing:
            error = "請填寫聯絡人姓名、手機、長者姓名與所在區域。"
        else:
            update_user_profile(username, profile)
            success = "已儲存長者與聯絡人資料，之後填寫需求時會自動帶入。"

    filled = sum(1 for k in PROFILE_FIELDS if k not in ("email", "care_notes") and profile.get(k))
    completeness = round(filled / (len(PROFILE_FIELDS) - 2) * 100)
    return render_template("profile.html", username=username, profile=profile, completeness=completeness,
                           success=success, error=error, relations=RELATIONS, age_groups=AGE_GROUPS,
                           districts=DISTRICTS, household_statuses=HOUSEHOLD_STATUSES, care_levels=CARE_LEVELS)

# ==========================================
# 路由 (Routes) - 使用者功能 (提案與 AI 對話)
# ==========================================
@app.route("/user")
def user_dashboard():
    if session.get("role") != "user": return redirect(url_for("home"))
    username = session.get("username")
    my_requests = get_user_help_requests(username)
    stats = {
        "pending": sum(1 for r in my_requests if r.get("status") in ("待處理", "已申請", "處理中")),
        "arranged": sum(1 for r in my_requests if r.get("status") in ("已安排", "已完成")),
        "activities": sum(1 for r in load_registrations() if r.get("username") == username),
    }
    return render_template("user.html", username=username, stats=stats)


@app.route("/user/help-request", methods=["GET", "POST"])
def user_help_request():
    if session.get("role") != "user":
        return redirect(url_for("home"))

    error = None
    if request.method == "POST":
        need_type = request.form.get("need_type", "").strip()
        need_when = request.form.get("need_when", "").strip()
        location = request.form.get("location", "").strip()
        duration = request.form.get("duration", "").strip()
        details = request.form.get("details", "").strip()
        contact_name = request.form.get("contact_name", "").strip()
        contact_phone = request.form.get("contact_phone", "").strip()
        elder_name = request.form.get("elder_name", "").strip()
        age_group = request.form.get("age_group", "").strip()
        district = request.form.get("district", "").strip()
        urgency = request.form.get("urgency", "一般").strip()
        household_status = request.form.get("household_status", "").strip()
        care_level = request.form.get("care_level", "").strip()

        if not need_type or not need_when or not location or not district:
            error = "請填寫需求類型、時間、地點與所在區域，才能提交需求。"
        else:
            created = create_help_request(
                username=session.get("username"),
                need_type=need_type,
                need_when=need_when,
                location=location,
                duration=duration or "依需求安排",
                details=details,
                contact_name=contact_name or elder_name or "家屬",
                contact_phone=contact_phone,
                elder_name=elder_name,
                age_group=age_group,
                district=district,
                urgency=urgency,
                household_status=household_status,
                care_level=care_level,
            )
            return redirect(url_for("user_service_matches") + f"?request_id={created['id']}")

    return render_template("user_help_request_form.html", username=session.get("username"), choices=NEED_TYPES,
                           districts=DISTRICTS, age_groups=AGE_GROUPS, household_statuses=HOUSEHOLD_STATUSES,
                           care_levels=CARE_LEVELS, profile=get_user_profile(session.get("username")),
                           form=request.form if request.method == "POST" else {}, error=error)


@app.route("/user/service-matches")
def user_service_matches():
    if session.get("role") != "user":
        return redirect(url_for("home"))

    username = session.get("username")
    selected_request = get_help_request(request.args.get("request_id", ""))
    if not selected_request or selected_request.get("username") != username:
        return redirect(url_for("user_help_requests"))
    return render_template(
        "user_service_matches.html",
        username=username,
        selected_request=selected_request,
        matches=get_help_request_matches(selected_request),
    )


@app.route("/user/help-requests")
def user_help_requests():
    if session.get("role") != "user":
        return redirect(url_for("home"))

    requests = get_user_help_requests(session.get("username"))
    return render_template(
        "user_help_requests.html",
        username=session.get("username"),
        requests=requests,
    )


@app.route("/user/help-requests/<request_id>/apply/<service_id>", methods=["POST"])
def user_apply_service(request_id, service_id):
    if session.get("role") != "user":
        return redirect(url_for("home"))

    request_item = get_help_request(request_id)
    if request_item and request_item.get("username") == session.get("username"):
        apply_help_request_service(request_id, service_id)
    return redirect(url_for("user_help_requests"))


@app.route("/admin/help-requests")
def admin_help_requests():
    if session.get("role") != "admin":
        return redirect(url_for("home"))

    requests = load_help_requests()
    service_options = load_services()
    profiles = {r.get("username"): get_user_profile(r.get("username")) for r in requests}
    return render_template("admin_help_requests.html", username=session.get("username"), requests=requests,
                           service_options=service_options, profiles=profiles)


@app.route("/admin/help-requests/<request_id>/status", methods=["POST"])
def admin_update_help_request_status(request_id):
    if session.get("role") != "admin":
        return redirect(url_for("home"))

    status = request.form.get("status", "待處理").strip()
    admin_note = request.form.get("admin_note", "").strip()
    assigned_service = request.form.get("assigned_service", "").strip()
    assigned_unit = request.form.get("assigned_unit", "").strip()
    update_help_request_status(request_id, status, admin_note, assigned_service, assigned_unit)
    return redirect(url_for("admin_help_requests"))


@app.route("/admin/proposal/download")
def download_proposal():
    if session.get("role") != "admin": return redirect(url_for("home"))
    proposal = session.get("last_proposal")
    if not proposal: return redirect(url_for("admin_proposal"))
    return Response(proposal, mimetype="text/plain; charset=utf-8", headers={"Content-Disposition": "attachment; filename=proposal.txt"})

@app.route("/admin/proposal/download/<int:idx>")
def download_proposal_index(idx):
    if session.get("role") != "admin": return redirect(url_for("home"))
    history = session.get('proposal_history', [])
    if not history or idx < 0 or idx >= len(history): return redirect(url_for('admin_proposal'))
    text = history[idx]
    filename = request.args.get('filename', f"proposal_{idx+1}.txt").strip()
    try: filename = secure_filename(filename)
    except: pass
    return Response(text, mimetype="text/plain; charset=utf-8", headers={"Content-Disposition": f"attachment; filename={filename}"})

@app.route("/admin/assistant", methods=["GET", "POST"])
def admin_assistant():
    if session.get("role") != "admin": return redirect(url_for("home"))
    subsidy_summary = request.values.get("subsidy_summary", "").strip()

    if request.args.get("save_history") == "1":
        chat_history = session.get('chat_history', [])
        editing_idx = session.get('editing_conversation_idx')
        if chat_history:
            ts = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
            convs = session.get('conversation_history', [])
            if editing_idx is not None and editing_idx < len(convs):
                convs[editing_idx]['chat'] = chat_history
                convs[editing_idx]['timestamp'] = ts
            else:
                conv_id = str(uuid.uuid4())[:8]
                conv_name = "未命名對話"
                for msg in chat_history:
                    if msg.get('role') == 'user':
                        preview = msg.get('content', '')[:40]
                        if preview: conv_name = preview; break
                convs.insert(0, {'id': conv_id, 'name': conv_name, 'timestamp': ts, 'chat': chat_history, 'proposal_idx': None})
            session['conversation_history'] = convs[:20]
        session['chat_history'] = []
        session['editing_conversation_idx'] = None
        chat_history = []
    else:
        chat_history = session.get("chat_history", [])

    if request.method == "POST":
        user_input = request.form.get("user_input", "").strip()
        subsidy_summary = request.form.get("subsidy_summary", subsidy_summary).strip()
        if user_input:
            assistant_response = generate_chat_response(user_input, chat_history, subsidy_summary)
            chat_history.append({"role": "user", "content": user_input})
            chat_history.append({"role": "assistant", "content": assistant_response})
            session["chat_history"] = chat_history

    return render_template("assistant.html", username=session.get("username"), chat_history=chat_history, subsidy_summary=subsidy_summary)

@app.route('/api/generate-proposal', methods=['POST'])
def api_generate_proposal():
    """API 端點：生成企劃書"""
    if session.get('role') != 'admin': 
        return jsonify({'status': 'error', 'message': '權限不足'}), 403
    
    try:
        # 處理 FormData - 使用正確的表單字段名稱
        project_name = (request.form.get('project_name') or '').strip()
        background = (request.form.get('background') or '').strip()
        goals = (request.form.get('goals') or '').strip()
        activities = (request.form.get('activities') or '').strip()
        org_name = (request.form.get('org_name') or '').strip()
        target_people = (request.form.get('target_people') or '').strip()
        
        # 解析預算和時程 JSON 數據
        budget_json_str = request.form.get('budget_items_json', '[]')
        timeline_json_str = request.form.get('timeline_json', '[]')
        
        try:
            budget_items = json.loads(budget_json_str) if budget_json_str else []
        except:
            budget_items = []
        
        try:
            timeline_items = json.loads(timeline_json_str) if timeline_json_str else []
        except:
            timeline_items = []
        
        if not project_name or not background:
            return jsonify({'status': 'error', 'message': '請輸入計畫名稱與需求背景'}), 400
        
        # 組合問題敘述
        issues = target_people or "尚待補充具體目標族群。"
        
        agent = choose_ai_agent(background, issues)
        ai_agent = agent["name"]
        proposal = generate_case_proposal(
            project_name, 
            background, 
            issues, 
            goals or "尚待補充具體目標與預期成效。", 
            ai_agent
        )
        
        # 添加預算表格：新版表單使用 name / amount / note，不再用舊版 qty / price。
        budget_html = ""
        clean_budget_items = []
        for item in budget_items:
            name = (item.get('name') or item.get('description') or '').strip()
            note = (item.get('note') or '').strip()
            try:
                amount = int(float(item.get('amount') or 0))
            except (TypeError, ValueError):
                amount = 0
            if name and amount > 0:
                clean_budget_items.append({'name': name, 'note': note, 'amount': amount})

        if clean_budget_items:
            total = sum(item['amount'] for item in clean_budget_items)
            budget_html = "<h4 style='margin-top: 24px;'>預算表</h4>"
            budget_html += "<table class='budget-table' style='width: 100%; border-collapse: collapse; margin: 12px 0;'>"
            budget_html += "<thead><tr style='background: #e8f5f0;'><th style='padding: 10px; border: 1px solid #ddd; text-align: left;'>經費項目</th><th style='padding: 10px; border: 1px solid #ddd; text-align: left;'>用途說明</th><th style='padding: 10px; border: 1px solid #ddd; text-align: right;'>金額</th></tr></thead><tbody>"
            for item in clean_budget_items:
                budget_html += (
                    "<tr>"
                    f"<td style='padding: 10px; border: 1px solid #ddd;'>{escape(item['name'])}</td>"
                    f"<td style='padding: 10px; border: 1px solid #ddd;'>{escape(item['note'] or '—')}</td>"
                    f"<td style='padding: 10px; border: 1px solid #ddd; text-align: right;'>NT$ {item['amount']:,}</td>"
                    "</tr>"
                )
            budget_html += f"<tr class='budget-total' style='background: #f0f7f4; font-weight: bold;'><td colspan='2' style='padding: 10px; border: 1px solid #ddd;'>合計</td><td style='padding: 10px; border: 1px solid #ddd; text-align: right;'>NT$ {total:,}</td></tr>"
            budget_html += "</tbody></table>"
        
        # 添加甘特圖：使用月尺度表格，避免日尺度長表格撐破結果視窗。
        gantt_html = ""
        if timeline_items:
            from datetime import datetime
            
            valid_items = []
            for item in timeline_items:
                start_str = item.get('start_date') or item.get('start')
                end_str = item.get('end_date') or item.get('end')
                title = (item.get('title') or item.get('name') or '').strip()
                if not title or not start_str or not end_str:
                    continue
                try:
                    start_dt = datetime.strptime(start_str, '%Y-%m-%d')
                    end_dt = datetime.strptime(end_str, '%Y-%m-%d')
                except ValueError:
                    continue
                if end_dt < start_dt:
                    continue
                try:
                    progress = max(0, min(100, int(float(item.get('progress') or 0))))
                except (TypeError, ValueError):
                    progress = 0
                valid_items.append({
                    'title': title,
                    'owner': (item.get('owner') or '未填負責人').strip(),
                    'start': start_dt,
                    'end': end_dt,
                    'progress': progress
                })
            
            if valid_items:
                today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                min_date = min(item['start'] for item in valid_items)
                max_date = max(item['end'] for item in valid_items)
                months = []
                cursor = datetime(min_date.year, min_date.month, 1)
                last = datetime(max_date.year, max_date.month, 1)
                while cursor <= last and len(months) < 24:
                    months.append(cursor)
                    cursor = datetime(cursor.year + (1 if cursor.month == 12 else 0), 1 if cursor.month == 12 else cursor.month + 1, 1)

                def month_end(month_dt):
                    next_month = datetime(month_dt.year + (1 if month_dt.month == 12 else 0), 1 if month_dt.month == 12 else month_dt.month + 1, 1)
                    return next_month - datetime.resolution

                def item_status(item):
                    if item['end'] < today or item['progress'] >= 100:
                        return ('done', '已完成')
                    if item['start'] > today and item['progress'] == 0:
                        return ('planned', '未開始')
                    return ('active', '進行中')

                gantt_html = "<h4 style='margin-top: 24px;'>甘特圖（專案進度時程表）</h4>"
                gantt_html += "<div class='gantt-legend'><span class='legend-item legend-done'>已完成</span><span class='legend-item legend-active'>進行中</span><span class='legend-item legend-planned'>未開始</span></div>"
                gantt_html += "<div class='gantt-scroll' style='max-width: 100%; overflow-x: auto; border: 1px solid #ddd; border-radius: 10px; margin: 12px 0;'>"
                gantt_html += "<table class='gantt-table' style='width: 100%; min-width: 720px; border-collapse: collapse; font-size: 12px;'>"
                gantt_html += "<thead><tr style='background: #e8f5f0;'>"
                gantt_html += "<th style='padding: 8px; border: 1px solid #ddd; text-align: left; min-width: 150px;'>工作項目</th>"
                gantt_html += "<th style='padding: 8px; border: 1px solid #ddd; min-width: 90px;'>負責人</th>"
                gantt_html += "<th style='padding: 8px; border: 1px solid #ddd; min-width: 80px;'>狀態</th>"
                gantt_html += "<th style='padding: 8px; border: 1px solid #ddd; min-width: 90px;'>完成度</th>"
                for month in months:
                    gantt_html += f"<th style='padding: 8px; border: 1px solid #ddd; text-align: center; min-width: 78px;'>{month.year}/{month.month:02d}</th>"
                gantt_html += "</tr></thead><tbody>"

                for item in valid_items:
                    status_key, status_label = item_status(item)
                    gantt_html += "<tr>"
                    gantt_html += f"<td style='padding: 8px; border: 1px solid #ddd;'><strong>{escape(item['title'])}</strong><br><small>{item['start'].strftime('%Y/%m/%d')} - {item['end'].strftime('%Y/%m/%d')}</small></td>"
                    gantt_html += f"<td style='padding: 8px; border: 1px solid #ddd; text-align: center;'>{escape(item['owner'])}</td>"
                    gantt_html += f"<td class='gantt-{status_key}' style='padding: 8px; border: 1px solid #ddd; text-align: center; font-weight: 700;'>{status_label}</td>"
                    gantt_html += (
                        "<td style='padding: 8px; border: 1px solid #ddd; text-align: center;'>"
                        f"<div style='height: 8px; background: #edf1ee; border-radius: 999px; overflow: hidden; margin-bottom: 4px;'><div style='width: {item['progress']}%; height: 8px; background: #1a7a5e;'></div></div>"
                        f"{item['progress']}%</td>"
                    )
                    for month in months:
                        active = item['start'] <= month_end(month) and item['end'] >= month
                        cell_class = f"gantt-{status_key}" if active else "gantt-empty"
                        label = "■" if active else ""
                        gantt_html += f"<td class='{cell_class}' style='padding: 8px; border: 1px solid #ddd; text-align: center;'>{label}</td>"
                    gantt_html += "</tr>"

                total_days = (max_date - min_date).days + 1
                gantt_html += "</tbody></table></div>"
                gantt_html += f"<p style='margin-top: 12px; font-size: 12px; color: #666;'>計畫期間：<strong>{min_date.strftime('%Y年%m月%d日')} 至 {max_date.strftime('%Y年%m月%d日')}</strong>，共 {total_days} 天。</p>"
            else:
                gantt_html += "<p style='color: #999;'>時程資料為空，請至少新增一項完整的時程項目。</p>"
        
        # 組合完整的 HTML 內容
        full_html = proposal.replace('\n', '<br>') + budget_html + gantt_html
        
        # 保存到 session
        session["last_proposal"] = proposal
        history = session.get('proposal_history', [])
        history.insert(0, proposal)
        session['proposal_history'] = history[:10]
        
        # 返回前端期望的格式
        return jsonify({
            'status': 'success',
            'html_content': full_html,
            'template_filename': None,
            'gantt_included': bool(timeline_items),
            'message': '企劃書生成成功'
        })
    except Exception as err:
        import traceback
        error_detail = traceback.format_exc()
        print(f"API 錯誤: {error_detail}")
        return jsonify({
            'status': 'error', 
            'message': f'生成失敗: {str(err)[:100]}'
        }), 500

@app.route('/api/chat', methods=['POST'])
def api_chat():
    if session.get('role') != 'admin': return jsonify({'error': '權限不足'}), 403
    data = request.get_json() or {}
    user_message = (data.get('message') or '').strip()
    if not user_message: return jsonify({'error': 'empty message'}), 400
    subsidy_summary = session.get('last_subsidy_summary', '') or request.args.get('subsidy_summary', '')
    chat_history = session.get('chat_history', [])
    assistant_response = generate_chat_response(user_message, chat_history, subsidy_summary)
    chat_history.append({'role': 'user', 'content': user_message})
    chat_history.append({'role': 'assistant', 'content': assistant_response})
    session['chat_history'] = chat_history
    return jsonify({'reply': assistant_response})

@app.route("/admin/assistant/export")
def assistant_export():
    if session.get("role") != "admin": return redirect(url_for("home"))
    chat_history = session.get("chat_history", [])
    subsidy_summary = request.args.get("subsidy_summary", "").strip()
    lines = []
    if subsidy_summary: lines.extend([f"補助摘要：{subsidy_summary}", ""])
    if chat_history:
        for message in chat_history:
            role = "您" if message.get("role") == "user" else "助理"
            lines.extend([f"{role}：{message.get('content', '')}", ""])
    else:
        lines.append("尚無對話紀錄。")
    export_text = "\n".join(lines)
    return Response(export_text, mimetype="text/plain; charset=utf-8", headers={"Content-Disposition": "attachment; filename=assistant_export.txt"})

@app.route("/admin/assistant/import_proposal")
def assistant_import_proposal():
    if session.get("role") != "admin": return redirect(url_for("home"))
    proposal = session.get("last_proposal")
    subsidy_summary = request.args.get("subsidy_summary", "").strip()
    if not proposal: return redirect(url_for("admin_assistant", subsidy_summary=subsidy_summary))
    chat_history = session.get("chat_history", [])
    chat_history.append({"role": "assistant", "content": f"初步企劃草稿：\n\n{proposal}"})
    session["chat_history"] = chat_history
    return redirect(url_for("admin_assistant", subsidy_summary=subsidy_summary))

@app.route("/admin/assistant/export_selected")
def assistant_export_selected():
    if session.get("role") != "admin": return redirect(url_for("home"))
    idx_list = request.args.getlist('idx')
    subsidy_summary = request.args.get("subsidy_summary", "").strip()
    chat_history = session.get("chat_history", [])
    if not idx_list: return redirect(url_for('assistant_export', subsidy_summary=subsidy_summary))
    lines = []
    if subsidy_summary: lines.extend([f"補助摘要：{subsidy_summary}", ""])
    for idx_str in idx_list:
        try: idx = int(idx_str)
        except ValueError: continue
        if 0 <= idx < len(chat_history):
            m = chat_history[idx]
            role = "您" if m.get('role') == 'user' else '助理'
            lines.extend([f"{role}：{m.get('content','')}", ""])
    if not lines: lines = ["未找到選取的訊息。"]
    filename = request.args.get('filename', 'assistant_selected.txt').strip()
    try: filename = secure_filename(filename)
    except: pass
    return Response("\n".join(lines), mimetype="text/plain; charset=utf-8", headers={"Content-Disposition": f"attachment; filename={filename}"})

@app.route('/admin/assistant/load_conversation/<int:idx>')
def load_conversation(idx):
    if session.get('role') != 'admin': return redirect(url_for('home'))
    convs = session.get('conversation_history', [])
    if not convs or idx < 0 or idx >= len(convs): return redirect(url_for('admin_assistant'))
    session['chat_history'] = convs[idx].get('chat', [])
    session['editing_conversation_idx'] = idx
    session['editing_proposal_idx'] = convs[idx].get('proposal_idx')
    return redirect(url_for('admin_assistant'))

@app.route('/admin/assistant/download_conversation/<int:idx>')
def download_conversation(idx):
    if session.get('role') != 'admin': return redirect(url_for('home'))
    convs = session.get('conversation_history', [])
    if not convs or idx < 0 or idx >= len(convs): return redirect(url_for('admin_assistant'))
    conv = convs[idx]
    lines = [f"對話紀錄（{conv.get('timestamp','')})\n\n"]
    for m in conv.get('chat', []):
        role = '您' if m.get('role') == 'user' else '助理'
        lines.extend([f"{role}：{m.get('content','')}", ""])
    filename = request.args.get('filename', f"conversation_{idx+1}.txt").strip()
    try: filename = secure_filename(filename)
    except: pass
    return Response("\n".join(lines), mimetype='text/plain; charset=utf-8', headers={"Content-Disposition": f"attachment; filename={filename}"})

@app.route('/admin/assistant/rename_conversation/<int:idx>', methods=['POST'])
def rename_conversation(idx):
    if session.get('role') != 'admin': return jsonify({'error': '權限不足'}), 403
    data = request.get_json() or {}
    new_name = (data.get('name') or '').strip()
    if not new_name: return jsonify({'error': '名稱不能為空'}), 400
    convs = session.get('conversation_history', [])
    if not convs or idx < 0 or idx >= len(convs): return jsonify({'error': '對話不存在'}), 404
    convs[idx]['name'] = new_name
    session['conversation_history'] = convs
    session.modified = True
    return jsonify({'success': True, 'name': new_name})

@app.route('/admin/assistant/from_proposal/<int:idx>')
def resume_conversation_from_proposal(idx):
    if session.get('role') != 'admin': return redirect(url_for('home'))
    proposals = session.get('proposal_history', [])
    if not proposals or idx < 0 or idx >= len(proposals): return redirect(url_for('admin_assistant'))
    session['chat_history'] = []
    session['last_proposal'] = proposals[idx]
    return redirect(url_for('admin_assistant'))

# ==========================================
# 路由 (Routes) - 補助資源清單
# ==========================================
@app.route("/welfare")
def welfare_page():
    if not session.get("username"): return redirect(url_for("home"))
    category = request.args.get("category", "")
    keyword = request.args.get("q", "").strip()
    return render_template("welfare.html", username=session.get("username"), items=search_welfare(category, keyword),
                           categories=WELFARE_CATEGORIES, selected_category=category, keyword=keyword)

@app.route("/welfare/<int:welfare_id>")
def welfare_detail(welfare_id):
    if not session.get("username"): return redirect(url_for("home"))
    item = get_welfare(welfare_id)
    if not item: return redirect(url_for("welfare_page"))
    return render_template("welfare_detail.html", username=session.get("username"), item=item)

# --- User: AI 福利小幫手 ---
def _welfare_context():
    lines = []
    for w in load_welfare():
        lines.append(f"【{w.get('title')}】類別：{w.get('category')}；主辦：{w.get('agency')}；資格：{w.get('eligibility')}；"
                     f"內容：{w.get('benefit')}；申請方式：{w.get('apply_method')}；聯絡：{w.get('contact')}")
    return "\n".join(lines)

def _welfare_fallback(question):
    """未啟用 OpenAI 時，以關鍵詞比對福利資料回覆。"""
    q = _normalize_text(question)
    synonyms = {"吃飯": "餐食", "煮飯": "備餐", "三餐": "餐食", "沒錢": "收入", "經濟": "收入", "行動不便": "失能",
                "走不動": "失能", "臥床": "失能", "公車": "大眾運輸", "捷運": "大眾運輸", "牙齒": "假牙", "跌倒": "緊急救援"}
    q += " " + " ".join(v for k, v in synonyms.items() if k in q)
    stop = {"申請", "可以", "什麼", "請問", "需要", "長者", "老人", "以上", "歲以", "我們", "家裡", "爸爸", "媽媽", "有沒", "沒有", "怎麼"}
    grams = {q[i:i + 2] for i in range(len(q) - 1) if all("一" <= ch <= "鿿" for ch in q[i:i + 2])} - stop
    scored = []
    for w in load_welfare():
        weighted = [(w.get("title", ""), 3), (w.get("eligibility", ""), 2), (w.get("category", ""), 2),
                    (f"{w.get('benefit', '')} {w.get('apply_method', '')}", 1)]
        score = sum(weight for g in grams for text, weight in weighted if g in text)
        if score: scored.append((score, w))
    scored.sort(key=lambda x: x[0], reverse=True)
    if not scored:
        return ("目前找不到與您問題直接相關的福利項目。建議先撥打長照專線 1966，或洽里辦公處、區公所社會課詢問；"
                "您也可以描述長者的年齡、是否獨居、身體狀況或經濟狀況，我會再幫您比對。")
    parts = ["依您的描述，以下福利可能適用（實際資格請以主管機關公告為準）："]
    for _, w in scored[:3]:
        parts.append(f"\n■ {w.get('title')}\n　資格：{w.get('eligibility')}\n　內容：{w.get('benefit')}\n　申請：{w.get('apply_method')}")
    return "\n".join(parts)

def generate_welfare_response(question, history):
    question = _normalize_text(question)
    if not question:
        return "請輸入想詢問的問題，例如：「我爸爸 70 歲獨居，可以申請什麼？」"
    if openai_client is None:
        return _welfare_fallback(question)
    system_prompt = (
        "你是里辦公處的「長者福利小幫手」，協助里內長者與家屬了解可申請的老人福利。"
        "請使用親切、簡單易懂的口語，句子簡短，適合長者閱讀。"
        "回答時優先引用下列福利資料，說明適用資格、內容與申請方式；資料沒有的內容不可捏造金額、法規或電話，"
        "並提醒實際資格以主管機關公告為準。若資訊不足，請詢問長者年齡、居住狀況、身體與經濟狀況。\n\n"
        f"福利資料：\n{_welfare_context()}"
    )
    messages = [{"role": "system", "content": system_prompt}]
    for item in history[-8:]:
        messages.append({"role": item.get("role", "user"), "content": _normalize_text(item.get("content", ""))})
    messages.append({"role": "user", "content": question})
    try:
        completion = openai_client.chat.completions.create(model=AI_MODEL, messages=messages, temperature=0.3, max_tokens=700)
        content = completion.choices[0].message.content
        return content.strip() if content else _welfare_fallback(question)
    except Exception:
        return _welfare_fallback(question)

@app.route("/user/welfare-assistant")
def user_welfare_assistant():
    if session.get("role") != "user": return redirect(url_for("home"))
    if request.args.get("clear") == "1":
        session["welfare_chat"] = []
        return redirect(url_for("user_welfare_assistant"))
    return render_template("welfare_assistant.html", username=session.get("username"),
                           chat=session.get("welfare_chat", []), preset=request.args.get("q", ""))

@app.route("/api/welfare-chat", methods=["POST"])
def api_welfare_chat():
    if session.get("role") != "user": return jsonify({"error": "權限不足"}), 403
    question = (request.get_json(silent=True) or {}).get("message", "")
    history = session.get("welfare_chat", [])
    answer = generate_welfare_response(question, history)
    history = (history + [{"role": "user", "content": _normalize_text(question)},
                          {"role": "assistant", "content": answer}])[-20:]
    session["welfare_chat"] = history
    return jsonify({"reply": answer})

# ==========================================
# 路由 (Routes) - 管理者後台 (Admin Dashboards)
# ==========================================
@app.route("/admin")
def admin_dashboard():
    if session.get("role") != "admin": return redirect(url_for("home"))
    
    # 計算統計數據
    # 活動總數
    activities = load_activities()
    activities_count = len(activities) if activities else 0
    
    # 註冊成員（non-admin）
    users = load_users()
    members_count = sum(1 for user in users if user.get("role") != "admin")
    
    # 待處理個案
    cases = load_cases()
    pending_cases_count = sum(1 for case in cases if case.get("status") == "待處理")
    
    # 系統公告
    announcements = load_announcements()
    announcements_count = len(announcements) if announcements else 0
    
    return render_template(
        "admin.html",
        username=session.get("username"),
        activities_count=activities_count,
        members_count=members_count,
        pending_cases_count=pending_cases_count,
        announcements_count=announcements_count
    )

@app.route("/admin/members")
def admin_members():
    if session.get("role") != "admin": return redirect(url_for("home"))
    return render_template("members.html", users=load_users(), username=session.get("username"))

@app.route("/admin/members/delete/<username>", methods=["POST"])
def admin_delete_member(username):
    if session.get("role") != "admin": return redirect(url_for("home"))
    if username == session.get("username"): return render_template("members.html", users=load_users(), username=session.get("username"), error="無法刪除目前登入帳號。")
    delete_user(username)
    return redirect(url_for("admin_members"))

@app.route("/admin/members/role/<username>", methods=["POST"])
def admin_change_member_role(username):
    if session.get("role") != "admin": return redirect(url_for("home"))
    new_role = request.form.get("new_role")
    if username == session.get("username"): return render_template("members.html", users=load_users(), username=session.get("username"), error="無法變更目前登入帳號的身分。")
    if new_role in ("user", "admin"): update_user_role(username, new_role)
    return redirect(url_for("admin_members"))

# --- Admin: Cases ---
@app.route("/admin/cases")
def admin_cases():
    if session.get("role") != "admin": return redirect(url_for("home"))
    return render_template("cases.html", cases=load_cases(), username=session.get("username"))

@app.route("/admin/cases/create", methods=["GET", "POST"])
def admin_create_case():
    if session.get("role") != "admin": return redirect(url_for("home"))
    error = None
    if request.method == "POST":
        case_name = request.form.get("case_name", "").strip()
        member_name = request.form.get("member_name", "").strip()
        issue_description = request.form.get("issue_description", "").strip()
        status = request.form.get("status", "進行中")
        if not case_name or not member_name: error = "請輸入個案名稱與成員名稱。"
        else:
            create_case(case_name, member_name, issue_description, status)
            return redirect(url_for("admin_cases"))
    return render_template("case_create.html", username=session.get("username"), error=error)

@app.route("/admin/cases/<case_id>/edit", methods=["GET", "POST"])
def admin_edit_case(case_id):
    if session.get("role") != "admin": return redirect(url_for("home"))
    case = get_case(case_id)
    if not case: return redirect(url_for("admin_cases"))
    error = None
    if request.method == "POST":
        case_name = request.form.get("case_name", "").strip()
        member_name = request.form.get("member_name", "").strip()
        issue_description = request.form.get("issue_description", "").strip()
        status = request.form.get("status", "進行中")
        if not case_name or not member_name: error = "請輸入個案名稱與成員名稱。"
        else:
            update_case(case_id, case_name, member_name, issue_description, status)
            return redirect(url_for("admin_cases"))
    return render_template("case_edit.html", case=case, username=session.get("username"), error=error)

@app.route("/admin/cases/<case_id>/delete", methods=["POST"])
def admin_delete_case(case_id):
    if session.get("role") != "admin": return redirect(url_for("home"))
    delete_case(case_id)
    return redirect(url_for("admin_cases"))

# --- User: Activities ---
@app.route("/user/activities")
def user_activities():
    if session.get("role") != "user": return redirect(url_for("home"))
    username = session.get("username")
    items = []
    for activity in load_activities():
        if activity.get("status") == "已取消": continue
        items.append({
            "activity": activity,
            "registration": get_user_registration(activity["id"], username),
            "attendance": get_user_attendance(activity["id"], username),
            "block_reason": registration_block_reason(activity, username),
        })
    return render_template("user_activities.html", username=username, items=items,
                           phone=get_user_profile(username).get("phone", ""))

@app.route("/user/activities/<activity_id>/register", methods=["POST"])
def user_register_activity(activity_id):
    if session.get("role") != "user": return redirect(url_for("home"))
    username = session.get("username")
    activity = get_activity(activity_id)
    if not activity: return redirect(url_for("user_activities"))
    reason = registration_block_reason(activity, username)
    if reason:
        flash(reason, "error")
    else:
        create_registration(activity_id, username, request.form.get("email", "").strip(), request.form.get("phone", "").strip())
        flash(f"已報名「{activity['activity_name']}」，待管理者審核通過後即可簽到。", "success")
    return redirect(url_for("user_activities"))

@app.route("/user/activities/<activity_id>/cancel", methods=["POST"])
def user_cancel_registration(activity_id):
    if session.get("role") != "user": return redirect(url_for("home"))
    reg = get_user_registration(activity_id, session.get("username"))
    if reg and reg.get("status") == "待審核":
        delete_registration(reg["id"])
        flash("已取消報名。", "success")
    else:
        flash("只有待審核的報名可以取消。", "error")
    return redirect(url_for("user_activities"))

@app.route("/user/activities/<activity_id>/checkin", methods=["POST"])
def user_check_in(activity_id):
    if session.get("role") != "user": return redirect(url_for("home"))
    username = session.get("username")
    reg = get_user_registration(activity_id, username)
    if not reg or reg.get("status") != "已通過":
        flash("報名審核通過後才可簽到。", "error")
    elif get_user_attendance(activity_id, username):
        flash("您已完成簽到。", "error")
    else:
        create_attendance(activity_id, username, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        flash("簽到成功！", "success")
    return redirect(url_for("user_activities"))

# --- Admin: Welfare ---
@app.route("/admin/welfare")
def admin_welfare():
    if session.get("role") != "admin": return redirect(url_for("home"))
    return render_template("admin_welfare.html", username=session.get("username"), items=load_welfare())

@app.route("/admin/welfare/create", methods=["GET", "POST"])
@app.route("/admin/welfare/<int:welfare_id>/edit", methods=["GET", "POST"])
def admin_welfare_form(welfare_id=None):
    if session.get("role") != "admin": return redirect(url_for("home"))
    items = load_welfare()
    item = next((w for w in items if w.get("id") == welfare_id), None) if welfare_id else {}
    if welfare_id and item is None: return redirect(url_for("admin_welfare"))
    error = None
    if request.method == "POST":
        data = welfare_from_form(request.form)
        if not data["title"] or not data["eligibility"] or not data["apply_method"]:
            error = "請填寫福利名稱、申請資格與申請方式。"
            item = {**item, **data}
        else:
            data["updated_at"] = datetime.date.today().isoformat()
            if welfare_id:
                item.update(data)
            else:
                data["id"] = max((w.get("id", 0) for w in items), default=0) + 1
                items.append(data)
            save_welfare(items)
            return redirect(url_for("admin_welfare"))
    return render_template("admin_welfare_form.html", username=session.get("username"), item=item,
                           categories=WELFARE_CATEGORIES, error=error)

@app.route("/admin/welfare/<int:welfare_id>/delete", methods=["POST"])
def admin_welfare_delete(welfare_id):
    if session.get("role") != "admin": return redirect(url_for("home"))
    save_welfare([w for w in load_welfare() if w.get("id") != welfare_id])
    return redirect(url_for("admin_welfare"))

# --- Admin: Proposal ---
@app.route("/admin/proposal")
def admin_proposal():
    if session.get("role") != "admin": return redirect(url_for("home"))
    return render_template("admin_proposal.html", username=session.get("username"),
                           page_title="社區計畫企劃書產生器", budget_reference=WELFARE_BUDGET_REFERENCE)

# --- Admin: Activities ---
@app.route("/admin/activities")
def admin_activities():
    if session.get("role") != "admin": return redirect(url_for("home"))
    registrations, attendances = load_registrations(), load_attendances()
    reg_counts = {a["id"]: sum(1 for r in registrations if r["activity_id"] == a["id"]) for a in load_activities()}
    att_counts = {a["id"]: sum(1 for t in attendances if t["activity_id"] == a["id"]) for a in load_activities()}
    return render_template("admin_activities.html", activities=load_activities(), reg_counts=reg_counts,
                           att_counts=att_counts, username=session.get("username"))

@app.route("/admin/activities/create", methods=["GET", "POST"])
def admin_create_activity():
    if session.get("role") != "admin": return redirect(url_for("home"))
    error = None
    if request.method == "POST":
        activity_name = request.form.get("activity_name", "").strip()
        description = request.form.get("description", "").strip()
        category = request.form.get("category", "其他")
        start_date = request.form.get("start_date", "")
        end_date = request.form.get("end_date", "")
        location = request.form.get("location", "").strip()
        max_capacity = request.form.get("max_capacity", "0")
        registration_deadline = request.form.get("registration_deadline", "")
        status = request.form.get("status", "進行中")
        if not activity_name: error = "請輸入活動名稱。"
        else:
            create_activity("admin", activity_name, description, category, start_date, end_date, location, max_capacity, registration_deadline, status)
            return redirect(url_for("admin_activities"))
    return render_template("admin_activity_create.html", username=session.get("username"), error=error)

@app.route("/admin/activities/<activity_id>/edit", methods=["GET", "POST"])
def admin_edit_activity(activity_id):
    if session.get("role") != "admin": return redirect(url_for("home"))
    activity = get_activity(activity_id)
    if not activity: return redirect(url_for("admin_activities"))
    error = None
    if request.method == "POST":
        activity_name = request.form.get("activity_name", "").strip()
        description = request.form.get("description", "").strip()
        category = request.form.get("category", "其他")
        start_date = request.form.get("start_date", "")
        end_date = request.form.get("end_date", "")
        location = request.form.get("location", "").strip()
        max_capacity = request.form.get("max_capacity", "0")
        registration_deadline = request.form.get("registration_deadline", "")
        status = request.form.get("status", "進行中")
        if not activity_name: error = "請輸入活動名稱。"
        else:
            update_activity(activity_id, activity_name, description, category, start_date, end_date, location, max_capacity, registration_deadline, status)
            return redirect(url_for("admin_activities"))
    return render_template("admin_activity_edit.html", activity=activity, username=session.get("username"), error=error)

@app.route("/admin/activities/<activity_id>/delete", methods=["POST"])
def admin_delete_activity(activity_id):
    if session.get("role") != "admin": return redirect(url_for("home"))
    delete_activity(activity_id)
    return redirect(url_for("admin_activities"))

@app.route("/admin/activities/<activity_id>/registrations")
def admin_activity_registrations(activity_id):
    if session.get("role") != "admin": return redirect(url_for("home"))
    activity = get_activity(activity_id)
    if not activity: return redirect(url_for("admin_activities"))
    checked_in = {a["username"] for a in get_activity_attendances(activity_id)}
    return render_template("admin_activity_registrations.html", activity=activity, registrations=get_activity_registrations(activity_id),
                           checked_in=checked_in, username=session.get("username"))

@app.route("/admin/registrations/<registration_id>/approve", methods=["POST"])
def admin_approve_registration(registration_id):
    if session.get("role") != "admin": return redirect(url_for("home"))
    update_registration_status(registration_id, "已通過")
    return redirect(request.referrer or url_for("admin_activities"))

@app.route("/admin/registrations/<registration_id>/reject", methods=["POST"])
def admin_reject_registration(registration_id):
    if session.get("role") != "admin": return redirect(url_for("home"))
    update_registration_status(registration_id, "已拒絕")
    return redirect(request.referrer or url_for("admin_activities"))

@app.route("/admin/registrations/<registration_id>/delete", methods=["POST"])
def admin_delete_registration(registration_id):
    if session.get("role") != "admin": return redirect(url_for("home"))
    delete_registration(registration_id)
    return redirect(request.referrer or url_for("admin_activities"))

@app.route("/admin/activities/<activity_id>/attendance")
def admin_activity_attendance(activity_id):
    if session.get("role") != "admin": return redirect(url_for("home"))
    activity = get_activity(activity_id)
    if not activity: return redirect(url_for("admin_activities"))
    attendances = get_activity_attendances(activity_id)
    checked_in = {a["username"] for a in attendances}
    pending = [r for r in get_activity_registrations(activity_id) if r.get("status") == "已通過" and r["username"] not in checked_in]
    return render_template("admin_activity_attendance.html", activity=activity, attendances=attendances,
                           pending=pending, username=session.get("username"))

@app.route("/admin/activities/<activity_id>/checkin", methods=["POST"])
def admin_check_in(activity_id):
    if session.get("role") != "admin": return redirect(url_for("home"))
    username = request.form.get("username", "").strip()
    if username and not get_user_attendance(activity_id, username):
        check_in_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        create_attendance(activity_id, username, check_in_time)
    return redirect(request.referrer or url_for("admin_activities"))

@app.route("/admin/attendances/<attendance_id>/checkout", methods=["POST"])
def admin_check_out(attendance_id):
    if session.get("role") != "admin": return redirect(url_for("home"))
    attendances = load_attendances()
    for att in attendances:
        if att["id"] == attendance_id:
            att["check_out_time"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            break
    save_attendances(attendances)
    return redirect(request.referrer or url_for("admin_activities"))

# --- Admin: Services ---
@app.route("/admin/services")
def admin_services():
    if session.get("role") != "admin": return redirect(url_for("home"))
    return render_template("admin_services.html", services=load_services(), username=session.get("username"))

@app.route("/admin/services/create", methods=["GET", "POST"])
def admin_create_service():
    if session.get("role") != "admin": return redirect(url_for("home"))
    error = None
    if request.method == "POST":
        service_name = request.form.get("service_name", "").strip()
        description = request.form.get("description", "").strip()
        service_type = request.form.get("service_type", "").strip()
        target_group = request.form.get("target_group", "").strip()
        contact = request.form.get("contact", "").strip()
        status = request.form.get("status", "開放申請")
        district = request.form.get("district", "").strip()
        service_scope = request.form.get("service_scope", "全區").strip()
        if not service_name: error = "請輸入服務名稱。"
        elif service_type not in NEED_TYPES: error = "請選擇服務類型。"
        else:
            create_service("admin", service_name, description, service_type, target_group, contact, status, district, service_scope)
            return redirect(url_for("admin_services"))
    return render_template("admin_service_create.html", username=session.get("username"), error=error,
                           need_types=NEED_TYPES, districts=DISTRICTS)

@app.route("/admin/services/<service_id>/edit", methods=["GET", "POST"])
def admin_edit_service(service_id):
    if session.get("role") != "admin": return redirect(url_for("home"))
    service = get_service(service_id)
    if not service: return redirect(url_for("admin_services"))
    error = None
    if request.method == "POST":
        service_name = request.form.get("service_name", "").strip()
        description = request.form.get("description", "").strip()
        service_type = request.form.get("service_type", "").strip()
        target_group = request.form.get("target_group", "").strip()
        contact = request.form.get("contact", "").strip()
        status = request.form.get("status", "開放申請")
        district = request.form.get("district", "").strip()
        service_scope = request.form.get("service_scope", "全區").strip()
        if not service_name: error = "請輸入服務名稱。"
        elif service_type not in NEED_TYPES and service_type != service.get("service_type"): error = "請選擇服務類型。"
        else:
            update_service(service_id, service_name, description, service_type, target_group, contact, status, district, service_scope)
            return redirect(url_for("admin_services"))
    return render_template("admin_service_edit.html", service=service, username=session.get("username"), error=error,
                           need_types=NEED_TYPES, districts=DISTRICTS)

@app.route("/admin/services/<service_id>/delete", methods=["POST"])
def admin_delete_service(service_id):
    if session.get("role") != "admin": return redirect(url_for("home"))
    delete_service(service_id)
    return redirect(url_for("admin_services"))

# --- Admin: Contents ---
@app.route("/admin/contents")
def admin_contents():
    if session.get("role") != "admin": return redirect(url_for("home"))
    return render_template("admin_contents.html", contents=load_contents(), username=session.get("username"))

@app.route("/admin/contents/create", methods=["GET", "POST"])
def admin_create_content():
    if session.get("role") != "admin": return redirect(url_for("home"))
    error = None
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        category = request.form.get("category", "其他")
        content_text = request.form.get("content", "").strip()
        image_url = request.form.get("image_url", "").strip()
        status = request.form.get("status", "已發佈")
        if not title or not content_text: error = "請輸入標題與內容。"
        else:
            create_content(title, category, content_text, image_url, "admin", status)
            return redirect(url_for("admin_contents"))
    return render_template("admin_content_create.html", username=session.get("username"), error=error)

@app.route("/admin/contents/<content_id>/edit", methods=["GET", "POST"])
def admin_edit_content(content_id):
    if session.get("role") != "admin": return redirect(url_for("home"))
    content = get_content(content_id)
    if not content: return redirect(url_for("admin_contents"))
    error = None
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        category = request.form.get("category", "其他")
        content_text = request.form.get("content", "").strip()
        image_url = request.form.get("image_url", "").strip()
        status = request.form.get("status", "已發佈")
        if not title or not content_text: error = "請輸入標題與內容。"
        else:
            update_content(content_id, title, category, content_text, image_url, status)
            return redirect(url_for("admin_contents"))
    return render_template("admin_content_edit.html", content=content, username=session.get("username"), error=error)

@app.route("/admin/contents/<content_id>/delete", methods=["POST"])
def admin_delete_content(content_id):
    if session.get("role") != "admin": return redirect(url_for("home"))
    delete_content(content_id)
    return redirect(url_for("admin_contents"))

# --- Admin: Announcements ---
@app.route("/admin/announcements")
def admin_announcements():
    if session.get("role") != "admin": return redirect(url_for("home"))
    return render_template("admin_announcements.html", announcements=load_announcements(), username=session.get("username"))

@app.route("/admin/announcements/create", methods=["GET", "POST"])
def admin_create_announcement():
    if session.get("role") != "admin": return redirect(url_for("home"))
    error = None
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        announcement_text = request.form.get("content", "").strip()
        priority = request.form.get("priority", "普通")
        status = request.form.get("status", "已發佈")
        if not title or not announcement_text: error = "請輸入標題與公告內容。"
        else:
            create_announcement(title, announcement_text, priority, status)
            return redirect(url_for("admin_announcements"))
    return render_template("admin_announcement_create.html", username=session.get("username"), error=error)

@app.route("/admin/announcements/<announcement_id>/edit", methods=["GET", "POST"])
def admin_edit_announcement(announcement_id):
    if session.get("role") != "admin": return redirect(url_for("home"))
    announcement = get_announcement(announcement_id)
    if not announcement: return redirect(url_for("admin_announcements"))
    error = None
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        announcement_text = request.form.get("content", "").strip()
        priority = request.form.get("priority", "普通")
        status = request.form.get("status", "已發佈")
        if not title or not announcement_text: error = "請輸入標題與公告內容。"
        else:
            update_announcement(announcement_id, title, announcement_text, priority, status)
            return redirect(url_for("admin_announcements"))
    return render_template("admin_announcement_edit.html", announcement=announcement, username=session.get("username"), error=error)

@app.route("/admin/announcements/<announcement_id>/delete", methods=["POST"])
def admin_delete_announcement(announcement_id):
    if session.get("role") != "admin": return redirect(url_for("home"))
    delete_announcement(announcement_id)
    return redirect(url_for("admin_announcements"))

if __name__ == "__main__":
    app.run(debug=True)
