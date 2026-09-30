"""Durchsagen der Lehrkraft an alle Teams.

Je Wettbewerb an- und abschaltbar. Die Durchsage erscheint oben auf jeder
Teamseite - über die Standabfrage ohne Neuladen von Hand - und über der
Rangliste am Beamer. Es gibt immer nur eine, und ihr Text steht nicht im
Protokoll und nicht in der Sicherung.
"""

from datetime import datetime, timedelta

from tests.helpers import csrf_token


def frisch(challenge):
    from extensions import db
    from models import Challenge

    db.session.expire_all()
    return db.session.get(Challenge, challenge.id)


def posten(admin, pfad, daten=None):
    daten = dict(daten or {})
    daten["csrf_token"] = csrf_token(admin, "/admin/challenges/new")
    return admin.post(pfad, data=daten, follow_redirects=True)


def wettbewerb(make_challenge, **kwargs):
    kwargs.setdefault("announcements_enabled", True)
    return make_challenge(
        start_time=datetime.now() - timedelta(minutes=10),
        end_time=datetime.now() + timedelta(minutes=30),
        **kwargs,
    )


def senden(admin, challenge, text):
    return posten(admin, f"/admin/challenges/{challenge.id}/durchsage", {"text": text})


class TestSenden:
    def test_die_teams_sehen_sie(self, admin, make_challenge, logged_in_team):
        challenge = wettbewerb(make_challenge)
        client, _team = logged_in_team(challenge)

        senden(admin, challenge, "Noch 10 Minuten, bitte speichern")

        html = client.get("/challenge").get_data(as_text=True)
        assert "📢 Durchsage" in html
        assert "Noch 10 Minuten, bitte speichern" in html

    def test_der_beamer_zeigt_sie(self, admin, client, make_challenge):
        challenge = wettbewerb(make_challenge)
        senden(admin, challenge, "Alle mal herschauen")
        assert "Alle mal herschauen" in client.get("/scoreboard").get_data(as_text=True)

    def test_eine_neue_ersetzt_die_alte(self, admin, client, make_challenge):
        challenge = wettbewerb(make_challenge)
        senden(admin, challenge, "Erste Durchsage")
        senden(admin, challenge, "Zweite Durchsage")

        html = client.get("/scoreboard").get_data(as_text=True)
        assert "Zweite Durchsage" in html
        assert "Erste Durchsage" not in html

    def test_entfernen(self, admin, client, make_challenge):
        challenge = wettbewerb(make_challenge)
        senden(admin, challenge, "Gleich weg")
        posten(admin, f"/admin/challenges/{challenge.id}/durchsage/entfernen")

        assert "Gleich weg" not in client.get("/scoreboard").get_data(as_text=True)
        assert frisch(challenge).announcement_at is None

    def test_eine_leere_wird_abgewiesen(self, admin, make_challenge):
        challenge = wettbewerb(make_challenge)
        antwort = senden(admin, challenge, "   ")
        assert "Die Durchsage ist leer" in antwort.get_data(as_text=True)
        assert frisch(challenge).announcement is None

    def test_zu_lang_wird_gekuerzt(self, admin, make_challenge):
        challenge = wettbewerb(make_challenge)
        antwort = senden(admin, challenge, "x" * 300)
        assert len(frisch(challenge).announcement_text) == 200
        assert "gekürzt" in antwort.get_data(as_text=True)

    def test_html_wird_nicht_ausgefuehrt(self, admin, client, make_challenge):
        challenge = wettbewerb(make_challenge)
        senden(admin, challenge, "<script>alert(1)</script>")
        html = client.get("/scoreboard").get_data(as_text=True)
        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;" in html

    def test_nur_fuer_die_lehrkraft(self, client, make_challenge):
        challenge = wettbewerb(make_challenge)
        client.post(f"/admin/challenges/{challenge.id}/durchsage",
                    data={"csrf_token": csrf_token(client, "/login"), "text": "Hallo"})
        assert frisch(challenge).announcement is None


