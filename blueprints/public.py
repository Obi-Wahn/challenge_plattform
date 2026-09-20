from flask import Blueprint, render_template, request, redirect, url_for, session
from extensions import db, limiter
from sqlalchemy.exc import IntegrityError
from models import Team, Challenge
from scoring import get_standings, get_podium
from network import join_url
import base64
import io
import qrcode

public_bp = Blueprint('public', __name__)

# Grenzen für das, was von außen ankommt. Die Registrierung ist die einzige
# Seite, die ohne Anmeldung schreibend auf die Datenbank zugreift - und im
# Klassenraum wird erfahrungsgemäß ausprobiert, was durchgeht. SQLite setzt
# die Länge aus String(100) nicht selbst durch: Ohne diese Prüfung landen
# auch 5000 Zeichen in der Spalte.
MAX_TEAMNAME = 100
MAX_PASSWORT = 128


def bereinigter_teamname(wert):
    """Der Teamname ohne umgebende Leerzeichen.

    Ohne das Trimmen wäre ein Name aus lauter Leerzeichen gültig - in Python
    ist " " wahr, die Prüfung auf "nicht leer" ginge also durch. Das Team
    stünde dann namenlos in der Rangliste und auf seiner Urkunde.
    """
    return " ".join(str(wert or "").split())


def team_zur_anmeldung(challenge, name):
    """Das Team zu einem eingetippten Namen - oder None.

    Zuerst wird genau so gesucht, wie es dasteht. Wer die Schreibweise
    trifft, bekommt sein Team; damit ist die Sache entschieden, auch wenn
    das Passwort danach nicht passt. Es wird also nie weitergesucht, nachdem
    ein Team gefunden wurde.

    Findet sich kein Team mit dieser Schreibweise, wird sie ignoriert - aber
    nur, wenn dann genau ein Team passt. Gibt es „Die Hacker“ und
    „die hacker“ nebeneinander, bleibt es beim leeren Ergebnis, statt dass
    die Anwendung rät.

    Der Grund: Ein Team, das sich als „Die Pixelpiraten“ angemeldet hat und
    später „die pixelpiraten“ tippt, kam bisher nicht mehr hinein, obwohl
    Name und Passwort stimmten.
    """
    genau = Team.query.filter_by(challenge_id=challenge.id, name=name).first()
    if genau:
        return genau

    # lower() statt casefold(): Es geht um Groß- und Kleinschreibung, nicht
    # um Schreibvarianten - „Straße“ und „STRASSE“ sollen verschieden bleiben.
    gesucht = name.lower()
    passende = [team for team in Team.query.filter_by(challenge_id=challenge.id).all()
                if team.name.lower() == gesucht]

    return passende[0] if len(passende) == 1 else None


def generate_qr_code(adresse):
    """QR-Code der Adresse, unter der die Teams beitreten."""
    qr_img = qrcode.make(adresse)
    buffer = io.BytesIO()
    qr_img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")

