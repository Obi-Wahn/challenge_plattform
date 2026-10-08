import secrets

from flask import Blueprint, render_template, request, redirect, url_for, session, current_app
from extensions import limiter
from models import Settings
from protokoll import absender, stoerung
from sitzung import bewertung_abmelden, bewertung_anmelden

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
    """Eine Anmeldeseite für beide Zugänge: Das Passwort entscheidet.

    Mit dem Admin-Passwort geht es in die Steuerzentrale, mit dem Passwort
    für die Bewertung (falls die Lehrkraft eines gesetzt hat) nur auf die
    Bewertungsseite. Beide teilen sich die Bremse von fünf Versuchen.
    """
    site_settings = Settings.get()

    if request.method == "POST":
        password = request.form.get("password")
        if passwort_stimmt(password, current_app.config['ADMIN_PASSWORD']):
            session["is_admin"] = True
            return redirect(url_for('admin.dashboard')) # Assuming admin blueprint has a dashboard route
        if site_settings.check_review_password(password):
            bewertung_anmelden(site_settings)
            return redirect(url_for('admin.submissions'))

        # Im Schul-LAN ist das Protokoll der einzige Ort, an dem zu sehen
        # ist, dass jemand das Admin-Passwort ausprobiert hat.
        stoerung("Admin-Anmeldung fehlgeschlagen, von %s", absender())
        return render_template(
            "admin/login.html",
            error="Falsches Passwort",
            bewertungszugang=site_settings.review_access,
        )

    return render_template("admin/login.html",
                           bewertungszugang=site_settings.review_access)

@auth_bp.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    bewertung_abmelden()
    return redirect(url_for('public.index'))
