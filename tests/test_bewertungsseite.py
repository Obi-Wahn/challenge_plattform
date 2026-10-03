"""Die Bewertungsseite: was sie mitbringt und was sie nachlädt.

Sie las bisher beim Öffnen jede Abgabe des Wettbewerbs vollständig ein und
schrieb sie ins HTML - auch die, die niemand aufklappt, und auch die, die
kein Text sind. Zehn Scratch-Projekte von je 2 MB ergaben so eine Seite von
35 MB, in der nichts Lesbares stand. Jetzt steht in der Seite nur, was die
Entscheidung trägt; der Inhalt kommt beim Aufklappen nach.
"""

import io
import zipfile

import pytest

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

    def test_groesse_mit_deutschem_komma(
            self, admin, make_challenge, make_task, logged_in_team):
        challenge = make_challenge()
        task = make_task(challenge, allowed_extension=".sb3")
        client, _team = logged_in_team(challenge)
        abgeben(client, task, "loesung.sb3", b"x" * (1536 * 1024))

        html = admin.get("/admin/submissions").get_data(as_text=True)

        assert "1,5 MB" in html
        assert "1.5 MB" not in html


class TestAufgabentextNurEinmalUmwandeln:
    """Jede Abgabe zeigt ihre Aufgabenbeschreibung. Bei 40 Teams und 10
    Aufgaben wurden dieselben zehn Texte 370-mal umgewandelt - nach jeder
    Bewertung von vorn."""

    def test_gleicher_text_wird_einmal_umgewandelt(
            self, admin, make_challenge, make_task, make_team, flask_app,
            database, monkeypatch):
        import markdown

        import app as anwendung
        from models import Submission

        challenge = make_challenge()
        task = make_task(challenge, description="Die Katze **läuft** im Kreis.")
        for nummer in range(5):
            team = make_team(challenge, name=f"Team {nummer}")
            database.session.add(Submission(team_id=team.id, task_id=task.id,
                                            filename=f"{team.id}/task_{task.id}_a.sb3"))
        database.session.commit()

        aufrufe = []
        original = markdown.markdown
        monkeypatch.setattr(markdown, "markdown",
                            lambda text, **kw: aufrufe.append(text) or original(text, **kw))
        anwendung.markdown_html.cache_clear()

        html = admin.get("/admin/submissions").get_data(as_text=True)

        assert html.count("<strong>läuft</strong>") == 5
        assert len(aufrufe) == 1

    def test_geaenderter_text_wird_neu_umgewandelt(self, flask_app):
        from app import markdown_html

        assert "<em>alt</em>" in markdown_html("*alt*")
        assert "<em>neu</em>" in markdown_html("*neu*")

    def test_entschaerfen_gilt_auch_aus_dem_zwischenspeicher(self, flask_app):
        from app import markdown_html

        for _ in range(2):
            html = markdown_html("[klick](javascript:alert(1)) <b>fett</b>")
            assert "javascript:" not in html
            assert "<b>" not in html


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


    def test_ein_arduino_sketch_bekommt_einen(
            self, admin, make_challenge, make_task, logged_in_team):
        challenge = make_challenge()
        task = make_task(challenge, allowed_extension=".ino")
        client, _team = logged_in_team(challenge)
        abgeben(client, task, "blinken.ino", b"void setup() {}\nvoid loop() {}")

        html = admin.get("/admin/submissions").get_data(as_text=True)

        assert "Code anzeigen" in html

    @pytest.mark.parametrize("endung", [".xml", ".aia", ".ipynb"])
    def test_bloecke_apps_und_notebooks_bekommen_keinen(
            self, admin, make_challenge, make_task, logged_in_team, endung):
        """Erst in Open Roberta, Snap!, App Inventor oder Jupyter lesbar."""
        challenge = make_challenge()
        task = make_task(challenge, allowed_extension=endung)
        client, _team = logged_in_team(challenge)
        abgeben(client, task, f"loesung{endung}", b"<xml></xml>")

        html = admin.get("/admin/submissions").get_data(as_text=True)

        assert "Code anzeigen" not in html
        assert "Datei herunterladen" in html


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
        os.remove(abgabe.pfad)

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


class TestKnoepfeOhneBewertung:
    """Die Knöpfe unter einer Abgabe teilen sich das Formular mit dem
    Punktefeld, und das ist ein Pflichtfeld. Ohne formnovalidate hält der
    Browser „Erneut abgeben erlauben“ und „Abgabe löschen“ an, solange die
    Abgabe keine Punkte hat - der Test-Client merkt davon nichts, deshalb
    steht es hier als Prüfung auf das Attribut."""

    def test_beide_knoepfe_umgehen_die_pflichtfeldpruefung(
            self, admin, make_challenge, make_task, logged_in_team):
        import re
        challenge = make_challenge()
        task = make_task(challenge, allowed_extension=".py")
        client, _team = logged_in_team(challenge)
        abgeben(client, task, "loesung.py")

        html = admin.get("/admin/submissions").get_data(as_text=True)

        knoepfe = re.findall(r"<button[^>]*formaction=[^>]*>", html)
        assert len(knoepfe) == 2
        assert all("formnovalidate" in knopf for knopf in knoepfe)


class TestDownload:
    def test_eine_fehlende_datei_meldet_die_bewertungsseite(
            self, admin, make_challenge, make_task, logged_in_team):
        import os
        from models import Submission
        challenge = make_challenge()
        task = make_task(challenge, title="Katze", allowed_extension=".py")
        client, _team = logged_in_team(challenge)
        abgeben(client, task, "loesung.py")
        abgabe = Submission.query.one()
        os.remove(abgabe.pfad)

        antwort = admin.get(f"/admin/download/{abgabe.id}", follow_redirects=True)
        seite = antwort.get_data(as_text=True)

        assert antwort.status_code == 200
        assert "liegt nicht mehr auf dem Server" in seite
        assert "Tippfehler" not in seite

    def test_der_name_nennt_die_aufgabe_wie_die_rangliste(
            self, admin, make_challenge, make_task, logged_in_team):
        from models import Submission
        # Ein früherer Wettbewerb treibt die Nummern der Datenbank hoch.
        alt = make_challenge(title="Alt", active=False)
        make_task(alt, title="Alt 1")
        make_task(alt, title="Alt 2")
        challenge = make_challenge()
        make_task(challenge, title="Erste", allowed_extension=".py")
        zweite = make_task(challenge, title="Zweite", allowed_extension=".py")
        client, _team = logged_in_team(challenge, name="Pixel")
        abgeben(client, zweite, "loesung.py")

        antwort = admin.get(f"/admin/download/{Submission.query.one().id}")

        assert "Pixel_A2.py" in antwort.headers["Content-Disposition"]
