import os
import json
import hashlib
import random
import uuid
import datetime
from pathlib import Path
from flask import Flask, request, jsonify, render_template, send_from_directory, redirect, url_for, session, Response
from werkzeug.utils import secure_filename

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from psycopg2 import OperationalError
from db_config import get_db_connection

app = Flask(__name__, template_folder="templates")
app.secret_key = os.getenv("SECRET_KEY", "dev_secret_key")

# ==========================================
# 檔案路徑與全域設定 (融合雙方設定)
# ==========================================
USERS_FILE = Path(app.root_path) / "users.json"
SUBSIDIES_FILE = Path(app.root_path) / "subsidies.json"
CASES_FILE = Path(app.root_path) / "cases.json"
ACTIVITIES_FILE = Path(app.root_path) / "activities.json"
SERVICES_FILE = Path(app.root_path) / "services.json"
CONTENTS_FILE = Path(app.root_path) / "contents.json"
ANNOUNCEMENTS_FILE = Path(app.root_path) / "announcements.json"
REGISTRATIONS_FILE = Path(app.root_path) / "registrations.json"
ATTENDANCES_FILE = Path(app.root_path) / "attendances.json"
VOLUNTEER_SHIFTS_FILE = Path(app.root_path) / "volunteer_shifts.json"

UPLOAD_FOLDER = Path(app.root_path) / "uploads"
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
ALLOWED_EXTENSIONS = {"pdf"}

ADMIN_REG_CODE = os.getenv("ADMIN_REG_CODE", "ADMIN2026")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai_client = OpenAI(api_key=OPENAI_API_KEY) if OpenAI and OPENAI_API_KEY else None

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

