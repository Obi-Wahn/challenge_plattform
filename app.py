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
import secrets
import sqlite3
from datetime import datetime
from logging.handlers import RotatingFileHandler

from dotenv import load_dotenv
load_dotenv()

from flask import Flask
from config import Config
from extensions import db, csrf, limiter
from network import FESTE_ADRESSE, lan_adresse, server_port
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

# Was auf einer Fehlerseite steht, je Fehlerart: ein Zeichen, eine
# Überschrift und ein Satz, der sagt, was zu tun ist.
#
# Ohne diese Seiten zeigt der Webserver seine eigene: englisch, ohne
# Erklärung und ohne Weg zurück. Das trifft genau die Momente, in denen im
# Wettbewerb jemand die Hand hebt - die falsche Dateiart, die zu große Datei,
# der fünfte Fehlversuch am Admin-Passwort.
FEHLERSEITEN = {
    400: ("🤔", "Damit konnte der Server nichts anfangen",
          "Die Anfrage kam unvollständig an. Am einfachsten ist es, die Seite "
          "neu zu laden und es noch einmal zu versuchen."),
    403: ("🔒", "Das geht gerade nicht",
          "Entweder ist die Anmeldung abgelaufen, oder der Wettbewerb nimmt "
          "gerade nichts mehr entgegen. Auf der Startseite geht es weiter."),
    404: ("🧭", "Diese Seite gibt es nicht",
          "Vielleicht hat sich in der Adresse ein Tippfehler versteckt."),
    413: ("📦", "Die Datei ist zu groß",
          "Bis zu 16 MB nimmt der Server an. Bei einem Scratch-Projekt helfen "
          "meist kleinere Klänge oder Bilder - fragt sonst die Lehrkraft."),
    429: ("⏱️", "Zu viele Versuche",
          "Zum Schutz vor Rateversuchen ist die Anmeldung kurz gesperrt. "
          "Wartet eine Minute, dann geht es wieder."),
    500: ("🛠️", "Da ist etwas schiefgegangen",
          "Der Fehler steht mit Zeitstempel in der Protokolldatei "
          "logs/anwendung.log. Ein Neuladen der Seite hilft oft schon."),
}


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
    # "event" ist Name und Untertitel des Wettbewerbs, den eine Seite meint.
    # Eine Seite, die einen anderen als den aktiven Wettbewerb zeigt, reicht
    # ihr eigenes "event" an render_template weiter; das gewinnt gegen den
    # Wert von hier. "site_event" ist dasselbe für den aktiven Wettbewerb und
    # bleibt davon unberührt: Browsertitel, Leiste oben und Fußzeile sollen
    # sagen, was gerade läuft, auch auf einer Seite über einen älteren
    # Wettbewerb. Läuft keiner, gelten die Standardwerte aus den
    # Einstellungen. "site_settings" gibt es weiter für alles andere, was dort
    # eingestellt wird.
    @app.context_processor
    def inject_site_settings():
        from models import Challenge, Settings, event_branding
        branding = event_branding(Challenge.current())
        return {
            "site_settings": Settings.get(),
            "event": branding,
            "site_event": branding,
        }

    @app.context_processor
    def inject_navigation():
        """Was die obere Leiste über den Wettbewerb wissen muss.

        Die Leiste steht in base.html und kennt von sich aus weder den
        Wettbewerb noch das angemeldete Team. Sie wächst um höchstens einen
        Eintrag: die Urkunde, sobald der Wettbewerb beendet ist. Vorher war
        hier auch ein Countdown-Eintrag; die Restzeit steht inzwischen auf
        der Wettbewerbsseite selbst.
        """
        from models import Challenge
        from sitzung import angemeldetes_team

        challenge = Challenge.current()
        status = challenge.status() if challenge else None

        # Das Team kommt aus der Datenbank, nicht aus der Sitzung: Nach dem
        # Löschen des Wettbewerbs steht der Name noch im Cookie, das Team
        # gibt es aber nicht mehr. Die Leiste zeigte es sonst weiter als
        # angemeldet an, samt "Abmelden".
        team = angemeldetes_team(challenge)

        return {
            "nav_team": team.name if team else None,
            "nav_urkunde": status == "finished",
        }

    register_error_handlers(app)

    return app


