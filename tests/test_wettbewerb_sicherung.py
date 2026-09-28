"""Einen ganzen Wettbewerb sichern und wieder einlesen."""

import io
import json
import os
import zipfile
from datetime import datetime

import pytest

from models import Challenge, Submission, Task, Team
from tests.helpers import csrf_token


@pytest.fixture
def wettbewerb(flask_app, make_challenge, make_task, make_team, database):
    """Ein Wettbewerb mit zwei Aufgaben, zwei Teams und drei Abgaben."""
    challenge = make_challenge(title="Scratch-Cup", tagline="Klasse 6",
                               start_time=datetime(2026, 9, 1, 8, 0),
                               end_time=datetime(2026, 9, 1, 9, 30))
    labyrinth = make_task(challenge, title="Labyrinth", max_points=10,
                          hint="Nimm eine Schleife", difficulty="mittel")
    labyrinth.hint_visible = True
    quiz = make_task(challenge, title="Quiz", max_points=5, allowed_extension=".py")

    blitz = make_team(challenge, name="Team Blitz")
    blitz.member_names = "Anna Beispiel\nBen Muster"
    blitz.members_approved = True
    donner = make_team(challenge, name="Team Donner")

    ordner = flask_app.config["UPLOAD_FOLDER"]

    def abgabe(team, task, inhalt, name, **werte):
        pfad = os.path.join(ordner, str(team.id), f"task_{task.id}_{name}")
        os.makedirs(os.path.dirname(pfad), exist_ok=True)
        with open(pfad, "wb") as f:
            f.write(inhalt)
        database.session.add(Submission(team_id=team.id, task_id=task.id,
                                        filename=pfad, **werte))

    abgabe(blitz, labyrinth, b"scratch-blitz", "labyrinth.sb3", points=8,
           feedback="Schön gelöst", timestamp=datetime(2026, 9, 1, 8, 40))
    abgabe(blitz, quiz, b"print('hallo')", "quiz.py", points=None)
    abgabe(donner, labyrinth, b"scratch-donner", "labyrinth.sb3", points=6,
           resubmit_allowed=True)
    database.session.commit()
    return challenge


def sichern(admin, challenge, namen=False):
    adresse = f"/admin/challenges/{challenge.id}/sichern"
    if namen:
        adresse += "?namen=mit"
    return admin.get(adresse)


def zip_lesen(antwort):
    zf = zipfile.ZipFile(io.BytesIO(antwort.data))
    return zf, json.loads(zf.read("wettbewerb.json"))


def einlesen(admin, inhalt, name="Sicherung.zip"):
    return admin.post("/admin/challenges/einlesen", data={
        "csrf_token": csrf_token(admin, "/admin/challenges/new"),
        "file": (io.BytesIO(inhalt), name),
    }, content_type="multipart/form-data", follow_redirects=True)


def zip_aus(daten, dateien=None):
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w") as zf:
        zf.writestr("wettbewerb.json", json.dumps(daten))
        for name, inhalt in (dateien or {}).items():
            zf.writestr(name, inhalt)
    return puffer.getvalue()


def rahmen(**werte):
    daten = {"format": "coding-wettbewerb-sicherung", "version": 1,
             "wettbewerb": {"titel": "Aus der Datei"},
             "aufgaben": [], "teams": [], "abgaben": []}
    daten.update(werte)
    return daten


