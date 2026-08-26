import os


def _require_env(key):
    value = os.environ.get(key)
    if not value:
        raise RuntimeError(
            f"{key} ist nicht gesetzt. Kopiere .env.example zu .env und setze einen echten Wert, "
            "bevor die Anwendung gestartet wird."
        )
    return value


class Config:
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))

    # Security
    SECRET_KEY = _require_env("SECRET_KEY")
    ADMIN_PASSWORD = _require_env("ADMIN_PASSWORD")
    
    # Database
    # The data/ directory only exists on disk because of this file (it holds
    # no other tracked files), so it must be created before SQLite can open
    # a database inside it on a fresh checkout.
    os.makedirs(os.path.join(BASE_DIR, "data"), exist_ok=True)
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or \
        "sqlite:///" + os.path.join(BASE_DIR, "data", "challenge.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Uploads
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    ALLOWED_EXTENSIONS = {"pde"}
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload

    # Rate limiting
    # The app runs as a single process on one machine, so per-process
    # in-memory storage is sufficient - this makes that an explicit choice
    # instead of Flask-Limiter's unconfigured fallback (which warns on startup).
    RATELIMIT_STORAGE_URI = "memory://"
