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
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or \
        "sqlite:///" + os.path.join(BASE_DIR, "data", "challenge.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Uploads
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    ALLOWED_EXTENSIONS = {"pde"}
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload
