from flask import Flask, render_template, request, redirect, url_for, abort, session
from datetime import datetime, timedelta
import os
import sqlite3

from config import DATABASE, UPLOAD_FOLDER, SECRET_KEY, ADMIN_PASSWORD
#print("APP LOADED")


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

def get_active_challenge():
    return query_db(
        "SELECT * FROM challenges WHERE active = 1",
        one=True
    )

# ---------- Initialisierung ----------
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        team_name = request.form["team"]

        team = query_db(
            "SELECT * FROM teams WHERE name = ?",
            (team_name,),
            one=True
        )

        if not team:
            query_db(
                "INSERT INTO teams (name) VALUES (?)",
                (team_name,)
            )

            team = query_db(
                "SELECT * FROM teams WHERE name = ?",
                (team_name,),
                one=True
            )

        session["team_id"] = team["id"]
        session["team_name"] = team["name"]

        return redirect(url_for("challenge_view"))

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
  
@app.route("/admin/challenge/<int:cid>/activate")
def activate_challenge(cid):
    # alle deaktivieren
    query_db("UPDATE challenges SET active = 0")

    # diese aktivieren
    query_db("UPDATE challenges SET active = 1 WHERE id = ?", (cid,))

    return redirect(url_for("admin_dashboard"))

@app.route("/admin/challenge/<int:cid>/tasks", methods=["GET", "POST"])
def manage_tasks(cid):
    challenge = query_db(
        "SELECT * FROM challenges WHERE id = ?", (cid,), one=True
    )

    if request.method == "POST":
        title = request.form["title"]
        desc = request.form["description"]
        max_points = int(request.form["max_points"])

        query_db(
            "INSERT INTO tasks (challenge_id, title, description, max_points) VALUES (?, ?, ?, ?)",
            (cid, title, desc, max_points)
        )

    tasks = query_db(
        "SELECT * FROM tasks WHERE challenge_id = ?", (cid,)
    )
    print("TASK ROUTE REGISTERED")
    return render_template(
        "admin/tasks.html",
        challenge=challenge,
        tasks=tasks
    )

# ---------- Teams ----------
@app.route("/challenge")
def challenge_view():
    if "team_id" not in session:
        return redirect(url_for("index"))

    challenge = get_active_challenge()

    if not challenge:
        return render_template(
            "challenge.html",
            message="Aktuell ist keine Challenge aktiv."
        )

    tasks = query_db(
        "SELECT * FROM tasks WHERE challenge_id = ?",
        (challenge["id"],)
    )

    return render_template(
        "challenge.html",
        challenge=challenge,
        tasks=tasks,
        team=session["team_name"]
    )


if __name__ == "__main__":
    app.run(debug=True)
