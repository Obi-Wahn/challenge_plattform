"""Wo die Datei einer Abgabe liegt - auch nach einem Update aus dem ZIP.

In der Datenbank steht nur der Teil unterhalb von uploads/. Bis v1.15.0 stand
dort der ganze Pfad, und nach einem Update in einen neuen Ordner (so steht es
in der README für ZIP-Installationen) zeigte er in den alten.
"""

import io
import os
import shutil
import sqlite3
import zipfile

import pytest

from tests.helpers import csrf_token


def abgeben(client, task, dateiname="loesung.sb3", inhalt=b"projekt"):
    return client.post(f"/submit/{task.id}", data={
        "csrf_token": csrf_token(client, "/login"),
        "file": (io.BytesIO(inhalt), dateiname),
    }, content_type="multipart/form-data")


@pytest.fixture
def abgabe(make_challenge, make_task, logged_in_team):
    """Eine echte Abgabe über die Oberfläche: (challenge, team, abgabe)."""
    from models import Submission

    challenge = make_challenge()
    task = make_task(challenge)
    client, team = logged_in_team(challenge)
    abgeben(client, task, inhalt=b"katze")
    return challenge, team, Submission.query.one()


@pytest.fixture
def umgezogen(flask_app, tmp_path, monkeypatch):
    """Wie ein Update aus dem ZIP: uploads/ in den neuen Ordner kopiert, der alte weg."""
    def _umziehen():
        alt = flask_app.config["UPLOAD_FOLDER"]
        neu = str(tmp_path / "plattform-neu" / "uploads")
        shutil.copytree(alt, neu)
        shutil.rmtree(alt)
        monkeypatch.setitem(flask_app.config, "UPLOAD_FOLDER", neu)
        return neu

    return _umziehen


class TestAblageort:
    def test_in_der_datenbank_steht_nur_der_teil_unter_uploads(self, abgabe):
        _challenge, team, eintrag = abgabe
        assert eintrag.filename == f"{team.id}/task_{eintrag.task_id}_loesung.sb3"
        assert not os.path.isabs(eintrag.filename)

    def test_der_ganze_pfad_kommt_von_der_laufenden_installation(self, abgabe, flask_app):
        _challenge, team, eintrag = abgabe
        assert eintrag.pfad == os.path.join(
            flask_app.config["UPLOAD_FOLDER"], str(team.id),
            f"task_{eintrag.task_id}_loesung.sb3")
        with open(eintrag.pfad, "rb") as datei:
            assert datei.read() == b"katze"

    def test_korrektur_mit_gleichem_namen_bleibt_unter_uploads(self, abgabe, flask_app,
                                                               database):
        from models import Task

        challenge, team, eintrag = abgabe
        alter_pfad = eintrag.pfad
        eintrag.resubmit_allowed = True
        database.session.commit()

        client = flask_app.test_client()
        with client.session_transaction() as sitzung:
            sitzung.update(team_id=team.id, team_uid=team.uid, team_name=team.name)
        abgeben(client, database.session.get(Task, eintrag.task_id), inhalt=b"katze 2")

        database.session.refresh(eintrag)
        assert not os.path.isabs(eintrag.filename)
        assert eintrag.filename.startswith(f"{team.id}/")
        with open(eintrag.pfad, "rb") as datei:
            assert datei.read() == b"katze 2"
        assert not os.path.exists(alter_pfad)

    def test_eingelesene_sicherung_steht_unter_uploads(self, abgabe, admin):
        from models import Challenge, Submission

        challenge, _team, _eintrag = abgabe
        zip_daten = admin.get(f"/admin/challenges/{challenge.id}/sichern").data
        admin.post("/admin/challenges/einlesen", data={
            "csrf_token": csrf_token(admin, "/admin/challenges/new"),
            "file": (io.BytesIO(zip_daten), "Sicherung.zip"),
        }, content_type="multipart/form-data")

        neu = Challenge.query.filter(Challenge.id != challenge.id).one()
        eingelesen = Submission.query.filter(Submission.task.has(challenge_id=neu.id)).one()
        assert not os.path.isabs(eingelesen.filename)
        with open(eingelesen.pfad, "rb") as datei:
            assert datei.read() == b"katze"


