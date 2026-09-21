from flask import (Blueprint, render_template, request, redirect, url_for, session,
                   send_from_directory, send_file, flash)
from extensions import db
from models import (Team, Challenge, Task, Submission, Settings, TASK_FORMATS,
                    MAX_MEMBERS, MAX_MEMBER_TEXT_LENGTH, format_member_names,
                    parse_member_names, event_branding)
from scoring import get_standings
from task_rules import KEIN_TITEL, PUNKTE_KEINE_ZAHL, clean_task_values
from certificates import (build_certificates_for, certificate_entry, signature_font,
                          SIGNATURE_FONTS, DEFAULT_SIGNATURE_FONT,
                          certificate_orientation, CERTIFICATE_ORIENTATIONS,
                          DEFAULT_ORIENTATION, names_line)
from task_exchange import export_bytes, parse_tasks, ImportError_
from datetime import datetime
import io
import os

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.before_request
def restrict_admin():
    if request.endpoint == 'auth.admin_login':
        return
    if not session.get("is_admin"):
        return redirect(url_for('auth.admin_login'))

# Was der Lehrkraft angezeigt wird, wenn aus dem Formular keine Aufgabe wird.
PROBLEM_MELDUNG = {
    KEIN_TITEL: "Die Aufgabe braucht einen Titel - nichts gespeichert.",
    PUNKTE_KEINE_ZAHL: "Die Punktzahl muss eine Zahl sein - nichts gespeichert.",
}


def geprüfte_aufgabenwerte(form):
    """Die Werte aus dem Aufgabenformular, nach denselben Regeln wie beim Einlesen."""
    return clean_task_values(
        form.get("title"),
        form.get("description"),
        form.get("max_points"),
        form.get("allowed_extension"),
        form.get("hint"),
    )


def challenge_overview(challenge):
    """The numbers both the control centre and the competition page show."""
    if not challenge:
        return {"teams": 0, "tasks": 0, "submissions": 0, "open_reviews": 0}

    submissions = Submission.query.join(Task).filter(Task.challenge_id == challenge.id)
    return {
        "teams": Team.query.filter_by(challenge_id=challenge.id).count(),
        "tasks": Task.query.filter_by(challenge_id=challenge.id).count(),
        "submissions": submissions.count(),
        "open_reviews": submissions.filter(Submission.points.is_(None)).count(),
    }

def safe_redirect_target(default):
    """A "next" value from a form, but only if it stays on this site."""
    target = (request.form.get("next") or "").strip()
    if target.startswith("/") and not target.startswith("//"):
        return target
    return default

@admin_bp.route("/")
def index():
    """/admin ist die Adresse, die man eintippt - von dort geht es weiter.

    Wer nicht angemeldet ist, landet über restrict_admin auf der Anmeldung.
    """
    return redirect(url_for('admin.dashboard'))

@admin_bp.route("/dashboard")
def dashboard():
    # The control centre is about one competition: the current one. Everything
    # else (older competitions) lives on the competition list.
    challenge = Challenge.current()
    return render_template(
        "admin/dashboard.html",
        challenge=challenge,
        overview=challenge_overview(challenge),
        challenge_count=Challenge.query.count()
    )

@admin_bp.route("/challenges")
def challenges_list():
    challenges = Challenge.query.order_by(Challenge.id.desc()).all()
    return render_template(
        "admin/challenges.html",
        challenges=challenges,
        current=Challenge.current()
    )

@admin_bp.route("/wettbewerb/<int:cid>")
def challenge_detail(cid):
    """Everything about one competition on a single page."""
    challenge = db.get_or_404(Challenge, cid)

    tasks = Task.query.filter_by(challenge_id=cid).order_by(Task.id).all()
    teams = Team.query.filter_by(challenge_id=cid).order_by(Team.name).all()

    # The public pages (scoreboard, award ceremony, certificates) always show
    # the current competition, so they are only offered for that one.
    is_current = Challenge.current() is not None and Challenge.current().id == cid

    return render_template(
        "admin/challenge_detail.html",
        challenge=challenge,
        tasks=tasks,
        teams=teams,
        overview=challenge_overview(challenge),
        is_current=is_current
    )

def parse_datetime_local(value):
    # Parses the value of an <input type="datetime-local">, e.g. "2026-09-19T14:30".
    # Empty or malformed input means "not scheduled" rather than an error.
    value = (value or "").strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None

