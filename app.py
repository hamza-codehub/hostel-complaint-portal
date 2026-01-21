from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.secret_key = "secretkey"


# =====================
# DATABASE CONNECTION
# =====================
def get_db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn


# =====================
# DATABASE SETUP
# =====================
def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT UNIQUE,
        hostel TEXT,
        room TEXT,
        password TEXT,
        role TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS complaints (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        category TEXT,
        description TEXT,
        status TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS login_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT,
        status TEXT,
        time TEXT
    )
    """)

    conn.commit()
    conn.close()


init_db()


# =====================
# REGISTER
# =====================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        hostel = request.form["hostel"]
        room = request.form["room"]
        password = generate_password_hash(request.form["password"])

        conn = get_db()
        cur = conn.cursor()

        try:
            cur.execute(
                "INSERT INTO users (name,email,hostel,room,password,role) VALUES (?,?,?,?,?,?)",
                (name, email, hostel, room, password, "user")
            )
            conn.commit()
            flash("Registration successful", "success")
            return redirect(url_for("login"))
        except:
            flash("Email already exists", "error")

        conn.close()

    return render_template("register.html")


# =====================
# LOGIN
# =====================
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db()
        cur = conn.cursor()

        cur.execute("SELECT * FROM users WHERE email=?", (email,))
        user = cur.fetchone()

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # ✅ SUCCESS LOGIN
        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["role"] = user["role"]

            cur.execute(
                "INSERT INTO login_logs (email, status, time) VALUES (?, ?, ?)",
                (email, "SUCCESS", current_time)
            )
            conn.commit()
            conn.close()

            if user["role"] == "admin":
                return redirect(url_for("admin_dashboard"))
            else:
                return redirect(url_for("dashboard"))

        # ❌ FAILED LOGIN
        else:
            cur.execute(
                "INSERT INTO login_logs (email, status, time) VALUES (?, ?, ?)",
                (email, "FAILED", current_time)
            )
            conn.commit()
            conn.close()

            flash("Invalid email or password", "error")

    return render_template("login.html")

@app.route("/admin/update_status/<int:complaint_id>", methods=["POST"])
def update_status(complaint_id):
    # Only admin allowed
    if session.get("role") != "admin":
        return redirect(url_for("login"))

    new_status = request.form["status"]

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "UPDATE complaints SET status=? WHERE id=?",
        (new_status, complaint_id)
    )

    conn.commit()
    conn.close()

    return redirect(url_for("admin_dashboard"))


# =====================
# USER DASHBOARD
# =====================
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    SELECT * FROM complaints WHERE user_id=?
    """, (session["user_id"],))

    complaints = cur.fetchall()
    conn.close()

    return render_template("dashboard.html", complaints=complaints)


# =====================
# SUBMIT COMPLAINT
# =====================
@app.route("/complaint", methods=["GET", "POST"])
def complaint():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        category = request.form["category"]
        description = request.form["description"]

        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
        INSERT INTO complaints (user_id,category,description,status)
        VALUES (?,?,?,?)
        """, (session["user_id"], category, description, "Pending"))

        conn.commit()
        conn.close()

        flash("Complaint submitted", "success")
        return redirect(url_for("dashboard"))

    return render_template("complaint.html")


# =====================
# ADMIN DASHBOARD
# =====================
@app.route("/admin")
def admin_dashboard():
    if session.get("role") != "admin":
        return redirect(url_for("login"))

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    SELECT complaints.*, users.name, users.email, users.room
    FROM complaints
    JOIN users ON complaints.user_id = users.id
    """)

    complaints = cur.fetchall()
    conn.close()

    return render_template("admin.html", complaints=complaints)


# =====================
# LOGIN LOGS
# =====================
@app.route("/admin/logs")
def logs():
    if session.get("role") != "admin":
        return redirect(url_for("login"))

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM login_logs ORDER BY time DESC")
    logs = cur.fetchall()

    conn.close()
    return render_template("logs.html", logs=logs)


# =====================
# LOGOUT
# =====================
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))
 

@app.route("/admin/users")
def admin_users():
    # Allow only admin
    if session.get("role") != "admin":
        return redirect(url_for("login"))

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, name, email, hostel, room, role
        FROM users
        ORDER BY id DESC
    """)
    users = cur.fetchall()

    conn.close()

    return render_template("admin_users.html", users=users)

@app.route("/admin/reports")
def admin_reports():
    # Only admin can access
    if session.get("role") != "admin":
        return redirect(url_for("login"))

    conn = get_db()
    cur = conn.cursor()

    # Count complaints by status
    cur.execute("SELECT COUNT(*) FROM complaints WHERE status='Pending'")
    pending = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM complaints WHERE status='Received'")
    received = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM complaints WHERE status='Verified'")
    verified = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM complaints WHERE status='Resolved'")
    resolved = cur.fetchone()[0]

    conn.close()

    return render_template(
        "reports.html",
        pending=pending,
        received=received,
        verified=verified,
        resolved=resolved
    )
# =====================
# DELETE COMPLAINT
# =====================
@app.route("/admin/delete_complaint/<int:id>", methods=["POST"])
def delete_complaint(id):
    if session.get("role") != "admin":
        return redirect(url_for("login"))
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM complaints WHERE id=?", (id,))
    conn.commit()
    conn.close()
    flash("Complaint deleted successfully", "success")
    return redirect(url_for("admin_dashboard"))

# =====================
# DELETE USER
# =====================
@app.route("/admin/delete_user/<int:id>", methods=["POST"])
def delete_user(id):
    if session.get("role") != "admin":
        return redirect(url_for("login"))
    
    conn = get_db()
    cur = conn.cursor()
    # Prevent admin from deleting themselves
    if id == session.get("user_id"):
        flash("You cannot delete your own admin account", "error")
    else:
        cur.execute("DELETE FROM users WHERE id=?", (id,))
        conn.commit()
        flash("User deleted successfully", "success")
    
    conn.close()
    return redirect(url_for("admin_users"))

# =====================
# DELETE LOG
# =====================
@app.route("/admin/delete_log/<int:id>", methods=["POST"])
def delete_log(id):
    if session.get("role") != "admin":
        return redirect(url_for("login"))
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM login_logs WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for("logs"))

def create_admin():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE role='admin'")
    admin = cur.fetchone()

    if not admin:
        cur.execute("""
        INSERT INTO users (name,email,hostel,room,password,role)
        VALUES (?,?,?,?,?,?)
        """, (
            "Admin",
            "admin@gmail.com",
            "Admin Block",
            "000",
            generate_password_hash("admin123"),
            "admin"
        ))
        conn.commit()

    conn.close()
init_db()
create_admin()

 
if __name__ == "__main__":
    app.run(debug=True)
