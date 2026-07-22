"""
Ledger & Commission — Finance Dashboard (Web)
Software by O2 Nexus Global — otngqa@gmail.com

A real multi-user web application: Flask backend + a SQL database,
serving the dashboard to every browser that visits it. All users and
the admin share one live dataset over the internet — no manual sync,
no per-computer data files. Passwords are hashed, never stored or
sent in plain text once this app is deployed behind HTTPS.

Database: uses SQLite by default (zero setup, a real .db file next
to the app) — or, if a DATABASE_URL environment variable is set
(pointing at a PostgreSQL database, e.g. from Render/Railway/Supabase),
it uses that instead. Same schema, same queries, same code either
way — only the connection underneath changes.
"""
import os
import json
import time
import uuid
import secrets
import sqlite3
from functools import wraps

from flask import Flask, request, jsonify, session, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__)

# ---- persistent secret key so sessions survive restarts ----
SECRET_PATH = os.path.join(BASE_DIR, ".secret_key")
if os.path.exists(SECRET_PATH):
    with open(SECRET_PATH, "r") as f:
        app.secret_key = f.read().strip()
else:
    key = secrets.token_hex(32)
    with open(SECRET_PATH, "w") as f:
        f.write(key)
    app.secret_key = key

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("LEDGER_COOKIE_SECURE", "1") == "1",
)

# ============================================================
# DATABASE — SQLite by default; a real PostgreSQL SQL database
# when DATABASE_URL is set. Both are accessed through the same
# get_db()/execute() interface below, so every query in this file
# is written once and works against either engine unchanged.
# ============================================================
DB_PATH = os.environ.get("LEDGER_DB_PATH", os.path.join(BASE_DIR, "ledger.db"))
DATABASE_URL = os.environ.get("DATABASE_URL")
USE_POSTGRES = bool(DATABASE_URL)

if USE_POSTGRES:
    import psycopg2
    import psycopg2.extras
    # Some hosts (Render, Heroku) hand out "postgres://"; psycopg2 needs "postgresql://"
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://"):]

DEFAULT_SERVICES = [
    "Travel", "Accommodation", "Meals & Entertainment", "Office Supplies",
    "Transportation", "Client Gifts", "Software & Subscriptions", "Miscellaneous",
]


class PgConnWrapper:
    """Makes a psycopg2 connection behave like sqlite3's Connection:
    conn.execute(sql, params) returns a cursor you can fetchone/fetchall
    straight away, and rows support row['column_name'] access — exactly
    like sqlite3.Row does. This is the only place that needs to know
    the two engines differ; every route in this file just calls
    conn.execute(...) the same way regardless of which database is live."""
    def __init__(self, conn):
        self._conn = conn

    @staticmethod
    def _q(sql):
        # sqlite-style "?" placeholders -> psycopg2-style "%s"
        return sql.replace("?", "%s")

    def execute(self, sql, params=()):
        cur = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(self._q(sql), params)
        return cur

    def executemany(self, sql, seq_of_params):
        cur = self._conn.cursor()
        cur.executemany(self._q(sql), seq_of_params)
        return cur

    def executescript(self, sql):
        cur = self._conn.cursor()
        cur.execute(sql)
        return cur

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()


def get_db():
    if USE_POSTGRES:
        return PgConnWrapper(psycopg2.connect(DATABASE_URL))
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# One exception type to catch a "unique constraint violated" error,
# whichever engine is running underneath.
DB_INTEGRITY_ERROR = psycopg2.IntegrityError if USE_POSTGRES else sqlite3.IntegrityError


