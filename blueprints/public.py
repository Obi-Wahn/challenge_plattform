from flask import Blueprint, render_template, request, redirect, url_for, session
from extensions import db, limiter
from sqlalchemy.exc import IntegrityError
from models import Challenge, Settings, Team, MAX_TEAMNAME
from scoring import get_standings, get_podium
from sitzung import team_abmelden, team_anmelden
from network import abtipp_adresse, join_url
from protokoll import ereignis
import base64
import io
import qrcode

public_bp = Blueprint('public', __name__)

# Grenzen für das, was von außen ankommt. Die Registrierung ist die einzige
# Seite, die ohne Anmeldung schreibend auf die Datenbank zugreift - und im
# Klassenraum wird erfahrungsgemäß ausprobiert, was durchgeht. Die Länge des
# Teamnamens kommt aus models.py, wo sie auch die Breite der Spalte ist.
MAX_PASSWORT = 128

# Warum gerade keine Anmeldung möglich ist, je Zustand des Wettbewerbs. Der
# Satz steht an zwei Stellen - auf der Startseite anstelle des Formulars und
# als Antwort auf ein von Hand abgeschicktes Formular -, deshalb hier.
ANMELDUNG_ZU = {
    "finished": "Der Wettbewerb ist beendet - neue Teams können sich nicht "
                "mehr registrieren. Wer schon registriert ist, kommt über "
                "„Anmelden“ an seine Urkunde.",
    "paused": "Der Wettbewerb ist gerade pausiert. Sobald es weitergeht, "
              "könnt ihr euch hier registrieren.",
    "keiner": "Gerade ist kein Wettbewerb aktiv. Sobald die Lehrkraft einen "
              "aktiviert, könnt ihr euch hier registrieren oder anmelden.",
}

# Was die Anmeldeseite sagt, solange kein Wettbewerb aktiv ist. Sie suchte das
# Team sonst in keinem Wettbewerb, fand es nicht und meldete „Ungültiger
# Teamname oder Passwort“ - obwohl beides stimmte.
KEIN_AKTIVER = ("Gerade ist kein Wettbewerb aktiv, deshalb kann sich kein Team "
                "anmelden. Sobald die Lehrkraft einen aktiviert, geht es hier weiter.")


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
    # Dieselbe Adresse steckt im QR-Code und steht zum Abtippen darüber:
    # An einem normalen PC nützt ein QR-Code nichts. Zum Abtippen steht sie
    # gekürzt da, siehe abtipp_adresse().
    adresse = join_url(request.host_url)
    beitritt = abtipp_adresse(adresse)
    qr_code_data = generate_qr_code(adresse)

    challenge = Challenge.current()

    # Steht hier ein Satz, ist die Anmeldung zu und er sagt, warum - siehe
    # Challenge.accepts_registrations. None heißt offen.
    #
    # Ohne Wettbewerb bleibt das Formular stehen: Das ist der Fall auf einer
    # frischen Installation, in der noch keiner angelegt ist, und die Lehrkraft
    # soll dort ausprobieren können, wie die Anmeldung aussieht.
    anmeldung_zu = None
    if not challenge and Challenge.query.first():
        # Es gibt Wettbewerbe, aber keiner ist aktiv - etwa nach dem Löschen
        # des aktiven. Das Formular führte nur zu einer Fehlermeldung.
        anmeldung_zu = ANMELDUNG_ZU["keiner"]
    elif challenge and not challenge.accepts_registrations:
        anmeldung_zu = ANMELDUNG_ZU[
            "finished" if challenge.status() == "finished" else "paused"]

    if request.method == "POST":
        team_name = bereinigter_teamname(request.form.get("team"))
        password = request.form.get("password") or ""

        def mit_fehler(text):
            return render_template("index.html", error=text,
                                   qr_code_data=qr_code_data, beitritt=beitritt,
                                   anmeldung_zu=anmeldung_zu,
                                   anmelden_offen=challenge is not None)

        if not challenge:
            return mit_fehler("Aktuell läuft kein Wettbewerb. Bitte wartet, "
                              "bis die Lehrkraft einen gestartet hat.")

        # Das Formular steht dann gar nicht auf der Seite. Ein von Hand
        # abgeschicktes kommt trotzdem hier an und wird abgewiesen, statt ein
        # Team in einen geschlossenen Wettbewerb zu setzen.
        if anmeldung_zu:
            return mit_fehler(anmeldung_zu)

        if not team_name or not password:
            return mit_fehler("Bitte Teamname und Passwort angeben.")

        if len(team_name) > MAX_TEAMNAME:
            return mit_fehler(f"Der Teamname darf höchstens {MAX_TEAMNAME} Zeichen lang sein.")

        if len(password) > MAX_PASSWORT:
            return mit_fehler(f"Das Passwort darf höchstens {MAX_PASSWORT} Zeichen lang sein.")

        # A team name only has to be free within the current competition.
        existing_team = Team.query.filter_by(challenge_id=challenge.id, name=team_name).first()
        if existing_team:
            return mit_fehler("Teamname vergeben. Bitte anmelden oder anderen Namen wählen.")

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
            return mit_fehler("Teamname vergeben. Bitte anmelden oder anderen Namen wählen.")

        ereignis("Team angelegt: „%s“ (#%s) in Wettbewerb „%s“ (#%s)",
                 new_team.name, new_team.id, challenge.title, challenge.id)

        # Auto-login
        team_anmelden(new_team)
        return redirect(url_for("challenge.view"))

    return render_template("index.html", qr_code_data=qr_code_data, beitritt=beitritt,
                           anmeldung_zu=anmeldung_zu,
                           # Ohne aktiven Wettbewerb führt „Hier anmelden“
                           # ins Leere - der Link fällt dann weg.
                           anmelden_offen=challenge is not None)

