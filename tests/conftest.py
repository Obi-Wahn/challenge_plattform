"""Gemeinsame Vorbereitung für alle Tests.

Die Tests laufen gegen eine eigene Datenbank in einem temporären Verzeichnis.
Die echte data/challenge.db wird dabei nie angefasst.
"""

import glob
import os
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests.helpers import ADMIN_PASSWORD, TMP_DIR, csrf_token # noqa: E402


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(TMP_DIR, ignore_errors=True)


@pytest.fixture(scope="session")
def flask_app():
    from app import app as application
    from extensions import limiter

    application.config.update(
        TESTING=True,
        UPLOAD_FOLDER=os.path.join(TMP_DIR, "uploads"),
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

    # Sicherungen, die eine Migration angelegt hat, dürfen nicht in den
    # nächsten Test hineinragen.
    import app as anwendung

    anwendung._backup_path = None
    for kopie in glob.glob(os.path.join(TMP_DIR, "*-vor-*.db")):
        os.remove(kopie)


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
