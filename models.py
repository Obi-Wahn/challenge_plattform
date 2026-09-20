from datetime import datetime
from extensions import db

class Team(db.Model):
    __tablename__ = 'teams'
    id = db.Column(db.Integer, primary_key=True)
    # A team belongs to the competition it registered for. Nullable so teams
    # from before this became a rule survive the migration.
    challenge_id = db.Column(db.Integer, db.ForeignKey('challenges.id'), nullable=True)
    name = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(200), nullable=True)
    submissions = db.relationship('Submission', backref='team', lazy=True, cascade="all, delete-orphan")

    # Team names only need to be unique within their own competition, so the
    # same team can take part in several competitions.
    __table_args__ = (db.UniqueConstraint('challenge_id', 'name', name='_challenge_team_uc'),)

    def set_password(self, password):
        from werkzeug.security import generate_password_hash
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        from werkzeug.security import check_password_hash
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

class Challenge(db.Model):
    __tablename__ = 'challenges'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    start_time = db.Column(db.DateTime, nullable=True)
    end_time = db.Column(db.DateTime, nullable=True)
    active = db.Column(db.Boolean, default=False)
    paused = db.Column(db.Boolean, default=False)
    tasks = db.relationship('Task', backref='challenge', lazy=True, cascade="all, delete-orphan")
    teams = db.relationship('Team', backref='challenge', lazy=True, cascade="all, delete-orphan")

    @classmethod
    def current(cls):
        """The competition everything refers to: the activated one.

        Falls back to the newest competition while none has been activated,
        so a fresh installation works without pressing "aktivieren" first.
        """
        return (cls.query.filter_by(active=True).first()
                or cls.query.order_by(cls.id.desc()).first())

    def status(self):
        # end_time is optional: a challenge can have a start countdown without
        # a fixed end, in which case it just keeps running once it has started.
        # A passed end time always means finished, also when no start time was
        # ever set - that is what the "Wettbewerb beenden" button relies on.
        now = datetime.now()
        if self.end_time and now > self.end_time:
            return "finished"
        if not self.start_time:
            return "not_scheduled"
        if now < self.start_time:
            return "upcoming"
        return "running"

    @property
    def accepts_submissions(self):
        """Whether teams may hand something in right now.

        A paused or finished competition is closed. A competition whose start
        time has not come yet stays open on purpose: the start time drives the
        countdown page, and a teacher testing beforehand should not be locked
        out by it.
        """
        return not self.paused and self.status() != "finished"

    @property
    def state_label(self):
        """Short German label for the current state, used across the admin."""
        if self.status() == "finished":
            return "beendet"
        if self.paused:
            return "pausiert"
        if self.status() == "upcoming":
            return "geplant"
        return "läuft"

    @property
    def seconds_until_start(self):
        if not self.start_time:
            return 0
        remaining = (self.start_time - datetime.now()).total_seconds()
        return max(0, int(remaining))

    @property
    def remaining_seconds(self):
        if not self.end_time:
            return 0
        now = datetime.now()
        remaining = (self.end_time - now).total_seconds()
        return max(0, int(remaining))

class Task(db.Model):
    __tablename__ = 'tasks'
    id = db.Column(db.Integer, primary_key=True)
    challenge_id = db.Column(db.Integer, db.ForeignKey('challenges.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    max_points = db.Column(db.Integer, default=0)
    allowed_extension = db.Column(db.String(10), default=".pde")
    hint = db.Column(db.Text, nullable=True)
    hint_visible = db.Column(db.Boolean, default=False)
    submissions = db.relationship('Submission', backref='task', lazy=True, cascade="all, delete-orphan")

class Submission(db.Model):
    __tablename__ = 'submissions'
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False)
    filename = db.Column(db.String(300), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.now)
    points = db.Column(db.Integer, nullable=True)
    feedback = db.Column(db.Text, nullable=True)
    # Set by an admin to let the team replace this submission once.
    resubmit_allowed = db.Column(db.Boolean, default=False)

    __table_args__ = (db.UniqueConstraint('team_id', 'task_id', name='_team_task_uc'),)

class Settings(db.Model):
    __tablename__ = 'settings'
    id = db.Column(db.Integer, primary_key=True)
    site_name = db.Column(db.String(100), nullable=False, default="Coding-Wettbewerb")
    tagline = db.Column(
        db.String(300),
        nullable=False,
        default="Ein Wettbewerb für Code, Ideen und Kreativität."
    )
    # Name under the signature line on the certificates, plus the handwriting
    # font it is written in. Empty means the certificates keep saying
    # "Unterschrift", as they did before this was configurable.
    signature_name = db.Column(db.String(100), nullable=False, default="")
    signature_font = db.Column(db.String(30), nullable=False, default="caveat")

    @classmethod
    def get(cls):
        settings = cls.query.first()
        if not settings:
            settings = cls()
            db.session.add(settings)
            db.session.commit()
        return settings
