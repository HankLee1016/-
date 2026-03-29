import os
import json
import hashlib
from pathlib import Path
from flask import Flask, request, jsonify, render_template, send_from_directory, redirect, url_for, session
from psycopg2 import OperationalError
from db_config import get_db_connection

app = Flask(__name__, template_folder="templates")
app.secret_key = os.getenv("SECRET_KEY", "dev_secret_key")

USERS_FILE = Path(app.root_path) / "users.json"
ADMIN_REG_CODE = os.getenv("ADMIN_REG_CODE", "ADMIN2026")


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

@app.route("/css/<path:filename>")
def css(filename):
    return send_from_directory(os.path.join(app.root_path, "static", "css"), filename)

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
    return render_template("user.html", username=session.get("username"))

@app.route("/admin")
def admin_dashboard():
    if session.get("role") != "admin":
        return redirect(url_for("home"))
    return render_template("admin.html", username=session.get("username"))

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
