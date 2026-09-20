from flask import (Blueprint, render_template, request, redirect, url_for, session,
                   abort, current_app, send_file)
from extensions import db
from models import Team, Challenge, Task, Submission
from scoring import get_standings
from certificates import build_certificates_for, certificate_entry
from werkzeug.utils import secure_filename
import io
import os
from datetime import datetime

challenge_bp = Blueprint('challenge', __name__)

def allowed_file(filename, allowed_ext):
    return "." in filename and filename.lower().endswith(allowed_ext.lower())

def team_of_current_challenge(challenge):
    """The logged-in team, but only if it belongs to this competition.

    A session from an earlier competition must not carry over once another one
    has been activated.
    """
    team_id = session.get("team_id")
    if not team_id or not challenge:
        return None

    team = db.session.get(Team, team_id)
    if team is None or team.challenge_id != challenge.id:
        return None
    return team

@challenge_bp.route("/challenge")
def view():
    if "team_id" not in session:
        return redirect(url_for("public.index"))

    # Teams always see the currently active competition.
    challenge = Challenge.current()
    team = team_of_current_challenge(challenge)

    if challenge and team is None:
        # Logged in for a competition that is no longer the current one.
        session.pop("team_id", None)
        session.pop("team_name", None)
        return redirect(url_for("public.index"))

    if not challenge:
        return render_template(
            "challenge.html",
            challenge=None,
            tasks=[],
            submission_map={},
            team=session.get("team_name")
        )

    team_id = team.id
    tasks = Task.query.filter_by(challenge_id=challenge.id).all()
    
    submissions = Submission.query.filter_by(team_id=team_id).join(Task).filter(Task.challenge_id == challenge.id).all()
    submission_map = {s.task_id: s for s in submissions}

    return render_template(
        "challenge.html",
        challenge=challenge,
        tasks=tasks,
        submission_map=submission_map,
        team=team.name
    )

@challenge_bp.route("/submit/<int:task_id>", methods=["POST"])
def submit_task(task_id):
    if "team_id" not in session:
        abort(403)

    # Submissions are only accepted for the active competition,
    # matching what teams see on the challenge page.
    challenge = Challenge.current()
    if not challenge:
        abort(403)

    # A team may only submit for its own competition.
    team = team_of_current_challenge(challenge)
    if team is None:
        abort(403)

    task = db.get_or_404(Task, task_id)
    if task.challenge_id != challenge.id:
        abort(403) # Task not part of the current challenge

    # Closed means closed: paused, or past the end time.
    if not challenge.accepts_submissions:
        abort(403)

    team_id = team.id

    # A team may only submit once per task, unless an admin explicitly
    # released this submission for a correction.
    existing = Submission.query.filter_by(team_id=team_id, task_id=task_id).first()
    if existing and not existing.resubmit_allowed:
        abort(403)

    if "file" not in request.files:
        abort(400)
    
    file = request.files["file"]
    if file.filename == "" or not allowed_file(file.filename, task.allowed_extension):
        abort(400)

    filename = secure_filename(file.filename)
    team_folder = os.path.join(current_app.config["UPLOAD_FOLDER"], str(team_id))
    os.makedirs(team_folder, exist_ok=True)
    
    filepath = os.path.join(team_folder, f"task_{task_id}_{filename}")
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

        if previous_filepath != filepath:
            try:
                os.remove(previous_filepath)
            except OSError:
                pass # An already missing old file must not break the submission.
    else:
        db.session.add(Submission(
            team_id=team_id,
            task_id=task_id,
            filename=filepath,
            timestamp=datetime.now()
        ))

    db.session.commit()

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
    team = team_of_current_challenge(challenge)
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
