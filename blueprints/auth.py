import secrets

from flask import Blueprint, render_template, request, redirect, url_for, session, current_app
from extensions import limiter

auth_bp = Blueprint('auth', __name__)


def passwort_stimmt(eingabe, erwartet):
    """Vergleicht die beiden Passwörter, ohne die Dauer zu verraten.

    Ein gewöhnlicher Vergleich bricht beim ersten falschen Zeichen ab und
    braucht damit unterschiedlich lange. Im Schul-LAN und hinter der Bremse
    von fünf Versuchen pro Minute ist daraus nichts zu holen - aber richtig
    vergleichen kostet hier nichts.
    """
    return secrets.compare_digest(str(eingabe or ""), str(erwartet or ""))

@auth_bp.route("/admin/login", methods=["GET", "POST"])
# Only actual login attempts count towards the limit - merely opening or
# reloading the login page must not lock anyone out.
@limiter.limit("5 per minute", methods=["POST"])
def admin_login():
    if request.method == "POST":
        password = request.form.get("password")
        if passwort_stimmt(password, current_app.config['ADMIN_PASSWORD']):
            session["is_admin"] = True
            return redirect(url_for('admin.dashboard')) # Assuming admin blueprint has a dashboard route
        else:
            return render_template(
                "admin/login.html",
                error="Falsches Passwort"
            )

    return render_template("admin/login.html")

@auth_bp.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for('public.index'))
