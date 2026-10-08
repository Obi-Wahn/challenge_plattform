"""Teams korrigieren ihre Abgabe selbst, ohne Freigabe der Lehrkraft.

Je Wettbewerb schaltbar und von Anfang an eingeschaltet. Vorher musste die
Lehrkraft jede Korrektur einzeln freigeben - und die Karte mit dem Knopf dazu
erst wiederfinden, denn nach dem Bewerten rückt sie in der Liste nach unten.

Eine Korrektur macht dasselbe wie eine freigegebene: Die neue Datei ersetzt
die alte, Punkte und Feedback fallen weg, und die Abgabe steht wieder als
offen in der Bewertungsliste.
"""

import io
import os
from datetime import datetime, timedelta

import pytest

from tests.helpers import csrf_token


def abgeben(client, task, dateiname="loesung.sb3", inhalt=b"projekt"):
    return client.post(f"/submit/{task.id}", data={
        "csrf_token": csrf_token(client, "/login"),
        "file": (io.BytesIO(inhalt), dateiname),
    }, content_type="multipart/form-data")


def inhalt_der_abgabe():
    from models import Submission

    with open(Submission.query.one().pfad, "rb") as datei:
        return datei.read()


def frisch(challenge):
    from extensions import db
    from models import Challenge

    db.session.expire_all()
    return db.session.get(Challenge, challenge.id)


class TestStandard:
    def test_ein_neuer_wettbewerb_hat_es_an(self, make_challenge):
        assert make_challenge().self_correction is True

    def test_ein_im_formular_angelegter_auch(self, admin):
        from models import Challenge

        admin.post("/admin/challenges/new", data={
            "csrf_token": csrf_token(admin, "/admin/challenges/new"),
            "title": "Herbst-AG",
        })

        assert Challenge.query.filter_by(title="Herbst-AG").one().self_correction is True


class TestKorrigieren:
    def test_ohne_freigabe_ersetzt_die_neue_datei_die_alte(
            self, make_challenge, make_task, logged_in_team):
        challenge = make_challenge()
        task = make_task(challenge)
        client, _team = logged_in_team(challenge)

        abgeben(client, task, inhalt=b"erster versuch")
        assert abgeben(client, task, inhalt=b"zweiter versuch").status_code == 302

        assert inhalt_der_abgabe() == b"zweiter versuch"

    def test_es_geht_beliebig_oft(self, make_challenge, make_task, logged_in_team):
        challenge = make_challenge()
        task = make_task(challenge)
        client, _team = logged_in_team(challenge)

        for versuch in (b"eins", b"zwei", b"drei"):
            abgeben(client, task, inhalt=versuch)

        assert inhalt_der_abgabe() == b"drei"

    def test_eine_bewertete_abgabe_wird_wieder_offen(
            self, make_challenge, make_task, logged_in_team, database):
        """Tobias' Wahl: Kein Team behält Punkte für eine Datei, die noch
        niemand angesehen hat."""
        from models import Submission

        challenge = make_challenge()
        task = make_task(challenge)
        client, _team = logged_in_team(challenge)
        abgeben(client, task)
        abgabe = Submission.query.one()
        abgabe.points = 7
        abgabe.feedback = "Fast fertig"
        database.session.commit()

        abgeben(client, task, inhalt=b"verbessert")

        database.session.refresh(abgabe)
        assert abgabe.points is None
        assert abgabe.feedback is None

    def test_die_alte_datei_bleibt_nicht_liegen(
            self, flask_app, make_challenge, make_task, logged_in_team):
        challenge = make_challenge()
        task = make_task(challenge)
        client, team = logged_in_team(challenge)

        abgeben(client, task, dateiname="alt.sb3")
        abgeben(client, task, dateiname="neu.sb3")

        ordner = os.path.join(flask_app.config["UPLOAD_FOLDER"], str(team.id))
        assert os.listdir(ordner) == [f"task_{task.id}_neu.sb3"]

    def test_nach_dem_ende_nicht_mehr(self, make_challenge, make_task, logged_in_team,
                                      database):
        challenge = make_challenge(
            start_time=datetime.now() - timedelta(minutes=30),
            end_time=datetime.now() + timedelta(minutes=30),
        )
        task = make_task(challenge)
        client, _team = logged_in_team(challenge)
        abgeben(client, task, inhalt=b"erster versuch")

        challenge.end_time = datetime.now() - timedelta(minutes=1)
        database.session.commit()
        abgeben(client, task, inhalt=b"zu spaet")

        assert inhalt_der_abgabe() == b"erster versuch"

    def test_ausgeschaltet_braucht_es_wieder_die_freigabe(
            self, make_challenge, make_task, logged_in_team):
        challenge = make_challenge(self_correction=False)
        task = make_task(challenge)
        client, _team = logged_in_team(challenge)

        abgeben(client, task, inhalt=b"erster versuch")
        abgeben(client, task, inhalt=b"zweiter versuch")

        assert inhalt_der_abgabe() == b"erster versuch"