class TestAnUndAus:
    def formular(self, challenge, **mehr):
        daten = {
            "title": challenge.title,
            "tagline": "",
            "start_time": challenge.start_time.strftime("%Y-%m-%dT%H:%M"),
            "end_time": challenge.end_time.strftime("%Y-%m-%dT%H:%M"),
        }
        daten.update(mehr)
        return daten

    def test_ein_neuer_wettbewerb_hat_sie_aus(self, make_challenge):
        assert make_challenge().announcements_enabled is False

    def test_ausgeschaltet_gibt_es_kein_feld(self, admin, make_challenge):
        challenge = wettbewerb(make_challenge, announcements_enabled=False)
        html = admin.get(f"/admin/wettbewerb/{challenge.id}").get_data(as_text=True)
        assert "📢 Senden" not in html

    def test_eingeschaltet_gibt_es_das_feld(self, admin, make_challenge):
        challenge = wettbewerb(make_challenge)
        html = admin.get(f"/admin/wettbewerb/{challenge.id}").get_data(as_text=True)
        assert "📢 Senden" in html

    def test_ausgeschaltet_laesst_sich_nichts_senden(self, admin, make_challenge):
        challenge = wettbewerb(make_challenge, announcements_enabled=False)
        antwort = senden(admin, challenge, "Hallo")
        assert "ausgeschaltet" in antwort.get_data(as_text=True)
        assert frisch(challenge).announcement_text == ""

    def test_einschalten_im_formular(self, admin, make_challenge):
        challenge = wettbewerb(make_challenge, announcements_enabled=False)
        posten(admin, f"/admin/challenges/{challenge.id}/edit",
               self.formular(challenge, announcements_enabled="on"))
        assert frisch(challenge).announcements_enabled is True

    def test_ausschalten_entfernt_die_durchsage(self, admin, client, make_challenge):
        """Sonst tauchte sie beim nächsten Einschalten unverhofft wieder auf."""
        challenge = wettbewerb(make_challenge)
        senden(admin, challenge, "Alte Nachricht")
        posten(admin, f"/admin/challenges/{challenge.id}/edit", self.formular(challenge))

        challenge = frisch(challenge)
        assert challenge.announcements_enabled is False
        assert challenge.announcement_text == ""
        assert "Alte Nachricht" not in client.get("/scoreboard").get_data(as_text=True)


class TestKommtVonSelbstAn:
    def test_die_offene_teamseite_merkt_eine_neue_durchsage(self, admin, make_challenge,
                                                            logged_in_team):
        challenge = wettbewerb(make_challenge)
        client, _team = logged_in_team(challenge)
        vorher = client.get("/challenge/stand").get_json()["stand"]

        senden(admin, challenge, "Neu!")
        nachher = client.get("/challenge/stand").get_json()["stand"]
        assert nachher != vorher

        posten(admin, f"/admin/challenges/{challenge.id}/durchsage/entfernen")
        assert client.get("/challenge/stand").get_json()["stand"] != nachher


class TestDatensparsam:
    def test_das_protokoll_nennt_den_text_nicht(self, admin, flask_app, make_challenge):
        import os

        challenge = wettbewerb(make_challenge)
        senden(admin, challenge, "Lena bitte zur Tafel")
        posten(admin, f"/admin/challenges/{challenge.id}/durchsage/entfernen")

        pfad = os.path.join(os.environ["LOG_DIR"], "anwendung.log")
        with open(pfad, encoding="utf-8") as datei:
            text = datei.read()
        assert "Durchsage gesendet" in text
        assert "Durchsage entfernt" in text
        assert "Lena" not in text

    def test_die_sicherung_nimmt_nur_den_schalter_mit(self, admin, flask_app, make_challenge):
        import json
        import zipfile

        from wettbewerb_sicherung import sicherung_bauen, sicherung_einlesen

        challenge = wettbewerb(make_challenge)
        senden(admin, challenge, "Lena bitte zur Tafel")
        challenge = frisch(challenge)

        datei, _zahlen = sicherung_bauen(challenge, mit_namen=False)
        with datei:
            datei.seek(0)
            with zipfile.ZipFile(datei) as zf:
                inhalt = "".join(zf.read(n).decode("utf-8", "replace")
                                 for n in zf.namelist() if n.endswith(".json"))
            assert "Lena" not in inhalt
            assert json.loads(inhalt)["wettbewerb"]["durchsagen"] is True

            datei.seek(0)
            neu, _zahlen, _hinweise = sicherung_einlesen(
                datei, flask_app.config["UPLOAD_FOLDER"])
        assert neu.announcements_enabled is True
        assert neu.announcement_text == ""
