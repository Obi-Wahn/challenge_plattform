"""Was passiert, wenn etwas schiefgeht.

Bis hierher zeigte der Webserver in diesen Fällen seine eigene Seite:
englisch, ohne Erklärung und ohne Weg zurück. Das trifft aber genau die
Momente, in denen mitten im Wettbewerb jemand die Hand hebt - die falsche
Dateiart erwischt, die Seite zu lange offen gehabt. Geprüft wird deshalb
beides: dass es eigene Fehlerseiten gibt, und dass die gewöhnlichen
Missgeschicke einer Schulstunde gar nicht erst auf einer landen.
"""

import io
from datetime import datetime, timedelta

from tests.helpers import csrf_token


def abgeben(client, task, dateiname="loesung.sb3", inhalt=b"projekt"):
    return client.post(f"/submit/{task.id}", data={
        "csrf_token": csrf_token(client, "/"),
        "file": (io.BytesIO(inhalt), dateiname),
    }, content_type="multipart/form-data", follow_redirects=True)


class TestEigeneFehlerseiten:
    def test_eine_unbekannte_adresse_zeigt_die_eigene_seite(self, client):
        antwort = client.get("/gibt-es-nicht")
        html = antwort.get_data(as_text=True)

        assert antwort.status_code == 404
        assert "Diese Seite gibt es nicht" in html
        # Die Seite der Anwendung, nicht die des Webservers.
        assert "Zur Startseite" in html
        assert "The requested URL was not found" not in html

    def test_sie_ist_auf_deutsch_und_nennt_den_fehler(self, client):
        html = client.get("/gibt-es-nicht").get_data(as_text=True)

        assert "Fehler 404" in html

    def test_eine_gesperrte_seite_zeigt_die_eigene_seite(
            self, client, make_challenge, make_task, logged_in_team):
        """Eine Aufgabe aus einem fremden Wettbewerb bleibt verboten."""
        aktuell = make_challenge(title="Aktuell", active=True)
        fremd = make_challenge(title="Fremd", active=False)
        fremde_aufgabe = make_task(fremd)
        client, _team = logged_in_team(aktuell)

        antwort = abgeben(client, fremde_aufgabe)
        html = antwort.get_data(as_text=True)

        assert antwort.status_code == 403
        assert "Das geht gerade nicht" in html

    def test_ein_angemeldetes_team_kommt_zurueck_an_die_arbeit(
            self, make_challenge, logged_in_team):
        challenge = make_challenge()
        client, _team = logged_in_team(challenge)

        html = client.get("/gibt-es-nicht").get_data(as_text=True)

        assert "Zurück zu den Aufgaben" in html
        assert "/challenge" in html

    def test_ohne_anmeldung_gibt_es_nur_den_weg_zur_startseite(self, client, make_challenge):
        make_challenge()

        html = client.get("/gibt-es-nicht").get_data(as_text=True)

        assert "Zurück zu den Aufgaben" not in html
        assert "Zur Startseite" in html


class TestEineZuGrosseDatei:
    def test_sie_landet_auf_der_eigenen_seite(
            self, flask_app, make_challenge, make_task, logged_in_team):
        """Die Grenze wird für den Test herabgesetzt - der Weg ist derselbe."""
        challenge = make_challenge()
        task = make_task(challenge, allowed_extension=".sb3")
        client, _team = logged_in_team(challenge)

        grenze = flask_app.config["MAX_CONTENT_LENGTH"]
        flask_app.config["MAX_CONTENT_LENGTH"] = 2048
        try:
            antwort = abgeben(client, task, inhalt=b"x" * 5000)
        finally:
            flask_app.config["MAX_CONTENT_LENGTH"] = grenze

        html = antwort.get_data(as_text=True)
        assert antwort.status_code == 413
        assert "zu groß" in html
        assert "16 MB" in html


class TestAbgabeMitMissgeschick:
    """Die gewöhnlichen Fälle landen auf der Wettbewerbsseite, nicht im Fehler."""

    def test_falsche_dateiart_sagt_welche_erlaubt_ist(
            self, make_challenge, make_task, logged_in_team):
        from models import Submission

        challenge = make_challenge()
        task = make_task(challenge, title="Hüpfendes Ei", allowed_extension=".sb3")
        client, _team = logged_in_team(challenge)

        antwort = abgeben(client, task, dateiname="loesung.exe")
        html = antwort.get_data(as_text=True)

        assert antwort.status_code == 200
        assert ".sb3" in html
        assert "Hüpfendes Ei" in html
        assert "gespeichert wurde nichts" in html
        # Und vor allem: Es ist wirklich nichts gespeichert worden.
        assert Submission.query.count() == 0

    def test_ohne_datei_kommt_eine_meldung(self, make_challenge, make_task, logged_in_team):
        from models import Submission

        challenge = make_challenge()
        task = make_task(challenge)
        client, _team = logged_in_team(challenge)

        antwort = client.post(f"/submit/{task.id}", data={
            "csrf_token": csrf_token(client, "/"),
        }, content_type="multipart/form-data", follow_redirects=True)

        assert antwort.status_code == 200
        assert "keine Datei" in antwort.get_data(as_text=True)
        assert Submission.query.count() == 0

    def test_nach_dem_ende_sagt_die_seite_warum(
            self, make_challenge, make_task, logged_in_team, database):
        from models import Submission

        challenge = make_challenge()
        task = make_task(challenge)
        client, _team = logged_in_team(challenge)

        challenge.end_time = datetime.now() - timedelta(minutes=1)
        database.session.commit()

        antwort = abgeben(client, task)

        assert antwort.status_code == 200
        assert "gesperrt" in antwort.get_data(as_text=True)
        assert Submission.query.count() == 0

    def test_die_pause_sagt_es_ebenso(
            self, make_challenge, make_task, logged_in_team, database):
        from models import Submission

        challenge = make_challenge()
        task = make_task(challenge)
        client, _team = logged_in_team(challenge)

        challenge.paused = True
        database.session.commit()

        antwort = abgeben(client, task)

        assert antwort.status_code == 200
        assert "gesperrt" in antwort.get_data(as_text=True)
        assert Submission.query.count() == 0

    def test_die_zweite_abgabe_verweist_auf_die_freigabe(
            self, make_challenge, make_task, logged_in_team):
        from models import Submission

        challenge = make_challenge()
        task = make_task(challenge)
        client, _team = logged_in_team(challenge)

        abgeben(client, task)
        antwort = abgeben(client, task, inhalt=b"zweiter versuch")
        html = antwort.get_data(as_text=True)

        assert antwort.status_code == 200
        assert "freigeben" in html or "freigegeben" in html
        # Die erste Abgabe steht unverändert da.
        abgabe = Submission.query.one()
        with open(abgabe.filename, "rb") as datei:
            assert datei.read() == b"projekt"

    def test_ohne_anmeldung_geht_es_zur_startseite(self, client, make_challenge, make_task):
        from models import Submission

        challenge = make_challenge()
        task = make_task(challenge)

        antwort = client.post(f"/submit/{task.id}", data={
            "csrf_token": csrf_token(client, "/"),
            "file": (io.BytesIO(b"x"), "loesung.sb3"),
        }, content_type="multipart/form-data")

        assert antwort.status_code == 302
        assert antwort.headers["Location"] == "/"
        assert Submission.query.count() == 0
