"""Wer gerade als Team angemeldet ist - und wann diese Anmeldung verfällt.

Die Anmeldung eines Teams steht in der Sitzung des Browsers, der Wettbewerb
dazu in der Datenbank. Der kann verschwinden, während das Cookie weiterlebt:
Wird ein Wettbewerb gelöscht, gehen seine Teams mit, im Browser bleibt die
Anmeldung aber stehen. Hier entscheidet deshalb eine einzige Stelle, ob eine
Anmeldung noch gilt, und räumt sie weg, sobald sie es nicht mehr tut.
"""

from flask import session

from extensions import db
from models import Team

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