class TestSichern:

    def test_liefert_eine_zip_mit_allem(self, admin, wettbewerb):
        antwort = sichern(admin, wettbewerb)

        assert antwort.status_code == 200
        assert antwort.mimetype == "application/zip"
        assert "Wettbewerb_Scratch-Cup_" in antwort.headers["Content-Disposition"]

        zf, daten = zip_lesen(antwort)
        assert daten["wettbewerb"]["titel"] == "Scratch-Cup"
        assert daten["wettbewerb"]["untertitel"] == "Klasse 6"
        assert daten["wettbewerb"]["start"] == "2026-09-01T08:00:00"
        assert [a["titel"] for a in daten["aufgaben"]] == ["Labyrinth", "Quiz"]
        assert daten["aufgaben"][0]["hinweis_sichtbar"] is True
        assert daten["aufgaben"][0]["schwierigkeit"] == "mittel"
        assert [t["name"] for t in daten["teams"]] == ["Team Blitz", "Team Donner"]
        assert len(daten["abgaben"]) == 3

        erste = daten["abgaben"][0]
        assert erste["punkte"] == 8
        assert erste["feedback"] == "Schön gelöst"
        assert zf.read(erste["datei"]) == b"scratch-blitz"

    def test_ohne_passwoerter_und_kennzeichen(self, admin, wettbewerb):
        """Was sich zum Anmelden eignet, gehört nicht in eine Datei, die
        weitergegeben wird."""
        team = Team.query.filter_by(name="Team Blitz").one()

        text = zip_lesen(sichern(admin, wettbewerb, namen=True))[0] \
            .read("wettbewerb.json").decode("utf-8")

        assert team.password_hash not in text
        assert team.uid not in text
        assert "passwort" not in text.lower()

    def test_namen_nur_wenn_gewaehlt(self, admin, wettbewerb):
        _, ohne = zip_lesen(sichern(admin, wettbewerb))
        _, mit = zip_lesen(sichern(admin, wettbewerb, namen=True))

        assert ohne["mit_namen"] is False
        assert "Anna" not in json.dumps(ohne)
        assert mit["mit_namen"] is True
        assert mit["teams"][0]["namen"] == ["Anna Beispiel", "Ben Muster"]
        assert mit["teams"][0]["namen_freigegeben"] is True

    def test_die_seite_bietet_namen_abgewaehlt_an(self, admin, wettbewerb):
        html = admin.get(f"/admin/wettbewerb/{wettbewerb.id}").get_data(as_text=True)

        assert "Wettbewerb sichern" in html
        assert 'name="namen" value="mit"' in html
        assert 'value="mit" id="sichern-namen" checked' not in html

    def test_fehlende_datei_bricht_nicht_ab(self, admin, wettbewerb):
        submission = Submission.query.filter(Submission.points == 6).one()
        os.remove(submission.filename)

        zf, daten = zip_lesen(sichern(admin, wettbewerb))

        ohne = [a for a in daten["abgaben"] if a["datei"] is None]
        assert len(ohne) == 1
        assert ohne[0]["punkte"] == 6

    def test_steht_im_protokoll(self, admin, wettbewerb, caplog):
        with caplog.at_level("INFO"):
            sichern(admin, wettbewerb)

        assert "Wettbewerb gesichert: „Scratch-Cup“" in caplog.text
        assert "ohne Namen" in caplog.text

    def test_nur_fuer_die_lehrkraft(self, client, wettbewerb):
        antwort = client.get(f"/admin/challenges/{wettbewerb.id}/sichern")

        assert antwort.status_code == 302
        assert "/admin/login" in antwort.headers["Location"]


