"""Schutzmechanismen, die im Schul-LAN wirken sollen."""

import pytest

from tests.helpers import ADMIN_PASSWORD, csrf_token


class TestCsrf:
    """Ohne Token darf kein Formular durchgehen - auch keins von außerhalb."""

    def test_anmeldung_ohne_token_wird_abgewiesen(self, client, make_challenge, make_team):
        challenge = make_challenge()
        make_team(challenge, name="Team Blitz", password="geheim")

        antwort = client.post("/login", data={"team": "Team Blitz", "password": "geheim"})

        assert antwort.status_code == 400

    def test_admin_anmeldung_ohne_token_wird_abgewiesen(self, client):
        antwort = client.post("/admin/login", data={"password": ADMIN_PASSWORD})

        assert antwort.status_code == 400

    def test_wettbewerb_beenden_ohne_token_wird_abgewiesen(
            self, admin, make_challenge, database):
        challenge = make_challenge()

        antwort = admin.post(f"/admin/challenges/{challenge.id}/finish")

        assert antwort.status_code == 400
        database.session.refresh(challenge)
        assert challenge.end_time is None


class TestPasswoerter:
    def test_werden_nicht_im_klartext_gespeichert(self, make_challenge, make_team):
        challenge = make_challenge()
        team = make_team(challenge, name="Team Blitz", password="geheim")

        assert team.password_hash != "geheim"
        assert "geheim" not in team.password_hash
        assert team.check_password("geheim")
        assert not team.check_password("falsch")

    def test_team_ohne_passwort_kommt_nicht_rein(self, make_challenge, database):
        from models import Team

        challenge = make_challenge()
        team = Team(name="Ohne Passwort", challenge_id=challenge.id)
        database.session.add(team)
        database.session.commit()

        assert not team.check_password("")
        assert not team.check_password("irgendwas")

    def test_neues_passwort_wird_nicht_zurueckgemeldet(
            self, admin, make_challenge, make_team):
        """Der Bildschirm hängt beim Event womöglich am Beamer."""
        challenge = make_challenge()
        team = make_team(challenge, name="Team Blitz")

        antwort = admin.post(f"/admin/team/{team.id}/reset_password", data={
            "csrf_token": csrf_token(admin, "/admin/teams"),
            "new_password": "streng-geheim",
        }, follow_redirects=True)

        assert "streng-geheim" not in antwort.get_data(as_text=True)


class TestDateiUpload:
    def test_nur_das_erlaubte_format(self, make_challenge, make_task, logged_in_team):
        import io

        challenge = make_challenge()
        task = make_task(challenge, allowed_extension=".sb3")
        client, _team = logged_in_team(challenge)

        for name in ["schad.exe", "skript.sh", "bild.png"]:
            antwort = client.post(f"/submit/{task.id}", data={
                "csrf_token": csrf_token(client, "/"),
                "file": (io.BytesIO(b"x"), name),
            }, content_type="multipart/form-data")
            assert antwort.status_code == 400, name

    def test_pfadangaben_im_dateinamen_werden_entschaerft(
            self, flask_app, make_challenge, make_task, logged_in_team):
        """secure_filename darf keinen Ausbruch aus dem Upload-Ordner zulassen."""
        import io
        import os

        from models import Submission

        challenge = make_challenge()
        task = make_task(challenge, allowed_extension=".sb3")
        client, _team = logged_in_team(challenge)

        client.post(f"/submit/{task.id}", data={
            "csrf_token": csrf_token(client, "/"),
            "file": (io.BytesIO(b"x"), "../../../etc/passwd.sb3"),
        }, content_type="multipart/form-data")

        gespeichert = os.path.abspath(Submission.query.one().filename)
        upload_ordner = os.path.abspath(flask_app.config["UPLOAD_FOLDER"])
        assert gespeichert.startswith(upload_ordner)

    def test_es_gibt_eine_obergrenze_fuer_die_dateigroesse(self, flask_app):
        assert flask_app.config["MAX_CONTENT_LENGTH"] == 16 * 1024 * 1024

    def test_uploads_liegen_nicht_im_oeffentlichen_ordner(self, flask_app):
        """Sonst könnte der Webserver sie direkt ausliefern."""
        import os

        uploads = os.path.abspath(flask_app.config["UPLOAD_FOLDER"])
        statisch = os.path.abspath(flask_app.static_folder)
        assert not uploads.startswith(statisch)