@public_bp.route("/login", methods=["GET", "POST"])
# Only actual login attempts count towards the limit - merely opening or
# reloading the login page must not lock anyone out.
@limiter.limit("5 per minute", methods=["POST"])
def login():
    # Teams gehören zu einem Wettbewerb. Ist keiner aktiv, gibt es nichts,
    # wofür man sich anmelden könnte - das sagt die Seite, statt ein Formular
    # anzubieten, das nur mit „Ungültiger Teamname oder Passwort“ endet.
    if Challenge.current() is None:
        return render_template("login.html", kein_wettbewerb=KEIN_AKTIVER)

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
            team_anmelden(team)
            return redirect(url_for("challenge.view"))
        else:
             return render_template("login.html", error="Ungültiger Teamname oder Passwort.")

    return render_template("login.html")

@public_bp.route("/logout")
def logout():
    team_abmelden()
    return redirect(url_for("public.index"))

@public_bp.route("/scoreboard")
def scoreboard():
    challenge = Challenge.current()

    if not challenge:
        return render_template("scoreboard.html", challenge=None)

    # Eingefroren zählen nur die Abgaben bis zum Einfrieren - für alle, auch
    # am Beamer der Lehrkraft. Den echten Stand zeigt ihr die Siegerehrung.
    eingefroren = challenge.scoreboard_frozen
    tasks, standings = get_standings(
        challenge, bis=challenge.freeze_point if eingefroren else None)

    # Die Rangliste hängt den ganzen Tag am Beamer, deshalb steht die
    # Restzeit auch hier - dieselbe wie auf der Wettbewerbsseite der Teams.
    status = challenge.status()
    seconds = challenge.countdown_seconds

    return render_template(
        "scoreboard.html",
        challenge=challenge,
        tasks=tasks,
        teams=standings,
        status=status,
        seconds=seconds,
        aufgabentitel=Settings.get().scoreboard_task_titles,
        eingefroren=eingefroren,
    )

@public_bp.route("/siegerehrung")
def siegerehrung():
    challenge = Challenge.current()

    if not challenge:
        return render_template("siegerehrung.html", challenge=None, podium=[])

    # Solange die Rangliste eingefroren ist, sieht nur die angemeldete
    # Lehrkraft das Podium. Ein Team, das die Adresse am Handy aufruft,
    # bekommt es nicht vorab - auch nicht im Quelltext der Seite.
    if challenge.scoreboard_frozen and not session.get("is_admin"):
        return render_template("siegerehrung.html", challenge=challenge,
                               podium=[], eingefroren=True)

    _tasks, standings = get_standings(challenge)

    return render_template(
        "siegerehrung.html",
        challenge=challenge,
        podium=get_podium(standings),
        eingefroren=challenge.scoreboard_frozen,
    )

@public_bp.route("/start")
def start():
    # Die eigene Countdown-Seite gibt es nicht mehr: Die Restzeit steht auf der
    # Wettbewerbsseite der Teams und über der Rangliste, und gestartet wird von
    # Hand, nicht nach einer heruntergezählten Uhr. Die Adresse bleibt, damit
    # ein altes Lesezeichen nicht ins Leere läuft.
    return redirect(url_for("public.scoreboard"))