def register_error_handlers(app):
    """Zeigt für jeden Fehler eine Seite der Anwendung statt der des Servers."""
    from flask import render_template

    def fehlerseite(code):
        zeichen, ueberschrift, erklaerung = FEHLERSEITEN[code]

        # Ein angemeldetes Team kommt mit einem Klick zurück an die Arbeit,
        # statt sich über die Startseite neu durchklicken zu müssen.
        zurueck = None
        try:
            from flask import url_for
            from models import Challenge
            from sitzung import angemeldetes_team
            if angemeldetes_team(Challenge.current()):
                zurueck = url_for("challenge.view")
        except Exception: # noqa: BLE001 - eine Fehlerseite darf nie selbst scheitern
            zurueck = None

        return render_template(
            "fehler.html", code=code, zeichen=zeichen,
            ueberschrift=ueberschrift, erklaerung=erklaerung, zurueck=zurueck
        ), code

    for code in FEHLERSEITEN:
        # Der Umweg über die Vorgabe bindet den Wert fest: Ohne sie zeigten
        # am Ende alle Handler auf dieselbe letzte Zahl.
        @app.errorhandler(code)
        def zeigen(error, code=code):
            if code == 500:
                # Nach einem Fehler steht die Sitzung der Datenbank womöglich
                # quer. Die Fehlerseite fragt aber selbst noch einmal nach dem
                # Wettbewerb - also erst aufräumen.
                db.session.rollback()
            return fehlerseite(code)

app = create_app()

# Columns added after the initial schema, as {table: {column: definition}}.
# db.create_all() only creates missing tables, not missing columns on a table
# that already exists (e.g. on an existing school-PC database), so these are
# migrated in explicitly on startup.
ADDED_COLUMNS = {
    "challenges": {
        "tagline": "VARCHAR(300) NOT NULL DEFAULT ''",
        "paused_at": "DATETIME",
    },
    "teams": {
        "member_names": "TEXT",
        "members_approved": "BOOLEAN DEFAULT 0",
        "uid": "VARCHAR(32)",
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

def startmeldung(adresse, port, protokoll):
    """Die Zeilen, die beim Start im Fenster stehen.

    Ist die Netzwerkadresse nicht bekannt, wird das gesagt, statt
    127.0.0.1 als Adresse "für andere Geräte" auszugeben - die führt kein
    Handy zum Server, und man sucht den Fehler dann bei der Firewall.
    """
    zeilen = ["Server läuft auf:", f"  http://localhost:{port}  (auf diesem Rechner)"]

    if adresse:
        zeilen.append(f"  http://{adresse}:{port}  (für andere Geräte im gleichen Netzwerk)")
    else:
        zeilen.append("  Die Adresse für andere Geräte konnte nicht ermittelt werden.")
        zeilen.append(f"  Trage sie als {FESTE_ADRESSE}=192.168.… in die .env ein - sonst")
        zeilen.append("  steht auch auf der Startseite und im QR-Code keine brauchbare Adresse.")

    zeilen.append(f"Protokoll: {protokoll}")
    zeilen.append("Zum Beenden: STRG+C\n")
    return zeilen


def run_startup_migrations():
    """Alle Änderungen am Bestand, in der Reihenfolge, in der sie laufen müssen.

    Erst der Umbau der teams-Tabelle, dann die ergänzten Spalten: Der Umbau
    schreibt die Tabelle neu und kennt dabei nur die Spalten, die es zu seiner
    Zeit gab. Liefe er hinterher, fielen alle später ergänzten Spalten - die
    Namen der Teammitglieder etwa - stillschweigend wieder heraus.

    Der Zeitpunkt der Pause und die Kennzeichen der Teams kommen zuletzt:
    Sie füllen Spalten, die der Schritt davor überhaupt erst anlegt.
    """
    ensure_team_challenge_binding()
    ensure_added_columns()
    ensure_pause_timestamp()
    ensure_team_uids()

if __name__ == "__main__":
    with app.app_context():
        db.create_all() # Auto-create tables for dev
        run_startup_migrations()

    # Debug mode is off by default: the built-in Werkzeug debugger allows
    # arbitrary code execution and this app is bound to 0.0.0.0 for LAN access,
    # so it must only be enabled explicitly for local development.
    debug_mode = os.environ.get("FLASK_DEBUG", "false").strip().lower() in ("1", "true", "yes")
    port = server_port()

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

        adresse = lan_adresse()

        for zeile in startmeldung(
            adresse, port, os.path.join(app.config["LOG_DIR"], "anwendung.log")
        ):
            print(zeile)

        # Der Start gehört ins Protokoll: Danach lässt sich später zuordnen,
        # welche Meldungen zu welchem Wettbewerbstag gehören.
        if adresse:
            app.logger.info("Server gestartet auf http://%s:%s", adresse, port)
        else:
            app.logger.warning(
                "Server gestartet auf Port %s, die Netzwerkadresse ist unbekannt "
                "(%s in der .env setzen).", port, FESTE_ADRESSE
            )

        serve(app, host="0.0.0.0", port=port)

