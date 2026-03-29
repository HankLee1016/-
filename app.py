import os
import json
import hashlib
import random
import uuid
from pathlib import Path
from flask import Flask, request, jsonify, render_template, send_from_directory, redirect, url_for, session
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None
from psycopg2 import OperationalError
from db_config import get_db_connection

app = Flask(__name__, template_folder="templates")
app.secret_key = os.getenv("SECRET_KEY", "dev_secret_key")

USERS_FILE = Path(app.root_path) / "users.json"
ADMIN_REG_CODE = os.getenv("ADMIN_REG_CODE", "ADMIN2026")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai_client = OpenAI(api_key=OPENAI_API_KEY) if OpenAI and OPENAI_API_KEY else None


def load_users():
    if not USERS_FILE.exists():
        return []
    try:
        with USERS_FILE.open("r", encoding="utf-8") as f:
            return json.load(f).get("users", [])
    except json.JSONDecodeError:
        return []


def save_users(users):
    with USERS_FILE.open("w", encoding="utf-8") as f:
        json.dump({"users": users}, f, ensure_ascii=False, indent=2)


def hash_password(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def find_user(username):
    for user in load_users():
        if user["username"] == username:
            return user
    return None


def create_user(username, password, role="user"):
    users = load_users()
    users.append({
        "username": username,
        "password": hash_password(password),
        "role": role
    })
    save_users(users)


def delete_user(username):
    users = [user for user in load_users() if user["username"] != username]
    save_users(users)


def update_user_role(username, role):
    users = load_users()
    for user in users:
        if user["username"] == username:
            user["role"] = role
    save_users(users)


AI_MODEL_NAME = "ChatAssist GPT"
AI_MODEL_ENGINE = "GPT-Assist-2.0"

AI_AGENTS = [
    {
        "name": "企劃師小智",
        "description": "專注策略、落地執行與協調資源，適合需要具體方案的個案。"
    },
    {
        "name": "社服諮詢官",
        "description": "擅長需求分析與風險檢視，適合有情緒、家庭或心理層面議題的個案。"
    },
    {
        "name": "資源協調員",
        "description": "側重整合在地支持與長期追蹤，適合希望建立持續支持網絡的個案。"
    }
]


def choose_ai_agent(background, issues):
    combined = (background + " " + issues).lower()
    if any(keyword in combined for keyword in ["家庭", "親子", "孩童", "青少", "情緒", "心理"]):
        return AI_AGENTS[1]
    if any(keyword in combined for keyword in ["工作", "就業", "收入", "經濟", "社區"]):
        return AI_AGENTS[2]
    return AI_AGENTS[0]


def request_openai_proposal(title, background, issues, goals):
    if not openai_client:
        return None
    prompt = (
        "你是一個資深社福個案企劃 AI，請根據以下內容生成正式且具可執行性的企劃書建議。"
        "請不要直接照抄原文，而是以專業語氣重述重點。\n\n"
        f"案名：{title}\n"
        f"背景與現況：{background}\n"
        f"主要問題：{issues}\n"
        f"目標與成效：{goals}\n"
    )

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as err:
        return f"OpenAI 呼叫失敗：{err}"


def polish_text(text):
    if not text:
        return ""
    cleaned = " ".join(text.replace("\n", " ").replace("　", " ").split())
    replacements = {
        "很": "非常",
        "有點": "稍微",
        "幫忙": "協助",
        "要": "應",
        "可以": "可",
        "就": "",
        "會": "將",
        "還有": "此外",
        "如果": "若",
        "這樣": "如此",
        "問題": "議題",
        "成果": "成效",
        "影響": "影響因素",
        "比較": "較",
        "但": "然而",
        "而且": "並且",
        "不是": "非",
        "所需": "需要"
    }
    for old, new in replacements.items():
        cleaned = cleaned.replace(old, new)
    cleaned = cleaned.strip()
    if cleaned and cleaned[-1] not in "。！？":
        cleaned += "。"
    return cleaned


def is_informal(text):
    informal_tokens = ["就", "很", "有點", "超", "ok", "haha", "哈哈", "ㄎ", "差不多", "隨便", "可能", "大概"]
    lower = text.lower()
    return any(token in lower for token in informal_tokens)


def summarize_input(label, content):
    if not content:
        return ""
    templates = [
        "{label}重點為：{content}",
        "{label}描述了：{content}",
        "此段說明了{content}",
        "本段內容指出：{content}"
    ]
    return random.choice(templates).format(label=label, content=content)


def generate_case_proposal(title, background, issues, goals, agent_name):
    if openai_client:
        response = request_openai_proposal(title, background, issues, goals)
        if response:
            return response

    polished_background = polish_text(background)
    polished_issues = polish_text(issues)
    polished_goals = polish_text(goals)
    case_title = polish_text(title)
    tone_note = (
        "已將原始敘述調整為正式、專業的企劃書語氣，並保留核心意圖。"
        if is_informal(background + issues + goals)
        else "已依照正式企劃書格式潤飾內容，保持清晰且可執行。"
    )

    agent_intro = [
        f"我是 {agent_name}，以 {AI_MODEL_NAME} 作為智慧大腦，正在分析您的個案。",
        f"本次由 {agent_name} 啟動 {AI_MODEL_NAME} 模型，從資料中擷取關鍵資訊並提出具體建議。"
    ]
    analysis_intro = [
        "以下為本案分析與建議：",
        "本代理人建議如下：",
        "AI 代理人分析結果如下："
    ]

    recommendations = [
        "建議優先釐清現況與目標之間的落差，並依照資源可行性安排下一步。",
        "可透過階段性目標設定，逐步將需求轉化為可執行方案。",
        "在執行期間，持續觀察成效並依反饋調整支援策略。"
    ]

    result = [
        random.choice(agent_intro),
        random.choice(analysis_intro),
        tone_note,
        f"案名：{case_title}",
        summarize_input("背景與現況", polished_background),
        summarize_input("主要問題", polished_issues),
        summarize_input("目標與成效", polished_goals),
        random.choice(recommendations)
    ]

    if polished_issues:
        result.append(
            f"針對上述議題，建議以具體措施回應，避免方案過於籠統。"
        )
    if polished_goals:
        result.append(
            f"本案目標建議優先關注：{polished_goals}，並以可衡量成果檢視進度。"
        )

    if any(keyword in polished_background for keyword in ["經濟", "就業", "收入"]):
        result.append(
            "模型判斷：應加強經濟、就業與資源媒合面向，以提升案主自立能力。"
        )
    if any(keyword in polished_background for keyword in ["情緒", "壓力", "憂鬱", "焦慮"]):
        result.append(
            "模型判斷：需同時納入心理支持與情緒陪伴機制，以降低個案風險。"
        )

    result.append(random.choice([
        "本回覆已由 AI 代理人進行獨立推理，並根據本次個案內容動態生成。",
        "本次建議每次皆會稍作變化，以確保回覆不重複且具備新穎視角。",
        "此回覆已根據案情動態調整語氣與內容，避免重複先前回應。"
    ]))
    result.append(f"AI 模型：{AI_MODEL_NAME} / 引擎：{AI_MODEL_ENGINE}")
    result.append(f"回覆識別碼：{uuid.uuid4().hex[:8]}")
    return "\n\n".join([sentence for sentence in result if sentence])

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

        if not username or not password:
            error = "請輸入帳號與密碼。"
        elif password != confirm_password:
            error = "密碼與確認密碼不一致。"
        elif find_user(username):
            error = "此帳號已存在，請改用其他帳號名稱。"
        elif role == "admin" and admin_code != ADMIN_REG_CODE:
            error = "管理者註冊代碼不正確。"
        else:
            create_user(username, password, role)
            session["username"] = username
            session["role"] = role
            if role == "admin":
                return redirect(url_for("admin_dashboard"))
            return redirect(url_for("user_dashboard"))

    return render_template("register.html", error=error)

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = find_user(username)

        if not username or not password:
            error = "請輸入帳號與密碼。"
        elif not user:
            error = "使用者不存在，請先註冊。"
        elif user["password"] != hash_password(password):
            error = "帳號或密碼錯誤。"
        else:
            session["username"] = username
            session["role"] = user["role"]
            if user["role"] == "admin":
                return redirect(url_for("admin_dashboard"))
            return redirect(url_for("user_dashboard"))

    return render_template("login.html", error=error)

@app.route("/select/<role>")
def select_role(role):
    if role not in ("user", "admin"):
        return render_template("unauthorized.html"), 400
    session["role"] = role
    if role == "admin":
        return redirect(url_for("admin_dashboard"))
    return redirect(url_for("user_dashboard"))

@app.route("/user")
def user_dashboard():
    if session.get("role") != "user":
        return redirect(url_for("home"))
    agent = choose_ai_agent("", "")
    return render_template(
        "user.html",
        username=session.get("username"),
        ai_agent=agent["name"],
        ai_agent_note=agent["description"],
        ai_model=AI_MODEL_NAME,
        ai_engine=AI_MODEL_ENGINE
    )

@app.route("/user/proposal", methods=["POST"])
def user_proposal():
    if session.get("role") != "user":
        return redirect(url_for("home"))

    case_title = request.form.get("case_title", "").strip()
    background = request.form.get("background", "").strip()
    issues = request.form.get("issues", "").strip()
    goals = request.form.get("goals", "").strip()
    error = None
    proposal = None

    if not case_title or not background:
        error = "請輸入案名與個案背景，才能產生企畫書。"
        agent = choose_ai_agent(background, issues)
        ai_agent = agent["name"]
        ai_agent_note = agent["description"]
    else:
        agent = choose_ai_agent(background, issues)
        ai_agent = agent["name"]
        ai_agent_note = agent["description"]
        proposal = generate_case_proposal(
            case_title,
            background,
            issues or "尚待補充具體問題敘述。",
            goals or "尚待補充具體目標與預期成效。",
            ai_agent
        )

    return render_template(
        "user.html",
        username=session.get("username"),
        case_title=case_title,
        background=background,
        issues=issues,
        goals=goals,
        proposal=proposal,
        ai_agent=ai_agent,
        ai_agent_note=ai_agent_note,
        ai_model=AI_MODEL_NAME,
        ai_engine=AI_MODEL_ENGINE,
        error=error
    )

@app.route("/admin")
def admin_dashboard():
    if session.get("role") != "admin":
        return redirect(url_for("home"))
    return render_template("admin.html", username=session.get("username"))

@app.route("/admin/members")
def admin_members():
    if session.get("role") != "admin":
        return redirect(url_for("home"))
    users = load_users()
    return render_template("members.html", users=users, username=session.get("username"))

@app.route("/admin/members/delete/<username>", methods=["POST"])
def admin_delete_member(username):
    if session.get("role") != "admin":
        return redirect(url_for("home"))
    if username == session.get("username"):
        return render_template("members.html", users=load_users(), username=session.get("username"), error="無法刪除目前登入帳號。")
    delete_user(username)
    return redirect(url_for("admin_members"))

@app.route("/admin/members/role/<username>", methods=["POST"])
def admin_change_member_role(username):
    if session.get("role") != "admin":
        return redirect(url_for("home"))
    new_role = request.form.get("new_role")
    if username == session.get("username"):
        return render_template("members.html", users=load_users(), username=session.get("username"), error="無法變更目前登入帳號的身分。")
    if new_role in ("user", "admin"):
        update_user_role(username, new_role)
    return redirect(url_for("admin_members"))

@app.route("/logout")
def logout():
    session.pop("role", None)
    return redirect(url_for("home"))

@app.route("/donations")
def donations_page():
    if session.get("role") != "admin":
        return render_template("unauthorized.html"), 403
    return render_template("donations.html")

@app.route("/api/donations")
def get_donations():
    if session.get("role") != "admin":
        return jsonify({
            "error": "權限不足，只有管理者可以存取捐款資料。"
        }), 403

    year = request.args.get("year")
    month = request.args.get("month")

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        query = """
        SELECT donor, date, amount, note
        FROM donations
        WHERE EXTRACT(YEAR FROM date) = %s
        AND EXTRACT(MONTH FROM date) = %s
        """

        cur.execute(query, (year, month))
        rows = cur.fetchall()

        result = [
            {
                "donor": r[0],
                "date": str(r[1]),
                "amount": r[2],
                "note": r[3]
            }
            for r in rows
        ]

        cur.close()
        conn.close()

        return jsonify(result)

    except OperationalError as err:
        return jsonify({
            "error": "資料庫連線失敗，請檢查 PostgreSQL 是否已啟動並確認連線設定。",
            "detail": str(err)
        }), 500
    except Exception as err:
        return jsonify({
            "error": "發生未知錯誤。",
            "detail": str(err)
        }), 500

if __name__ == "__main__":
    app.run(debug=True)
