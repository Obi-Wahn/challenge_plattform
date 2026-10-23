"""Was beim Start an einer bestehenden Datenbank umgebaut wird.

db.create_all() legt nur fehlende Tabellen an. Spalten, die später dazukamen,
geänderte Einschränkungen und umgestellte Werte holt diese Datei nach, damit
eine Datenbank vom Schul-PC ohne Datenverlust auf den neuen Stand kommt. Vor
dem ersten Umbau eines Starts entsteht eine Kopie (backup_before_migration).

Alles hier läuft im App-Kontext; app.py ruft run_startup_migrations() beim
Start auf.
"""

import os
import re
import secrets
import sqlite3
from datetime import datetime

from flask import current_app

from extensions import db

# Columns added after the initial schema, as {table: {column: definition}}.
# db.create_all() only creates missing tables, not missing columns on a table
# that already exists (e.g. on an existing school-PC database), so these are
# migrated in explicitly on startup.
ADDED_COLUMNS = {
    "challenges": {
        "tagline": "VARCHAR(300) NOT NULL DEFAULT ''",
        "greeting": "VARCHAR(200) NOT NULL DEFAULT ''",
        "paused_at": "DATETIME",
        "freeze_enabled": "BOOLEAN NOT NULL DEFAULT 0",
        "freeze_minutes": "INTEGER NOT NULL DEFAULT 15",
        "frozen_since": "DATETIME",
        "scoreboard_revealed": "BOOLEAN NOT NULL DEFAULT 0",
        "announcements_enabled": "BOOLEAN NOT NULL DEFAULT 0",
        "announcement_text": "VARCHAR(200) NOT NULL DEFAULT ''",
        "announcement_at": "DATETIME",
        "self_correction": "BOOLEAN NOT NULL DEFAULT 1",
    },
    "teams": {
        "member_names": "TEXT",
        "members_approved": "BOOLEAN DEFAULT 0",
        "uid": "VARCHAR(32)",
    },
    "tasks": {
        "hint": "TEXT",
        "hint_visible": "BOOLEAN DEFAULT 0",
        "difficulty": "VARCHAR(10) NOT NULL DEFAULT ''",
        "position": "INTEGER NOT NULL DEFAULT 0",
    },
    "submissions": {
        "resubmit_allowed": "BOOLEAN DEFAULT 0",
        "frozen_points": "INTEGER",
        "frozen_timestamp": "DATETIME",
    },
    "settings": {
        "signature_name": "VARCHAR(100) NOT NULL DEFAULT ''",
        "signature_font": "VARCHAR(30) NOT NULL DEFAULT 'caveat'",
        "certificate_orientation": "VARCHAR(10) NOT NULL DEFAULT 'landscape'",
        "member_names_enabled": "BOOLEAN NOT NULL DEFAULT 0",
        "scoreboard_task_titles": "BOOLEAN NOT NULL DEFAULT 1",
        "greeting": "VARCHAR(200) NOT NULL DEFAULT 'Schön, dass ihr dabei seid!'",
        "review_password_hash": "VARCHAR(200) NOT NULL DEFAULT ''",
    },
}

# Pfad der Sicherung, die in diesem Start angelegt wurde. Eine pro Start
# genügt: Sie entsteht vor der ersten Änderung und zeigt damit den Stand,
# wie er vor allen Umbauten dieses Starts war.
_backup_path = None

def datenbankdatei():
    """Der Pfad der SQLite-Datei, oder None bei einer anderen Datenbank."""
    uri = current_app.config["SQLALCHEMY_DATABASE_URI"]
    if not uri.startswith("sqlite:///"):
        return None
    return uri[len("sqlite:///"):]

def backup_before_migration(reason):
    """Legt eine Kopie der Datenbank an, bevor an ihrer Struktur etwas geändert wird.

    Die Migrationen laufen in einer Transaktion, ein Absturz mittendrin kann
    also nichts zerreißen. Die Kopie ist für den anderen Fall da: Der Umbau
    läuft sauber durch, macht aber nicht das Gewünschte - dann kommt man an
    den Stand davor heran.

    Schlägt das Anlegen fehl, bricht der Start ab. Lieber gar nicht starten
    als ohne Netz umbauen.
    """
    global _backup_path

    if _backup_path:
        return _backup_path

    path = datenbankdatei()
    if not path or not os.path.exists(path):
        return None # frische Installation, es gibt noch nichts zu sichern

    stamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    target = os.path.join(
        os.path.dirname(path),
        f"{os.path.splitext(os.path.basename(path))[0]}-vor-{reason}-{stamp}.db"
    )

    try:
        # Die Sicherungs-Schnittstelle von SQLite statt einer einfachen
        # Dateikopie: Sie liefert auch dann einen sauberen Stand, wenn die
        # Anwendung die Datei gerade geöffnet hat.
        source = sqlite3.connect(path)
        try:
            copy = sqlite3.connect(target)
            try:
                with copy:
                    source.backup(copy)
            finally:
                copy.close()
        finally:
            source.close()
    except (sqlite3.Error, OSError) as error:
        raise RuntimeError(
            f"Die Datenbank konnte vor der Änderung nicht gesichert werden: {error}\n"
            f"Gewünschte Kopie: {target}\n"
            "Der Start wurde abgebrochen, damit nichts ungesichert umgebaut wird."
        ) from error

    _backup_path = target
    print(f"Datenbank vor der Änderung gesichert: {target}")
    current_app.logger.info("Datenbank vor der Änderung gesichert: %s", target)
    return target

