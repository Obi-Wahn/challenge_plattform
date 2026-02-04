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
    return render_template("admin/dashboard.html")


if __name__ == "__main__":
    app.run(debug=True)
