import sys

# fpdf2 (Urkunden) und Flask-Limiter setzen Python 3.10 voraus. Ohne diese
# Prüfung endet ein Start unter einer älteren Fassung in einem ImportError,
# der nicht verrät, woran es wirklich liegt.
if sys.version_info < (3, 10):
    raise SystemExit(
        "Python 3.10 oder neuer wird gebraucht, gefunden: "
        f"{sys.version_info.major}.{sys.version_info.minor}.\n"
        "Die Urkunden (fpdf2) und die Anmeldebremse (Flask-Limiter) laufen "
        "unter älteren Fassungen nicht."
    )

import logging
import os
import re
import sqlite3
from datetime import datetime
from logging.handlers import RotatingFileHandler

from dotenv import load_dotenv
load_dotenv()

from flask import Flask
from config import Config
from extensions import db, csrf, limiter
from network import get_local_ip
from blueprints.auth import auth_bp
from blueprints.public import public_bp
from blueprints.challenge import challenge_bp
from blueprints.admin import admin_bp

# Registriert die Haken, die hochgeladene Dateien mit ihrer Abgabe löschen.
import uploads # noqa: F401

# Verweise, die nicht ins Web zeigen. Markdown erzeugt aus [Text](ziel) ein
# href, und "ziel" kommt aus dem Aufgabentext - javascript: gehoert da nicht
# hinein. Erlaubt bleiben http, https, mailto, Sprungmarken und Pfade.
UNSICHERE_ZIELE = re.compile(
    r'(href|src)="(?!https?:|mailto:|#|/)[^"]*"', re.IGNORECASE
)

# Name des Handlers, damit ein zweiter Aufruf von create_app() - in den
# Tests kommt das vor - nicht ein zweites Mal in dieselbe Datei schreibt.
LOG_HANDLER_NAME = "protokolldatei"


def configure_logging(app):
    """Schreibt Fehler und wichtige Ereignisse in eine Datei.

    Ohne das stünde ein Traceback nur im Terminal: Wer das Fenster schließt
    oder den Server als Dienst laufen lässt, hat nach einer Störung nichts
    mehr in der Hand - und am Wettbewerbstag ist genau dann keine Zeit, den
    Fehler noch einmal herbeizuführen.

    Die Datei rotiert bei 1 MB und behält fünf ältere Stände, damit sie nicht
    unbegrenzt wächst.
    """
    if any(h.name == LOG_HANDLER_NAME for h in app.logger.handlers):
        return

    log_dir = app.config["LOG_DIR"]
    os.makedirs(log_dir, exist_ok=True)

    handler = RotatingFileHandler(
        os.path.join(log_dir, "anwendung.log"),
        maxBytes=1_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    handler.name = LOG_HANDLER_NAME
    handler.setLevel(logging.INFO)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s  %(levelname)-8s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)

    # waitress meldet über einen eigenen Logger, was die Anwendung selbst
    # nicht mehr abfangen konnte. Auch das gehört in dieselbe Datei.
    waitress_log = logging.getLogger("waitress")
    if not any(h.name == LOG_HANDLER_NAME for h in waitress_log.handlers):
        waitress_log.addHandler(handler)
        waitress_log.setLevel(logging.INFO)


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    configure_logging(app)

    # Initialize Extensions
    db.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    # Register Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(public_bp)
    app.register_blueprint(challenge_bp)
    app.register_blueprint(admin_bp)

    # Custom Filters
    @app.template_filter('markdown')
    def render_markdown(text):
        """Aufgabentext als Markdown, ohne rohes HTML durchzulassen.

        Das Ergebnis wird als vertrauenswürdiges HTML ausgegeben, darf also
        nichts enthalten, was der Aufgabentext eingeschleust hat. Solange die
        Lehrkraft jede Aufgabe selbst tippt, wäre das unkritisch - seit dem
        Aufgaben-Import kann der Text aber aus einer Datei stammen, die
        jemand anderes geschrieben hat. Und gerendert wird er unter anderem
        in der Bewertungsansicht, also in der Sitzung des Admins.

        Zwei Dinge werden deshalb entschärft: rohes HTML im Text (es wird
        vorher escaped und erscheint als Text, wie es dasteht) und Verweise
        auf andere Ziele als das Web (javascript:, data: und Ähnliches).
        Die Markdown-Auszeichnung selbst - Fettdruck, Listen, Code, Links
        ins Web - funktioniert unverändert.
        """
        from markupsafe import Markup, escape
        import markdown
        if not text:
            return ""

        html = markdown.markdown(str(escape(text)))
        return Markup(UNSICHERE_ZIELE.sub(r'\1="#"', html))

    # Site branding (name, tagline) is admin-editable, stored in the DB,
    # and injected into every template instead of being hardcoded.
    #
    # "site_settings" ist dabei der Name der Installation: Er steht im
    # Browsertitel, in der Navigationsleiste und in der Fußzeile, also auch
    # auf Seiten, die zu keinem Wettbewerb gehören. "event" ist der Name der
    # Veranstaltung, den der aktive Wettbewerb überschreiben darf - ihn
    # zeigen die Seiten, die einen Wettbewerb meinen. Eine Seite, die einen
    # anderen als den aktiven Wettbewerb zeigt, reicht ihr eigenes "event" an
    # render_template weiter; das gewinnt gegen den Wert von hier.
    @app.context_processor
    def inject_site_settings():
        from models import Challenge, Settings, event_branding
        return {
            "site_settings": Settings.get(),
            "event": event_branding(Challenge.current()),
        }

    @app.context_processor
    def inject_navigation():
        """Was die obere Leiste über den Wettbewerb wissen muss.

        Die Leiste steht in base.html und kennt den Wettbewerb sonst nicht.
        Sie wächst um höchstens einen Eintrag: die Urkunde, sobald der
        Wettbewerb beendet ist. Vorher war hier auch ein Countdown-Eintrag;
        die Restzeit steht inzwischen auf der Wettbewerbsseite selbst.
        """
        from models import Challenge
        challenge = Challenge.current()
        status = challenge.status() if challenge else None

        return {
            "nav_urkunde": status == "finished",
        }

    return app

