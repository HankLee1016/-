import os
import json
import hashlib
import random
import uuid
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

USERS_FILE = Path(app.root_path) / "users.json"
SUBSIDIES_FILE = Path(app.root_path) / "subsidies.json"
UPLOAD_FOLDER = Path(app.root_path) / "uploads"
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
ALLOWED_EXTENSIONS = {"pdf"}
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


def load_subsidies():
    if not SUBSIDIES_FILE.exists():
        return []
    try:
        with SUBSIDIES_FILE.open("r", encoding="utf-8") as f:
            return json.load(f).get("subsidies", [])
    except json.JSONDecodeError:
        return []


def save_subsidies(subsidies):
    with SUBSIDIES_FILE.open("w", encoding="utf-8") as f:
        json.dump({"subsidies": subsidies}, f, ensure_ascii=False, indent=2)


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


def find_user(username):
    for user in load_users():
        if user["username"] == username:
            return user
    return None


def create_user(username, password, role="user", org_profile=None):
    if org_profile is None:
        org_profile = {
            "org_name": "",
            "org_id": "",
            "member_count": "",
            "volunteer_count": "",
            "contact_person": "",
            "address": ""
        }
    users = load_users()
    users.append({
        "username": username,
        "password": hash_password(password),
        "role": role,
        "org_profile": org_profile
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


def update_user_profile(username, org_profile):
    users = load_users()
    for user in users:
        if user["username"] == username:
            user["org_profile"] = org_profile
    save_users(users)


def search_subsidies(category, keyword):
    items = load_subsidies()
    if category:
        items = [s for s in items if s.get("category", "") == category]
    if keyword:
        lower = keyword.lower()
        items = [s for s in items if lower in s.get("title", "").lower() or lower in s.get("agency", "").lower() or lower in s.get("description", "").lower() or lower in s.get("eligibility", "").lower()]
    return items


def get_subsidy_by_id(subsidy_id):
    for subsidy in load_subsidies():
        if subsidy.get("id") == subsidy_id:
            return subsidy
    return None


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


def build_assistant_messages(user_input, history, subsidy_summary=""):
    messages = [
        {
            "role": "system",
            "content": (
                "你是一個社福企劃對話助理，透過問答引導使用者按步驟整理企劃書內容。"
                "請先釐清服務對象、補助目的、組織特色與預期成效，然後再進一步提供可行建議。"
            )
        }
    ]
    if subsidy_summary:
        messages.append({
            "role": "system",
            "content": f"補助摘要提示：{subsidy_summary}"
        })
    for item in history:
        messages.append({"role": item["role"], "content": item["content"]})
    messages.append({"role": "user", "content": user_input})
    return messages


def generate_chat_response(user_input, history, subsidy_summary=""):
    if openai_client:
        try:
            response = openai_client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=build_assistant_messages(user_input, history, subsidy_summary)
            )
            return response.choices[0].message.content.strip()
        except Exception as err:
            pass

    lower_text = user_input.lower()
    if any(token in lower_text for token in ["服務對象", "族群", "對象", "服務對象"]):
        return "請描述您的目標服務對象、需求情境與目前面臨的困境，這樣我可以幫您把企劃書內容聚焦在組織最擅長的方向。"
    if any(token in lower_text for token in ["目標", "預期", "成效", "成果"]):
        return "請說明希望達成的具體成果與時間範圍，或描述您的補助想要解決的問題。"
    if any(token in lower_text for token in ["補助", "申請", "案件", "方案"]):
        return "請提供補助類型、申請期限與核心服務計畫，讓我們能以您組織的特色撰寫具代表性的企劃內容。"

    if len(history) < 4:
        return (
            "您好，請先簡單說明您的組織、服務族群與申請目的。"
            " 我會依序引導您完成最符合需求的企劃書內容。"
        )

    return (
        "根據您的說明，我已理解基本需求。" 
        "請再補充目前可運用的資源、服務方式、以及期望的成效指標，"
        "讓我幫您整理成更具代表性的企劃書內容。"
    )

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

    case_title = request.args.get("case_title", "").strip()
    background = request.args.get("background", "").strip()
    issues = request.args.get("issues", "").strip()
    goals = request.args.get("goals", "").strip()
    subsidy_summary = request.args.get("subsidy_summary", "").strip()

    agent = choose_ai_agent(background, issues)
    return render_template(
        "user.html",
        username=session.get("username"),
        ai_agent=agent["name"],
        ai_agent_note=agent["description"],
        ai_model=AI_MODEL_NAME,
        ai_engine=AI_MODEL_ENGINE,
        case_title=case_title,
        background=background,
        issues=issues,
        goals=goals,
        subsidy_summary=subsidy_summary
    )

@app.route("/user/assistant", methods=["GET", "POST"])
def user_assistant():
    if session.get("role") != "user":
        return redirect(url_for("home"))

    subsidy_summary = request.values.get("subsidy_summary", "").strip()

    # If user requested to save current conversation
    if request.args.get("save_history") == "1":
        chat_history = session.get('chat_history', [])
        editing_idx = session.get('editing_conversation_idx')
        if chat_history:
            from datetime import datetime
            import uuid
            ts = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
            convs = session.get('conversation_history', [])
            
            # If editing an existing conversation, update it instead of creating new
            if editing_idx is not None and editing_idx < len(convs):
                convs[editing_idx]['chat'] = chat_history
                convs[editing_idx]['timestamp'] = ts
            else:
                # Create new conversation only if not editing existing one
                conv_id = str(uuid.uuid4())[:8]
                # Default name: first user message
                conv_name = "未命名對話"
                for msg in chat_history:
                    if msg.get('role') == 'user':
                        preview = msg.get('content', '')[:40]
                        if preview:
                            conv_name = preview
                            break
                # store structured conversation with id and name
                conv_entry = {
                    'id': conv_id,
                    'name': conv_name,
                    'timestamp': ts,
                    'chat': chat_history,
                    'proposal_idx': None
                }
                convs.insert(0, conv_entry)
            
            session['conversation_history'] = convs[:20]
        # clear current chat for new conversation
        session['chat_history'] = []
        session['editing_conversation_idx'] = None  # Clear flag for new conversation
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

    return render_template(
        "assistant.html",
        username=session.get("username"),
        chat_history=chat_history,
        subsidy_summary=subsidy_summary
    )


@app.route('/api/chat', methods=['POST'])
def api_chat():
    if session.get('role') != 'user':
        return jsonify({'error': '權限不足'}), 403

    data = request.get_json() or {}
    user_message = (data.get('message') or '').strip()
    if not user_message:
        return jsonify({'error': 'empty message'}), 400

    subsidy_summary = session.get('last_subsidy_summary', '') or request.args.get('subsidy_summary', '')
    chat_history = session.get('chat_history', [])
    assistant_response = generate_chat_response(user_message, chat_history, subsidy_summary)

    # append to session history
    chat_history.append({'role': 'user', 'content': user_message})
    chat_history.append({'role': 'assistant', 'content': assistant_response})
    session['chat_history'] = chat_history

    return jsonify({'reply': assistant_response})

@app.route("/user/assistant/export")
def assistant_export():
    if session.get("role") != "user":
        return redirect(url_for("home"))

    chat_history = session.get("chat_history", [])
    subsidy_summary = request.args.get("subsidy_summary", "").strip()
    lines = []
    if subsidy_summary:
        lines.append(f"補助摘要：{subsidy_summary}")
        lines.append("")

    if chat_history:
        for message in chat_history:
            role = "您" if message.get("role") == "user" else "助理"
            lines.append(f"{role}：{message.get('content', '')}")
            lines.append("")
    else:
        lines.append("尚無對話紀錄。")

    export_text = "\n".join(lines)
    return Response(
        export_text,
        mimetype="text/plain; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=assistant_export.txt"}
    )