class TestNachDemUmzug:
    """Alles, was eine Abgabe braucht, findet sie im neuen Ordner."""

    def test_download(self, abgabe, admin, umgezogen):
        _challenge, _team, eintrag = abgabe
        umgezogen()
        antwort = admin.get(f"/admin/download/{eintrag.id}")
        assert antwort.status_code == 200
        assert antwort.data == b"katze"

    def test_bewertungsseite_kennt_die_groesse(self, abgabe, admin, umgezogen):
        umgezogen()
        seite = admin.get("/admin/submissions").get_data(as_text=True)
        assert "5 Byte" in seite

    def test_sicherung_enthaelt_die_datei(self, abgabe, admin, umgezogen):
        challenge, _team, _eintrag = abgabe
        umgezogen()
        zf = zipfile.ZipFile(io.BytesIO(admin.get(f"/admin/challenges/{challenge.id}/sichern").data))
        dateien = [name for name in zf.namelist() if name.startswith("abgaben/")]
        assert len(dateien) == 1
        assert zf.read(dateien[0]) == b"katze"

    def test_aufraeumen_loescht_die_kopie_im_neuen_ordner(self, abgabe, umgezogen):
        # Vorher löschte das Aufräumen im alten Pfad, und die Programme der
        # Kinder blieben im neuen Ordner liegen.
        from datenschutz import wettbewerb_aufraeumen

        challenge, team, eintrag = abgabe
        neu = umgezogen()
        datei = os.path.join(neu, str(team.id), os.path.basename(eintrag.filename))
        assert os.path.exists(datei)

        wettbewerb_aufraeumen(challenge)

        assert not os.path.exists(datei)


class TestUmstellungBeimStart:
    @pytest.mark.parametrize("gespeichert, erwartet", [
        ("/home/lehrer/plattform-1.14/uploads/3/task_5_katze.sb3", "3/task_5_katze.sb3"),
        ("C:\\Users\\Lehrer\\Desktop\\plattform\\uploads\\12\\task_1_x.py", "12/task_1_x.py"),
        ("/srv/plattform/uploads/7/task_2_fehlt.sb3", "7/task_2_fehlt.sb3"),
    ])
    def test_ganzer_pfad_wird_zum_ablageort(self, gespeichert, erwartet):
        from app import gedeuteter_ablageort
        assert gedeuteter_ablageort(gespeichert) == erwartet

    @pytest.mark.parametrize("gespeichert", [
        "3/task_5_katze.sb3",          # schon umgestellt
        "x.sb3",                        # kein Ordner davor
        "/irgendwo/ohne/team.sb3",      # kein Teamordner
        "",
    ])
    def test_anderes_bleibt_unangetastet(self, gespeichert):
        from app import gedeuteter_ablageort
        assert gedeuteter_ablageort(gespeichert) is None

    def test_alte_abgaben_werden_umgestellt_und_gefunden(
            self, make_challenge, make_task, make_team, database, flask_app):
        import app as anwendung
        from models import Submission

        challenge = make_challenge()
        task = make_task(challenge)
        team = make_team(challenge)
        ordner = os.path.join(flask_app.config["UPLOAD_FOLDER"], str(team.id))
        os.makedirs(ordner, exist_ok=True)
        with open(os.path.join(ordner, f"task_{task.id}_alt.sb3"), "wb") as datei:
            datei.write(b"alt")
        # So stand es bis v1.15.0 da: der Pfad der alten Installation.
        database.session.add(Submission(
            team_id=team.id, task_id=task.id,
            filename=f"/home/lehrer/plattform-1.14/uploads/{team.id}/task_{task.id}_alt.sb3"))
        database.session.commit()

        anwendung.ensure_relative_upload_paths()
        database.session.expire_all()

        eintrag = Submission.query.one()
        assert eintrag.filename == f"{team.id}/task_{task.id}_alt.sb3"
        with open(eintrag.pfad, "rb") as datei:
            assert datei.read() == b"alt"

    def test_vorher_entsteht_eine_kopie_der_datenbank(
            self, make_challenge, make_task, make_team, database):
        import app as anwendung
        from models import Submission

        challenge = make_challenge()
        task = make_task(challenge)
        team = make_team(challenge)
        database.session.add(Submission(team_id=team.id, task_id=task.id,
                                        filename=f"/alt/uploads/{team.id}/task_1_a.sb3"))
        database.session.commit()

        anwendung.ensure_relative_upload_paths()

        kopie = anwendung._backup_path
        assert kopie and "-vor-pfade-" in kopie
        with sqlite3.connect(kopie) as verbindung:
            alt = verbindung.execute("SELECT filename FROM submissions").fetchone()[0]
        assert alt == f"/alt/uploads/{team.id}/task_1_a.sb3"

    def test_ohne_alte_pfade_keine_kopie(self, abgabe):
        import app as anwendung

        anwendung.ensure_relative_upload_paths()
        assert anwendung._backup_path is None
