import os

# Werte, die öffentlich im Repository stehen: in .env.example und als Beispiel
# in der README. Mit einem bekannten SECRET_KEY kann sich jeder ein
# Sitzungs-Cookie mit „is_admin“ selbst unterschreiben, ganz ohne Passwort -
# mit diesen Werten startet die Anwendung deshalb nicht. Dieselbe Liste steht
# in starter.py, der sie beim Start selbst ersetzt.
PLATZHALTER = {
    "change-this-in-production-random-string",
    "change-this-password",
    "dein-geheimer-schluessel",
    "dein-sicheres-passwort",
}

# Ab dieser Länge lässt sich ein SECRET_KEY nicht mehr durchprobieren. Ein
# Team sieht sein eigenes Cookie im Browser, und für kurze Schlüssel gibt es
# fertige Werkzeuge mit Wortlisten. Der Starter vergibt 64 Zeichen.
MIN_SCHLUESSEL = 32


def _require_env(key):
    value = os.environ.get(key)
    if not value:
        raise RuntimeError(
            f"{key} ist nicht gesetzt. Kopiere .env.example zu .env und setze einen echten Wert, "
            "bevor die Anwendung gestartet wird."
        )
    if value in PLATZHALTER:
        raise RuntimeError(
            f"{key} steht in der .env noch auf dem Beispielwert „{value}“. Der steht "
            "öffentlich im Repository. Die Startdatei ersetzt ihn beim nächsten Start "
            "selbst - oder in der .env einen eigenen Wert eintragen."
        )
    return value


def schluessel_zu_kurz(schluessel):
    """Ob sich der SECRET_KEY durchprobieren ließe - siehe MIN_SCHLUESSEL."""
    return len(schluessel or "") < MIN_SCHLUESSEL


class Config:
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))

    # Security
    SECRET_KEY = _require_env("SECRET_KEY")
    ADMIN_PASSWORD = _require_env("ADMIN_PASSWORD")
    
    # Das Sitzungs-Cookie geht nur mit, wenn die Anfrage von dieser Seite
    # selbst ausgeht - nicht, wenn eine fremde Seite sie auslöst.
    # SESSION_COOKIE_SECURE bleibt aus: Im Schul-LAN läuft die Anwendung über
    # http, mit Secure=True käme niemand mehr hinein.
    SESSION_COOKIE_SAMESITE = "Lax"

    # Database
    # The data/ directory only exists on disk because of this file (it holds
    # no other tracked files), so it must be created before SQLite can open
    # a database inside it on a fresh checkout.
    os.makedirs(os.path.join(BASE_DIR, "data"), exist_ok=True)
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or \
        "sqlite:///" + os.path.join(BASE_DIR, "data", "challenge.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Uploads
    # The allowed file type is configured per task (Task.allowed_extension),
    # not globally.
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload

    # Protokolldatei
    # Eigener Ort per LOG_DIR, damit die Tests nicht in das Verzeichnis der
    # laufenden Installation schreiben.
    LOG_DIR = os.environ.get("LOG_DIR") or os.path.join(BASE_DIR, "logs")

    # Rate limiting
    # The app runs as a single process on one machine, so per-process
    # in-memory storage is sufficient - this makes that an explicit choice
    # instead of Flask-Limiter's unconfigured fallback (which warns on startup).
    RATELIMIT_STORAGE_URI = "memory://"
