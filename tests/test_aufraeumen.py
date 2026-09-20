"""Hochgeladene Dateien verschwinden mit ihrer Abgabe.

Bis dahin blieben die Dateien der Schülerinnen und Schüler auf der Platte
liegen, auch wenn Abgabe, Team, Aufgabe oder der ganze Wettbewerb gelöscht
waren. Wer nach dem Wettbewerb aufräumt, darf sich darauf verlassen, dass
"gelöscht" auch gelöscht heißt.
"""

import os
from datetime import datetime, timedelta

import pytest

from tests.helpers import csrf_token


def abgabe_mit_datei(flask_app, database, challenge, team, task, inhalt=b"projektdatei"):
    """Legt eine Abgabe samt Datei an, so wie es der Upload tut."""
    from models import Submission

    ordner = os.path.join(flask_app.config["UPLOAD_FOLDER"], str(team.id))
    os.makedirs(ordner, exist_ok=True)
    pfad = os.path.join(ordner, f"task_{task.id}_loesung.sb3")
    with open(pfad, "wb") as datei:
        datei.write(inhalt)

    abgabe = Submission(team_id=team.id, task_id=task.id, filename=pfad)
    database.session.add(abgabe)
    database.session.commit()
    return abgabe, pfad


@pytest.fixture
def wettbewerb_mit_abgabe(flask_app, database, make_challenge, make_team, make_task):
    challenge = make_challenge()
    team = make_team(challenge, name="Team A")
    task = make_task(challenge)
    abgabe, pfad = abgabe_mit_datei(flask_app, database, challenge, team, task)
    assert os.path.exists(pfad)
    return challenge, team, task, abgabe, pfad


class TestDieVierLoeschwege:
    """Eine Abgabe kann auf vier Wegen verschwinden - die Datei muss mit."""

    def test_abgabe_loeschen(self, admin, wettbewerb_mit_abgabe):
        _challenge, _team, _task, abgabe, pfad = wettbewerb_mit_abgabe

        admin.post(f"/admin/reset/{abgabe.id}", data={
            "csrf_token": csrf_token(admin, "/admin/submissions"),
        })

        assert not os.path.exists(pfad)

    def test_team_loeschen(self, admin, wettbewerb_mit_abgabe):
        _challenge, team, _task, _abgabe, pfad = wettbewerb_mit_abgabe

        admin.post(f"/admin/team/delete/{team.id}", data={
            "csrf_token": csrf_token(admin, "/admin/teams"),
        })

        assert not os.path.exists(pfad)

    def test_aufgabe_loeschen(self, admin, wettbewerb_mit_abgabe):
        challenge, _team, task, _abgabe, pfad = wettbewerb_mit_abgabe

        admin.post(f"/admin/tasks/{task.id}/delete", data={
            "csrf_token": csrf_token(admin, f"/admin/challenges/{challenge.id}/tasks"),
        })

        assert not os.path.exists(pfad)

    def test_wettbewerb_loeschen(self, admin, wettbewerb_mit_abgabe):
        challenge, _team, _task, _abgabe, pfad = wettbewerb_mit_abgabe

        admin.post(f"/admin/challenges/{challenge.id}/delete", data={
            "csrf_token": csrf_token(admin, f"/admin/wettbewerb/{challenge.id}"),
        })

        assert not os.path.exists(pfad)


class TestNurDasEigene:
    def test_fremde_dateien_bleiben(self, flask_app, admin, database,
                                    make_challenge, make_team, make_task):
        """Das Löschen eines Teams darf nicht die Dateien anderer mitnehmen."""
        challenge = make_challenge()
        task = make_task(challenge)
        team_a = make_team(challenge, name="Team A")
        team_b = make_team(challenge, name="Team B")

        _, pfad_a = abgabe_mit_datei(flask_app, database, challenge, team_a, task)
        _, pfad_b = abgabe_mit_datei(flask_app, database, challenge, team_b, task)

        admin.post(f"/admin/team/delete/{team_a.id}", data={
            "csrf_token": csrf_token(admin, "/admin/teams"),
        })

        assert not os.path.exists(pfad_a)
        assert os.path.exists(pfad_b), "die Datei des anderen Teams wurde mitgelöscht"

    def test_leerer_teamordner_verschwindet(self, flask_app, admin,
                                            wettbewerb_mit_abgabe):
        _challenge, team, _task, _abgabe, pfad = wettbewerb_mit_abgabe
        ordner = os.path.join(flask_app.config["UPLOAD_FOLDER"], str(team.id))
        assert os.path.isdir(ordner)

        admin.post(f"/admin/team/delete/{team.id}", data={
            "csrf_token": csrf_token(admin, "/admin/teams"),
        })

        assert not os.path.isdir(ordner)


class TestKeinVorschnellesLoeschen:
    def test_fehlende_datei_bricht_das_loeschen_nicht_ab(
            self, admin, wettbewerb_mit_abgabe, database):
        """Eine schon verschwundene Datei darf das Löschen nicht scheitern lassen."""
        from models import Submission

        _challenge, _team, _task, abgabe, pfad = wettbewerb_mit_abgabe
        abgabe_id = abgabe.id
        os.remove(pfad)

        antwort = admin.post(f"/admin/reset/{abgabe_id}", data={
            "csrf_token": csrf_token(admin, "/admin/submissions"),
        })

        assert antwort.status_code in (200, 302)
        assert database.session.get(Submission, abgabe_id) is None

    def test_ohne_abschluss_bleibt_die_datei(self, flask_app, database,
                                             make_challenge, make_team, make_task):
        """Wird die Änderung zurückgenommen, bleibt auch die Datei."""
        challenge = make_challenge()
        team = make_team(challenge, name="Team A")
        task = make_task(challenge)
        abgabe, pfad = abgabe_mit_datei(flask_app, database, challenge, team, task)

        database.session.delete(abgabe)
        database.session.flush() # der Haken merkt sich den Pfad
        database.session.rollback()

        assert os.path.exists(pfad), "die Datei wurde ohne Abschluss gelöscht"


class TestAbgabeUeberDieOberflaeche:
    """Derselbe Weg wie im Betrieb: Team lädt hoch, Admin löscht."""

    def test_hochgeladene_datei_wird_mitgeloescht(
            self, flask_app, admin, database, make_challenge, make_task,
            logged_in_team, upload):
        from models import Submission

        challenge = make_challenge(
            start_time=datetime.now() - timedelta(hours=1),
            end_time=datetime.now() + timedelta(hours=1),
        )
        task = make_task(challenge)
        client, _team = logged_in_team(challenge)

        client.post(f"/submit/{task.id}", data={
            "csrf_token": csrf_token(client, "/challenge"),
            "file": upload(),
        }, content_type="multipart/form-data")

        abgabe = Submission.query.first()
        assert abgabe is not None
        pfad = abgabe.filename
        assert os.path.exists(pfad)

        admin.post(f"/admin/reset/{abgabe.id}", data={
            "csrf_token": csrf_token(admin, "/admin/submissions"),
        })

        assert not os.path.exists(pfad)
