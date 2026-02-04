from flask import Flask, render_template, request, redirect, url_for, abort
from datetime import datetime, timedelta
import os
import sqlite3

from config import DATABASE, UPLOAD_FOLDER, SECRET_KEY, ADMIN_PASSWORD

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


# ---------- Datenbank ----------
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def query_db(query, args=(), one=False):
    conn = get_db()
    cur = conn.execute(query, args)
    rv = cur.fetchall()
    conn.commit()
    conn.close()
    return (rv[0] if rv else None) if one else rv

# ---------- Initialisierung ----------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/challenge")
def challenge():
    return render_template("challenge.html")


@app.route("/scoreboard")
def scoreboard():
    return render_template("scoreboard.html")


# ---------- Admin ----------
@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if request.form["password"] == ADMIN_PASSWORD:
            return redirect(url_for("admin_dashboard"))
        else:
            abort(403)
    return render_template("admin/login.html")


@app.route("/admin/dashboard")
def admin_dashboard():
    challenges = query_db("SELECT * FROM challenges ORDER BY id DESC")
    return render_template("admin/dashboard.html", challenges=challenges)

@app.route("/admin/challenge/new", methods=["GET", "POST"])
def new_challenge():
    if request.method == "POST":
        title = request.form["title"]
        duration = int(request.form["duration"])  # Minuten

        start = datetime.now()
        end = start + timedelta(minutes=duration)

        query_db(
            "INSERT INTO challenges (title, start_time, end_time, active) VALUES (?, ?, ?, 0)",
            (title, start.isoformat(), end.isoformat())
        )
        return redirect(url_for("admin_dashboard"))

    return render_template("admin/new_challenge.html")


if __name__ == "__main__":
    app.run(debug=True)