class TestTeamseite:
    def test_unter_einer_abgabe_steht_das_formular(
            self, make_challenge, make_task, logged_in_team):
        challenge = make_challenge()
        task = make_task(challenge)
        client, _team = logged_in_team(challenge)
        abgeben(client, task)

        html = client.get("/challenge").get_data(as_text=True)

        assert "🔁 Korrektur abgeben" in html
        assert "Eine neue Datei ersetzt eure Abgabe" in html
        # Noch ohne Punkte gibt es nichts, was wegfallen könnte.
        assert "Die Punkte fallen dann weg" not in html

    def test_bei_einer_bewerteten_sagt_sie_was_mit_den_punkten_passiert(
            self, make_challenge, make_task, logged_in_team, database):
        from models import Submission

        challenge = make_challenge()
        task = make_task(challenge)
        client, _team = logged_in_team(challenge)
        abgeben(client, task)
        Submission.query.one().points = 5
        database.session.commit()

        html = client.get("/challenge").get_data(as_text=True)

        assert "Die Punkte fallen dann weg" in html

    def test_ausgeschaltet_gibt_es_kein_formular(
            self, make_challenge, make_task, logged_in_team):
        challenge = make_challenge(self_correction=False)
        task = make_task(challenge)
        client, _team = logged_in_team(challenge)
        abgeben(client, task)

        html = client.get("/challenge").get_data(as_text=True)

        assert "🔁 Korrektur abgeben" not in html

    def test_nach_dem_ende_kein_ausgegrautes_formular(
            self, make_challenge, make_task, logged_in_team, database):
        challenge = make_challenge(
            start_time=datetime.now() - timedelta(minutes=30),
            end_time=datetime.now() + timedelta(minutes=30),
        )
        task = make_task(challenge)
        client, _team = logged_in_team(challenge)
        abgeben(client, task)
        challenge.end_time = datetime.now() - timedelta(minutes=1)
        database.session.commit()

        html = client.get("/challenge").get_data(as_text=True)

        assert "🔁 Korrektur abgeben" not in html

    def test_die_offene_seite_merkt_das_umschalten(
            self, make_challenge, logged_in_team, database):
        challenge = make_challenge()
        client, _team = logged_in_team(challenge)
        vorher = client.get("/challenge/stand").get_json()["stand"]

        challenge.self_correction = False
        database.session.commit()

        assert client.get("/challenge/stand").get_json()["stand"] != vorher


class TestBewertungsseite:
    @pytest.mark.parametrize("an, knopf_da", [(True, False), (False, True)])
    def test_der_freigabe_knopf_nur_wenn_ausgeschaltet(
            self, admin, make_challenge, make_task, logged_in_team, an, knopf_da):
        challenge = make_challenge(self_correction=an)
        task = make_task(challenge)
        client, _team = logged_in_team(challenge)
        abgeben(client, task)

        html = admin.get("/admin/submissions").get_data(as_text=True)

        assert ("Erneut abgeben erlauben" in html) is knopf_da
        assert "Abgabe vollständig löschen" in html


class TestSchalter:
    def formular(self, challenge, **mehr):
        daten = {
            "csrf_token": None,
            "title": challenge.title,
            "tagline": "",
        }
        daten.update(mehr)
        return daten

    def speichern(self, admin, challenge, **mehr):
        daten = self.formular(challenge, **mehr)
        daten["csrf_token"] = csrf_token(admin, f"/admin/challenges/{challenge.id}/edit")
        return admin.post(f"/admin/challenges/{challenge.id}/edit", data=daten)

    def test_das_formular_zeigt_ihn_angehakt(self, admin, make_challenge):
        challenge = make_challenge()
        html = admin.get(f"/admin/challenges/{challenge.id}/edit").get_data(as_text=True)

        assert "Teams dürfen ihre Abgabe selbst korrigieren" in html
        assert 'name="self_correction"\n        id="self_correction" checked' in html

    def test_ausschalten(self, admin, make_challenge):
        challenge = make_challenge()
        self.speichern(admin, challenge)
        assert frisch(challenge).self_correction is False

    def test_einschalten(self, admin, make_challenge):
        challenge = make_challenge(self_correction=False)
        self.speichern(admin, challenge, self_correction="on")
        assert frisch(challenge).self_correction is True


class TestSicherung:
    def test_der_schalter_reist_mit(self, flask_app, make_challenge):
        import json
        import zipfile

        from wettbewerb_sicherung import sicherung_bauen, sicherung_einlesen

        challenge = make_challenge(self_correction=False)

        datei, _zahlen = sicherung_bauen(challenge, mit_namen=False)
        with datei:
            datei.seek(0)
            with zipfile.ZipFile(datei) as zf:
                inhalt = "".join(zf.read(n).decode("utf-8")
                                 for n in zf.namelist() if n.endswith(".json"))
            assert json.loads(inhalt)["wettbewerb"]["korrektur_ohne_freigabe"] is False

            datei.seek(0)
            neu, _zahlen, _hinweise = sicherung_einlesen(
                datei, flask_app.config["UPLOAD_FOLDER"])
        assert neu.self_correction is False

    def test_eine_aeltere_sicherung_bekommt_den_standard(self, flask_app):
        """Das Beispiel stammt aus der Zeit vor dem Schalter."""
        from wettbewerb_sicherung import sicherung_einlesen

        beispiel = os.path.join(os.path.dirname(__file__), "..", "beispiele",
                                "scratch-wettbewerb.zip")
        with open(beispiel, "rb") as datei:
            neu, _zahlen, _hinweise = sicherung_einlesen(
                io.BytesIO(datei.read()), flask_app.config["UPLOAD_FOLDER"])

        assert neu.self_correction is True