def ensure_team_challenge_binding():
    """Binds existing teams to a competition.

    Teams used to be global with a globally unique name. SQLite cannot drop
    that UNIQUE constraint with ALTER TABLE, so the table is rebuilt with the
    new (challenge_id, name) constraint and existing teams are assigned to the
    current competition, which is the one they were registered for in practice.
    """
    from sqlalchemy import inspect, text

    inspector = inspect(db.engine)
    if "teams" not in inspector.get_table_names():
        return

    with db.engine.connect() as conn:
        definition = conn.execute(text(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='teams'"
        )).scalar() or ""

    if "_challenge_team_uc" in definition:
        return # already migrated

    backup_before_migration("teams")

    with db.engine.begin() as conn:
        columns = {c["name"] for c in inspector.get_columns("teams")}
        if "challenge_id" in columns:
            source_challenge = "challenge_id"
        else:
            target = conn.execute(text(
                "SELECT id FROM challenges ORDER BY active DESC, id DESC LIMIT 1"
            )).scalar()
            source_challenge = str(target) if target is not None else "NULL"

        conn.execute(text("""
            CREATE TABLE teams_migrated (
                id INTEGER NOT NULL,
                challenge_id INTEGER,
                name VARCHAR(100) NOT NULL,
                password_hash VARCHAR(200),
                PRIMARY KEY (id),
                CONSTRAINT _challenge_team_uc UNIQUE (challenge_id, name),
                FOREIGN KEY(challenge_id) REFERENCES challenges (id)
            )
        """))
        conn.execute(text(
            "INSERT INTO teams_migrated (id, challenge_id, name, password_hash) "
            f"SELECT id, {source_challenge}, name, password_hash FROM teams"
        ))
        conn.execute(text("DROP TABLE teams"))
        conn.execute(text("ALTER TABLE teams_migrated RENAME TO teams"))

def ensure_added_columns():
    from sqlalchemy import inspect, text

    inspector = inspect(db.engine)
    existing_tables = set(inspector.get_table_names())

    # Erst sammeln, was fehlt: Nur wenn wirklich etwas ergänzt wird, lohnt
    # sich eine Sicherung. Sonst entstünde bei jedem Start eine Kopie.
    missing = []
    for table, columns in ADDED_COLUMNS.items():
        if table not in existing_tables:
            continue
        present = {c["name"] for c in inspector.get_columns(table)}
        for column, definition in columns.items():
            if column not in present:
                missing.append((table, column, definition))

    if not missing:
        return

    backup_before_migration("spalten")

    with db.engine.begin() as conn:
        for table, column, definition in missing:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))

def ensure_pause_timestamp():
    """Gibt einer laufenden Pause aus der Zeit davor einen Zeitpunkt.

    Wird während eines Updates gerade pausiert, steht in paused_at nichts,
    und die Uhr liefe trotz Pause weiter. Der Start des Updates ist der
    genaueste Zeitpunkt, den es hier noch gibt.
    """
    from sqlalchemy import DateTime, bindparam, inspect, text

    inspector = inspect(db.engine)
    if "challenges" not in set(inspector.get_table_names()):
        return

    # Der Zeitpunkt wird als DateTime angemeldet, damit SQLAlchemy ihn selbst
    # in Text umwandelt - so, wie es beim Weg über die Modelle ohnehin
    # geschieht. Ohne die Angabe ginge das datetime-Objekt unverändert an
    # sqlite3, und dessen eingebauter Adapter ist seit Python 3.12
    # abgekündigt. Gespeichert wird in beiden Fällen derselbe Text.
    befehl = text(
        "UPDATE challenges SET paused_at = :jetzt "
        "WHERE paused = 1 AND paused_at IS NULL"
    ).bindparams(bindparam("jetzt", type_=DateTime))

    with db.engine.begin() as conn:
        conn.execute(befehl, {"jetzt": datetime.now()})

def ensure_team_uids():
    """Gibt Teams aus der Zeit vor der Spalte ihr Kennzeichen.

    Ohne Kennzeichen käme ein Team nicht mehr auf seine Seite: Die Anmeldung
    vergleicht es mit dem, was in der Sitzung steht. Der Wert wird einmal
    vergeben und bleibt dann, solange es das Team gibt.
    """
    from sqlalchemy import inspect, text

    inspector = inspect(db.engine)
    if "teams" not in set(inspector.get_table_names()):
        return

    with db.engine.begin() as conn:
        offene = conn.execute(text(
            "SELECT id FROM teams WHERE uid IS NULL OR uid = ''"
        )).scalars().all()

        # Jedes Team bekommt einen eigenen Wert - ein gemeinsamer wäre kein
        # Kennzeichen, sondern nur eine zweite Art, "irgendein Team" zu sagen.
        for team_id in offene:
            conn.execute(text("UPDATE teams SET uid = :uid WHERE id = :id"),
                         {"uid": secrets.token_hex(16), "id": team_id})

