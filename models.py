import re
import secrets
from datetime import datetime, timedelta

from extensions import db

# Wie viele Namen ein Team für seine Urkunde einträgt und wie lang einer sein
# darf. Beides ist großzügig bemessen und nur dafür da, dass aus dem Feld kein
# Aufsatz wird - eine Urkunde hat für einen Roman keinen Platz.
MAX_MEMBERS = 12
MAX_MEMBER_NAME_LENGTH = 60

# Wie lang die fertige Aufzählung auf der Urkunde höchstens werden darf, in
# Zeichen. Zwölf übliche Vor- und Nachnamen kommen auf rund 200 Zeichen und
# passen damit; darüber hinaus wird das Blatt so voll, dass der Text an den
# Unterschriftsblock stößt. Dann lieber nachfragen als eine Urkunde drucken,
# auf der es klemmt.
MAX_MEMBER_TEXT_LENGTH = 220


def parse_member_names(text):
    """Die Namen aus dem Eingabefeld, in der Reihenfolge der Eingabe.

    Gedacht ist ein Name pro Zeile. Komma und Semikolon trennen aber genauso,
    weil Schüler ihre Namen erfahrungsgemäß in einer Zeile aneinanderreihen.
    Leere Zeilen und doppelte Leerzeichen fallen weg; die Zahl der Namen
    begrenzt hier niemand, das entscheidet die Stelle, die sie entgegennimmt.
    """
    namen = []
    for teil in re.split(r"[\n,;]", str(text or "")):
        name = " ".join(teil.split())
        if name:
            namen.append(name[:MAX_MEMBER_NAME_LENGTH])
    return namen


def format_member_names(namen):
    """Die Namen so, wie sie in der Datenbank stehen: einer pro Zeile."""
    return "\n".join(namen)


class Team(db.Model):
    __tablename__ = 'teams'
    id = db.Column(db.Integer, primary_key=True)
    # A team belongs to the competition it registered for. Nullable so teams
    # from before this became a rule survive the migration.
    challenge_id = db.Column(db.Integer, db.ForeignKey('challenges.id'), nullable=True)
    name = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(200), nullable=True)
    # Ein Kennzeichen, das genau dieses eine Team meint - und nur dann in
    # einer Sitzung steht, wenn sich dieses Team angemeldet hat. Die Nummer
    # allein taugt dafür nicht: SQLite vergibt die Nummer eines gelöschten
    # Teams wieder, und das Cookie eines gelöschten Teams passte damit auf
    # das nächste, das dieselbe Nummer bekam. Nullable, weil Teams aus der
    # Zeit davor die Spalte erst beim Start nachgetragen bekommen.
    uid = db.Column(db.String(32), nullable=True,
                    default=lambda: secrets.token_hex(16))
    # Die Namen der Teammitglieder für die Urkunde, einer pro Zeile, so wie
    # die Schüler sie selbst eingetragen haben.
    member_names = db.Column(db.Text, nullable=True)
    # Ob der Admin diese Namen gesehen und freigegeben hat. Nur dann stehen
    # sie auf der Urkunde. Ändert das Team etwas, fällt die Freigabe wieder
    # weg - sonst könnte nach der Kontrolle noch etwas anderes hineinrutschen.
    members_approved = db.Column(db.Boolean, default=False)
    submissions = db.relationship('Submission', backref='team', lazy=True, cascade="all, delete-orphan")

    # Team names only need to be unique within their own competition, so the
    # same team can take part in several competitions.
    #
    # Die Schreibweise zählt mit: „Die Hacker“ und „die hacker“ sind zwei
    # verschiedene Teams. Das ist eine bewusste Entscheidung - ein Team soll
    # seinen Namen genau so bekommen, wie es ihn geschrieben hat, und die
    # Anwendung soll nicht entscheiden, welche zwei Namen „dasselbe“ sind.
    #
    # Beim Anmelden ist das anders: Dort verzeiht team_zur_anmeldung() eine
    # abweichende Schreibweise, solange sie eindeutig bleibt. Siehe dort.
    __table_args__ = (db.UniqueConstraint('challenge_id', 'name', name='_challenge_team_uc'),)

    def set_password(self, password):
        from werkzeug.security import generate_password_hash
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        from werkzeug.security import check_password_hash
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    @property
    def member_list(self):
        """Die eingetragenen Namen, ob freigegeben oder nicht."""
        return parse_member_names(self.member_names)

    @property
    def certificate_names(self):
        """Die Namen, die auf die Urkunde dürfen - ohne Freigabe keine."""
        return self.member_list if self.members_approved else []

