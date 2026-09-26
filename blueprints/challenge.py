from flask import (Blueprint, render_template, request, redirect, url_for,
                   abort, current_app, send_file, flash, jsonify)
from extensions import db
from models import (Challenge, Task, Submission, Settings, MAX_MEMBERS,
                    MAX_MEMBER_TEXT_LENGTH, format_member_names, parse_member_names)
from sitzung import angemeldetes_team
from uploads import zum_loeschen_vormerken
from scoring import get_standings
from certificates import build_certificates_for, certificate_entry, names_line
from werkzeug.utils import secure_filename
import io
import os
import secrets
from datetime import datetime

challenge_bp = Blueprint('challenge', __name__)

# Wie lang der Name einer abgelegten Abgabe werden darf. Dateisysteme lassen
# meist 255 Zeichen je Namensbestandteil zu; darüber scheitert das Speichern
# mit einem OSError, und die Abgabe endete für das Team in einer Fehlerseite.
# 100 Zeichen sind mehr, als ein Mensch tippt, und lassen Luft für das
# vorangestellte "task_<nummer>_".
MAX_DATEINAME = 100

# So lang ist Task.allowed_extension höchstens (String(10)). Was darüber
# hinausgeht, ist keine Endung mehr, sondern Name.
MAX_ENDUNG = 10

def allowed_file(filename, allowed_ext):
    return "." in filename and filename.lower().endswith(allowed_ext.lower())

def gekuerzter_dateiname(filename):
    """Kürzt einen zu langen Dateinamen, behält dabei aber die Endung.

    Gekürzt statt abgewiesen: Wie die Datei heißt, ist nebensächlich - es
    zählt, was darin steht -, und ein Team hat pro Aufgabe nur einen
    Versuch. Die Endung bleibt, weil der Download in der Verwaltung sie aus
    dem abgelegten Namen nimmt.

    secure_filename() hat den Namen vorher auf ASCII gebracht, ein Zeichen
    ist hier also auch ein Byte.
    """
    if len(filename) <= MAX_DATEINAME:
        return filename

    stamm, endung = os.path.splitext(filename)
    endung = endung[:MAX_ENDUNG]
    return stamm[:MAX_DATEINAME - len(endung)] + endung

def freier_pfad(pfad):
    """Weicht auf einen noch unbelegten Pfad aus, ohne die Endung zu ändern.

    Gebraucht bei der Korrektur: Gibt das Team seiner zweiten Fassung
    denselben Dateinamen wie der ersten, zeigte der berechnete Pfad genau
    auf die noch gültige alte Datei. Die würde beim Speichern
    überschrieben - und zwar bevor feststeht, ob die Umstellung in der
    Datenbank überhaupt gelingt. Scheitert sie danach, wären beide
    Fassungen weg. Mit einem eigenen Pfad für die neue Datei greift
    stattdessen dieselbe Vormerkung wie beim Namenswechsel: Die alte Datei
    geht erst weg, wenn die Umstellung gespeichert ist.

    Das Kennzeichen steht vor der Endung, weil der Download sie aus dem
    abgelegten Namen nimmt. Dem Team fällt nichts davon auf - der Name der
    heruntergeladenen Datei wird in der Verwaltung ohnehin neu gebildet.
    """
    stamm, endung = os.path.splitext(pfad)
    while True:
        kandidat = f"{stamm}-{secrets.token_hex(4)}{endung}"
        if not os.path.exists(kandidat):
            return kandidat

# Wie oft die offene Seite eines Teams nach dem Stand fragt, in Millisekunden.
# 15 Sekunden sind nah genug, dass eine Pause nicht als Stillstand missdeutet
# wird, und selten genug, dass dreißig Tablets im Schul-LAN nichts davon
# merken.
STAND_TAKT_MS = 15000

