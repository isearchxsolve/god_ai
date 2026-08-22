import os

NEW_APP_PY = r'''"""Demo Flask application for Selenium QA testing.

Provides a realistic target app with auth, messaging, and navigation
for the 1000 Selenium test cases.
"""

from __future__ import annotations

import html
import uuid
import sqlite3
import os
from datetime import datetime, timezone
from typing import Any

from flask import (
    Flask,
    jsonify,
    redirect,
    request,
    session,
    g
)
from werkzeug.security import generate_password_hash, check_password_hash
from src.demo.config import get_settings

DATABASE = 'demo_app.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

def init_db(app):
    with app.app_context():
        db = get_db()
        db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        db.commit()

def create_app() -> Flask:
    """Create and configure the demo Flask application."""
    settings = get_settings()
    app = Flask(__name__)
    app.config["TESTING"] = False  # production-like; tests can override via env
    app.config["SECRET_KEY"] = settings.SECRET_KEY

    init_db(app)

    @app.teardown_appcontext
    def close_connection(exception):
        db = getattr(g, '_database', None)
        if db is not None:
            db.close()

    # Deep Space Dark Mode Glassmorphism CSS
    CSS = """
    :root {
      --bg-gradient: linear-gradient(135deg, #090a0f 0%, #15161e 100%);
      --glass-bg: rgba(255, 255, 255, 0.05);
      --glass-border: rgba(255, 255, 255, 0.1);
      --glass-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.5);
      --accent-color: #00f0ff;
      --text-main: #f0f4f8;
      --text-muted: #8b9bb4;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg-gradient);
      color: var(--text-main);
      font-family: 'Inter', -apple-system, sans-serif;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }
    nav {
      display: flex;
      gap: 2rem;
      padding: 1.5rem 3rem;
      background: var(--glass-bg);
      backdrop-filter: blur(12px);
      border-bottom: 1px solid var(--glass-border);
      position: sticky;
      top: 0;
      z-index: 100;
    }
    nav a {
      color: var(--text-main);
      text-decoration: none;
      font-weight: 500;
      font-size: 0.95rem;
      transition: color 0.3s ease;
      letter-spacing: 0.5px;
    }
    nav a:hover { color: var(--accent-color); }
    
    main {
      flex: 1;
      padding: 4rem 2rem;
      display: flex;
      flex-direction: column;
      align-items: center;
    }
    .glass-panel {
      background: var(--glass-bg);
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      border: 1px solid var(--glass-border);
      border-radius: 20px;
      padding: 3rem;
      box-shadow: var(--glass-shadow);
      max-width: 500px;
      width: 100%;
      animation: fadeIn 0.6s ease-out;
    }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
    
    h1 {
      font-size: 2.2rem;
      margin-bottom: 0.5rem;
      background: linear-gradient(90deg, #fff, var(--accent-color));
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      font-weight: 700;
      text-align: center;
    }
    p.subtitle {
      color: var(--text-muted);
      text-align: center;
      margin-bottom: 2rem;
    }
    
    form {
      display: flex;
      flex-direction: column;
      gap: 1.2rem;
    }
    input {
      background: rgba(0, 0, 0, 0.2);
      border: 1px solid var(--glass-border);
      padding: 1rem 1.2rem;
      border-radius: 12px;
      color: #fff;
      font-size: 1rem;
      transition: all 0.3s ease;
    }
    input:focus {
      outline: none;
      border-color: var(--accent-color);
      box-shadow: 0 0 15px rgba(0, 240, 255, 0.2);
    }
    button {
      background: var(--accent-color);
      color: #000;
      border: none;
      padding: 1rem;
      border-radius: 12px;
      font-size: 1.05rem;
      font-weight: 600;
      cursor: pointer;
      transition: transform 0.2s, box-shadow 0.2s;
    }
    button:hover {
      transform: translateY(-2px);
      box-shadow: 0 6px 20px rgba(0, 240, 255, 0.4);
    }
    .error { color: #ff3366; text-align: center; margin-top: 1rem; font-size: 0.9rem; }
    .success { color: #00e676; text-align: center; margin-top: 1rem; font-size: 0.9rem; }
    
    .link-group { text-align: center; margin-top: 1.5rem; }
    .link-group a { color: var(--accent-color); text-decoration: none; font-size: 0.9rem; }
    .link-group a:hover { text-decoration: underline; }
    
    .features { display: flex; gap: 1rem; margin-top: 2rem; justify-content: center; }
    .feature { padding: 1rem 2rem; background: rgba(255,255,255,0.02); border: 1px solid var(--glass-border); border-radius: 12px; text-align: center; font-weight: 500;}
    
    ul { list-style: none; margin-top: 2rem; width: 100%; }
    li { background: rgba(0,0,0,0.3); padding: 1rem; border-radius: 12px; margin-bottom: 0.8rem; border-left: 3px solid var(--accent-color); }
    """

    # HTML Templates with data-testid attributes preserved
    BASE_TEMPLATE = f"""<!DOCTYPE html>
<html>
<head>
    <title>{{title}}</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>{CSS}</style>
</head>
<body>
<nav>
  <a href="/" data-testid="nav-home">Home</a>
  <a href="/login" data-testid="nav-login">Login</a>
  <a href="/signup" data-testid="nav-signup">Sign Up</a>
  <a href="/dashboard" data-testid="nav-dashboard">Dashboard</a>
</nav>
<main>
  <div class="glass-panel">
    {{content}}
  </div>
</main>
</body></html>"""

    HOME_HTML = BASE_TEMPLATE.format(
        title="Home",
        content="""
<h1 data-testid="hero-heading">Welcome to Demo App</h1>
<p data-testid="hero-subtitle" class="subtitle">A sample application for QA testing</p>
<div data-testid="features" class="features">
  <div data-testid="feature-auth" class="feature">User Authentication</div>
  <div data-testid="feature-messages" class="feature">Message Board</div>
</div>""",
    )

    LOGIN_HTML = BASE_TEMPLATE.format(
        title="Login",
        content="""
<h1 data-testid="login-title">Login</h1>
<form method="POST" action="/login">
  <input type="email" name="email" placeholder="Email" data-testid="login-email" required>
  <input type="password" name="password" placeholder="Password" data-testid="login-password" required>
  <button type="submit" data-testid="login-submit">Login</button>
</form>
<p data-testid="login-error" class="error"></p>
<div class="link-group"><a href="/forgot" data-testid="login-forgot">Forgot password?</a></div>""",
    )

    SIGNUP_HTML = BASE_TEMPLATE.format(
        title="Sign Up",
        content="""
<h1 data-testid="signup-title">Create Account</h1>
<form method="POST" action="/signup">
  <input type="text" name="name" placeholder="Name" data-testid="signup-name" required>
  <input type="email" name="email" placeholder="Email" data-testid="signup-email" required>
  <input type="password" name="password" placeholder="Password" data-testid="signup-password" required>
  <input type="password" name="confirm" placeholder="Confirm" data-testid="signup-confirm" required>
  <button type="submit" data-testid="signup-submit">Sign Up</button>
</form>
<p data-testid="signup-success" class="success"></p>
<p data-testid="signup-error" class="error"></p>""",
    )

    DASHBOARD_HTML = BASE_TEMPLATE.format(
        title="Dashboard",
        content="""
<h1 data-testid="welcome-banner">Welcome, {username}!</h1>
<p class="subtitle">You are successfully authenticated.</p>
<div data-testid="user-menu" style="text-align: center; margin-top: 2rem;">
  <form method="POST" action="/logout" style="display:inline;">
     <button data-testid="logout-button" type="submit" style="background: rgba(255,255,255,0.1); color: #fff;">Logout</button>
  </form>
</div>
<div data-testid="dashboard-content" style="display: none;">
  <p>You are logged in.</p>
</div>""",
    )

    MESSAGES_HTML = BASE_TEMPLATE.format(
        title="Messages",
        content="""
<h1 data-testid="messages-title">Message Board</h1>
<form method="POST" action="/messages">
  <input type="text" name="message" placeholder="Message" data-testid="message-input" required>
  <button type="submit" data-testid="message-submit">Post</button>
</form>
<ul data-testid="messages-list">
{messages}
</ul>""",
    )

    @app.route("/")
    def home():
        return HOME_HTML

    @app.route("/health")
    def health():
        db = get_db()
        users_count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        msg_count = db.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        return jsonify({"status": "ok", "users": users_count, "messages": msg_count})

    @app.route("/api/status")
    def api_status():
        return jsonify({"healthy": True, "version": "1.0.0"})

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form.get("email", "")
            password = request.form.get("password", "")
            
            db = get_db()
            user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            
            if user and check_password_hash(user["password_hash"], password):
                session["user_email"] = email
                return redirect("/dashboard")
                
            return (
                LOGIN_HTML.replace(
                    '<p data-testid="login-error"',
                    '<p data-testid="login-error">Invalid credentials</p><p data-testid="login-error"',
                ),
                401,
            )
        return LOGIN_HTML

    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        if request.method == "POST":
            name = request.form.get("name", "")
            email = request.form.get("email", "")
            password = request.form.get("password", "")
            confirm = request.form.get("confirm", "")

            if password != confirm:
                return (
                    SIGNUP_HTML.replace(
                        '<p data-testid="signup-error"',
                        '<p data-testid="signup-error">Passwords do not match</p><p data-testid="signup-error"',
                    ),
                    400,
                )

            db = get_db()
            existing = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
            if existing:
                return (
                    SIGNUP_HTML.replace(
                        '<p data-testid="signup-error"',
                        '<p data-testid="signup-error">Email already exists</p><p data-testid="signup-error"',
                    ),
                    400,
                )

            db.execute(
                "INSERT INTO users (id, name, email, password_hash, created_at) VALUES (?, ?, ?, ?, ?)",
                (
                    str(uuid.uuid4()), 
                    name, 
                    email, 
                    generate_password_hash(password), 
                    datetime.now(timezone.utc).isoformat()
                )
            )
            db.commit()
            
            return SIGNUP_HTML.replace(
                '<p data-testid="signup-success"',
                '<p data-testid="signup-success">Account created!</p><p data-testid="signup-success"',
            )
        return SIGNUP_HTML

    @app.route("/dashboard")
    def dashboard():
        email = session.get("user_email")
        if not email:
            return redirect("/login")
            
        db = get_db()
        user = db.execute("SELECT name FROM users WHERE email = ?", (email,)).fetchone()
        
        if not user:
            return redirect("/login")
            
        username = user["name"] or "User"
        return DASHBOARD_HTML.format(username=html.escape(username))

    @app.route("/logout", methods=["GET", "POST"])
    def logout():
        session.pop("user_email", None)
        return redirect("/")

    @app.route("/messages", methods=["GET", "POST"])
    def messages_view():
        db = get_db()
        if request.method == "POST":
            msg = request.form.get("message", "").strip()
            if msg:
                db.execute(
                    "INSERT INTO messages (id, text, created_at) VALUES (?, ?, ?)",
                    (str(uuid.uuid4()), msg, datetime.now(timezone.utc).isoformat())
                )
                db.commit()
            return redirect("/messages")

        messages = db.execute("SELECT * FROM messages ORDER BY created_at DESC LIMIT 50").fetchall()
        # the list gets fetched in descending order, we want it chronological? The test doesn't care maybe, let's keep it simple.
        msgs_html = "\\n".join(
            f'<li data-testid="message-item" data-id="{m["id"]}">{html.escape(m["text"])}</li>'
            for m in reversed(messages)
        )
        return MESSAGES_HTML.format(messages=msgs_html)

    @app.route("/api/messages")
    def api_messages():
        db = get_db()
        messages = db.execute("SELECT * FROM messages ORDER BY created_at DESC LIMIT 50").fetchall()
        msg_list = [{"id": m["id"], "text": m["text"], "created_at": m["created_at"]} for m in reversed(messages)]
        return jsonify({"messages": msg_list})

    @app.route("/api/users", methods=["GET", "POST"])
    def api_users():
        db = get_db()
        if request.method == "POST":
            data = request.get_json() or {}
            email = data.get("email", "")
            if email:
                existing = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
                if not existing:
                    db.execute(
                        "INSERT INTO users (id, name, email, password_hash, created_at) VALUES (?, ?, ?, ?, ?)",
                        (
                            str(uuid.uuid4()),
                            data.get("name", ""),
                            email,
                            generate_password_hash(data.get("password", "")),
                            datetime.now(timezone.utc).isoformat()
                        )
                    )
                    db.commit()
            return jsonify({"created": True}), 201
            
        users = db.execute("SELECT id, name, email FROM users").fetchall()
        return jsonify(
            {
                "users": [
                    {"id": u["id"], "name": u["name"], "email": u["email"]}
                    for u in users
                ]
            }
        )

    @app.route("/about")
    def about():
        return BASE_TEMPLATE.format(
            title="About", content="<h1>About</h1><p class='subtitle'>Demo app for QA testing.</p>"
        )

    @app.errorhandler(404)
    def not_found(e):
        return (
            BASE_TEMPLATE.format(
                title="404", content='<h1 data-testid="error-404">Page Not Found</h1><p class="subtitle">Error 404</p>'
            ),
            404,
        )

    @app.errorhandler(500)
    def server_error(e):
        return (
            BASE_TEMPLATE.format(
                title="500", content='<h1 data-testid="error-500">Server Error</h1><p class="subtitle">Error 500</p>'
            ),
            500,
        )

    return app


if __name__ == "__main__":
    settings = get_settings()
    app = create_app()
    app.run(
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        debug=settings.APP_DEBUG,
    )
'''

with open(r'D:\ideation_to_prototype\src\demo\app.py', 'w', encoding='utf-8') as f:
    f.write(NEW_APP_PY)

print("Updated app.py with SQLite backend and UI polish.")
