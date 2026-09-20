import os
import socket

from dotenv import load_dotenv
load_dotenv()

from flask import Flask
from config import Config
from extensions import db, csrf, limiter
from blueprints.auth import auth_bp
from blueprints.public import public_bp
from blueprints.challenge import challenge_bp
from blueprints.admin import admin_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

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
        from markupsafe import Markup
        import markdown
        if not text:
            return ""
        return Markup(markdown.markdown(text))

    # Site branding (name, tagline) is admin-editable, stored in the DB,
    # and injected into every template instead of being hardcoded.
    @app.context_processor
    def inject_site_settings():
        from models import Settings
        return {"site_settings": Settings.get()}

    return app

app = create_app()

def get_local_ip():
    # Determines the IP this machine would use to reach the network, without
    # actually sending anything - used to show students which address to open.
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()

# Columns added after the initial schema, as {table: {column: definition}}.
# db.create_all() only creates missing tables, not missing columns on a table
# that already exists (e.g. on an existing school-PC database), so these are
# migrated in explicitly on startup.
ADDED_COLUMNS = {
    "tasks": {
        "hint": "TEXT",
        "hint_visible": "BOOLEAN DEFAULT 0",
    },
    "submissions": {
        "resubmit_allowed": "BOOLEAN DEFAULT 0",
    },
}

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

    with db.engine.begin() as conn:
        definition = conn.execute(text(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='teams'"
        )).scalar() or ""

        if "_challenge_team_uc" in definition:
            return # already migrated

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

    with db.engine.begin() as conn:
        for table, columns in ADDED_COLUMNS.items():
            if table not in existing_tables:
                continue
            present = {c["name"] for c in inspector.get_columns(table)}
            for column, definition in columns.items():
                if column not in present:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))

if __name__ == "__main__":
    with app.app_context():
        db.create_all() # Auto-create tables for dev
        ensure_added_columns()
        ensure_team_challenge_binding()

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

        print(f"Server läuft auf:")
        print(f"  http://localhost:{port}  (auf diesem Rechner)")
        print(f"  http://{get_local_ip()}:{port}  (für andere Geräte im gleichen Netzwerk)")
        print("Zum Beenden: STRG+C\n")

        serve(app, host="0.0.0.0", port=port)