def seitenstand(challenge):
    """Kurze Kennung dessen, was die Wettbewerbsseite eines Teams zeigt.

    Die Seite bekommt sie beim Ausliefern mit und fragt sie danach im Takt
    beim Server nach. Ist sie eine andere geworden, ist die offene Seite
    veraltet und wird neu geladen.

    Drin steht, was ein Team sofort sehen muss: welcher Wettbewerb läuft, ob
    er pausiert oder beendet ist, wann er anfängt und aufhört, welche Hinweise
    freigeschaltet sind und wie viele Aufgaben es gibt.

    Die Zeiten gehören dazu, weil die Uhr im Browser nichts davon weiß, wenn
    die Lehrkraft die Dauer mitten im Wettbewerb neu setzt - die Seite zeigte
    sonst bis zum nächsten Neuladen eine Restzeit, die es nicht mehr gibt.

    Eine Bewertung gehört bewusst nicht dazu: Sie ändert nichts daran, was ein
    Team gerade tun darf, und ein Neuladen mitten im Arbeiten kostet mehr, als
    die Punkte ein paar Minuten früher zu zeigen.
    """
    hinweise = (
        db.session.query(Task.id)
        .filter(Task.challenge_id == challenge.id, Task.hint_visible.is_(True))
        .order_by(Task.id)
        .all()
    )
    anzahl = db.session.query(Task.id).filter(Task.challenge_id == challenge.id).count()

    return ":".join([
        str(challenge.id),
        challenge.status(),
        "pause" if challenge.paused else "lauf",
        challenge.start_time.isoformat() if challenge.start_time else "-",
        challenge.end_time.isoformat() if challenge.end_time else "-",
        str(anzahl),
        ",".join(str(nummer) for (nummer,) in hinweise),
    ])


@challenge_bp.route("/challenge/stand")
def stand():
    """Der Stand als JSON, für die offene Seite eines Teams.

    Bewusst eine schlanke Abfrage und kein zweiter Zustellweg: Es sind ein
    paar Dutzend Geräte in einem Schul-LAN, und eine Anfrage alle 15 Sekunden
    ist billiger zu haben und zu verstehen als WebSockets oder SSE.

    "angemeldet": false heißt, dass die Seite dort nicht mehr hingehört - der
    Wettbewerb ist gelöscht oder das Team abgemeldet.
    """
    challenge = Challenge.current()
    team = angemeldetes_team(challenge)

    if team is None:
        antwort = jsonify({"angemeldet": False})
    else:
        antwort = jsonify({"angemeldet": True, "stand": seitenstand(challenge)})

    # Eine zwischengespeicherte Antwort wäre hier das Gegenteil des Zwecks:
    # Die Seite fragt ja gerade, weil sich etwas geändert haben kann.
    antwort.headers["Cache-Control"] = "no-store"
    return antwort


@challenge_bp.route("/challenge")
def view():
    # Teams always see the currently active competition.
    challenge = Challenge.current()

    # Wer hier nicht mehr angemeldet ist, gehört auf die Startseite. Das gilt
    # auch nach dem Löschen des Wettbewerbs: Mit ihm sind seine Teams weg,
    # und angemeldetes_team() räumt die Sitzung dann gleich mit auf.
    team = angemeldetes_team(challenge)
    if team is None:
        return redirect(url_for("public.index"))

    team_id = team.id
    tasks = Task.query.filter_by(challenge_id=challenge.id).all()
    
    submissions = Submission.query.filter_by(team_id=team_id).join(Task).filter(Task.challenge_id == challenge.id).all()
    submission_map = {s.task_id: s for s in submissions}

    # Dieselbe Rechnung wie auf der Countdown-Seite: vor dem Start bis zum
    # Beginn, danach bis zum Ende. Ohne gesetzte Zeit bleibt es bei 0, dann
    # zeigt die Leiste nur den Stand und keine Uhr.
    status = challenge.status()
    if status == "upcoming":
        seconds = challenge.seconds_until_start
    elif status == "running":
        seconds = challenge.remaining_seconds
    else:
        seconds = 0

    return render_template(
        "challenge.html",
        challenge=challenge,
        tasks=tasks,
        submission_map=submission_map,
        status=status,
        seconds=seconds,
        team=team.name,
        member_names_enabled=Settings.get().member_names_enabled,
        member_names_text=team.member_names or "",
        member_list=team.member_list,
        members_approved=team.members_approved,
        max_members=MAX_MEMBERS,
        # Damit die Seite selbst merkt, wenn sie veraltet ist - siehe
        # seitenstand().
        stand=seitenstand(challenge),
        stand_takt=STAND_TAKT_MS
    )


