from flask import Blueprint, render_template, request, redirect, url_for, session, abort, current_app
from extensions import db
from models import Team, Challenge, Task, Submission
from werkzeug.utils import secure_filename
import os
from datetime import datetime

challenge_bp = Blueprint('challenge', __name__)

def allowed_file(filename, allowed_ext):
    return "." in filename and filename.lower().endswith(allowed_ext.lower())

@challenge_bp.route("/challenge")
def view():
    if "team_id" not in session:
        return redirect(url_for("public.index"))

    team_id = session["team_id"]
    team = Team.query.get(team_id) # Ensure team exists

    # Teams always see the most recently created challenge, regardless of its active flag.
    challenge = Challenge.query.order_by(Challenge.id.desc()).first()

    if not challenge:
        return render_template(
            "challenge.html",
            challenge=None,
            tasks=[],
            submission_map={},
            team=team.name if team else session.get("team_name")
        )

    tasks = Task.query.filter_by(challenge_id=challenge.id).all()
    
    submissions = Submission.query.filter_by(team_id=team_id).join(Task).filter(Task.challenge_id == challenge.id).all()
    submission_map = {s.task_id: s for s in submissions}

    return render_template(
        "challenge.html",
        challenge=challenge,
        tasks=tasks,
        submission_map=submission_map,
        team=team.name if team else session.get("team_name")
    )

@challenge_bp.route("/submit/<int:task_id>", methods=["POST"])
def submit_task(task_id):
    if "team_id" not in session:
        abort(403)

    # Submissions are only accepted for the most recently created challenge,
    # matching what teams see on the challenge page.
    challenge = Challenge.query.order_by(Challenge.id.desc()).first()
    if not challenge:
        abort(403)

    task = Task.query.get_or_404(task_id)
    if task.challenge_id != challenge.id:
        abort(403) # Task not part of the current challenge

    if challenge.paused:
        abort(403)

    team_id = session["team_id"]

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
