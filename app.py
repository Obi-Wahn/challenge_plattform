import os
import socket

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, redirect, request
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

    # Global Middleware
    @app.before_request
    def force_http():
        if request.headers.get("X-Forwarded-Proto") == "https":
            return redirect(request.url.replace("https://", "http://"), code=301)

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

if __name__ == "__main__":
    with app.app_context():
        db.create_all() # Auto-create tables for dev

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