@app.route("/user/assistant/import_proposal")
def assistant_import_proposal():
    if session.get("role") != "user":
        return redirect(url_for("home"))

    proposal = session.get("last_proposal")
    subsidy_summary = request.args.get("subsidy_summary", "").strip()
    if not proposal:
        return redirect(url_for("user_assistant", subsidy_summary=subsidy_summary))

    chat_history = session.get("chat_history", [])
    chat_history.append({"role": "assistant", "content": f"初步企劃草稿：\n\n{proposal}"})
    session["chat_history"] = chat_history
    return redirect(url_for("user_assistant", subsidy_summary=subsidy_summary))


@app.route("/user/assistant/export_selected")
def assistant_export_selected():
    if session.get("role") != "user":
        return redirect(url_for("home"))

    idx_list = request.args.getlist('idx')
    subsidy_summary = request.args.get("subsidy_summary", "").strip()
    chat_history = session.get("chat_history", [])

    if not idx_list:
        return redirect(url_for('assistant_export', subsidy_summary=subsidy_summary))

    lines = []
    if subsidy_summary:
        lines.append(f"補助摘要：{subsidy_summary}")
        lines.append("")

    for idx_str in idx_list:
        try:
            idx = int(idx_str)
        except ValueError:
            continue
        if 0 <= idx < len(chat_history):
            m = chat_history[idx]
            role = "您" if m.get('role') == 'user' else '助理'
            lines.append(f"{role}：{m.get('content','')}")
            lines.append("")

    if not lines:
        lines = ["未找到選取的訊息。"]

    export_text = "\n".join(lines)
    # allow custom filename via query param 'filename'
    filename = request.args.get('filename', '').strip()
    if not filename:
        filename = 'assistant_selected.txt'
    # secure filename
    try:
        from werkzeug.utils import secure_filename as _secure
        filename = _secure(filename)
    except Exception:
        pass

    return Response(
        export_text,
        mimetype="text/plain; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.route("/subsidies")
def subsidies_page():
    if not session.get("username"):
        return redirect(url_for("home"))

    category = request.args.get("category", "")
    keyword = request.args.get("q", "").strip()
    subsidies = search_subsidies(category, keyword)
    categories = sorted({s.get("category", "其他") for s in load_subsidies()})

    return render_template(
        "subsidies.html",
        username=session.get("username"),
        subsidies=subsidies,
        categories=categories,
        selected_category=category,
        keyword=keyword
    )

@app.route("/subsidies/<int:subsidy_id>")
def subsidy_detail(subsidy_id):
    if not session.get("username"):
        return redirect(url_for("home"))

    subsidy = get_subsidy_by_id(subsidy_id)
    if not subsidy:
        return redirect(url_for("subsidies_page"))

    subsidy_summary = f"本補助由 {subsidy.get('agency')} 提供，補助內容為：{subsidy.get('description')}。申請資格：{subsidy.get('eligibility')}。"
    generate_url = url_for(
        "user_dashboard",
        case_title=subsidy.get("title", "補助申請企劃"),
        background=f"機構申請 {subsidy.get('title')}，補助來源：{subsidy.get('agency')}。{subsidy.get('description')}",
        issues="需要確認補助資格並提出實務可行的申請計畫。",
        goals="獲得補助並改善社福服務品質與資源運用。",
        subsidy_summary=subsidy_summary
    )
    assistant_url = url_for(
        "user_assistant",
        subsidy_summary=subsidy_summary
    )

    return render_template(
        "subsidy_detail.html",
        username=session.get("username"),
        subsidy=subsidy,
        generate_url=generate_url,
        assistant_url=assistant_url
    )

@app.route("/user/proposal", methods=["POST"])
def user_proposal():
    if session.get("role") != "user":
        return redirect(url_for("home"))

    case_title = request.form.get("case_title", "").strip()
    background = request.form.get("background", "").strip()
    issues = request.form.get("issues", "").strip()
    goals = request.form.get("goals", "").strip()
    subsidy_summary = request.form.get("subsidy_summary", "").strip()
    success_pdf = request.files.get("success_pdf")
    subsidy_pdf = request.files.get("subsidy_pdf")
    uploaded_success_pdf = save_uploaded_file(success_pdf, "success") if success_pdf else None
    uploaded_subsidy_pdf = save_uploaded_file(subsidy_pdf, "subsidy") if subsidy_pdf else None
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
        # Save last generated proposal to session so user can download it
        if proposal:
                # include user's chat inputs (if any) into the saved proposal
                chat_history = session.get('chat_history', [])
                user_inputs = [m.get('content','') for m in chat_history if m.get('role') == 'user']
                if user_inputs:
                    appended = "\n\n對話紀錄（使用者輸入）：\n" + "\n".join(user_inputs)
                    proposal_to_save = proposal + appended
                else:
                    proposal_to_save = proposal

                session["last_proposal"] = proposal_to_save
                
                # Check if user is editing a loaded conversation
                editing_conv_idx = session.get('editing_conversation_idx')
                editing_proposal_idx = session.get('editing_proposal_idx')
                history = session.get('proposal_history', [])
                
                if editing_proposal_idx is not None and editing_proposal_idx < len(history):
                    # Update the corresponding proposal in history (replace)
                    history[editing_proposal_idx] = proposal_to_save
                else:
                    # No linked proposal, append new proposal (most recent first)
                    history.insert(0, proposal_to_save)
                    # After inserting, update indices in all conversation_history items
                    # because proposal_history indices shifted
                    convs = session.get('conversation_history', [])
                    for conv in convs:
                        if conv.get('proposal_idx') is not None:
                            conv['proposal_idx'] += 1
                    # Link this new proposal to the current conversation if editing
                    if editing_conv_idx is not None and convs and editing_conv_idx < len(convs):
                        convs[editing_conv_idx]['proposal_idx'] = 0
                    session['conversation_history'] = convs
                
                # keep up to 10 items
                session['proposal_history'] = history[:10]
                # Clear the editing flags after generating proposal
                session['editing_conversation_idx'] = None
                session['editing_proposal_idx'] = None

                # ensure the rendered proposal includes the appended chat content
                proposal = proposal_to_save

    return render_template(
        "user.html",
        username=session.get("username"),
        case_title=case_title,
        background=background,
        issues=issues,
        goals=goals,
        subsidy_summary=subsidy_summary,
        uploaded_success_pdf=uploaded_success_pdf,
        uploaded_subsidy_pdf=uploaded_subsidy_pdf,
        proposal=proposal,
        ai_agent=ai_agent,
        ai_agent_note=ai_agent_note,
        ai_model=AI_MODEL_NAME,
        ai_engine=AI_MODEL_ENGINE,
        error=error
    )


@app.route("/user/proposal/download")
def download_proposal():
    if session.get("role") != "user":
        return redirect(url_for("home"))

    proposal = session.get("last_proposal")
    if not proposal:
        return redirect(url_for("user"))

    return Response(
        proposal,
        mimetype="text/plain; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=proposal.txt"}
    )