@public_bp.route("/", methods=["GET", "POST"])
def index():
    # Dieselbe Adresse steckt im QR-Code und steht zum Abtippen darunter:
    # An einem normalen PC nützt ein QR-Code nichts.
    beitritt = join_url(request.host_url)
    qr_code_data = generate_qr_code(beitritt)

    challenge = Challenge.current()

    if request.method == "POST":
        team_name = bereinigter_teamname(request.form.get("team"))
        password = request.form.get("password") or ""

        def mit_fehler(text):
            return render_template("index.html", error=text,
                                   qr_code_data=qr_code_data, beitritt=beitritt)

        if not challenge:
            return mit_fehler("Aktuell läuft kein Wettbewerb. Bitte wartet, "
                              "bis die Lehrkraft einen gestartet hat.")

        if not team_name or not password:
            return mit_fehler("Bitte Teamname und Passwort angeben.")

        if len(team_name) > MAX_TEAMNAME:
            return mit_fehler(f"Der Teamname darf höchstens {MAX_TEAMNAME} Zeichen lang sein.")

        if len(password) > MAX_PASSWORT:
            return mit_fehler(f"Das Passwort darf höchstens {MAX_PASSWORT} Zeichen lang sein.")

        # A team name only has to be free within the current competition.
        existing_team = Team.query.filter_by(challenge_id=challenge.id, name=team_name).first()
        if existing_team:
            return mit_fehler("Teamname vergeben. Bitte einloggen oder anderen Namen wählen.")

        # Create new team for the current competition
        new_team = Team(name=team_name, challenge_id=challenge.id)
        new_team.set_password(password)
        db.session.add(new_team)

        try:
            db.session.commit()
        except IntegrityError:
            # Zwei Teams haben im selben Moment denselben Namen abgeschickt:
            # Die Prüfung oben sah beide Male "noch frei", die Datenbank lässt
            # aber nur eines durch. Das zweite bekommt dieselbe Auskunft wie
            # bei einem schon vergebenen Namen.
            db.session.rollback()
            return mit_fehler("Teamname vergeben. Bitte einloggen oder anderen Namen wählen.")

        # Auto-login
        session["team_id"] = new_team.id
        session["team_name"] = new_team.name
        return redirect(url_for("challenge.view"))

    return render_template("index.html", qr_code_data=qr_code_data, beitritt=beitritt)

@public_bp.route("/login", methods=["GET", "POST"])
# Only actual login attempts count towards the limit - merely opening or
# reloading the login page must not lock anyone out.
@limiter.limit("5 per minute", methods=["POST"])
def login():
    if request.method == "POST":
        # Genauso bereinigt wie bei der Registrierung - sonst käme ein Team,
        # das sich mit einem versehentlichen Leerzeichen angemeldet hat, nie
        # wieder hinein.
        team_name = bereinigter_teamname(request.form.get("team"))
        password = request.form.get("password")

        # Teams are looked up in the current competition, since the same name
        # may exist in several competitions.
        challenge = Challenge.current()
        team = team_zur_anmeldung(challenge, team_name) if challenge else None
        if team and team.check_password(password):
            session["team_id"] = team.id
            session["team_name"] = team.name
            return redirect(url_for("challenge.view"))
        else:
             return render_template("login.html", error="Ungültiger Teamname oder Passwort.")

    return render_template("login.html")

@public_bp.route("/logout")
def logout():
    session.pop("team_id", None)
    session.pop("team_name", None)
    return redirect(url_for("public.index"))

@public_bp.route("/scoreboard")
def scoreboard():
    challenge = Challenge.current()

    if not challenge:
        return render_template("scoreboard.html", challenge=None)

    tasks, standings = get_standings(challenge)

    return render_template(
        "scoreboard.html",
        challenge=challenge,
        tasks=tasks,
        teams=standings
    )

@public_bp.route("/siegerehrung")
def siegerehrung():
    challenge = Challenge.current()

    if not challenge:
        return render_template("siegerehrung.html", challenge=None, podium=[])

    _tasks, standings = get_standings(challenge)

    return render_template(
        "siegerehrung.html",
        challenge=challenge,
        podium=get_podium(standings)
    )

@public_bp.route("/start")
def start():
    # Same competition the teams see on their own page.
    challenge = Challenge.current()

    status = "not_scheduled"
    seconds = 0

    if challenge:
        status = challenge.status()
        if status == "upcoming":
            seconds = challenge.seconds_until_start
        elif status == "running":
            # Stays 0 when no end time is set, which hides the countdown.
            seconds = challenge.remaining_seconds

    # The remaining seconds are counted down in the browser instead of passing
    # an absolute timestamp, so a wrong clock or timezone on a viewer's device
    # cannot skew the countdown.
    return render_template(
        "start.html",
        challenge=challenge,
        status=status,
        seconds=seconds
    )