class TestHinUndZurueck:

    def test_alles_kommt_wieder(self, admin, wettbewerb, flask_app):
        inhalt = sichern(admin, wettbewerb, namen=True).data

        antwort = einlesen(admin, inhalt)

        assert antwort.status_code == 200
        assert "eingelesen" in antwort.get_data(as_text=True)

        neu = Challenge.query.filter(Challenge.id != wettbewerb.id).one()
        assert neu.title == "Scratch-Cup"
        assert neu.tagline == "Klasse 6"
        assert neu.start_time == datetime(2026, 9, 1, 8, 0)
        assert neu.active is False

        aufgaben = Task.query.filter_by(challenge_id=neu.id).order_by(Task.id).all()
        assert [(a.title, a.max_points, a.hint_visible) for a in aufgaben] == \
            [("Labyrinth", 10, True), ("Quiz", 5, False)]

        blitz = Team.query.filter_by(challenge_id=neu.id, name="Team Blitz").one()
        assert blitz.member_list == ["Anna Beispiel", "Ben Muster"]
        assert blitz.members_approved is True
        assert blitz.password_hash is None

        abgabe = Submission.query.filter_by(team_id=blitz.id,
                                            task_id=aufgaben[0].id).one()
        assert abgabe.points == 8
        assert abgabe.feedback == "Schön gelöst"
        assert abgabe.timestamp == datetime(2026, 9, 1, 8, 40)
        assert abgabe.filename.startswith(
            os.path.join(flask_app.config["UPLOAD_FOLDER"], str(blitz.id)))
        with open(abgabe.filename, "rb") as f:
            assert f.read() == b"scratch-blitz"

        donner = Team.query.filter_by(challenge_id=neu.id, name="Team Donner").one()
        assert donner.submissions[0].resubmit_allowed is True

    def test_der_alte_bleibt_unberuehrt(self, admin, wettbewerb, database):
        einlesen(admin, sichern(admin, wettbewerb).data)

        assert database.session.get(Challenge, wettbewerb.id).active is True
        assert Challenge.current().id == wettbewerb.id
        assert Submission.query.count() == 6

    def test_ohne_namen_gesichert_kommen_keine(self, admin, wettbewerb):
        einlesen(admin, sichern(admin, wettbewerb).data)

        neu = Challenge.query.filter(Challenge.id != wettbewerb.id).one()
        blitz = Team.query.filter_by(challenge_id=neu.id, name="Team Blitz").one()
        assert blitz.member_list == []
        assert blitz.members_approved is False

    def test_urkunden_lassen_sich_drucken(self, admin, wettbewerb):
        einlesen(admin, sichern(admin, wettbewerb, namen=True).data)
        neu = Challenge.query.filter(Challenge.id != wettbewerb.id).one()

        antwort = admin.get(f"/admin/urkunden.pdf?wettbewerb={neu.id}")

        assert antwort.status_code == 200
        assert antwort.data.startswith(b"%PDF")

    def test_steht_im_protokoll(self, admin, wettbewerb, caplog):
        inhalt = sichern(admin, wettbewerb).data
        with caplog.at_level("INFO"):
            einlesen(admin, inhalt)

        assert "Wettbewerb eingelesen: „Scratch-Cup“" in caplog.text