def latest_challenge_with_teams():
    """The most recent competition that has teams, as a source for a carry-over."""
    return (Challenge.query.filter(Challenge.teams.any())
            .order_by(Challenge.id.desc()).first())

@admin_bp.route("/challenges/new", methods=["GET", "POST"])
def challenge_new():
    previous = latest_challenge_with_teams()

    if request.method == "POST":
        title = request.form["title"]
        challenge = Challenge(
            title=title,
            tagline=request.form.get("tagline", "").strip()[:300],
            start_time=parse_datetime_local(request.form.get("start_time")),
            end_time=parse_datetime_local(request.form.get("end_time"))
        )
        db.session.add(challenge)
        db.session.flush() # assigns the id the copied teams are bound to

        # Optionally take the teams of the previous competition along, keeping
        # their passwords so the same groups can log in as before.
        if previous and request.form.get("copy_teams"):
            for source in sorted(previous.teams, key=lambda t: t.name.lower()):
                copy = Team(name=source.name, challenge_id=challenge.id)
                copy.password_hash = source.password_hash
                db.session.add(copy)

        db.session.commit()

        if previous and request.form.get("copy_teams"):
            flash(
                f"Wettbewerb angelegt und {len(previous.teams)} Team(s) aus "
                f"„{previous.title}“ übernommen.",
                "success"
            )

        return redirect(url_for('admin.challenge_detail', cid=challenge.id))

    return render_template("admin/challenge_new.html", previous=previous)

@admin_bp.route("/challenges/<int:cid>/edit", methods=["GET", "POST"])
def challenge_edit(cid):
    challenge = db.get_or_404(Challenge, cid)

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if title:
            challenge.title = title
        # Anders als der Name darf der Untertitel leer bleiben: Leer ist die
        # Antwort "nimm den aus den Einstellungen", nicht ein Versehen.
        challenge.tagline = request.form.get("tagline", "").strip()[:300]
        challenge.start_time = parse_datetime_local(request.form.get("start_time"))
        challenge.end_time = parse_datetime_local(request.form.get("end_time"))
        db.session.commit()
        flash("Name, Untertitel und Zeiten gespeichert.", "success")
        return redirect(url_for('admin.challenge_detail', cid=cid))

    return render_template("admin/challenge_edit.html", challenge=challenge)

# Activating changes which competition everything refers to, so it is a POST
# with a CSRF token rather than a plain link.
@admin_bp.route("/challenge/<int:cid>/activate", methods=["POST"])
def challenge_activate(cid):
    challenge = db.get_or_404(Challenge, cid)
    Challenge.query.update({Challenge.active: False})
    challenge.active = True
    db.session.commit()
    flash(
        f"„{challenge.title}“ ist jetzt der aktive Wettbewerb. Teams melden sich "
        "ab sofort für ihn an.",
        "success"
    )
    return redirect(safe_redirect_target(url_for('admin.challenge_detail', cid=cid)))

@admin_bp.route("/challenges/<int:cid>/tasks", methods=["GET", "POST"])
def challenge_tasks(cid):
    challenge = db.get_or_404(Challenge, cid)

    if request.method == "POST":
        werte, hinweise, problem = geprüfte_aufgabenwerte(request.form)

        if problem:
            flash(PROBLEM_MELDUNG[problem], "warning")
            return redirect(url_for('admin.challenge_tasks', cid=cid))

        db.session.add(Task(challenge_id=cid, **werte))
        db.session.commit()

        for hinweis in hinweise:
            flash(hinweis, "warning")
        return redirect(url_for('admin.challenge_tasks', cid=cid))

    tasks = Task.query.filter_by(challenge_id=cid).order_by(Task.id).all()
    return render_template(
        "admin/challenge_tasks.html",
        challenge=challenge,
        tasks=tasks,
        task_formats=TASK_FORMATS
    )

@admin_bp.route("/challenges/<int:cid>/tasks/export")
def tasks_export(cid):
    """Downloads the tasks of this competition as a reusable JSON file."""
    challenge = db.get_or_404(Challenge, cid)
    tasks = Task.query.filter_by(challenge_id=cid).order_by(Task.id).all()

    if not tasks:
        flash("Dieser Wettbewerb hat noch keine Aufgaben zum Sichern.", "warning")
        return redirect(url_for('admin.challenge_tasks', cid=cid))

    return send_file(
        io.BytesIO(export_bytes(challenge, tasks)),
        mimetype="application/json",
        as_attachment=True,
        download_name=f"Aufgaben_{safe_name(challenge.title)}.json"
    )