# Postgres uses SERIAL/IDENTITY differently from SQLite's ROWID, but
# since every table here uses a TEXT primary key we already generate
# ourselves (username, uuid, service name, config key), the exact same
# CREATE TABLE statements are valid on both engines unchanged.
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users(
    username TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    commission_pct REAL,
    created_at BIGINT
);
CREATE TABLE IF NOT EXISTS orders(
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL,
    company TEXT NOT NULL,
    description TEXT,
    category TEXT,
    date TEXT,
    amount_total REAL,
    commission_pct REAL,
    client_phone TEXT,
    client_email TEXT,
    payments TEXT,
    comments TEXT,
    created_at BIGINT,
    updated_at BIGINT
);
CREATE TABLE IF NOT EXISTS services(name TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS config(key TEXT PRIMARY KEY, value TEXT);
"""


def init_db():
    conn = get_db()
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    n = conn.execute("SELECT COUNT(*) c FROM services").fetchone()["c"]
    if n == 0:
        conn.executemany("INSERT INTO services(name) VALUES (?)", [(s,) for s in DEFAULT_SERVICES])
        conn.commit()
    conn.close()


init_db()


def get_config(key, default=None):
    conn = get_db()
    row = conn.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def set_config(key, value):
    conn = get_db()
    conn.execute(
        "INSERT INTO config(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )
    conn.commit()
    conn.close()


# ---- auth helpers ----
def current_user():
    uname = session.get("username")
    if not uname:
        return None
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE username=?", (uname,)).fetchone()
    conn.close()
    return row


def login_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        u = current_user()
        if not u:
            return jsonify({"error": "Not signed in"}), 401
        return f(u, *a, **kw)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        u = current_user()
        if not u:
            return jsonify({"error": "Not signed in"}), 401
        if u["role"] != "admin":
            return jsonify({"error": "Admins only"}), 403
        return f(u, *a, **kw)
    return wrapper


# ============================================================
# AUTH / SETUP
# ============================================================
@app.route("/api/setup-status")
def setup_status():
    conn = get_db()
    n = conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
    conn.close()
    return jsonify({"setupDone": n > 0})


@app.route("/api/setup", methods=["POST"])
def setup():
    conn = get_db()
    n = conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
    if n > 0:
        conn.close()
        return jsonify({"error": "Setup already completed"}), 400
    data = request.get_json(force=True)
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    comm = float(data.get("commissionPct") or 5)
    if not username or not password:
        conn.close()
        return jsonify({"error": "Username and password required"}), 400
    conn.execute(
        "INSERT INTO users(username,password_hash,role,commission_pct,created_at) VALUES (?,?,?,?,?)",
        (username, generate_password_hash(password), "admin", None, int(time.time() * 1000)),
    )
    conn.commit()
    conn.close()
    set_config("globalCommissionPct", str(comm))
    session["username"] = username
    return jsonify({"username": username, "role": "admin", "commissionPct": None})


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(force=True)
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    conn.close()
    if not row or not check_password_hash(row["password_hash"], password):
        return jsonify({"error": "Incorrect username or password"}), 401
    session["username"] = row["username"]
    return jsonify({"username": row["username"], "role": row["role"], "commissionPct": row["commission_pct"]})


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/session")
def session_info():
    u = current_user()
    if not u:
        return jsonify(None)
    return jsonify({"username": u["username"], "role": u["role"], "commissionPct": u["commission_pct"]})


# ============================================================
# CONFIG
# ============================================================
@app.route("/api/config")
@login_required
def api_get_config(u):
    return jsonify({"globalCommissionPct": float(get_config("globalCommissionPct", "5"))})


@app.route("/api/config", methods=["PUT"])
@admin_required
def api_set_config(u):
    data = request.get_json(force=True)
    set_config("globalCommissionPct", str(float(data.get("globalCommissionPct") or 0)))
    return jsonify({"ok": True})


# ============================================================
# SERVICES
# ============================================================
@app.route("/api/services")
@login_required
def api_services(u):
    conn = get_db()
    rows = conn.execute("SELECT name FROM services ORDER BY name").fetchall()
    conn.close()
    return jsonify([r["name"] for r in rows])


@app.route("/api/services", methods=["POST"])
@login_required
def api_add_service(u):
    name = (request.get_json(force=True).get("name") or "").strip()
    if not name:
        return jsonify({"error": "Name required"}), 400
    conn = get_db()
    try:
        conn.execute("INSERT INTO services(name) VALUES (?)", (name,))
        conn.commit()
    except DB_INTEGRITY_ERROR:
        conn.close()
        return jsonify({"error": "That service already exists"}), 400
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/services/<path:name>", methods=["DELETE"])
@login_required
def api_delete_service(u, name):
    conn = get_db()
    conn.execute("DELETE FROM services WHERE name=?", (name,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


# ============================================================
# USERS (admin only, except self-service /api/me)
# ============================================================
def user_public(row):
    return {"username": row["username"], "role": row["role"], "commissionPct": row["commission_pct"]}


@app.route("/api/users")
@admin_required
def api_list_users(u):
    conn = get_db()
    rows = conn.execute("SELECT * FROM users WHERE role='user' ORDER BY username").fetchall()
    conn.close()
    return jsonify([user_public(r) for r in rows])


@app.route("/api/users", methods=["POST"])
@admin_required
def api_add_user(u):
    data = request.get_json(force=True)
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    comm = data.get("commissionPct")
    comm = float(comm) if comm not in (None, "") else None
    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users(username,password_hash,role,commission_pct,created_at) VALUES (?,?,?,?,?)",
            (username, generate_password_hash(password), "user", comm, int(time.time() * 1000)),
        )
        conn.commit()
    except DB_INTEGRITY_ERROR:
        conn.close()
        return jsonify({"error": "That username already exists"}), 400
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/users/<path:username>", methods=["PUT"])
@admin_required
def api_edit_user(u, username):
    data = request.get_json(force=True)
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "Not found"}), 404
    new_username = (data.get("username") or username).strip()
    new_password = data.get("password") or None
    comm = data.get("commissionPct")
    comm = float(comm) if comm not in (None, "") else None
    if new_username != username:
        if conn.execute("SELECT 1 FROM users WHERE username=?", (new_username,)).fetchone():
            conn.close()
            return jsonify({"error": "That username is taken"}), 400
    pw_hash = generate_password_hash(new_password) if new_password else row["password_hash"]
    conn.execute(
        "UPDATE users SET username=?, password_hash=?, commission_pct=? WHERE username=?",
        (new_username, pw_hash, comm, username),
    )
    if new_username != username:
        conn.execute("UPDATE orders SET username=? WHERE username=?", (new_username, username))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/users/<path:username>", methods=["DELETE"])
@admin_required
def api_delete_user(u, username):
    conn = get_db()
    conn.execute("DELETE FROM users WHERE username=?", (username,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/me", methods=["PUT"])
@login_required
def api_edit_me(u):
    data = request.get_json(force=True)
    if not check_password_hash(u["password_hash"], data.get("currentPassword") or ""):
        return jsonify({"error": "Current password is incorrect"}), 400
    new_username = (data.get("username") or u["username"]).strip()
    new_password = data.get("password") or None
    conn = get_db()
    if new_username != u["username"]:
        if conn.execute("SELECT 1 FROM users WHERE username=?", (new_username,)).fetchone():
            conn.close()
            return jsonify({"error": "That username is taken"}), 400
    pw_hash = generate_password_hash(new_password) if new_password else u["password_hash"]
    conn.execute("UPDATE users SET username=?, password_hash=? WHERE username=?", (new_username, pw_hash, u["username"]))
    if new_username != u["username"]:
        conn.execute("UPDATE orders SET username=? WHERE username=?", (new_username, u["username"]))
    conn.commit()
    conn.close()
    session["username"] = new_username
    return jsonify({"username": new_username})


# ============================================================
# ORDERS  (each with a "payments" array, matching the app's model)
# ============================================================
def order_row_to_dict(row):
    return {
        "id": row["id"], "username": row["username"], "company": row["company"],
        "description": row["description"] or "", "category": row["category"],
        "date": row["date"], "amountTotal": row["amount_total"],
        "commissionPct": row["commission_pct"],
        "clientPhone": row["client_phone"] or "", "clientEmail": row["client_email"] or "",
        "payments": json.loads(row["payments"] or "[]"),
        "comments": json.loads(row["comments"] or "[]"),
        "createdAt": row["created_at"], "updatedAt": row["updated_at"],
    }


def get_owned_order(conn, u, order_id):
    row = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    if not row:
        return None
    if u["role"] != "admin" and row["username"] != u["username"]:
        return None
    return row


@app.route("/api/orders")
@login_required
def api_list_orders(u):
    conn = get_db()
    if u["role"] == "admin":
        rows = conn.execute("SELECT * FROM orders ORDER BY date DESC").fetchall()
    else:
        rows = conn.execute("SELECT * FROM orders WHERE username=? ORDER BY date DESC", (u["username"],)).fetchall()
    conn.close()
    return jsonify([order_row_to_dict(r) for r in rows])


@app.route("/api/orders", methods=["POST"])
@login_required
def api_create_order(u):
    data = request.get_json(force=True)
    company = (data.get("company") or "").strip()
    date = data.get("date")
    if not company or not date:
        return jsonify({"error": "Company and date required"}), 400
    commission_pct = u["commission_pct"] if u["commission_pct"] is not None else float(get_config("globalCommissionPct", "5"))
    first_payment = float(data.get("firstPayment") or 0)
    payments = [{"date": date, "amount": first_payment}] if first_payment > 0 else []
    oid = uuid.uuid4().hex
    now = int(time.time() * 1000)
    conn = get_db()
    conn.execute(
        """INSERT INTO orders(id,username,company,description,category,date,amount_total,commission_pct,
           client_phone,client_email,payments,comments,created_at,updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (oid, u["username"], company, data.get("description", ""), data.get("category", "Miscellaneous"), date,
         float(data.get("amountTotal") or 0), commission_pct, data.get("clientPhone", ""), data.get("clientEmail", ""),
         json.dumps(payments), json.dumps([]), now, now),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
    conn.close()
    return jsonify(order_row_to_dict(row))


@app.route("/api/orders/<order_id>", methods=["PUT"])
@login_required
def api_edit_order(u, order_id):
    data = request.get_json(force=True)
    conn = get_db()
    row = get_owned_order(conn, u, order_id)
    if not row:
        conn.close()
        return jsonify({"error": "Not found"}), 404
    now = int(time.time() * 1000)
    conn.execute(
        "UPDATE orders SET company=?, description=?, category=?, date=?, amount_total=?, client_phone=?, client_email=?, updated_at=? WHERE id=?",
        (data.get("company", row["company"]), data.get("description", row["description"]), data.get("category", row["category"]),
         data.get("date", row["date"]), float(data.get("amountTotal", row["amount_total"]) or 0),
         data.get("clientPhone", row["client_phone"]), data.get("clientEmail", row["client_email"]), now, order_id),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    conn.close()
    return jsonify(order_row_to_dict(row))


@app.route("/api/orders/<order_id>", methods=["DELETE"])
@login_required
def api_delete_order(u, order_id):
    conn = get_db()
    row = get_owned_order(conn, u, order_id)
    if not row:
        conn.close()
        return jsonify({"error": "Not found"}), 404
    conn.execute("DELETE FROM orders WHERE id=?", (order_id,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/orders/<order_id>/payments", methods=["POST"])
@login_required
def api_add_payment(u, order_id):
    data = request.get_json(force=True)
    amount = float(data.get("amount") or 0)
    date = data.get("date")
    if amount <= 0 or not date:
        return jsonify({"error": "Valid amount and date required"}), 400
    conn = get_db()
    row = get_owned_order(conn, u, order_id)
    if not row:
        conn.close()
        return jsonify({"error": "Not found"}), 404
    payments = json.loads(row["payments"] or "[]")
    payments.append({"date": date, "amount": amount})
    now = int(time.time() * 1000)
    conn.execute("UPDATE orders SET payments=?, updated_at=? WHERE id=?", (json.dumps(payments), now, order_id))
    conn.commit()
    row = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    conn.close()
    return jsonify(order_row_to_dict(row))


@app.route("/api/orders/<order_id>/payments/<int:idx>", methods=["DELETE"])
@login_required
def api_delete_payment(u, order_id, idx):
    conn = get_db()
    row = get_owned_order(conn, u, order_id)
    if not row:
        conn.close()
        return jsonify({"error": "Not found"}), 404
    payments = json.loads(row["payments"] or "[]")
    if 0 <= idx < len(payments):
        payments.pop(idx)
    now = int(time.time() * 1000)
    conn.execute("UPDATE orders SET payments=?, updated_at=? WHERE id=?", (json.dumps(payments), now, order_id))
    conn.commit()
    row = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    conn.close()
    return jsonify(order_row_to_dict(row))


@app.route("/api/orders/<order_id>/comments", methods=["POST"])
@login_required
def api_add_comment(u, order_id):
    text = (request.get_json(force=True).get("text") or "").strip()
    if not text:
        return jsonify({"error": "Comment text required"}), 400
    conn = get_db()
    row = get_owned_order(conn, u, order_id)
    if not row:
        conn.close()
        return jsonify({"error": "Not found"}), 404
    comments = json.loads(row["comments"] or "[]")
    comments.append({"by": u["username"], "role": u["role"], "text": text, "ts": int(time.time() * 1000)})
    now = int(time.time() * 1000)
    conn.execute("UPDATE orders SET comments=?, updated_at=? WHERE id=?", (json.dumps(comments), now, order_id))
    conn.commit()
    row = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    conn.close()
    return jsonify(order_row_to_dict(row))


# ============================================================
# BACKUP EXPORT (admin only)
# ============================================================
@app.route("/api/export")
@admin_required
def api_export(u):
    conn = get_db()
    users = [user_public(r) for r in conn.execute("SELECT * FROM users").fetchall()]
    orders = [order_row_to_dict(r) for r in conn.execute("SELECT * FROM orders").fetchall()]
    services = [r["name"] for r in conn.execute("SELECT name FROM services").fetchall()]
    conn.close()
    payload = {"users": users, "orders": orders, "services": services, "exportedAt": int(time.time() * 1000)}
    resp = jsonify(payload)
    resp.headers["Content-Disposition"] = "attachment; filename=ledger-backup.json"
    return resp


# ============================================================
# FRONTEND
# ============================================================
@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "dashboard.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