app = create_app()

# Columns added after the initial schema, as {table: {column: definition}}.
# db.create_all() only creates missing tables, not missing columns on a table
# that already exists (e.g. on an existing school-PC database), so these are
# migrated in explicitly on startup.
ADDED_COLUMNS = {
    "challenges": {
        "tagline": "VARCHAR(300) NOT NULL DEFAULT ''",
    },
    "teams": {
        "member_names": "TEXT",
        "members_approved": "BOOLEAN DEFAULT 0",
    },
    "tasks": {
        "hint": "TEXT",
        "hint_visible": "BOOLEAN DEFAULT 0",
    },
    "submissions": {
        "resubmit_allowed": "BOOLEAN DEFAULT 0",
    },
    "settings": {
        "signature_name": "VARCHAR(100) NOT NULL DEFAULT ''",
        "signature_font": "VARCHAR(30) NOT NULL DEFAULT 'caveat'",
        "certificate_orientation": "VARCHAR(10) NOT NULL DEFAULT 'landscape'",
        "member_names_enabled": "BOOLEAN NOT NULL DEFAULT 0",
    },
}

# Pfad der Sicherung, die in diesem Start angelegt wurde. Eine pro Start
# genügt: Sie entsteht vor der ersten Änderung und zeigt damit den Stand,
# wie er vor allen Umbauten dieses Starts war.
_backup_path = None

def database_file():
    """Der Pfad der SQLite-Datei, oder None bei einer anderen Datenbank."""
    uri = app.config["SQLALCHEMY_DATABASE_URI"]
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

    path = database_file()
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
    app.logger.info("Datenbank vor der Änderung gesichert: %s", target)
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

def run_startup_migrations():
    """Alle Änderungen am Bestand, in der Reihenfolge, in der sie laufen müssen.

    Erst der Umbau der teams-Tabelle, dann die ergänzten Spalten: Der Umbau
    schreibt die Tabelle neu und kennt dabei nur die Spalten, die es zu seiner
    Zeit gab. Liefe er hinterher, fielen alle später ergänzten Spalten - die
    Namen der Teammitglieder etwa - stillschweigend wieder heraus.
    """
    ensure_team_challenge_binding()
    ensure_added_columns()

if __name__ == "__main__":
    with app.app_context():
        db.create_all() # Auto-create tables for dev
        run_startup_migrations()

    # Debug mode is off by default: the built-in Werkzeug debugger allows
    # arbitrary code execution and this app is bound to 0.0.0.0 for LAN access,
    # so it must only be enabled explicitly for local development.
    debug_mode = os.environ.get("FLASK_DEBUG", "false").strip().lower() in ("1", "true", "yes")
    port = 8000

    if debug_mode:
        # Flask's built-in dev server, with debugger and auto-reload, for local development only.
        app.run(
          host="0.0.0.0",
          port=port,
          debug=True
        )
    else:
        # Production WSGI server for real deployments (e.g. the school LAN).
        from waitress import serve

        adresse = get_local_ip()

        print("Server läuft auf:")
        print(f"  http://localhost:{port}  (auf diesem Rechner)")
        print(f"  http://{adresse}:{port}  (für andere Geräte im gleichen Netzwerk)")
        print(f"Protokoll: {os.path.join(app.config['LOG_DIR'], 'anwendung.log')}")
        print("Zum Beenden: STRG+C\n")

        # Der Start gehört ins Protokoll: Danach lässt sich später zuordnen,
        # welche Meldungen zu welchem Wettbewerbstag gehören.
        app.logger.info("Server gestartet auf http://%s:%s", adresse, port)

        serve(app, host="0.0.0.0", port=port)

