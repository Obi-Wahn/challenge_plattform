"""Die Bewertungsseite: was sie mitbringt und was sie nachlädt.

Sie las bisher beim Öffnen jede Abgabe des Wettbewerbs vollständig ein und
schrieb sie ins HTML - auch die, die niemand aufklappt, und auch die, die
kein Text sind. Zehn Scratch-Projekte von je 2 MB ergaben so eine Seite von
35 MB, in der nichts Lesbares stand. Jetzt steht in der Seite nur, was die
Entscheidung trägt; der Inhalt kommt beim Aufklappen nach.
"""

import io
import zipfile

from tests.helpers import csrf_token


def abgeben(client, task, dateiname, inhalt=b"print('hallo')"):
    return client.post(f"/submit/{task.id}", data={
        "csrf_token": csrf_token(client, "/"),
        "file": (io.BytesIO(inhalt), dateiname),
    }, content_type="multipart/form-data")


def scratch_projekt(nutzdaten=200_000):
    """Eine .sb3-Datei ist eine ZIP-Datei - also nichts zum Lesen."""
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w") as archiv:
        archiv.writestr("project.json", '{"targets": []}')
        archiv.writestr("klang.wav", bytes(range(256)) * (nutzdaten // 256))
    return puffer.getvalue()


class TestDieSeiteBleibtSchlank:
    def test_der_inhalt_steht_nicht_mehr_in_der_seite(
            self, admin, make_challenge, make_task, logged_in_team):
        challenge = make_challenge()
        task = make_task(challenge, allowed_extension=".py")
        client, _team = logged_in_team(challenge)
        abgeben(client, task, "loesung.py", b"geheimes_wort_aus_der_datei")

        html = admin.get("/admin/submissions").get_data(as_text=True)

        assert "geheimes_wort_aus_der_datei" not in html
        assert "Code anzeigen" in html

    def test_eine_grosse_abgabe_blaeht_die_seite_nicht_auf(
            self, admin, make_challenge, make_task, logged_in_team):
        challenge = make_challenge()
        task = make_task(challenge, allowed_extension=".sb3")
        client, _team = logged_in_team(challenge)
        abgeben(client, task, "loesung.sb3", scratch_projekt())

        seite = admin.get("/admin/submissions").get_data()

        # Die Datei allein ist größer als das, was hier an Seite entsteht.
        assert len(seite) < 100_000

    def test_die_seite_nennt_endung_und_groesse(
            self, admin, make_challenge, make_task, logged_in_team):
        challenge = make_challenge()
        task = make_task(challenge, allowed_extension=".sb3")
        client, _team = logged_in_team(challenge)
        abgeben(client, task, "loesung.sb3", scratch_projekt())

        html = admin.get("/admin/submissions").get_data(as_text=True)

        assert ".sb3" in html
        assert "KB" in html


class TestWasSichAlsTextLesenLaesst:
    def test_eine_scratch_datei_bekommt_keinen_knopf(
            self, admin, make_challenge, make_task, logged_in_team):
        challenge = make_challenge()
        task = make_task(challenge, allowed_extension=".sb3")
        client, _team = logged_in_team(challenge)
        abgeben(client, task, "loesung.sb3", scratch_projekt(1024))

        html = admin.get("/admin/submissions").get_data(as_text=True)

        assert "Code anzeigen" not in html
        assert "zum Ansehen herunterladen" in html
        # Der Weg zur Datei selbst bleibt.
        assert "Datei herunterladen" in html

    def test_eine_python_datei_bekommt_einen(
            self, admin, make_challenge, make_task, logged_in_team):
        challenge = make_challenge()
        task = make_task(challenge, allowed_extension=".py")
        client, _team = logged_in_team(challenge)
        abgeben(client, task, "loesung.py")

        html = admin.get("/admin/submissions").get_data(as_text=True)

        assert "Code anzeigen" in html


class TestDerInhaltWirdNachgeladen:
    def abgabe_anlegen(self, make_challenge, make_task, logged_in_team,
                       endung=".py", inhalt=b"print('hallo')"):
        from models import Submission

        challenge = make_challenge()
        task = make_task(challenge, allowed_extension=endung)
        client, _team = logged_in_team(challenge)
        abgeben(client, task, f"loesung{endung}", inhalt)
        return Submission.query.one()

    def test_er_kommt_als_json(self, admin, make_challenge, make_task, logged_in_team):
        abgabe = self.abgabe_anlegen(make_challenge, make_task, logged_in_team)

        antwort = admin.get(f"/admin/submissions/{abgabe.id}/code")

        assert antwort.status_code == 200
        assert antwort.get_json()["code"] == "print('hallo')"

    def test_html_in_der_datei_bleibt_text(
            self, admin, make_challenge, make_task, logged_in_team):
        """Der Inhalt darf im Browser unter keinen Umständen Code werden."""
        abgabe = self.abgabe_anlegen(
            make_challenge, make_task, logged_in_team,
            inhalt=b"<script>alert(1)</script>")

        antwort = admin.get(f"/admin/submissions/{abgabe.id}/code")

        # Als JSON ausgeliefert, und mit der Ansage, nicht zu raten: So kann
        # der Browser daraus unter keinen Umständen HTML machen.
        assert antwort.mimetype == "application/json"
        assert antwort.headers["X-Content-Type-Options"] == "nosniff"
        assert antwort.get_json()["code"] == "<script>alert(1)</script>"

    def test_eine_riesige_datei_wird_gekuerzt(
            self, admin, make_challenge, make_task, logged_in_team):
        from blueprints.admin import MAX_CODE_ZEICHEN

        abgabe = self.abgabe_anlegen(
            make_challenge, make_task, logged_in_team,
            inhalt=b"x" * (MAX_CODE_ZEICHEN + 5000))

        daten = admin.get(f"/admin/submissions/{abgabe.id}/code").get_json()

        assert len(daten["code"]) == MAX_CODE_ZEICHEN
        assert "Anfang" in daten["hinweis"]

    def test_eine_scratch_datei_wird_gar_nicht_erst_gelesen(
            self, admin, make_challenge, make_task, logged_in_team):
        abgabe = self.abgabe_anlegen(
            make_challenge, make_task, logged_in_team,
            endung=".sb3", inhalt=scratch_projekt(1024))

        daten = admin.get(f"/admin/submissions/{abgabe.id}/code").get_json()

        assert daten["code"] == ""
        assert "herunterladen" in daten["hinweis"]
        assert "Scratch" in daten["hinweis"]

    def test_eine_verschwundene_datei_sagt_das(
            self, admin, make_challenge, make_task, logged_in_team):
        import os

        abgabe = self.abgabe_anlegen(make_challenge, make_task, logged_in_team)
        os.remove(abgabe.filename)

        daten = admin.get(f"/admin/submissions/{abgabe.id}/code").get_json()

        assert daten["code"] == ""
        assert "nicht mehr" in daten["hinweis"]

    def test_ohne_anmeldung_gibt_es_keinen_inhalt(
            self, client, admin, make_challenge, make_task, logged_in_team):
        abgabe = self.abgabe_anlegen(make_challenge, make_task, logged_in_team)

        antwort = client.get(f"/admin/submissions/{abgabe.id}/code")

        assert antwort.status_code == 302
        assert "/admin/login" in antwort.headers["Location"]


class TestPunkteEintragen:
    def test_eine_punktzahl_die_keine_zahl_ist_wird_gemeldet(
            self, admin, make_challenge, make_task, logged_in_team):
        """Über das Formular kommt das nicht vor - von Hand abgeschickt schon."""
        from models import Submission

        challenge = make_challenge()
        task = make_task(challenge, max_points=10, allowed_extension=".py")
        client, _team = logged_in_team(challenge)
        abgeben(client, task, "loesung.py")
        abgabe = Submission.query.one()

        antwort = admin.post("/admin/submissions", data={
            "csrf_token": csrf_token(admin, "/admin/submissions"),
            "submission_id": abgabe.id,
            "points": "abc",
        }, follow_redirects=True)

        assert antwort.status_code == 200
        assert "muss eine Zahl sein" in antwort.get_data(as_text=True)
        assert Submission.query.one().points is None