class TestEinlesenPrueft:

    def test_keine_zip(self, admin):
        antwort = einlesen(admin, b"kein zip")

        assert "keine ZIP-Datei" in antwort.get_data(as_text=True)
        assert Challenge.query.count() == 0

    def test_zip_ohne_json(self, admin):
        puffer = io.BytesIO()
        with zipfile.ZipFile(puffer, "w") as zf:
            zf.writestr("irgendwas.txt", "hallo")

        antwort = einlesen(admin, puffer.getvalue())

        assert "fehlt die Datei wettbewerb.json" in antwort.get_data(as_text=True)

    def test_fremdes_format(self, admin):
        antwort = einlesen(admin, zip_aus({"format": "etwas-anderes"}))

        assert "keine Sicherung eines Wettbewerbs" in antwort.get_data(as_text=True)
        assert Challenge.query.count() == 0

    def test_neuere_fassung(self, admin):
        antwort = einlesen(admin, zip_aus(rahmen(version=99)))

        assert "neueren Fassung" in antwort.get_data(as_text=True)

    def test_ohne_namen_des_wettbewerbs(self, admin):
        antwort = einlesen(admin, zip_aus(rahmen(wettbewerb={"titel": "  "})))

        assert "keinen Namen" in antwort.get_data(as_text=True)
        assert Challenge.query.count() == 0

    def test_pfad_aus_der_zip_wird_nie_ziel(self, admin, flask_app, tmp_path):
        """Ein Eintrag „../../boese.py“ landet im Ordner des Teams, nicht
        daneben."""
        daten = rahmen(
            aufgaben=[{"nr": 1, "titel": "A", "punkte": 5, "dateiformat": ".py"}],
            teams=[{"nr": 1, "name": "Team"}],
            abgaben=[{"team": 1, "aufgabe": 1, "datei": "../../boese.py"}],
        )
        einlesen(admin, zip_aus(daten, {"../../boese.py": b"x"}))

        abgabe = Submission.query.one()
        ordner = os.path.join(flask_app.config["UPLOAD_FOLDER"], str(abgabe.team_id))
        assert os.path.dirname(abgabe.filename) == ordner
        assert os.path.basename(abgabe.filename) == f"task_{abgabe.task_id}_boese.py"
        assert not os.path.exists(os.path.join(flask_app.config["UPLOAD_FOLDER"],
                                               "..", "boese.py"))

    def test_punkte_ueber_dem_hoechstwert_werden_gekappt(self, admin):
        daten = rahmen(
            aufgaben=[{"nr": 1, "titel": "A", "punkte": 5, "dateiformat": ".py"}],
            teams=[{"nr": 1, "name": "Team"}],
            abgaben=[{"team": 1, "aufgabe": 1, "datei": None, "punkte": 500}],
        )
        einlesen(admin, zip_aus(daten))

        assert Submission.query.one().points == 5

    def test_abgabe_ohne_datei_behaelt_punkte(self, admin):
        daten = rahmen(
            aufgaben=[{"nr": 1, "titel": "A", "punkte": 5, "dateiformat": ".py"}],
            teams=[{"nr": 1, "name": "Team"}],
            abgaben=[{"team": 1, "aufgabe": 1, "datei": "fehlt.py", "punkte": 3}],
        )
        antwort = einlesen(admin, zip_aus(daten))

        assert Submission.query.one().points == 3
        assert "fehlte die Datei" in antwort.get_data(as_text=True)

    def test_doppelte_teamnamen_werden_uebersprungen(self, admin):
        daten = rahmen(teams=[{"nr": 1, "name": "Team"}, {"nr": 2, "name": "Team"}])

        einlesen(admin, zip_aus(daten))

        assert Team.query.count() == 1

    def test_nur_fuer_die_lehrkraft(self, client):
        antwort = client.post("/admin/challenges/einlesen")

        assert antwort.status_code in (302, 400)
        assert Challenge.query.count() == 0

    def test_ohne_datei(self, admin):
        antwort = admin.post("/admin/challenges/einlesen", data={
            "csrf_token": csrf_token(admin, "/admin/challenges/new"),
        }, follow_redirects=True)

        assert "keine Datei ausgewählt" in antwort.get_data(as_text=True)

    def test_groesser_als_16_mb_geht_fuer_die_lehrkraft(self, admin, flask_app):
        """Die Grenze für einzelne Abgaben gilt hier nicht."""
        groesse = flask_app.config["MAX_CONTENT_LENGTH"] + 1024
        daten = rahmen(
            aufgaben=[{"nr": 1, "titel": "A", "punkte": 5, "dateiformat": ".sb3"}],
            teams=[{"nr": 1, "name": "Team"}],
            abgaben=[{"team": 1, "aufgabe": 1, "datei": "abgaben/a.sb3"}],
        )
        puffer = io.BytesIO()
        with zipfile.ZipFile(puffer, "w", compression=zipfile.ZIP_STORED) as zf:
            zf.writestr("wettbewerb.json", json.dumps(daten))
            zf.writestr("abgaben/a.sb3", os.urandom(8 * 1024 * 1024))
            zf.writestr("abgaben/b.sb3", os.urandom(groesse - 8 * 1024 * 1024))

        antwort = einlesen(admin, puffer.getvalue())

        assert antwort.status_code == 200
        assert Submission.query.count() == 1

    def test_ohne_anmeldung_bleibt_es_bei_16_mb(self, client, flask_app):
        groesse = flask_app.config["MAX_CONTENT_LENGTH"] + 1024

        antwort = client.post("/admin/challenges/einlesen", data={
            "file": (io.BytesIO(b"x" * groesse), "gross.zip"),
        }, content_type="multipart/form-data")

        assert antwort.status_code == 413

    def test_formular_steht_bei_neuer_wettbewerb(self, admin):
        html = admin.get("/admin/challenges/new").get_data(as_text=True)

        assert "Oder aus einer Sicherung einlesen" in html
        assert 'action="/admin/challenges/einlesen"' in html