# So sieht ein Ablageort aus, wie er inzwischen in der Datenbank steht:
# Teamnummer, Schrägstrich, Dateiname - siehe models.abgabe_pfad().
ABLAGE = re.compile(r"\d+/[^/\\]+")


def gedeuteter_ablageort(gespeichert):
    """Der Ablageort zu einem ganzen Pfad aus der Zeit bis v1.15.0, oder None.

    Abgaben lagen immer unter uploads/<Team>/<Datei>, also genügen die
    letzten zwei Teile. Getrennt wird an / und an \\, damit auch eine
    Datenbank von einem Windows-Rechner auf Linux passt und umgekehrt. Was
    nicht so aussieht, bleibt unangetastet.
    """
    if not gespeichert or ABLAGE.fullmatch(gespeichert):
        return None
    teile = [teil for teil in re.split(r"[/\\]", gespeichert) if teil]
    if len(teile) < 2 or not teile[-2].isdigit():
        return None
    return f"{teile[-2]}/{teile[-1]}"


def ensure_relative_upload_paths():
    """Stellt die Abgaben von ganzen Pfaden auf den Ablageort unter uploads/ um.

    Bis v1.15.0 stand in der Datenbank der ganze Pfad, samt dem Ordner der
    Installation. Nach einem Update aus dem ZIP zeigte er in den alten
    Ordner, siehe models.abgabe_pfad(). Läuft einmal; danach steht überall
    der kurze Ablageort, und es gibt nichts mehr umzustellen.
    """
    from sqlalchemy import inspect, text

    if "submissions" not in set(inspect(db.engine).get_table_names()):
        return

    with db.engine.connect() as conn:
        zeilen = conn.execute(text("SELECT id, filename FROM submissions")).all()

    umstellen = [(nummer, neu) for nummer, alt in zeilen
                 if (neu := gedeuteter_ablageort(alt))]
    if not umstellen:
        return

    backup_before_migration("pfade")

    with db.engine.begin() as conn:
        for nummer, neu in umstellen:
            conn.execute(text("UPDATE submissions SET filename = :neu WHERE id = :id"),
                         {"neu": neu, "id": nummer})

    current_app.logger.info("Abgaben auf den Ablageort unter uploads/ umgestellt: %s", len(umstellen))


def ensure_active_challenge():
    """Macht den Wettbewerb ausdrücklich aktiv, der bisher nur einsprang.

    Bis v1.9.0 galt ohne aktivierten Wettbewerb der neueste. Seitdem gilt
    ohne Aktivierung keiner. Damit ein Update nicht plötzlich die Startseite
    leert, wird genau der Wettbewerb aktiv geschaltet, der vorher angezeigt
    wurde. Danach greift das nie wieder: Es gibt dann einen aktiven.
    """
    from sqlalchemy import inspect, text

    if "challenges" not in set(inspect(db.engine).get_table_names()):
        return

    with db.engine.begin() as conn:
        if conn.execute(text("SELECT 1 FROM challenges WHERE active = 1")).first():
            return
        neuester = conn.execute(text(
            "SELECT id, title FROM challenges ORDER BY id DESC LIMIT 1")).first()
        if neuester is None:
            return
        conn.execute(text("UPDATE challenges SET active = 1 WHERE id = :id"),
                     {"id": neuester.id})

    current_app.logger.info("Wettbewerb beim Start aktiv geschaltet, er galt bisher ohne "
                    "Aktivierung: „%s“ (#%s)", neuester.title, neuester.id)


def run_startup_migrations():
    """Alle Änderungen am Bestand, in der Reihenfolge, in der sie laufen müssen.

    Erst der Umbau der teams-Tabelle, dann die ergänzten Spalten: Der Umbau
    schreibt die Tabelle neu und kennt dabei nur die Spalten, die es zu seiner
    Zeit gab. Liefe er hinterher, fielen alle später ergänzten Spalten - die
    Namen der Teammitglieder etwa - stillschweigend wieder heraus.

    Der Zeitpunkt der Pause und die Kennzeichen der Teams kommen danach:
    Sie füllen Spalten, die der Schritt davor überhaupt erst anlegt. Dann
    werden die Pfade der Abgaben umgestellt, und zuletzt bekommt ein Bestand
    ohne aktiven Wettbewerb seinen aktiven.
    """
    ensure_team_challenge_binding()
    ensure_added_columns()
    ensure_pause_timestamp()
    ensure_team_uids()
    ensure_relative_upload_paths()
    ensure_active_challenge()