@admin_bp.route("/tasks/<int:tid>/export")
def task_export(tid):
    """Downloads a single task, in the same format as a whole set."""
    task = db.get_or_404(Task, tid)

    return send_file(
        io.BytesIO(export_bytes(task.challenge, [task])),
        mimetype="application/json",
        as_attachment=True,
        download_name=f"Aufgabe_{safe_name(task.title)}.json"
    )

@admin_bp.route("/challenges/<int:cid>/tasks/import", methods=["POST"])
def tasks_import(cid):
    """Adds the tasks from an export file to this competition."""
    challenge = db.get_or_404(Challenge, cid)
    upload = request.files.get("file")

    if not upload or not upload.filename:
        flash("Es wurde keine Datei ausgewählt.", "warning")
        return redirect(url_for('admin.challenge_tasks', cid=cid))

    try:
        tasks, skipped = parse_tasks(upload.read())
    except ImportError_ as error:
        flash(f"Import nicht möglich: {error}", "danger")
        return redirect(url_for('admin.challenge_tasks', cid=cid))

    for values in tasks:
        # Hints always start hidden, whatever the source competition did.
        db.session.add(Task(challenge_id=cid, **values))
    db.session.commit()

    message = f"{len(tasks)} Aufgabe(n) zu „{challenge.title}“ hinzugefügt."
    if skipped:
        message += " Übersprungen bzw. angepasst: " + " · ".join(skipped[:5])
        if len(skipped) > 5:
            message += f" (und {len(skipped) - 5} weitere)"
    flash(message, "warning" if skipped else "success")

    return redirect(url_for('admin.challenge_tasks', cid=cid))

@admin_bp.route("/challenges/<int:cid>/pause", methods=["POST"])
def challenge_pause(cid):
    challenge = db.get_or_404(Challenge, cid)
    challenge.paused = True
    db.session.commit()
    flash(f"„{challenge.title}“ ist pausiert – Abgaben sind vorübergehend gesperrt.", "warning")
    return redirect(safe_redirect_target(url_for('admin.challenge_detail', cid=cid)))

@admin_bp.route("/challenges/<int:cid>/resume", methods=["POST"])
def challenge_resume(cid):
    challenge = db.get_or_404(Challenge, cid)
    challenge.paused = False
    db.session.commit()
    flash(f"„{challenge.title}“ läuft weiter – Abgaben sind wieder möglich.", "success")
    return redirect(safe_redirect_target(url_for('admin.challenge_detail', cid=cid)))

@admin_bp.route("/challenges/<int:cid>/finish", methods=["POST"])
def challenge_finish(cid):
    """Ends the competition now: no more submissions, ready for the ceremony."""
    challenge = db.get_or_404(Challenge, cid)
    # The end time is what makes a competition finished, so setting it to now
    # is the whole action - nothing is deleted and the pause flag is untouched.
    challenge.end_time = datetime.now()
    db.session.commit()
    flash(
        f"„{challenge.title}“ ist beendet. Abgaben sind gesperrt – "
        "jetzt könnt ihr Rangliste, Siegerehrung und Urkunden zeigen.",
        "success"
    )
    return redirect(safe_redirect_target(url_for('admin.challenge_detail', cid=cid)))

@admin_bp.route("/challenges/<int:cid>/reopen", methods=["POST"])
def challenge_reopen(cid):
    """Undoes "beenden", e.g. when a team still needs to hand something in."""
    challenge = db.get_or_404(Challenge, cid)
    challenge.end_time = None
    challenge.paused = False
    db.session.commit()
    flash(
        f"„{challenge.title}“ ist wieder geöffnet. Es gibt jetzt keine Endzeit – "
        "die lässt sich unter „Zeiten“ wieder setzen.",
        "success"
    )
    return redirect(safe_redirect_target(url_for('admin.challenge_detail', cid=cid)))

@admin_bp.route("/challenges/<int:cid>/delete", methods=["POST"])
def challenge_delete(cid):
    challenge = db.get_or_404(Challenge, cid)
    db.session.delete(challenge)
    db.session.commit()
    return redirect(url_for('admin.challenges_list'))

