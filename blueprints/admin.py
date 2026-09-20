from flask import Blueprint, render_template, request, redirect, url_for, session, abort, send_from_directory, send_file, current_app, flash
from extensions import db
from models import Team, Challenge, Task, Submission, Settings
from scoring import get_standings
from certificates import build_certificates_pdf
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
    challenge = Challenge.query.get_or_404(cid)

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
    challenge = Challenge.query.get_or_404(cid)

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if title:
            challenge.title = title
        challenge.start_time = parse_datetime_local(request.form.get("start_time"))
        challenge.end_time = parse_datetime_local(request.form.get("end_time"))
        db.session.commit()
        flash("Titel und Zeiten gespeichert.", "success")
        return redirect(url_for('admin.challenge_detail', cid=cid))

    return render_template("admin/challenge_edit.html", challenge=challenge)

# Activating changes which competition everything refers to, so it is a POST
# with a CSRF token rather than a plain link.
@admin_bp.route("/challenge/<int:cid>/activate", methods=["POST"])
def challenge_activate(cid):
    challenge = Challenge.query.get_or_404(cid)
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
    challenge = Challenge.query.get_or_404(cid)

    if request.method == "POST":
        title = request.form["title"]
        description = request.form["description"]
        max_points = int(request.form["max_points"])
        allowed_extension = request.form.get("allowed_extension", ".pde")
        hint = request.form.get("hint", "").strip() or None

        task = Task(
            challenge_id=cid,
            title=title,
            description=description,
            max_points=max_points,
            allowed_extension=allowed_extension,
            hint=hint
        )
        db.session.add(task)
        db.session.commit()
        return redirect(url_for('admin.challenge_tasks', cid=cid))

    tasks = Task.query.filter_by(challenge_id=cid).all()
    return render_template("admin/challenge_tasks.html", challenge=challenge, tasks=tasks)

@admin_bp.route("/challenges/<int:cid>/pause", methods=["POST"])
def challenge_pause(cid):
    challenge = Challenge.query.get_or_404(cid)
    challenge.paused = True
    db.session.commit()
    flash(f"„{challenge.title}“ ist pausiert – Abgaben sind vorübergehend gesperrt.", "warning")
    return redirect(safe_redirect_target(url_for('admin.challenge_detail', cid=cid)))

@admin_bp.route("/challenges/<int:cid>/resume", methods=["POST"])
def challenge_resume(cid):
    challenge = Challenge.query.get_or_404(cid)
    challenge.paused = False
    db.session.commit()
    flash(f"„{challenge.title}“ läuft weiter – Abgaben sind wieder möglich.", "success")
    return redirect(safe_redirect_target(url_for('admin.challenge_detail', cid=cid)))

@admin_bp.route("/challenges/<int:cid>/finish", methods=["POST"])
def challenge_finish(cid):
    """Ends the competition now: no more submissions, ready for the ceremony."""
    challenge = Challenge.query.get_or_404(cid)
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
    challenge = Challenge.query.get_or_404(cid)
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
    challenge = Challenge.query.get_or_404(cid)
    db.session.delete(challenge)
    db.session.commit()
    return redirect(url_for('admin.challenges_list'))

@admin_bp.route("/tasks/<int:tid>/delete", methods=["POST"])
def task_delete(tid):
    task = Task.query.get_or_404(tid)
    cid = task.challenge_id
    db.session.delete(task)
    db.session.commit()
    # Redirect back to tasks list
    return redirect(url_for('admin.challenge_tasks', cid=cid))

@admin_bp.route("/tasks/<int:tid>/edit", methods=["GET", "POST"])
def task_edit(tid):
    task = Task.query.get_or_404(tid)
    cid = task.challenge_id
    
    if request.method == "POST":
        task.title = request.form["title"]
        task.description = request.form["description"]
        task.max_points = int(request.form["max_points"])
        task.allowed_extension = request.form.get("allowed_extension", ".pde")
        task.hint = request.form.get("hint", "").strip() or None
        db.session.commit()
        return redirect(url_for('admin.challenge_tasks', cid=cid))

    return render_template("admin/task_edit.html", task=task)

@admin_bp.route("/tasks/<int:tid>/toggle_hint", methods=["POST"])
def task_toggle_hint(tid):
    task = Task.query.get_or_404(tid)
    task.hint_visible = not task.hint_visible
    db.session.commit()
    return redirect(url_for('admin.challenge_tasks', cid=task.challenge_id))

@admin_bp.route("/submissions", methods=["GET", "POST"])
def submissions():
    if request.method == "POST":
        submission_id = request.form.get("submission_id")
        
        if "soft_reset" in request.form:
             submission = Submission.query.get(submission_id)
             if submission:
                 submission.points = None
                 submission.feedback = None
                 db.session.commit()
        else:
             points = request.form.get("points")
             feedback = request.form.get("feedback", "")
             submission = Submission.query.get(submission_id)
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
    submission = Submission.query.get_or_404(submission_id)
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
    submission = Submission.query.get_or_404(submission_id)
    db.session.delete(submission)
    db.session.commit()
    return redirect(url_for('admin.submissions'))

def safe_name(text):
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
    return "".join(c if c in allowed else "_" for c in text)

@admin_bp.route("/download/<int:submission_id>")
def download_submission(submission_id):
    submission = Submission.query.get_or_404(submission_id)
    
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
    return render_template("admin/teams.html", teams=teams, challenge=challenge)

@admin_bp.route("/team/<int:team_id>/reset_password", methods=["POST"])
def team_reset_password(team_id):
    team = Team.query.get_or_404(team_id)
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
    team = Team.query.get_or_404(team_id)
    db.session.delete(team)
    db.session.commit()
    return redirect(url_for('admin.teams'))

def _certificate_data():
    """Collects everything the certificates need, for the latest challenge."""
    challenge = Challenge.current()
    if not challenge:
        return None, [], 0

    tasks, standings = get_standings(challenge)
    return challenge, standings, len(tasks)

@admin_bp.route("/urkunden")
def certificates_print():
    challenge, standings, task_count = _certificate_data()
    return render_template(
        "admin/urkunden.html",
        challenge=challenge,
        entries=standings,
        task_count=task_count,
        today=datetime.now().strftime("%d.%m.%Y")
    )

@admin_bp.route("/urkunden.pdf")
def certificates_pdf():
    challenge, standings, task_count = _certificate_data()
    if not standings:
        flash("Es sind noch keine Teams registriert – es gibt nichts zu drucken.", "warning")
        return redirect(url_for('admin.certificates_print'))

    pdf_bytes = build_certificates_pdf(
        Settings.get().site_name,
        challenge.title if challenge else "",
        standings,
        task_count
    )
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"Urkunden_{safe_name(challenge.title if challenge else 'Wettbewerb')}.pdf"
    )

@admin_bp.route("/urkunden/<int:team_id>.pdf")
def certificate_pdf_single(team_id):
    team = Team.query.get_or_404(team_id)
    challenge, standings, task_count = _certificate_data()

    entry = next((e for e in standings if e["team_id"] == team_id), None)
    if entry is None:
        # Team exists but has no place in the current challenge yet.
        entry = {"team_id": team.id, "name": team.name, "total": 0, "solved": 0, "rank": 0}

    pdf_bytes = build_certificates_pdf(
        Settings.get().site_name,
        challenge.title if challenge else "",
        [entry],
        task_count
    )
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
        db.session.commit()
        return redirect(url_for('admin.settings'))

    return render_template("admin/settings.html", settings=site_settings)