class TestCodeAnzeige:
    def test_hochgeladener_code_wird_escaped_angezeigt(
            self, admin, make_challenge, make_task, logged_in_team):
        """Eine abgegebene Datei darf im Browser kein Skript ausführen."""
        import io

        challenge = make_challenge()
        task = make_task(challenge, allowed_extension=".sb3")
        client, _team = logged_in_team(challenge)
        client.post(f"/submit/{task.id}", data={
            "csrf_token": csrf_token(client, "/"),
            "file": (io.BytesIO(b"<script>alert(1)</script>"), "loesung.sb3"),
        }, content_type="multipart/form-data")

        html = admin.get("/admin/submissions").get_data(as_text=True)

        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;" in html

    def test_teamname_wird_escaped_angezeigt(self, client, make_challenge, make_team):
        challenge = make_challenge()
        make_team(challenge, name="<script>alert(1)</script>")

        html = client.get("/scoreboard").get_data(as_text=True)

        assert "<script>alert(1)</script>" not in html


class TestRateLimit:
    def test_wiederholte_fehlversuche_werden_gebremst(self, flask_app, make_challenge):
        from extensions import limiter

        make_challenge()
        limiter.enabled = True
        limiter.reset()
        try:
            client = flask_app.test_client()
            for _ in range(5):
                client.post("/login", data={
                    "csrf_token": csrf_token(client, "/login"),
                    "team": "Team Blitz", "password": "raten",
                })

            gebremst = client.post("/login", data={
                "csrf_token": csrf_token(client, "/login"),
                "team": "Team Blitz", "password": "raten",
            })
            assert gebremst.status_code == 429
        finally:
            limiter.enabled = False
            limiter.reset()

    def test_das_blosse_aufrufen_der_seite_zaehlt_nicht(self, flask_app, make_challenge):
        """Sonst sperrt sich eine Klasse beim Nachladen selbst aus."""
        from extensions import limiter

        make_challenge()
        limiter.enabled = True
        limiter.reset()
        try:
            client = flask_app.test_client()
            for _ in range(20):
                assert client.get("/login").status_code == 200

            assert client.get("/login").status_code == 200
        finally:
            limiter.enabled = False
            limiter.reset()


class TestBetriebsmodus:
    def test_debug_ist_standardmaessig_aus(self, flask_app):
        """Der Werkzeug-Debugger würde im LAN fremden Code ausführen lassen."""
        import os

        assert os.environ.get("FLASK_DEBUG", "false").strip().lower() not in ("1", "true", "yes")

    def test_es_gibt_keine_eingebauten_zugangsdaten(self):
        """SECRET_KEY und ADMIN_PASSWORD müssen aus der Umgebung kommen."""
        import config

        quelltext = open(config.__file__, encoding="utf-8").read()
        assert '_require_env("SECRET_KEY")' in quelltext
        assert '_require_env("ADMIN_PASSWORD")' in quelltext