@challenge_bp.route("/team/namen", methods=["POST"])
def team_members():
    """Das Team trägt die Namen ein, die auf seine Urkunde sollen.

    Eintragen geht auch noch, wenn der Wettbewerb schon beendet ist: Die
    Urkunde gibt es ja erst danach, und bis dahin soll ein vergessener Name
    noch nachgetragen werden können.
    """
    challenge = Challenge.current()
    team = angemeldetes_team(challenge)
    if team is None:
        return redirect(url_for("public.index"))

    # Ohne Freigabe der Lehrkraft gibt es das Feld gar nicht - dann ist auch
    # ein von Hand abgeschicktes Formular nichts, was hier ankommen soll.
    if not Settings.get().member_names_enabled:
        abort(403)

    namen = parse_member_names(request.form.get("member_names"))
    zu_viele = len(namen) - MAX_MEMBERS
    namen = namen[:MAX_MEMBERS]

    # Zu lang heißt: nichts speichern. Die Namen von hinten abzuschneiden wäre
    # schlimmer als die Nachfrage - es fehlte dann jemand auf der Urkunde.
    if len(names_line(namen)) > MAX_MEMBER_TEXT_LENGTH:
        flash(
            "So viele Zeichen passen nicht auf eine Urkunde. Schreibt die Namen "
            "kürzer, zum Beispiel nur den Vornamen und den ersten Buchstaben des "
            "Nachnamens - gespeichert wurde nichts.",
            "warning"
        )
        return redirect(url_for("challenge.view"))

    neu = format_member_names(namen)

    if neu != (team.member_names or ""):
        team.member_names = neu
        # Geändert heißt wieder ungeprüft: Was kontrolliert wurde, darf sich
        # danach nicht mehr unbemerkt ändern.
        team.members_approved = False
        db.session.commit()

        if neu:
            flash(
                "Namen gespeichert. Sie kommen auf die Urkunde, sobald die "
                "Lehrkraft sie kontrolliert hat.",
                "success"
            )
        else:
            flash("Die Namen wurden gelöscht - auf der Urkunde steht jetzt keiner.", "warning")

    if zu_viele > 0:
        flash(
            f"Es passen höchstens {MAX_MEMBERS} Namen auf eine Urkunde - "
            f"die letzten {zu_viele} wurden nicht übernommen.",
            "warning"
        )

    return redirect(url_for("challenge.view"))

def zurueck_mit_meldung(text, kategorie="warning"):
    """Sagt dem Team, was schiefging, und bringt es zu seinen Aufgaben zurück.

    Vorher endeten diese Fälle in der nackten Fehlerseite des Webservers -
    englisch, ohne Erklärung und ohne Weg zurück. Es sind aber die
    gewöhnlichen Missgeschicke einer Schulstunde: die falsche Datei erwischt,
    die Seite zu lange offen gehabt. Dafür gehört eine Meldung an die Stelle,
    an der es weitergeht.
    """
    flash(text, kategorie)
    return redirect(url_for("challenge.view"))