class Challenge(db.Model):
    __tablename__ = 'challenges'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    # Der Untertitel dieses Wettbewerbs, unter seinem Titel. Leer heißt: es
    # gilt der Untertitel aus den Einstellungen.
    #
    # Einen eigenen Namen braucht ein Wettbewerb nicht - "title" ist sein
    # Name. Dieselbe Installation richtet so einmal den "Scratch-Wettbewerb"
    # und einmal den "Calliope-Wettbewerb" aus, und der Name bleibt bei dem
    # Wettbewerb, zu dem er gehört, auch wenn längst ein anderer läuft.
    tagline = db.Column(db.String(300), nullable=False, default="")
    # Der Gruß auf der Startseite, unter dem Namen. Leer heißt: es gilt der
    # aus den Einstellungen. Ein eigener Satz statt "Willkommen beim ...",
    # weil der Artikel vom Namen abhinge - "beim Scratch-Cup", "bei der
    # Calliope-Challenge" - und den kann die Seite nicht sicher wählen.
    greeting = db.Column(db.String(200), nullable=False, default="")
    start_time = db.Column(db.DateTime, nullable=True)
    end_time = db.Column(db.DateTime, nullable=True)
    active = db.Column(db.Boolean, default=False)
    paused = db.Column(db.Boolean, default=False)
    # Wann die Pause gedrückt wurde. Solange der Wert steht, rechnet der
    # Wettbewerb mit diesem Zeitpunkt statt mit der echten Uhr - die Restzeit
    # steht still, und die Endzeit rückt beim Fortsetzen um die Dauer der
    # Pause nach hinten. Leer heißt: keine Pause im Gang.
    paused_at = db.Column(db.DateTime, nullable=True)
    # Die Rangliste vor Schluss einfrieren: Ab freeze_minutes vor dem Ende
    # zeigt sie nur noch, was bis dahin abgegeben war. Die Punkte eines Teams
    # auf seiner eigenen Seite bleiben davon unberührt.
    freeze_enabled = db.Column(db.Boolean, nullable=False, default=False)
    freeze_minutes = db.Column(db.Integer, nullable=False, default=15)
    # Festgehaltener Zeitpunkt des Einfrierens. Leer heißt: er ergibt sich
    # aus der Endzeit. Festgehalten wird er, wenn sich die Endzeit nach dem
    # Einfrieren noch bewegt (Fortsetzen nach einer Pause, Beenden) - sonst
    # tauchten Abgaben wieder auf, die der Beamer schon verborgen hatte.
    frozen_since = db.Column(db.DateTime, nullable=True)
    # Mit „Rangliste auflösen“ zeigt die Rangliste wieder den echten Stand.
    scoreboard_revealed = db.Column(db.Boolean, nullable=False, default=False)
    # Durchsagen an die Teams, je Wettbewerb einzuschalten. Es gibt immer nur
    # eine: Eine neue ersetzt die alte, einen Verlauf gibt es nicht - was
    # nicht gespeichert ist, muss auch niemand wieder löschen.
    announcements_enabled = db.Column(db.Boolean, nullable=False, default=False)
    announcement_text = db.Column(db.String(200), nullable=False, default="")
    announcement_at = db.Column(db.DateTime, nullable=True)
    tasks = db.relationship('Task', backref='challenge', lazy=True, cascade="all, delete-orphan",
                            order_by="(Task.position, Task.id)")
    teams = db.relationship('Team', backref='challenge', lazy=True, cascade="all, delete-orphan")

    @classmethod
    def current(cls):
        """Der Wettbewerb, auf den sich alles bezieht: der aktivierte.

        Ist keiner aktiv, gibt es keinen - auch wenn andere Wettbewerbe
        angelegt sind. Früher sprang hier der neueste ein. Dann wurde nach
        dem Löschen des aktiven still irgendein alter zum aktuellen, und
        eine eingelesene Sicherung stand ohne Aktivieren auf der Startseite.
        Welcher gilt, entscheidet die Lehrkraft mit „Aktivieren“.

        Damit eine frische Installation ohne diesen Schritt auskommt, wird
        ein neu angelegter Wettbewerb von selbst aktiv, wenn gerade keiner
        aktiv ist - siehe admin.challenge_new.
        """
        return cls.query.filter_by(active=True).first()

    @property
    def reference_time(self):
        """Die Zeit, nach der sich alles richtet.

        Im Normalfall die echte Uhr. Während einer Pause der Zeitpunkt, an
        dem pausiert wurde: Dann steht die Restzeit still, und eine Endzeit,
        die während der Pause verstreicht, beendet den Wettbewerb nicht.

        Eine Pause ohne Zeitstempel stammt noch aus der Zeit vor dieser
        Spalte. Sie sperrt die Abgaben wie bisher, hält die Uhr aber nicht
        an - besser, als mit einem geratenen Zeitpunkt zu rechnen.
        """
        if self.paused and self.paused_at:
            return self.paused_at
        return datetime.now()

    @property
    def paused_seconds(self):
        """Wie lange die laufende Pause bisher dauert, in Sekunden."""
        if not (self.paused and self.paused_at):
            return 0
        return max(0, int((datetime.now() - self.paused_at).total_seconds()))

    def status(self):
        # end_time is optional: a challenge can have a start countdown without
        # a fixed end, in which case it just keeps running once it has started.
        # A passed end time always means finished, also when no start time was
        # ever set - that is what the "Wettbewerb beenden" button relies on.
        now = self.reference_time
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
        time has not come yet stays open on purpose: the start time only drives
        the remaining-time bar, and a teacher testing beforehand should not be
        locked out by it.
        """
        return not self.paused and self.status() != "finished"

    @property
    def accepts_registrations(self):
        """Ob sich gerade noch ein neues Team anmelden darf.

        Dieselbe Bedingung wie bei den Abgaben, aber aus einem eigenen Grund -
        deshalb steht sie hier getrennt.

        Ein **beendeter** Wettbewerb ist zu: Danach hängt die Rangliste am
        Beamer, und ein Team, das sich dann noch anmeldet, stünde mit null
        Punkten mitten in der Siegerehrung - und auf der Urkundenliste, denn
        die zählt jedes Team des Wettbewerbs, auch eines ohne Abgabe.

        Ein **pausierter** Wettbewerb ist ebenfalls zu: Die Pause ist der
        Moment, in dem die Lehrkraft nicht auf den Bildschirm sieht.

        Vor dem Start bleibt die Anmeldung offen: Genau dann melden sich die
        Teams an.
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
        remaining = (self.start_time - self.reference_time).total_seconds()
        return max(0, int(remaining))

    @property
    def remaining_seconds(self):
        if not self.end_time:
            return 0
        remaining = (self.end_time - self.reference_time).total_seconds()
        return max(0, int(remaining))

    @property
    def announcement(self):
        """Die Durchsage, die gerade gilt, oder None."""
        if self.announcements_enabled and self.announcement_text:
            return self.announcement_text
        return None

    def clear_announcement(self):
        self.announcement_text = ""
        self.announcement_at = None

    @property
    def duration_minutes(self):
        """Die eingestellte Dauer in Minuten, oder None.

        Nur eine andere Sicht auf Start- und Endzeit: Gespeichert wird immer
        die Endzeit. Das Formular zeigt die Dauer damit an, ohne sie doppelt
        zu fuehren.
        """
        if not (self.start_time and self.end_time):
            return None
        minutes = int((self.end_time - self.start_time).total_seconds() // 60)
        return minutes if minutes > 0 else None

    @property
    def freeze_point(self):
        """Ab wann die Rangliste eingefroren ist, oder None.

        Ohne Endzeit gibt es kein „vor Schluss“ und damit nichts einzufrieren.
        Eine Pause vor dem Einfrieren schiebt den Zeitpunkt mit der Endzeit
        nach hinten - die Teams haben dann ja auch länger Zeit.
        """
        if not self.freeze_enabled:
            return None
        if self.frozen_since:
            return self.frozen_since
        if not self.end_time:
            return None
        return self.end_time - timedelta(minutes=self.freeze_minutes or 0)

    @property
    def scoreboard_frozen(self):
        """Ob die Rangliste gerade den eingefrorenen Stand zeigt.

        Das bleibt auch nach dem Ende so, bis die Lehrkraft die Rangliste
        auflöst - sonst stünde das Ergebnis am Beamer, bevor die
        Siegerehrung es verkündet.
        """
        punkt = self.freeze_point
        if punkt is None or self.scoreboard_revealed:
            return False
        return self.reference_time >= punkt

    @property
    def certificates_open(self):
        """Ob ein Team seine Urkunde herunterladen darf.

        Nach dem Ende - aber nicht, solange die Rangliste eingefroren ist:
        Auf der Urkunde steht der Platz, und den soll die Siegerehrung
        verkünden, nicht das Handy eines Teams.
        """
        return self.status() == "finished" and not self.scoreboard_frozen

    def pin_freeze(self, jetzt):
        """Hält den Zeitpunkt des Einfrierens fest, bevor sich die Endzeit bewegt.

        `jetzt` ist die Zeit, nach der sich der Wettbewerb in diesem Moment
        richtet - beim Fortsetzen der Beginn der Pause. Ist die Rangliste da
        noch nicht eingefroren, bleibt alles, wie es ist.
        """
        punkt = self.freeze_point
        if self.frozen_since or punkt is None or self.scoreboard_revealed:
            return
        if jetzt >= punkt:
            self.frozen_since = punkt

    def freeze_on_finish(self, jetzt):
        """Beim Beenden: Nichts, was bis eben am Beamer stand, verschwindet.

        Endet der Wettbewerb vor dem geplanten Einfrieren, friert die
        Rangliste mit dem Ende ein. Die Siegerehrung bleibt so die Stelle, an
        der das Ergebnis herauskommt, und die Endzeit von jetzt zieht keine
        Abgaben der letzten Minuten nachträglich wieder vom Beamer.
        """
        if not self.freeze_enabled or self.frozen_since or self.scoreboard_revealed:
            return
        punkt = self.freeze_point
        self.frozen_since = min(punkt, jetzt) if punkt else jetzt

    def reset_freeze(self):
        """Neue Zeiten, neues Einfrieren: Festgehaltenes und Auflösen fallen weg."""
        self.frozen_since = None
        self.scoreboard_revealed = False

# File formats a task can ask for, as {extension: label}. Kept in one place so
# the task forms and the import agree on what is allowed.
TASK_FORMATS = {
    ".pde": "Processing",
    ".sb": "Scratch 1.4",
    ".sb3": "Scratch 3.0",
    ".java": "Java",
    ".py": "Python",
    ".hex": "MakeCode/Calliope",
    ".mkcd": "MakeCode-Projekt",
}

DEFAULT_TASK_FORMAT = ".pde"

# Wie schwer eine Aufgabe ist, als {Wert: Zeichen}. Bisher stand die
# Schwierigkeit im Titel („Punkte sammeln (mittel)“); als eigene Eigenschaft
# lässt sie sich anzeigen, sichern und wieder einlesen. Die Reihenfolge ist die
# des Auswahlfelds.
TASK_DIFFICULTIES = {
    "einfach": "🟢",
    "mittel": "🟡",
    "schwer": "🔴",
}

# Keine Angabe ist der Normalfall: Aufgaben aus der Zeit vor dem Feld haben
# keine, und eine Datei ohne den Schlüssel soll sich unverändert einlesen
# lassen.
NO_TASK_DIFFICULTY = ""

# Welche Formate sich in der Bewertung als Text lesen lassen. Eine .sb3- oder
# .mkcd-Datei ist eine ZIP-Datei und eine .hex-Datei eine Liste aus
# Maschinencode - im Anzeigefeld stünde davon nur Zeichensalat, und die Seite
# trüge dabei Megabyte davon mit sich herum. Für diese Formate gibt es den
# Knopf zum Herunterladen.
TEXT_FORMATS = {".pde", ".java", ".py"}

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
    # Leer heißt: keine Angabe. Sonst ein Schlüssel aus TASK_DIFFICULTIES.
    difficulty = db.Column(db.String(10), nullable=False, default=NO_TASK_DIFFICULTY)
    # Platz in der Reihenfolge des Wettbewerbs, kleiner steht weiter oben.
    # Aufgaben aus der Zeit vor dem Feld stehen alle auf 0 und behalten
    # damit die Reihenfolge, in der sie angelegt wurden (siehe geordnet()).
    position = db.Column(db.Integer, nullable=False, default=0)
    submissions = db.relationship('Submission', backref='task', lazy=True, cascade="all, delete-orphan")

    @property
    def difficulty_symbol(self):
        """Das Zeichen zur Schwierigkeit, oder "" ohne Angabe.

        Damit das Schild auf der Wettbewerbsseite und in der Aufgabenliste
        dieselben drei Stufen kennt wie die Prüfung der Eingaben.
        """
        return TASK_DIFFICULTIES.get(self.difficulty or "", "")

    @classmethod
    def geordnet(cls, challenge_id):
        """Die Aufgaben eines Wettbewerbs in der Reihenfolge, die der Admin festlegt.

        Überall, wo Aufgaben der Reihe nach stehen - Teamseite, Rangliste,
        Sicherung -, gilt diese eine Reihenfolge. Bei gleicher Position
        entscheidet die Nummer, also das Anlegen.
        """
        return (cls.query.filter_by(challenge_id=challenge_id)
                .order_by(cls.position, cls.id))

    @classmethod
    def naechste_position(cls, challenge_id):
        """Die Position für eine neue Aufgabe: hinter allen vorhandenen."""
        hoechste = (db.session.query(db.func.max(cls.position))
                    .filter(cls.challenge_id == challenge_id).scalar())
        return (hoechste or 0) + 1

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

STANDARDGRUSS = "Schön, dass ihr dabei seid!"

class Settings(db.Model):
    __tablename__ = 'settings'
    id = db.Column(db.Integer, primary_key=True)
    # Standardname und -untertitel: Sie gelten, solange kein Wettbewerb mit
    # eigenem Namen laeuft, also auf einer frischen Installation.
    site_name = db.Column(db.String(100), nullable=False, default="Coding-Wettbewerb")
    tagline = db.Column(
        db.String(300),
        nullable=False,
        default="Ein Wettbewerb für Code, Ideen und Kreativität."
    )
    # Der Standardgruß auf der Startseite, für jeden Wettbewerb ohne eigenen.
    greeting = db.Column(db.String(200), nullable=False, default=STANDARDGRUSS)
    # Name under the signature line on the certificates, plus the handwriting
    # font it is written in. Empty means the certificates keep saying
    # "Unterschrift", as they did before this was configurable.
    signature_name = db.Column(db.String(100), nullable=False, default="")
    signature_font = db.Column(db.String(30), nullable=False, default="caveat")
    # Quer- oder Hochformat der Urkunden. Quer ist die bisherige Fassung und
    # bleibt die Voreinstellung, damit sich für niemanden etwas ändert.
    certificate_orientation = db.Column(db.String(10), nullable=False, default="landscape")
    # Ob die Teams ihre Namen für die Urkunde überhaupt eintragen dürfen.
    # Aus, bis die Lehrkraft es freischaltet: Vorher soll auf der Team-Seite
    # kein Feld stehen, das noch niemand ausfüllen soll.
    member_names_enabled = db.Column(db.Boolean, nullable=False, default=False)
    # Ob über den Spalten der Rangliste „A1: Titel“ steht oder nur „A1“.
    # An ist die Voreinstellung; aus lohnt sich bei vielen Aufgaben mit
    # langen Titeln, wenn am Beamer ohnehin nur Wortanfänge übrig blieben.
    scoreboard_task_titles = db.Column(db.Boolean, nullable=False, default=True)

    @classmethod
    def get(cls):
        settings = cls.query.first()
        if not settings:
            settings = cls()
            db.session.add(settings)
            db.session.commit()
        return settings


def event_branding(challenge=None):
    """Name, Untertitel und Gruß, wie sie für diesen Wettbewerb gelten.

    Der Name ist der Titel des Wettbewerbs: Beides auseinanderzuhalten wäre
    doppelt, ein Wettbewerb heißt, wie er heißt. Den Untertitel darf er
    überschreiben, ebenso den Gruß auf der Startseite; lässt er sie leer,
    gelten die aus den Einstellungen.

    Ohne Wettbewerb gelten die Einstellungen allein - das ist der Fall auf
    einer frischen Installation, in der noch keiner angelegt ist. Die Werte
    dort sind also die Standardwerte, kein eigener Name der Anwendung: Läuft
    ein Wettbewerb, steht sein Name auch im Browsertitel, in der Leiste oben
    und in der Fußzeile.
    """
    settings = Settings.get()
    return {
        "name": (challenge.title if challenge else "") or settings.site_name,
        "tagline": (challenge.tagline if challenge else "") or settings.tagline,
        "greeting": ((challenge.greeting if challenge else "")
                     or settings.greeting or STANDARDGRUSS),
    }