@admin_bp.route("/tasks/<int:tid>/delete", methods=["POST"])
def task_delete(tid):
    task = db.get_or_404(Task, tid)
    cid = task.challenge_id
    db.session.delete(task)
    db.session.commit()
    # Redirect back to tasks list
    return redirect(url_for('admin.challenge_tasks', cid=cid))

@admin_bp.route("/tasks/<int:tid>/edit", methods=["GET", "POST"])
def task_edit(tid):
    task = db.get_or_404(Task, tid)
    cid = task.challenge_id
    
    if request.method == "POST":
        werte, hinweise, problem = geprüfte_aufgabenwerte(request.form)

        if problem:
            flash(PROBLEM_MELDUNG[problem], "warning")
            return redirect(url_for('admin.task_edit', tid=tid))

        for feld, wert in werte.items():
            setattr(task, feld, wert)
        db.session.commit()

        for hinweis in hinweise:
            flash(hinweis, "warning")
        return redirect(url_for('admin.challenge_tasks', cid=cid))

    return render_template("admin/task_edit.html", task=task, task_formats=TASK_FORMATS)

@admin_bp.route("/tasks/<int:tid>/toggle_hint", methods=["POST"])
def task_toggle_hint(tid):
    task = db.get_or_404(Task, tid)
    task.hint_visible = not task.hint_visible
    db.session.commit()
    return redirect(url_for('admin.challenge_tasks', cid=task.challenge_id))