def create_user(username, password, role="user", org_profile=None):
    if org_profile is None:
        org_profile = {
            "org_name": "", "org_id": "", "member_count": "", 
            "volunteer_count": "", "contact_person": "", "address": ""
        }
    users = load_users()
    users.append({
        "username": username, "password": hash_password(password),
        "role": role, "org_profile": org_profile
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

def update_user_profile(username, org_profile):
    users = load_users()
    for user in users:
        if user["username"] == username: user["org_profile"] = org_profile
    save_users(users)

# --- Subsidies ---
def load_subsidies():
    if not SUBSIDIES_FILE.exists(): return []
    try:
        with SUBSIDIES_FILE.open("r", encoding="utf-8") as f:
            return json.load(f).get("subsidies", [])
    except json.JSONDecodeError: return []

def save_subsidies(subsidies):
    with SUBSIDIES_FILE.open("w", encoding="utf-8") as f:
        json.dump({"subsidies": subsidies}, f, ensure_ascii=False, indent=2)

def search_subsidies(category, keyword):
    items = load_subsidies()
    if category: items = [s for s in items if s.get("category", "") == category]
    if keyword:
        lower = keyword.lower()
        items = [s for s in items if lower in s.get("title", "").lower() or lower in s.get("agency", "").lower() or lower in s.get("description", "").lower() or lower in s.get("eligibility", "").lower()]
    return items

def get_subsidy_by_id(subsidy_id):
    for subsidy in load_subsidies():
        if subsidy.get("id") == subsidy_id: return subsidy
    return None

# --- Cases ---
def load_cases():
    if not CASES_FILE.exists(): return []
    try:
        with CASES_FILE.open("r", encoding="utf-8") as f: return json.load(f).get("cases", [])
    except json.JSONDecodeError: return []

def save_cases(cases):
    with CASES_FILE.open("w", encoding="utf-8") as f:
        json.dump({"cases": cases}, f, ensure_ascii=False, indent=2)

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
        "email": email, "phone": phone, "status": status, "registered_at": str(uuid.uuid4().hex[:8])
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
        "check_in_time": check_in_time, "check_out_time": check_out_time, "created_at": str(uuid.uuid4().hex[:8])
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

# --- Volunteer Shifts ---
def load_volunteer_shifts():
    if not VOLUNTEER_SHIFTS_FILE.exists(): return []
    try:
        with VOLUNTEER_SHIFTS_FILE.open("r", encoding="utf-8") as f: return json.load(f).get("volunteer_shifts", [])
    except json.JSONDecodeError: return []

def save_volunteer_shifts(shifts):
    with VOLUNTEER_SHIFTS_FILE.open("w", encoding="utf-8") as f:
        json.dump({"volunteer_shifts": shifts}, f, ensure_ascii=False, indent=2)

def create_volunteer_shift(activity_id, shift_name, start_time, end_time, required_count=1, status="招募中"):
    shifts = load_volunteer_shifts()
    new_shift = {
        "id": str(uuid.uuid4()), "activity_id": activity_id, "shift_name": shift_name,
        "start_time": start_time, "end_time": end_time, "required_count": int(required_count),
        "volunteers": [], "status": status, "created_at": str(uuid.uuid4().hex[:8])
    }
    shifts.append(new_shift)
    save_volunteer_shifts(shifts)
    return new_shift

def add_volunteer_to_shift(shift_id, username):
    shifts = load_volunteer_shifts()
    for shift in shifts:
        if shift["id"] == shift_id:
            if username not in shift["volunteers"]:
                shift["volunteers"].append(username)
                if len(shift["volunteers"]) >= shift["required_count"]: shift["status"] = "已滿員"
            break
    save_volunteer_shifts(shifts)

def get_activity_volunteer_shifts(activity_id):
    return [s for s in load_volunteer_shifts() if s["activity_id"] == activity_id]

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

def create_service(username, service_name, description, service_type, target_group="", contact="", status="開放申請"):
    services = load_services()
    new_service = {
        "id": str(uuid.uuid4()), "username": username, "service_name": service_name,
        "description": description, "service_type": service_type, "target_group": target_group,
        "contact": contact, "status": status, "created_at": str(uuid.uuid4().hex[:8])
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

def update_service(service_id, service_name=None, description=None, service_type=None, target_group=None, contact=None, status=None):
    services = load_services()
    for service in services:
        if service["id"] == service_id:
            if service_name is not None: service["service_name"] = service_name
            if description is not None: service["description"] = description
            if service_type is not None: service["service_type"] = service_type
            if target_group is not None: service["target_group"] = target_group
            if contact is not None: service["contact"] = contact
            if status is not None: service["status"] = status
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

def request_openai_proposal(title, background, issues, goals):
    if not openai_client: return None
    prompt = (
        "你是一個資深社福個案企劃 AI，請根據以下內容生成正式且具可執行性的企劃書建議。"
        "請不要直接照抄原文，而是以專業語氣重述重點。\n\n"
        f"案名：{title}\n背景與現況：{background}\n主要問題：{issues}\n目標與成效：{goals}\n"
    )
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4.1-mini", messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as err:
        return f"OpenAI 呼叫失敗：{err}"

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

def generate_case_proposal(title, background, issues, goals, agent_name):
    if openai_client:
        response = request_openai_proposal(title, background, issues, goals)
        if response: return response

    polished_background = polish_text(background)
    polished_issues = polish_text(issues)
    polished_goals = polish_text(goals)
    case_title = polish_text(title)

    tone_note = "已將原始敘述調整為正式、專業的企劃書語氣，並保留核心意圖。" if is_informal(background + issues + goals) else "已依照正式企劃書格式潤飾內容，保持清晰且可執行。"
    agent_intro = [f"我是 {agent_name}，以 {AI_MODEL_NAME} 作為智慧大腦，正在分析您的個案。", f"本次由 {agent_name} 啟動 {AI_MODEL_NAME} 模型，從資料中擷取關鍵資訊並提出具體建議。"]
    analysis_intro = ["以下為本案分析與建議：", "本代理人建議如下：", "AI 代理人分析結果如下："]
    recommendations = ["建議優先釐清現況與目標之間的落差，並依照資源可行性安排下一步。", "可透過階段性目標設定，逐步將需求轉化為可執行方案。", "在執行期間，持續觀察成效並依反饋調整支援策略。"]

    result = [
        random.choice(agent_intro), random.choice(analysis_intro), tone_note, f"案名：{case_title}",
        summarize_input("背景與現況", polished_background), summarize_input("主要問題", polished_issues),
        summarize_input("目標與成效", polished_goals), random.choice(recommendations)
    ]
    if polished_issues: result.append(f"針對上述議題，建議以具體措施回應，避免方案過於籠統。")
    if polished_goals: result.append(f"本案目標建議優先關注：{polished_goals}，並以可衡量成果檢視進度。")
    if any(keyword in polished_background for keyword in ["經濟", "就業", "收入"]): result.append("模型判斷：應加強經濟、就業與資源媒合面向，以提升案主自立能力。")
    if any(keyword in polished_background for keyword in ["情緒", "壓力", "憂鬱", "焦慮"]): result.append("模型判斷：需同時納入心理支持與情緒陪伴機制，以降低個案風險。")
    result.append(random.choice(["本回覆已由 AI 代理人進行獨立推理，並根據本次個案內容動態生成。", "本次建議每次皆會稍作變化，以確保回覆不重複且具備新穎視角。", "此回覆已根據案情動態調整語氣與內容，避免重複先前回應。"]))
    result.append(f"AI 模型：{AI_MODEL_NAME} / 引擎：{AI_MODEL_ENGINE}")
    result.append(f"回覆識別碼：{uuid.uuid4().hex[:8]}")
    return "\n\n".join([sentence for sentence in result if sentence])

def build_assistant_messages(user_input, history, subsidy_summary=""):
    messages = [{"role": "system", "content": "你是一個社福企劃對話助理，透過問答引導使用者按步驟整理企劃書內容。請先釐清服務對象、補助目的、組織特色與預期成效，然後再進一步提供可行建議。"}]
    if subsidy_summary: messages.append({"role": "system", "content": f"補助摘要提示：{subsidy_summary}"})
    for item in history: messages.append({"role": item["role"], "content": item["content"]})
    messages.append({"role": "user", "content": user_input})
    return messages

def generate_chat_response(user_input, history, subsidy_summary=""):
    if openai_client:
        try:
            response = openai_client.chat.completions.create(model="gpt-4.1-mini", messages=build_assistant_messages(user_input, history, subsidy_summary))
            return response.choices[0].message.content.strip()
        except Exception as err: pass

    lower_text = user_input.lower()
    if any(token in lower_text for token in ["服務對象", "族群", "對象", "服務對象"]): return "請描述您的目標服務對象、需求情境與目前面臨的困境，這樣我可以幫您把企劃書內容聚焦在組織最擅長的方向。"
    if any(token in lower_text for token in ["目標", "預期", "成效", "成果"]): return "請說明希望達成的具體成果與時間範圍，或描述您的補助想要解決的問題。"
    if any(token in lower_text for token in ["補助", "申請", "案件", "方案"]): return "請提供補助類型、申請期限與核心服務計畫，讓我們能以您組織的特色撰寫具代表性的企劃內容。"
    if len(history) < 4: return "您好，請先簡單說明您的組織、服務族群與申請目的。 我會依序引導您完成最符合需求的企劃書內容。"
    return "根據您的說明，我已理解基本需求。請再補充目前可運用的資源、服務方式、以及期望的成效指標，讓我幫您整理成更具代表性的企劃書內容。"

# ==========================================
# 路由 (Routes) - 基礎認證與個人設定
# ==========================================
@app.route("/")
def home():
    return render_template("index.html")

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
    org_profile = user.get("org_profile", {
        "org_name": "", "org_id": "", "member_count": "",
        "volunteer_count": "", "contact_person": "", "address": ""
    })

    if request.method == "POST":
        org_profile = {
            "org_name": request.form.get("org_name", "").strip(), "org_id": request.form.get("org_id", "").strip(),
            "member_count": request.form.get("member_count", "").strip(), "volunteer_count": request.form.get("volunteer_count", "").strip(),
            "contact_person": request.form.get("contact_person", "").strip(), "address": request.form.get("address", "").strip()
        }
        update_user_profile(username, org_profile)
        success = "已儲存您的社福團體資料。"

    return render_template("profile.html", username=username, org_profile=org_profile, success=success, error=error)

# ==========================================
# 路由 (Routes) - 使用者功能 (提案與 AI 對話)
# ==========================================
@app.route("/user")
def user_dashboard():
    if session.get("role") != "user": return redirect(url_for("home"))
    case_title = request.args.get("case_title", "").strip()
    background = request.args.get("background", "").strip()
    issues = request.args.get("issues", "").strip()
    goals = request.args.get("goals", "").strip()
    subsidy_summary = request.args.get("subsidy_summary", "").strip()
    agent = choose_ai_agent(background, issues)
    return render_template(
        "user.html", username=session.get("username"), ai_agent=agent["name"], ai_agent_note=agent["description"],
        ai_model=AI_MODEL_NAME, ai_engine=AI_MODEL_ENGINE, case_title=case_title, background=background,
        issues=issues, goals=goals, subsidy_summary=subsidy_summary
    )

@app.route("/user/proposal", methods=["POST"])
def user_proposal():
    if session.get("role") != "user": return redirect(url_for("home"))

    case_title = request.form.get("case_title", "").strip()
    background = request.form.get("background", "").strip()
    issues = request.form.get("issues", "").strip()
    goals = request.form.get("goals", "").strip()
    subsidy_summary = request.form.get("subsidy_summary", "").strip()
    
    success_pdf = request.files.get("success_pdf")
    subsidy_pdf = request.files.get("subsidy_pdf")
    uploaded_success_pdf = save_uploaded_file(success_pdf, "success") if success_pdf else None
    uploaded_subsidy_pdf = save_uploaded_file(subsidy_pdf, "subsidy") if subsidy_pdf else None
    error = None; proposal = None

    if not case_title or not background:
        error = "請輸入案名與個案背景，才能產生企畫書。"
        agent = choose_ai_agent(background, issues)
        ai_agent = agent["name"]; ai_agent_note = agent["description"]
    else:
        agent = choose_ai_agent(background, issues)
        ai_agent = agent["name"]; ai_agent_note = agent["description"]
        proposal = generate_case_proposal(case_title, background, issues or "尚待補充具體問題敘述。", goals or "尚待補充具體目標與預期成效。", ai_agent)
        
        if proposal:
            chat_history = session.get('chat_history', [])
            user_inputs = [m.get('content','') for m in chat_history if m.get('role') == 'user']
            if user_inputs:
                appended = "\n\n對話紀錄（使用者輸入）：\n" + "\n".join(user_inputs)
                proposal_to_save = proposal + appended
            else:
                proposal_to_save = proposal

            session["last_proposal"] = proposal_to_save
            editing_conv_idx = session.get('editing_conversation_idx')
            editing_proposal_idx = session.get('editing_proposal_idx')
            history = session.get('proposal_history', [])

            if editing_proposal_idx is not None and editing_proposal_idx < len(history):
                history[editing_proposal_idx] = proposal_to_save
            else:
                history.insert(0, proposal_to_save)
                convs = session.get('conversation_history', [])
                for conv in convs:
                    if conv.get('proposal_idx') is not None: conv['proposal_idx'] += 1
                if editing_conv_idx is not None and convs and editing_conv_idx < len(convs):
                    convs[editing_conv_idx]['proposal_idx'] = 0
                session['conversation_history'] = convs

            session['proposal_history'] = history[:10]
            session['editing_conversation_idx'] = None
            session['editing_proposal_idx'] = None
            proposal = proposal_to_save

    return render_template(
        "user.html", username=session.get("username"), case_title=case_title, background=background,
        issues=issues, goals=goals, subsidy_summary=subsidy_summary, uploaded_success_pdf=uploaded_success_pdf,
        uploaded_subsidy_pdf=uploaded_subsidy_pdf, proposal=proposal, ai_agent=ai_agent, ai_agent_note=ai_agent_note,
        ai_model=AI_MODEL_NAME, ai_engine=AI_MODEL_ENGINE, error=error
    )

@app.route("/user/proposal/download")
def download_proposal():
    if session.get("role") != "user": return redirect(url_for("home"))
    proposal = session.get("last_proposal")
    if not proposal: return redirect(url_for("user"))
    return Response(proposal, mimetype="text/plain; charset=utf-8", headers={"Content-Disposition": "attachment; filename=proposal.txt"})

@app.route("/user/proposal/download/<int:idx>")
def download_proposal_index(idx):
    if session.get("role") != "user": return redirect(url_for("home"))
    history = session.get('proposal_history', [])
    if not history or idx < 0 or idx >= len(history): return redirect(url_for('user'))
    text = history[idx]
    filename = request.args.get('filename', f"proposal_{idx+1}.txt").strip()
    try: filename = secure_filename(filename)
    except: pass
    return Response(text, mimetype="text/plain; charset=utf-8", headers={"Content-Disposition": f"attachment; filename={filename}"})

@app.route("/user/assistant", methods=["GET", "POST"])
def user_assistant():
    if session.get("role") != "user": return redirect(url_for("home"))
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

@app.route('/api/chat', methods=['POST'])
def api_chat():
    if session.get('role') != 'user': return jsonify({'error': '權限不足'}), 403
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

@app.route("/user/assistant/export")
def assistant_export():
    if session.get("role") != "user": return redirect(url_for("home"))
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

@app.route("/user/assistant/import_proposal")
def assistant_import_proposal():
    if session.get("role") != "user": return redirect(url_for("home"))
    proposal = session.get("last_proposal")
    subsidy_summary = request.args.get("subsidy_summary", "").strip()
    if not proposal: return redirect(url_for("user_assistant", subsidy_summary=subsidy_summary))
    chat_history = session.get("chat_history", [])
    chat_history.append({"role": "assistant", "content": f"初步企劃草稿：\n\n{proposal}"})
    session["chat_history"] = chat_history
    return redirect(url_for("user_assistant", subsidy_summary=subsidy_summary))

@app.route("/user/assistant/export_selected")
def assistant_export_selected():
    if session.get("role") != "user": return redirect(url_for("home"))
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

@app.route('/user/assistant/load_conversation/<int:idx>')
def load_conversation(idx):
    if session.get('role') != 'user': return redirect(url_for('home'))
    convs = session.get('conversation_history', [])
    if not convs or idx < 0 or idx >= len(convs): return redirect(url_for('user_assistant'))
    session['chat_history'] = convs[idx].get('chat', [])
    session['editing_conversation_idx'] = idx
    session['editing_proposal_idx'] = convs[idx].get('proposal_idx')
    return redirect(url_for('user_assistant'))

@app.route('/user/assistant/download_conversation/<int:idx>')
def download_conversation(idx):
    if session.get('role') != 'user': return redirect(url_for('home'))
    convs = session.get('conversation_history', [])
    if not convs or idx < 0 or idx >= len(convs): return redirect(url_for('user_assistant'))
    conv = convs[idx]
    lines = [f"對話紀錄（{conv.get('timestamp','')})\n\n"]
    for m in conv.get('chat', []):
        role = '您' if m.get('role') == 'user' else '助理'
        lines.extend([f"{role}：{m.get('content','')}", ""])
    filename = request.args.get('filename', f"conversation_{idx+1}.txt").strip()
    try: filename = secure_filename(filename)
    except: pass
    return Response("\n".join(lines), mimetype='text/plain; charset=utf-8', headers={"Content-Disposition": f"attachment; filename={filename}"})

@app.route('/user/assistant/rename_conversation/<int:idx>', methods=['POST'])
def rename_conversation(idx):
    if session.get('role') != 'user': return jsonify({'error': '權限不足'}), 403
    data = request.get_json() or {}
    new_name = (data.get('name') or '').strip()
    if not new_name: return jsonify({'error': '名稱不能為空'}), 400
    convs = session.get('conversation_history', [])
    if not convs or idx < 0 or idx >= len(convs): return jsonify({'error': '對話不存在'}), 404
    convs[idx]['name'] = new_name
    session['conversation_history'] = convs
    session.modified = True
    return jsonify({'success': True, 'name': new_name})

@app.route('/user/assistant/from_proposal/<int:idx>')
def resume_conversation_from_proposal(idx):
    if session.get('role') != 'user': return redirect(url_for('home'))
    proposals = session.get('proposal_history', [])
    if not proposals or idx < 0 or idx >= len(proposals): return redirect(url_for('user_assistant'))
    session['chat_history'] = []
    session['last_proposal'] = proposals[idx]
    return redirect(url_for('user_assistant'))

# ==========================================
# 路由 (Routes) - 補助資源清單
# ==========================================
@app.route("/subsidies")
def subsidies_page():
    if not session.get("username"): return redirect(url_for("home"))
    category = request.args.get("category", "")
    keyword = request.args.get("q", "").strip()
    subsidies = search_subsidies(category, keyword)
    categories = sorted({s.get("category", "其他") for s in load_subsidies()})
    return render_template("subsidies.html", username=session.get("username"), subsidies=subsidies, categories=categories, selected_category=category, keyword=keyword)

@app.route("/subsidies/<int:subsidy_id>")
def subsidy_detail(subsidy_id):
    if not session.get("username"): return redirect(url_for("home"))
    subsidy = get_subsidy_by_id(subsidy_id)
    if not subsidy: return redirect(url_for("subsidies_page"))
    subsidy_summary = f"本補助由 {subsidy.get('agency')} 提供，補助內容為：{subsidy.get('description')}。申請資格：{subsidy.get('eligibility')}。"
    generate_url = url_for("user_dashboard", case_title=subsidy.get("title", "補助申請企劃"), background=f"機構申請 {subsidy.get('title')}，補助來源：{subsidy.get('agency')}。{subsidy.get('description')}", issues="需要確認補助資格並提出實務可行的申請計畫。", goals="獲得補助並改善社福服務品質與資源運用。", subsidy_summary=subsidy_summary)
    assistant_url = url_for("user_assistant", subsidy_summary=subsidy_summary)
    return render_template("subsidy_detail.html", username=session.get("username"), subsidy=subsidy, generate_url=generate_url, assistant_url=assistant_url)

# ==========================================
# 路由 (Routes) - 管理者後台 (Admin Dashboards)
# ==========================================
@app.route("/admin")
def admin_dashboard():
    if session.get("role") != "admin": return redirect(url_for("home"))
    return render_template("admin.html", username=session.get("username"))

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

# --- Admin: Activities ---
@app.route("/admin/activities")
def admin_activities():
    if session.get("role") != "admin": return redirect(url_for("home"))
    return render_template("admin_activities.html", activities=load_activities(), username=session.get("username"))

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
    return render_template("admin_activity_registrations.html", activity=activity, registrations=get_activity_registrations(activity_id), username=session.get("username"))

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
    return render_template("admin_activity_attendance.html", activity=activity, attendances=get_activity_attendances(activity_id), username=session.get("username"))

@app.route("/admin/activities/<activity_id>/checkin", methods=["POST"])
def admin_check_in(activity_id):
    if session.get("role") != "admin": return redirect(url_for("home"))
    username = request.form.get("username", "").strip()
    if username:
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

@app.route("/admin/activities/<activity_id>/volunteer-shifts")
def admin_volunteer_shifts(activity_id):
    if session.get("role") != "admin": return redirect(url_for("home"))
    activity = get_activity(activity_id)
    if not activity: return redirect(url_for("admin_activities"))
    return render_template("admin_volunteer_shifts.html", activity=activity, shifts=get_activity_volunteer_shifts(activity_id), username=session.get("username"))

@app.route("/admin/activities/<activity_id>/volunteer-shifts/create", methods=["GET", "POST"])
def admin_create_volunteer_shift(activity_id):
    if session.get("role") != "admin": return redirect(url_for("home"))
    activity = get_activity(activity_id)
    if not activity: return redirect(url_for("admin_activities"))
    error = None
    if request.method == "POST":
        shift_name = request.form.get("shift_name", "").strip()
        start_time = request.form.get("start_time", "")
        end_time = request.form.get("end_time", "")
        required_count = request.form.get("required_count", "1")
        if not shift_name or not start_time or not end_time: error = "請填寫所有必填欄位。"
        else:
            create_volunteer_shift(activity_id, shift_name, start_time, end_time, required_count)
            return redirect(url_for("admin_volunteer_shifts", activity_id=activity_id))
    return render_template("admin_volunteer_shift_create.html", activity=activity, username=session.get("username"), error=error)

@app.route("/admin/volunteer-shifts/<shift_id>/add-volunteer", methods=["POST"])
def admin_add_volunteer_to_shift(shift_id):
    if session.get("role") != "admin": return redirect(url_for("home"))
    username = request.form.get("username", "").strip()
    if username: add_volunteer_to_shift(shift_id, username)
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
        service_type = request.form.get("service_type", "其他")
        target_group = request.form.get("target_group", "").strip()
        contact = request.form.get("contact", "").strip()
        status = request.form.get("status", "開放申請")
        if not service_name: error = "請輸入服務名稱。"
        else:
            create_service("admin", service_name, description, service_type, target_group, contact, status)
            return redirect(url_for("admin_services"))
    return render_template("admin_service_create.html", username=session.get("username"), error=error)

@app.route("/admin/services/<service_id>/edit", methods=["GET", "POST"])
def admin_edit_service(service_id):
    if session.get("role") != "admin": return redirect(url_for("home"))
    service = get_service(service_id)
    if not service: return redirect(url_for("admin_services"))
    error = None
    if request.method == "POST":
        service_name = request.form.get("service_name", "").strip()
        description = request.form.get("description", "").strip()
        service_type = request.form.get("service_type", "其他")
        target_group = request.form.get("target_group", "").strip()
        contact = request.form.get("contact", "").strip()
        status = request.form.get("status", "開放申請")
        if not service_name: error = "請輸入服務名稱。"
        else:
            update_service(service_id, service_name, description, service_type, target_group, contact, status)
            return redirect(url_for("admin_services"))
    return render_template("admin_service_edit.html", service=service, username=session.get("username"), error=error)

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

# ==========================================
# 路由 (Routes) - Donations (API)
# ==========================================
@app.route("/donations")
def donations_page():
    if session.get("role") != "admin": return render_template("unauthorized.html"), 403
    return render_template("donations.html")

@app.route("/api/donations")
def get_donations():
    if session.get("role") != "admin":
        return jsonify({"error": "權限不足，只有管理者可以存取捐款資料。"}), 403
    year = request.args.get("year")
    month = request.args.get("month")
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        query = "SELECT donor, date, amount, note FROM donations WHERE EXTRACT(YEAR FROM date) = %s AND EXTRACT(MONTH FROM date) = %s"
        cur.execute(query, (year, month))
        rows = cur.fetchall()
        result = [{"donor": r[0], "date": str(r[1]), "amount": r[2], "note": r[3]} for r in rows]
        cur.close(); conn.close()
        return jsonify(result)
    except OperationalError as err:
        return jsonify({"error": "資料庫連線失敗，請檢查 PostgreSQL 是否已啟動並確認連線設定。", "detail": str(err)}), 500
    except Exception as err:
        return jsonify({"error": "發生未知錯誤。", "detail": str(err)}), 500

if __name__ == "__main__":
    app.run(debug=True)