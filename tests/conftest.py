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

# Im Betrieb hasht werkzeug jedes Passwort mit scrypt, gut eine Zehntelsekunde
# lang - das soll Erraten teuer machen. In den Tests ist es nur Wartezeit: Fast
# jeder legt Teams an oder meldet sich an, zusammen kostete das rund anderthalb
# Minuten je Lauf. Hier hasht deshalb ein schnelles Verfahren, das
# check_password_hash genauso versteht. Die Anwendung selbst bleibt bei scrypt,
# das prüft test_security.py mit dem echten Verfahren.
import werkzeug.security  # noqa: E402


def schnell_hashen(password, method="pbkdf2:sha256:1", salt_length=16):
    return schnell_hashen.echt(password, method=method, salt_length=salt_length)


schnell_hashen.echt = werkzeug.security.generate_password_hash
werkzeug.security.generate_password_hash = schnell_hashen


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(TMP_DIR, ignore_errors=True)


@pytest.fixture(scope="session")
def flask_app():
    from flask.testing import FlaskClient

    from app import app as application
    from plattform.extensions import limiter

    class GepufferterClient(FlaskClient):
        """Liest jede Antwort gleich ganz und schließt sie wieder.

        Downloads und Sicherungen kommen aus einer offenen Datei. Im Betrieb
        schließt waitress sie nach dem Senden, im Test bliebe sie offen, und
        Python meldete ResourceWarnings.
        """

        def open(self, *args, buffered=True, **kwargs):
            return super().open(*args, buffered=buffered, **kwargs)

    application.test_client_class = GepufferterClient
    application.config.update(
        TESTING=True,
        UPLOAD_FOLDER=os.path.join(TMP_DIR, "uploads"),
    )

    # Das Login-Limit würde nach fünf Anmeldungen zuschlagen und alle
    # folgenden Tests scheitern lassen. test_security.py schaltet es für
    # seine eigene Prüfung gezielt wieder ein.
    limiter.enabled = False

    # Jeder Test bekommt eine frische Datenbank (siehe database unten), und
    # SQLite wartet nach jedem Anlegen der Tabellen, bis die Platte das
    # Schreiben bestätigt. Bei einer Datenbank, die der Test gleich wieder
    # wegwirft, ist das nur Wartezeit: gut die Hälfte eines Laufs. Das gilt
    # nur für die Testdatenbank; die Anwendung schreibt weiter wie immer.
    from sqlalchemy import event

    from plattform.extensions import db

    with application.app_context():
        @event.listens_for(db.engine, "connect")
        def ohne_warten_auf_die_platte(verbindung, _eintrag):
            verbindung.execute("PRAGMA synchronous=OFF")
            verbindung.execute("PRAGMA journal_mode=MEMORY")

    return application


@pytest.fixture(autouse=True)
def database(flask_app):
    """Für jeden Test eine frische, leere Datenbank."""
    from plattform.extensions import db

    with flask_app.app_context():
        db.drop_all()
        db.create_all()
        yield db
        db.session.remove()

    shutil.rmtree(flask_app.config["UPLOAD_FOLDER"], ignore_errors=True)

    # Sicherungen, die eine Migration angelegt hat, dürfen nicht in den
    # nächsten Test hineinragen.
    from plattform import migrationen

    migrationen._backup_path = None
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
    from plattform.models import Challenge

    def _make(title="Test-Wettbewerb", active=True, **kwargs):
        challenge = Challenge(title=title, active=active,
                              paused=kwargs.pop("paused", False), **kwargs)
        database.session.add(challenge)
        database.session.commit()
        return challenge

    return _make


@pytest.fixture
def make_task(database):
    from plattform.models import Task

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
    from plattform.models import Team

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