@admin_bp.route("/submissions", methods=["GET", "POST"])
def submissions():
    if request.method == "POST":
        submission_id = request.form.get("submission_id")
        
        if "soft_reset" in request.form:
             submission = db.session.get(Submission, submission_id)
             if submission:
                 submission.points = None
                 submission.feedback = None
                 db.session.commit()
        else:
             points = request.form.get("points")
             feedback = request.form.get("feedback", "")
             submission = db.session.get(Submission, submission_id)
             if submission and points: # Check if points is not empty string
                 submission.points = max(0, min(int(points), submission.task.max_points))
                 submission.feedback = feedback
                 db.session.commit()
        return redirect(url_for('admin.submissions'))

    # Only the submissions of the current competition - older events stay in the
    # database but must not clutter the review list.
    challenge = Challenge.current()
    if not challenge:
        return render_template("admin/review.html", submissions=[], challenge=None)

    raw_submissions = Submission.query.join(Team).join(Task).filter(
        Task.challenge_id == challenge.id
    ).order_by(
        Submission.points.isnot(None),
        Team.name
    ).all()

    submissions_data = []
    for s in raw_submissions:
        content = "Datei konnte nicht gelesen werden."
        try:
            if os.path.exists(s.filename):
                with open(s.filename, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
            else:
                content = "Datei nicht gefunden."
        except Exception as e:
            content = f"Fehler: {e}"

        submissions_data.append({
            "id": s.id,
            "team_name": s.team.name,
            "task_title": s.task.title,
            "task_description": s.task.description,
            "max_points": s.task.max_points,
            "points": s.points,
            "feedback": s.feedback,
            "resubmit_allowed": s.resubmit_allowed,
            "code": content
        })

    return render_template("admin/review.html", submissions=submissions_data, challenge=challenge)

@admin_bp.route("/submissions/<int:submission_id>/allow_resubmit", methods=["POST"])
def submission_allow_resubmit(submission_id):
    submission = db.get_or_404(Submission, submission_id)
    submission.resubmit_allowed = not submission.resubmit_allowed
    db.session.commit()

    if submission.resubmit_allowed:
        flash(
            f"Team „{submission.team.name}“ kann die Aufgabe „{submission.task.title}“ "
            "jetzt noch einmal abgeben.",
            "success"
        )
    else:
        flash(
            f"Erneutes Abgeben für Team „{submission.team.name}“ wurde wieder gesperrt.",
            "warning"
        )

    return redirect(url_for('admin.submissions'))

@admin_bp.route("/reset/<int:submission_id>", methods=["POST"])
def submission_reset(submission_id):
    submission = db.get_or_404(Submission, submission_id)
    db.session.delete(submission)
    db.session.commit()
    return redirect(url_for('admin.submissions'))

def safe_name(text):
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
    return "".join(c if c in allowed else "_" for c in text)

@admin_bp.route("/download/<int:submission_id>")
def download_submission(submission_id):
    submission = db.get_or_404(Submission, submission_id)
    
    filepath = submission.filename
    directory = os.path.dirname(filepath)
    original_filename = os.path.basename(filepath)
    
    team_clean = safe_name(submission.team.name)
    ext = os.path.splitext(original_filename)[1]  # z.B. ".sb3" oder ".pde"
    download_name = f"{team_clean}_Aufgabe_{submission.task_id}{ext}"
    
    return send_from_directory(
        directory,
        original_filename,
        as_attachment=True,
        download_name=download_name
    )

@admin_bp.route("/teams")
def teams():
    # Teams belong to the competition they registered for, so only the current
    # one is listed here.
    challenge = Challenge.current()
    teams = (Team.query.filter_by(challenge_id=challenge.id).order_by(Team.name).all()
             if challenge else [])

    # Wie viele Teams auf die Kontrolle ihrer Namen warten - das ist die
    # Arbeit, die auf dieser Seite liegen bleibt.
    offen = sum(1 for team in teams if team.member_list and not team.members_approved)

    return render_template(
        "admin/teams.html",
        teams=teams,
        challenge=challenge,
        member_names_enabled=Settings.get().member_names_enabled,
        offene_namen=offen,
        max_members=MAX_MEMBERS
    )

@admin_bp.route("/team/<int:team_id>/namen", methods=["POST"])
def team_members(team_id):
    """Die Kontrolle der Namen: ändern, freigeben, Freigabe zurücknehmen.

    Der Admin darf die Namen dabei auch berichtigen - ein Tippfehler im
    eigenen Namen soll nicht bedeuten, dass das Team noch einmal antreten
    muss. Das Speichern allein gibt aber nichts frei; dafür gibt es den
    eigenen Knopf.
    """
    team = db.get_or_404(Team, team_id)

    namen = parse_member_names(request.form.get("member_names"))[:MAX_MEMBERS]

    # Dieselbe Grenze wie für die Teams: Was nicht auf die Urkunde passt, wird
    # auch hier nicht gespeichert.
    if len(names_line(namen)) > MAX_MEMBER_TEXT_LENGTH:
        flash(
            f"So viele Zeichen passen nicht auf eine Urkunde - bei Team "
            f"„{team.name}“ wurde nichts geändert.",
            "warning"
        )
        return redirect(url_for('admin.teams'))

    team.member_names = format_member_names(namen)

    if "freigeben" in request.form:
        if namen:
            team.members_approved = True
            flash(
                f"Die Namen von Team „{team.name}“ stehen jetzt auf der Urkunde: "
                f"{names_line(namen)}.",
                "success"
            )
        else:
            # Nichts freizugeben - und ein gesetztes Häkchen ohne Namen würde
            # später nur verwirren.
            team.members_approved = False
            flash(f"Team „{team.name}“ hat keine Namen eingetragen.", "warning")
    elif "sperren" in request.form:
        team.members_approved = False
        flash(
            f"Die Namen von Team „{team.name}“ stehen nicht mehr auf der Urkunde.",
            "warning"
        )
    else:
        # Geändert heißt wieder ungeprüft - dieselbe Regel wie beim Team.
        team.members_approved = False
        flash(f"Namen von Team „{team.name}“ gespeichert, noch nicht freigegeben.", "success")

    db.session.commit()
    return redirect(url_for('admin.teams'))

@admin_bp.route("/team/<int:team_id>/reset_password", methods=["POST"])
def team_reset_password(team_id):
    team = db.get_or_404(Team, team_id)
    new_password = request.form.get("new_password", "").strip()

    if not new_password:
        flash(f"Kein Passwort eingegeben – das Passwort von Team „{team.name}“ wurde nicht geändert.", "warning")
    else:
        team.set_password(new_password)
        db.session.commit()
        # The password is deliberately not echoed back: the admin screen may be
        # projected during an event, and whoever typed it already knows it.
        flash(f"Neues Passwort für Team „{team.name}“ gespeichert.", "success")

    return redirect(url_for('admin.teams'))

@admin_bp.route("/team/delete/<int:team_id>", methods=["POST"])
def team_delete(team_id):
    team = db.get_or_404(Team, team_id)
    db.session.delete(team)
    db.session.commit()
    return redirect(url_for('admin.teams'))

def _certificate_challenge():
    """Der Wettbewerb, dessen Urkunden gemeint sind.

    Ohne Angabe der aktive, mit "?wettbewerb=<id>" ein bestimmter. Letzteres
    gibt es, damit eine Urkunde auch dann noch nachgereicht werden kann, wenn
    längst der nächste Wettbewerb läuft - etwa für ein Team, das am Tag der
    Siegerehrung gefehlt hat.
    """
    cid = request.args.get("wettbewerb", type=int)
    if cid:
        return db.get_or_404(Challenge, cid)
    return Challenge.current()

def _certificate_data(challenge):
    """Collects everything the certificates need, for one competition."""
    if not challenge:
        return None, [], 0

    tasks, standings = get_standings(challenge)
    return challenge, standings, len(tasks)

@admin_bp.route("/urkunden")
def certificates_print():
    challenge, standings, task_count = _certificate_data(_certificate_challenge())
    return render_template(
        "admin/urkunden.html",
        challenge=challenge,
        entries=standings,
        task_count=task_count,
        today=datetime.now().strftime("%d.%m.%Y"),
        signature_css=signature_font(Settings.get().signature_font)["css"],
        orientation=certificate_orientation(Settings.get().certificate_orientation),
        # Der Veranstaltungsname dieses Wettbewerbs, nicht der des aktiven -
        # sonst trüge die Vorschau eines alten Wettbewerbs den heutigen Namen
        # und das PDF daneben den richtigen.
        event=event_branding(challenge),
        is_current=bool(challenge) and challenge.id == (
            Challenge.current().id if Challenge.current() else None
        ),
        # Dieselbe Aufzählung wie im PDF, damit Druckansicht und Datei
        # nicht auseinanderlaufen.
        names_line=names_line
    )

@admin_bp.route("/urkunden.pdf")
def certificates_pdf():
    challenge, standings, task_count = _certificate_data(_certificate_challenge())
    if not standings:
        flash("Es sind noch keine Teams registriert – es gibt nichts zu drucken.", "warning")
        return redirect(url_for('admin.certificates_print'))

    pdf_bytes = build_certificates_for(challenge, standings, task_count)
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"Urkunden_{safe_name(challenge.title if challenge else 'Wettbewerb')}.pdf"
    )