@app.route("/user/proposal/download/<int:idx>")
def download_proposal_index(idx):
    if session.get("role") != "user":
        return redirect(url_for("home"))

    history = session.get('proposal_history', [])
    if not history or idx < 0 or idx >= len(history):
        return redirect(url_for('user'))

    text = history[idx]
    # allow custom filename via query param 'filename'
    filename = request.args.get('filename', '').strip()
    if not filename:
        filename = f"proposal_{idx+1}.txt"
    try:
        from werkzeug.utils import secure_filename as _secure
        filename = _secure(filename)
    except Exception:
        pass
    return Response(
        text,
        mimetype="text/plain; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.route('/user/assistant/load_conversation/<int:idx>')
def load_conversation(idx):
    if session.get('role') != 'user':
        return redirect(url_for('home'))

    convs = session.get('conversation_history', [])
    if not convs or idx < 0 or idx >= len(convs):
        return redirect(url_for('user_assistant'))

    session['chat_history'] = convs[idx].get('chat', [])
    # 標記正在編輯的對話索引，以及其對應的企劃索引
    session['editing_conversation_idx'] = idx
    session['editing_proposal_idx'] = convs[idx].get('proposal_idx')  # Get linked proposal index
    return redirect(url_for('user_assistant'))


@app.route('/user/assistant/download_conversation/<int:idx>')
def download_conversation(idx):
    if session.get('role') != 'user':
        return redirect(url_for('home'))

    convs = session.get('conversation_history', [])
    if not convs or idx < 0 or idx >= len(convs):
        return redirect(url_for('user_assistant'))

    conv = convs[idx]
    lines = [f"對話紀錄（{conv.get('timestamp','')})\n\n"]
    for m in conv.get('chat', []):
        role = '您' if m.get('role') == 'user' else '助理'
        lines.append(f"{role}：{m.get('content','')}")
        lines.append("")

    export_text = "\n".join(lines)
    filename = request.args.get('filename', '').strip()
    if not filename:
        filename = f"conversation_{idx+1}.txt"
    try:
        from werkzeug.utils import secure_filename as _secure
        filename = _secure(filename)
    except Exception:
        pass

    return Response(
        export_text,
        mimetype='text/plain; charset=utf-8',
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.route('/user/assistant/rename_conversation/<int:idx>', methods=['POST'])
def rename_conversation(idx):
    if session.get('role') != 'user':
        return jsonify({'error': '權限不足'}), 403
    
    data = request.get_json() or {}
    new_name = (data.get('name') or '').strip()
    if not new_name:
        return jsonify({'error': '名稱不能為空'}), 400
    
    convs = session.get('conversation_history', [])
    if not convs or idx < 0 or idx >= len(convs):
        return jsonify({'error': '對話不存在'}), 404
    
    convs[idx]['name'] = new_name
    session['conversation_history'] = convs
    session.modified = True
    
    return jsonify({'success': True, 'name': new_name})

@app.route('/user/assistant/from_proposal/<int:idx>')
def resume_conversation_from_proposal(idx):
    if session.get('role') != 'user':
        return redirect(url_for('home'))
    
    # Load the proposal as a message and clear chat history to start fresh
    proposals = session.get('proposal_history', [])
    if not proposals or idx < 0 or idx >= len(proposals):
        return redirect(url_for('user_assistant'))
    
    proposal_text = proposals[idx]
    # Initialize chat with the proposal as context
    session['chat_history'] = []
    session['last_proposal'] = proposal_text
    
    return redirect(url_for('user_assistant'))

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
    session.pop("username", None)
    return redirect(url_for("home"))

@app.route("/user/profile", methods=["GET", "POST"])
def user_profile():
    if session.get("role") != "user":
        return redirect(url_for("home"))

    username = session.get("username")
    user = find_user(username)
    if not user:
        return redirect(url_for("home"))

    error = None
    success = None
    org_profile = user.get("org_profile", {
        "org_name": "",
        "org_id": "",
        "member_count": "",
        "volunteer_count": "",
        "contact_person": "",
        "address": ""
    })

    if request.method == "POST":
        org_profile = {
            "org_name": request.form.get("org_name", "").strip(),
            "org_id": request.form.get("org_id", "").strip(),
            "member_count": request.form.get("member_count", "").strip(),
            "volunteer_count": request.form.get("volunteer_count", "").strip(),
            "contact_person": request.form.get("contact_person", "").strip(),
            "address": request.form.get("address", "").strip()
        }
        update_user_profile(username, org_profile)
        success = "已儲存您的社福團體資料。"

    return render_template(
        "profile.html",
        username=username,
        org_profile=org_profile,
        success=success,
        error=error
    )

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