@challenge_bp.route("/submit/<int:task_id>", methods=["POST"])
def submit_task(task_id):
    # Submissions are only accepted for the active competition,
    # matching what teams see on the challenge page.
    challenge = Challenge.current()

    # A team may only submit for its own competition.
    team = angemeldetes_team(challenge)
    if team is None:
        # Wie auf der Wettbewerbsseite: Wer nicht (mehr) angemeldet ist,
        # gehört auf die Startseite, nicht auf eine Fehlerseite.
        return redirect(url_for("public.index"))

    task = db.get_or_404(Task, task_id)
    if task.challenge_id != challenge.id:
        abort(403) # Task not part of the current challenge

    # Closed means closed: paused, or past the end time.
    if not challenge.accepts_submissions:
        return zurueck_mit_meldung(
            "Abgaben sind gerade gesperrt - der Wettbewerb ist beendet oder "
            "pausiert. Gespeichert wurde nichts."
        )

    team_id = team.id

    # A team may only submit once per task, unless an admin explicitly
    # released this submission for a correction.
    existing = Submission.query.filter_by(team_id=team_id, task_id=task_id).first()
    if existing and not existing.resubmit_allowed:
        return zurueck_mit_meldung(
            f"„{task.title}“ habt ihr schon abgegeben. Soll die Abgabe ersetzt "
            "werden, muss die Lehrkraft sie dafür freigeben."
        )

    if "file" not in request.files:
        return zurueck_mit_meldung("Es war keine Datei dabei - gespeichert wurde nichts.")

    file = request.files["file"]
    if file.filename == "":
        return zurueck_mit_meldung("Es war keine Datei ausgewählt - gespeichert wurde nichts.")

    if not allowed_file(file.filename, task.allowed_extension):
        return zurueck_mit_meldung(
            f"„{task.title}“ nimmt nur Dateien mit der Endung "
            f"{task.allowed_extension} an - gespeichert wurde nichts."
        )

    filename = gekuerzter_dateiname(secure_filename(file.filename))
    team_folder = os.path.join(current_app.config["UPLOAD_FOLDER"], str(team_id))
    os.makedirs(team_folder, exist_ok=True)
    
    filepath = os.path.join(team_folder, f"task_{task_id}_{filename}")

    # Eine Korrektur darf die noch gültige Datei nicht überschreiben, auch
    # dann nicht, wenn sie denselben Namen trägt - siehe freier_pfad().
    if existing and existing.filename == filepath:
        filepath = freier_pfad(filepath)

    file.save(filepath)

    if existing:
        # Correction: replace the file and clear the previous grading, so the
        # submission goes back into the admin's review queue. The release is
        # used up, so a further correction needs a new one.
        previous_filepath = existing.filename
        existing.filename = filepath
        existing.timestamp = datetime.now()
        existing.points = None
        existing.feedback = None
        existing.resubmit_allowed = False

        # Die alte Datei geht erst weg, wenn die Umstellung gespeichert ist -
        # dieselbe Regel wie beim Löschen einer Abgabe. Würde sie vorher
        # gelöscht und das Speichern scheiterte, zeigte die Datenbank auf
        # eine Datei, die es nicht mehr gibt. Dass die neue Datei woanders
        # liegt als die alte, stellt freier_pfad() sicher.
        zum_loeschen_vormerken(db.session, previous_filepath)
    else:
        db.session.add(Submission(
            team_id=team_id,
            task_id=task_id,
            filename=filepath,
            timestamp=datetime.now()
        ))

    try:
        db.session.commit()
    except Exception:
        # Die gerade geschriebene Datei gehört zu einer Abgabe, die es nun
        # nicht gibt. Sie bliebe sonst als Waise liegen.
        db.session.rollback()
        try:
            os.remove(filepath)
        except OSError:
            pass
        raise

    return redirect(url_for("challenge.view"))


def certificate_filename(team_name):
    """A file name that survives any team name, including emoji."""
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
    cleaned = "".join(c if c in allowed else "_" for c in team_name).strip("_")
    return f"Urkunde_{cleaned or 'Team'}.pdf"

@challenge_bp.route("/urkunde.pdf")
def certificate():
    """A team downloads its own certificate, once the competition is over."""
    challenge = Challenge.current()
    team = angemeldetes_team(challenge)
    if team is None:
        return redirect(url_for("public.index"))

    # Before the end the result is not final, so there is nothing to hand out.
    if challenge.status() != "finished":
        abort(403)

    tasks, standings = get_standings(challenge)
    pdf_bytes = build_certificates_for(
        challenge, [certificate_entry(team, standings)], len(tasks)
    )

    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=certificate_filename(team.name)
    )