@admin_bp.route("/urkunden/<int:team_id>.pdf")
def certificate_pdf_single(team_id):
    team = db.get_or_404(Team, team_id)
    # Die Urkunde eines Teams gehört zu dem Wettbewerb, für den es angetreten
    # ist. Früher war hier immer der aktive gemeint; ein Team von damals kam
    # in dessen Rangliste nicht vor und bekam eine Urkunde über null Punkte
    # mit dem falschen Wettbewerbstitel.
    challenge, standings, task_count = _certificate_data(team.challenge or Challenge.current())

    entry = certificate_entry(team, standings)
    pdf_bytes = build_certificates_for(challenge, [entry], task_count)
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"Urkunde_{safe_name(team.name)}.pdf"
    )

@admin_bp.route("/settings", methods=["GET", "POST"])
def settings():
    site_settings = Settings.get()

    if request.method == "POST":
        site_name = request.form.get("site_name", "").strip()
        tagline = request.form.get("tagline", "").strip()
        if site_name:
            site_settings.site_name = site_name
        if tagline:
            site_settings.tagline = tagline

        # The signature may deliberately be emptied again, so it is stored as
        # given instead of only when something was typed.
        site_settings.signature_name = request.form.get("signature_name", "").strip()[:100]
        font = request.form.get("signature_font", "")
        site_settings.signature_font = font if font in SIGNATURE_FONTS else DEFAULT_SIGNATURE_FONT

        # Ein Häkchen schickt nichts mit, wenn es nicht gesetzt ist - das
        # Fehlen des Feldes ist also die Antwort "nein".
        site_settings.member_names_enabled = bool(request.form.get("member_names_enabled"))

        ausrichtung = request.form.get("certificate_orientation", "")
        site_settings.certificate_orientation = (
            ausrichtung if ausrichtung in CERTIFICATE_ORIENTATIONS else DEFAULT_ORIENTATION
        )

        db.session.commit()
        flash("Einstellungen gespeichert.", "success")
        return redirect(url_for('admin.settings'))

    return render_template(
        "admin/settings.html",
        settings=site_settings,
        signature_fonts=SIGNATURE_FONTS,
        certificate_orientations=CERTIFICATE_ORIENTATIONS
    )
