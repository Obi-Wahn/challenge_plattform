"""Gemeinsame Vorbereitung für alle Tests.

Die Tests laufen gegen eine eigene Datenbank in einem temporären Verzeichnis.
Die echte data/challenge.db wird dabei nie angefasst.
"""

import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Muss vor dem Import von app/config gesetzt sein: config.py verlangt diese
# Werte beim Laden. load_dotenv() überschreibt vorhandene Variablen nicht,
# eine .env der Entwicklerin kann also nicht dazwischenfunken.
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ADMIN_PASSWORD", "test-admin")

_TMP = tempfile.mkdtemp(prefix="challenge-tests-")
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(_TMP, "test.db")

ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_TMP, ignore_errors=True)


@pytest.fixture(scope="session")
def flask_app():
    from app import app as application
    from extensions import limiter

    application.config.update(
        TESTING=True,
        UPLOAD_FOLDER=os.path.join(_TMP, "uploads"),
    )

    # Das Login-Limit würde nach fünf Anmeldungen zuschlagen und alle
    # folgenden Tests scheitern lassen. test_security.py schaltet es für
    # seine eigene Prüfung gezielt wieder ein.
    limiter.enabled = False

    return application


@pytest.fixture(autouse=True)
def database(flask_app):
    """Für jeden Test eine frische, leere Datenbank."""
    from extensions import db

    with flask_app.app_context():
        db.drop_all()
        db.create_all()
        yield db
        db.session.remove()

    shutil.rmtree(flask_app.config["UPLOAD_FOLDER"], ignore_errors=True)


# ---------------------------------------------------------------- Hilfsmittel

def csrf_token(client, path):
    """Holt ein CSRF-Token von einer Seite, die ein Formular enthält.

    Ohne Token weist Flask-WTF jedes POST mit 400 ab - dann testet man nicht
    die Anwendung, sondern den Schutzmechanismus.

    Das g.csrf_token muss vorher weg: Flask-WTF merkt sich das Token im
    App-Kontext, und die Tests halten einen offen. Sonst bekäme ein zweiter
    Testclient im selben Test kein eigenes Session-Cookie. Im echten Betrieb
    gibt es diesen Fall nicht - dort lebt der Kontext nur für eine Anfrage.
    """
    from flask import g

    g.pop("csrf_token", None)
    html = client.get(path).get_data(as_text=True)
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match, f"Auf {path} steht kein CSRF-Token - falsche Seite gewählt?"
    return match.group(1)


@pytest.fixture
def token():
    return csrf_token


@pytest.fixture
def client(flask_app):
    return flask_app.test_client()


@pytest.fixture
def admin(flask_app):
    """Ein Testclient, der bereits als Admin angemeldet ist."""
    client = flask_app.test_client()
    client.post("/admin/login", data={
        "csrf_token": csrf_token(client, "/admin/login"),
        "password": ADMIN_PASSWORD,
    })
    return client


# ------------------------------------------------------------------ Factories

@pytest.fixture
def make_challenge(database):
    from models import Challenge

    def _make(title="Test-Wettbewerb", active=True, **kwargs):
        challenge = Challenge(title=title, active=active,
                              paused=kwargs.pop("paused", False), **kwargs)
        database.session.add(challenge)
        database.session.commit()
        return challenge

    return _make


@pytest.fixture
def make_task(database):
    from models import Task

    def _make(challenge, title="Aufgabe", max_points=10,
              allowed_extension=".sb3", **kwargs):
        task = Task(challenge_id=challenge.id, title=title, max_points=max_points,
                    allowed_extension=allowed_extension, **kwargs)
        database.session.add(task)
        database.session.commit()
        return task

    return _make


@pytest.fixture
def make_team(database):
    from models import Team

    def _make(challenge, name="Team", password="geheim"):
        team = Team(name=name, challenge_id=challenge.id)
        team.set_password(password)
        database.session.add(team)
        database.session.commit()
        return team

    return _make


@pytest.fixture
def logged_in_team(flask_app, make_team):
    """Meldet ein Team an und gibt (client, team) zurück."""
    def _login(challenge, name="Team Blitz", password="geheim"):
        team = make_team(challenge, name=name, password=password)
        client = flask_app.test_client()
        response = client.post("/login", data={
            "csrf_token": csrf_token(client, "/login"),
            "team": name,
            "password": password,
        })
        assert response.status_code == 302, "Anmeldung des Testteams schlug fehl"
        return client, team

    return _login


@pytest.fixture
def upload():
    """Baut den Datei-Teil für eine Abgabe."""
    import io

    def _upload(content=b"projektdatei", filename="loesung.sb3"):
        return (io.BytesIO(content), filename)

    return _upload
