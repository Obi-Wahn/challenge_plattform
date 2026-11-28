"""Wer gerade als Team oder zum Bewerten angemeldet ist - und wann das verfällt.

Die Anmeldung eines Teams steht in der Sitzung des Browsers, der Wettbewerb
dazu in der Datenbank. Der kann verschwinden, während das Cookie weiterlebt:
Wird ein Wettbewerb gelöscht, gehen seine Teams mit, im Browser bleibt die
Anmeldung aber stehen. Hier entscheidet deshalb eine einzige Stelle, ob eine
Anmeldung noch gilt, und räumt sie weg, sobald sie es nicht mehr tut.
"""

import hashlib
import hmac

from flask import current_app, session

from plattform.extensions import db
from plattform.models import Team

# Alles, was zu einer Team-Anmeldung gehört.
SITZUNGSSCHLUESSEL = ("team_id", "team_name", "team_uid")


def team_anmelden(team):
    """Merkt sich das Team im Browser: Nummer, Name und Kennzeichen.

    Das Kennzeichen gehört dazu, weil die Nummer allein ein Team nicht
    eindeutig bezeichnet: SQLite vergibt die Nummer eines gelöschten Teams
    wieder - auch die eines gelöschten Wettbewerbs. Ohne das Kennzeichen
    passte eine alte Sitzung auf das nächste Team mit derselben Nummer, und
    dessen Abgaben liefen unter fremdem Namen.
    """
    session["team_id"] = team.id
    session["team_name"] = team.name
    session["team_uid"] = team.uid


def team_abmelden():
    """Räumt die Anmeldung aus der Sitzung."""
    for schluessel in SITZUNGSSCHLUESSEL:
        session.pop(schluessel, None)


def angemeldetes_team(challenge):
    """Das angemeldete Team - oder None, wenn die Anmeldung nicht mehr gilt.

    Sie gilt, solange es dasselbe Team noch gibt und es zum aktuellen
    Wettbewerb gehört. Scheitert eines davon, wird die Anmeldung gleich hier
    geräumt: Sonst käme sie auf jeder folgenden Seite wieder hoch, und die
    obere Leiste zeigte ein Team an, das es längst nicht mehr gibt.

    "Dasselbe Team" prüft das Kennzeichen, nicht die Nummer - siehe
    team_anmelden(). Eine Sitzung ohne Kennzeichen, also eine aus der Zeit
    davor, gilt darum nicht mehr: Die Teams melden sich einmal neu an, das
    ist billiger, als solche Sitzungen ungeprüft durchzulassen.
    """
    team_id = session.get("team_id")
    team_uid = session.get("team_uid")
    if not team_id or not team_uid:
        team_abmelden()
        return None

    team = db.session.get(Team, team_id) if challenge else None
    if team is None or team.uid != team_uid or team.challenge_id != challenge.id:
        team_abmelden()
        return None

    return team


# ------------------------------------------------------------------ Admin

def admin_kennzeichen():
    """Das Kennzeichen, an dem die Anmeldung als Admin hängt.

    Flask legt die Sitzung ins Cookie selbst, unterschrieben mit dem
    SECRET_KEY. Stünde darin nur „ist Admin“, gälte ein einmal kopiertes
    Cookie, solange der Schlüssel bleibt - also für immer, auch nach dem
    Abmelden und nach einem neuen Passwort. Über http lässt sich ein Cookie
    im selben Netz mitlesen. Das Kennzeichen hängt deshalb am Passwort:
    Ein neues ADMIN_PASSWORD in der .env, danach neu starten, und jede alte
    Admin-Sitzung ist draußen.

    Es ist ein HMAC mit dem SECRET_KEY, kein Hash des Passworts allein: Das
    Cookie ist unterschrieben, aber lesbar, und ein bloßer Hash ließe sich
    für ein schwaches Passwort zurückraten.
    """
    schluessel = str(current_app.config["SECRET_KEY"]).encode("utf-8")
    passwort = str(current_app.config["ADMIN_PASSWORD"]).encode("utf-8")
    return hmac.new(schluessel, b"admin:" + passwort, hashlib.sha256).hexdigest()[:32]


def admin_anmelden():
    session.pop("is_admin", None)
    session["admin"] = admin_kennzeichen()


def admin_abmelden():
    # „is_admin“ stand bis v1.25.9 in der Sitzung und gilt nicht mehr.
    session.pop("admin", None)
    session.pop("is_admin", None)


def admin_angemeldet():
    """Ob die Anmeldung als Admin noch gilt - sonst wird sie hier geräumt.

    Eine Sitzung aus der Zeit vor dem Kennzeichen (nur „is_admin“) gilt
    nicht: Der Admin meldet sich nach dem Update einmal neu an.
    """
    kennzeichen = session.get("admin")
    if not kennzeichen or not hmac.compare_digest(str(kennzeichen), admin_kennzeichen()):
        admin_abmelden()
        return False
    return True


# ------------------------------------------------------- Bewertungszugang

def bewertung_anmelden(settings):
    """Merkt sich im Browser, dass hier jemand zum Bewerten angemeldet ist.

    Gespeichert wird das Kennzeichen des gerade gültigen Passworts, siehe
    Settings.review_token. Ein Name oder sonst etwas über die Person steht
    nicht darin: Der Zugang ist ein gemeinsamer, kein persönlicher.
    """
    session["bewertung"] = settings.review_token


def bewertung_abmelden():
    session.pop("bewertung", None)


def bewertung_angemeldet():
    """Ob die Anmeldung zur Bewertung noch gilt.

    Sie gilt, solange die Lehrkraft das Passwort weder geändert noch den
    Zugang abgeschaltet hat. Sonst wird sie hier geräumt - wie bei den Teams,
    damit eine alte Anmeldung nicht auf jeder Seite wieder hochkommt.
    """
    kennzeichen = session.get("bewertung")
    if not kennzeichen:
        return False

    from plattform.models import Settings
    if kennzeichen != Settings.get().review_token:
        bewertung_abmelden()
        return False
    return True