class TestAufgabentext:
    """Aufgabenbeschreibungen werden als HTML ausgegeben - aber nur das eigene.

    Seit dem Aufgaben-Import kann der Text aus einer Datei stammen, die
    jemand anderes geschrieben hat, und er wird unter anderem in der
    Bewertungsansicht gerendert, also in der Sitzung des Admins.
    """

    def markdown(self, flask_app, text):
        with flask_app.test_request_context():
            return str(flask_app.jinja_env.filters["markdown"](text))

    @pytest.mark.parametrize("angriff", [
        "<script>alert(1)</script>",
        "<img src=x onerror=alert(1)>",
        "<iframe src='https://example.invalid'></iframe>",
        "<a href='javascript:alert(1)'>klick</a>",
        "<style>body{display:none}</style>",
    ])
    def test_rohes_html_wird_nicht_ausgefuehrt(self, flask_app, angriff):
        html = self.markdown(flask_app, angriff)
        assert "<script" not in html.lower()
        assert "<img" not in html.lower()
        assert "<iframe" not in html.lower()
        assert "<style" not in html.lower()
        assert "onerror" not in html.lower() or "&lt;" in html

    @pytest.mark.parametrize("ziel", [
        "javascript:alert(1)",
        "JavaScript:alert(1)",
        "data:text/html,<script>alert(1)</script>",
        "vbscript:msgbox(1)",
    ])
    def test_verweise_ausserhalb_des_webs_werden_entschaerft(self, flask_app, ziel):
        html = self.markdown(flask_app, f"[klick]({ziel})")
        assert 'href="#"' in html
        assert "javascript" not in html.lower()
        assert "vbscript" not in html.lower()

    @pytest.mark.parametrize("text,erwartet", [
        ("**fett**", "<strong>fett</strong>"),
        ("*kursiv*", "<em>kursiv</em>"),
        ("`code()`", "<code>code()</code>"),
        ("- eins", "<li>eins</li>"),
        ("[Scratch](https://scratch.mit.edu)", 'href="https://scratch.mit.edu"'),
        ("[Mail](mailto:lehrer@schule.de)", 'href="mailto:lehrer@schule.de"'),
        ("[Sprung](#unten)", 'href="#unten"'),
    ])
    def test_markdown_funktioniert_weiterhin(self, flask_app, text, erwartet):
        assert erwartet in self.markdown(flask_app, text)

    def test_umlaute_bleiben_lesbar(self, flask_app):
        assert "Prüfe größer" in self.markdown(flask_app, "Prüfe größer")

    def test_leerer_text_bleibt_leer(self, flask_app):
        assert self.markdown(flask_app, "") == ""
        assert self.markdown(flask_app, None) == ""

    def test_importierte_aufgabe_kann_kein_skript_einschleusen(
            self, admin, make_challenge, database):
        """Der ganze Weg: Aufgabe einlesen, dann die Bewertungsansicht ansehen."""
        import io
        import json

        challenge = make_challenge()
        datei = json.dumps({
            "aufgaben": [{
                "titel": "Harmlos",
                "beschreibung": "<script>alert('uebernommen')</script>",
                "punkte": 10,
                "format": ".sb3",
            }]
        }).encode("utf-8")

        admin.post(
            f"/admin/challenges/{challenge.id}/tasks/import",
            data={
                "csrf_token": csrf_token(
                    admin, f"/admin/challenges/{challenge.id}/tasks"),
                "datei": (io.BytesIO(datei), "aufgaben.json"),
            },
            content_type="multipart/form-data",
        )

        html = admin.get("/admin/submissions").get_data(as_text=True)
        assert "<script>alert('uebernommen')</script>" not in html


class TestSitzungsCookie:
    def test_wird_nicht_an_fremde_seiten_geschickt(self, flask_app):
        # Ohne SameSite schickt der Browser das Cookie auch mit, wenn eine
        # fremde Seite eine Anfrage an den Server auslöst.
        assert flask_app.config["SESSION_COOKIE_SAMESITE"] == "Lax"

    def test_javascript_kommt_nicht_heran(self, flask_app):
        assert flask_app.config["SESSION_COOKIE_HTTPONLY"] is True

    def test_bleibt_ohne_https_nutzbar(self, flask_app):
        # Im Schul-LAN läuft die Anwendung über http. Mit Secure=True würde
        # der Browser das Cookie gar nicht erst schicken - niemand käme rein.
        assert flask_app.config["SESSION_COOKIE_SECURE"] is False
