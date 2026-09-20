"""Der Admin-Bereich: Steuerzentrale, Wettbewerbs-Seite und die Knöpfe darauf."""

from datetime import datetime, timedelta

from tests.helpers import csrf_token


def aktion(admin, pfad, quelle="/admin/dashboard", **felder):
    return admin.post(pfad, data={
        "csrf_token": csrf_token(admin, quelle),
        **felder,
    })


class TestZugriffsschutz:
    def test_admin_seiten_verlangen_eine_anmeldung(self, client, make_challenge):
        challenge = make_challenge()
        seiten = [
            "/admin/dashboard",
            "/admin/challenges",
            f"/admin/wettbewerb/{challenge.id}",
            "/admin/teams",
            "/admin/submissions",
            "/admin/settings",
            "/admin/urkunden",
        ]
        for seite in seiten:
            antwort = client.get(seite)
            assert antwort.status_code == 302, seite
            assert "/admin/login" in antwort.headers["Location"], seite

    def test_falsches_passwort_meldet_nicht_an(self, client):
        antwort = client.post("/admin/login", data={
            "csrf_token": csrf_token(client, "/admin/login"),
            "password": "falsch",
        })

        assert antwort.status_code == 200
        assert "Falsches Passwort" in antwort.get_data(as_text=True)
        assert client.get("/admin/dashboard").status_code == 302


class TestSteuerzentrale:
    def test_zeigt_den_aktuellen_wettbewerb_mit_kennzahlen(
            self, admin, make_challenge, make_task, make_team):
        challenge = make_challenge(title="Scratch-Wettbewerb")
        make_task(challenge)
        make_team(challenge, name="Team Blitz")

        html = admin.get("/admin/dashboard").get_data(as_text=True)

        assert "Scratch-Wettbewerb" in html
        assert "1 Teams" in html
        assert "1 Aufgaben" in html

    def test_zeigt_die_zahl_offener_bewertungen(
            self, admin, make_challenge, make_task, make_team, database):
        from models import Submission

        challenge = make_challenge()
        task = make_task(challenge)
        team = make_team(challenge, name="Team Blitz")
        database.session.add(Submission(team_id=team.id, task_id=task.id, filename="x.sb3"))
        database.session.commit()

        html = admin.get("/admin/dashboard").get_data(as_text=True)

        assert "1 Bewertungen offen" in html

    def test_ohne_wettbewerb_wird_das_anlegen_angeboten(self, admin, database):
        html = admin.get("/admin/dashboard").get_data(as_text=True)

        assert "Noch kein Wettbewerb angelegt" in html
        assert "Ersten Wettbewerb anlegen" in html

    def test_listet_nicht_alle_wettbewerbe_auf(self, admin, make_challenge):
        """Die doppelte Liste unten auf der Seite ist absichtlich weg."""
        make_challenge(title="Alter Wettbewerb", active=False)
        make_challenge(title="Aktueller Wettbewerb", active=True)

        html = admin.get("/admin/dashboard").get_data(as_text=True)

        assert "Alter Wettbewerb" not in html


class TestWettbewerbsSeite:
    def test_zeigt_aufgaben_und_teams(self, admin, make_challenge, make_task, make_team):
        challenge = make_challenge()
        make_task(challenge, title="Katze läuft im Kreis")
        make_team(challenge, name="Die Pixelpiraten")

        html = admin.get(f"/admin/wettbewerb/{challenge.id}").get_data(as_text=True)

        assert "Katze läuft im Kreis" in html
        assert "Die Pixelpiraten" in html

    def test_nicht_aktiver_wettbewerb_wird_gekennzeichnet(self, admin, make_challenge):
        make_challenge(title="Aktuell", active=True)
        alt = make_challenge(title="Alt", active=False)

        html = admin.get(f"/admin/wettbewerb/{alt.id}").get_data(as_text=True)

        assert "nicht aktiv" in html
        assert "aktivieren" in html.lower()

    def test_unbekannter_wettbewerb_ergibt_404(self, admin, database):
        assert admin.get("/admin/wettbewerb/9999").status_code == 404


class TestWettbewerbBeenden:
    def test_beenden_setzt_die_endzeit(self, admin, make_challenge, database):
        challenge = make_challenge()

        aktion(admin, f"/admin/challenges/{challenge.id}/finish")

        database.session.refresh(challenge)
        assert challenge.end_time is not None
        assert challenge.status() == "finished"
        assert challenge.accepts_submissions is False

    def test_wieder_oeffnen_nimmt_die_endzeit_zurueck(
            self, admin, make_challenge, database):
        challenge = make_challenge(end_time=datetime.now() - timedelta(minutes=1))

        aktion(admin, f"/admin/challenges/{challenge.id}/reopen")

        database.session.refresh(challenge)
        assert challenge.end_time is None
        assert challenge.accepts_submissions is True

    def test_wieder_oeffnen_hebt_auch_eine_pause_auf(
            self, admin, make_challenge, database):
        challenge = make_challenge(end_time=datetime.now() - timedelta(minutes=1),
                                   paused=True)

        aktion(admin, f"/admin/challenges/{challenge.id}/reopen")

        database.session.refresh(challenge)
        assert challenge.paused is False

    def test_beendeter_wettbewerb_zeigt_wieder_oeffnen_statt_beenden(
            self, admin, make_challenge):
        make_challenge(end_time=datetime.now() - timedelta(minutes=1))

        html = admin.get("/admin/dashboard").get_data(as_text=True)

        assert "Wieder öffnen" in html
        assert "Wettbewerb beenden" not in html


class TestPause:
    def test_pausieren_und_fortsetzen(self, admin, make_challenge, database):
        challenge = make_challenge()

        aktion(admin, f"/admin/challenges/{challenge.id}/pause")
        database.session.refresh(challenge)
        assert challenge.paused is True

        aktion(admin, f"/admin/challenges/{challenge.id}/resume")
        database.session.refresh(challenge)
        assert challenge.paused is False


class TestAktivieren:
    def test_aktivieren_braucht_ein_post(self, admin, make_challenge):
        challenge = make_challenge(active=False)

        assert admin.get(f"/admin/challenge/{challenge.id}/activate").status_code == 405

    def test_aktivieren_macht_ihn_zum_aktuellen(self, admin, make_challenge, database):
        from models import Challenge

        alt = make_challenge(title="Alt", active=True)
        neu = make_challenge(title="Neu", active=False)

        aktion(admin, f"/admin/challenge/{neu.id}/activate")

        assert Challenge.current().id == neu.id
        database.session.refresh(alt)
        assert alt.active is False


class TestRuecksprung:
    def test_aktion_kehrt_zur_aufrufenden_seite_zurueck(self, admin, make_challenge):
        challenge = make_challenge()

        antwort = aktion(admin, f"/admin/challenges/{challenge.id}/pause",
                         next="/admin/dashboard")

        assert antwort.headers["Location"].endswith("/admin/dashboard")

    def test_umleitung_auf_fremde_adressen_wird_ignoriert(self, admin, make_challenge):
        challenge = make_challenge()

        antwort = aktion(admin, f"/admin/challenges/{challenge.id}/pause",
                         next="https://boese.example/")

        assert "boese.example" not in antwort.headers["Location"]

    def test_protokollloses_ziel_wird_ignoriert(self, admin, make_challenge):
        """//example.com ist für den Browser ebenfalls eine fremde Adresse."""
        challenge = make_challenge()

        antwort = aktion(admin, f"/admin/challenges/{challenge.id}/pause",
                         next="//boese.example/")

        assert "boese.example" not in antwort.headers["Location"]


class TestWettbewerbAnlegen:
    def test_anlegen_fuehrt_zur_neuen_wettbewerbs_seite(self, admin, database):
        from models import Challenge

        antwort = admin.post("/admin/challenges/new", data={
            "csrf_token": csrf_token(admin, "/admin/challenges/new"),
            "title": "Neuer Wettbewerb",
        })

        challenge = Challenge.query.filter_by(title="Neuer Wettbewerb").one()
        assert antwort.headers["Location"].endswith(f"/admin/wettbewerb/{challenge.id}")

    def test_zeiten_werden_uebernommen(self, admin, database):
        from models import Challenge

        admin.post("/admin/challenges/new", data={
            "csrf_token": csrf_token(admin, "/admin/challenges/new"),
            "title": "Mit Zeiten",
            "start_time": "2026-09-20T14:00",
            "end_time": "2026-09-20T16:00",
        })

        challenge = Challenge.query.filter_by(title="Mit Zeiten").one()
        assert challenge.start_time == datetime(2026, 9, 20, 14, 0)
        assert challenge.end_time == datetime(2026, 9, 20, 16, 0)

    def test_unlesbare_zeit_bedeutet_keine_zeit(self, admin, database):
        from models import Challenge

        admin.post("/admin/challenges/new", data={
            "csrf_token": csrf_token(admin, "/admin/challenges/new"),
            "title": "Krumme Zeit",
            "start_time": "gestern",
        })

        assert Challenge.query.filter_by(title="Krumme Zeit").one().start_time is None

    def test_teams_lassen_sich_uebernehmen(self, admin, make_challenge, make_team, database):
        from models import Challenge, Team

        alt = make_challenge(title="Alt")
        make_team(alt, name="Die Pixelpiraten", password="geheim")

        admin.post("/admin/challenges/new", data={
            "csrf_token": csrf_token(admin, "/admin/challenges/new"),
            "title": "Neu",
            "copy_teams": "1",
        })

        neu = Challenge.query.filter_by(title="Neu").one()
        uebernommen = Team.query.filter_by(challenge_id=neu.id).all()
        assert [t.name for t in uebernommen] == ["Die Pixelpiraten"]
        assert uebernommen[0].check_password("geheim"), "Passwort ging verloren"
        assert uebernommen[0].id != Team.query.filter_by(challenge_id=alt.id).one().id

    def test_ohne_haekchen_bleibt_der_wettbewerb_leer(
            self, admin, make_challenge, make_team, database):
        from models import Challenge, Team

        alt = make_challenge(title="Alt")
        make_team(alt, name="Die Pixelpiraten")

        admin.post("/admin/challenges/new", data={
            "csrf_token": csrf_token(admin, "/admin/challenges/new"),
            "title": "Neu",
        })

        neu = Challenge.query.filter_by(title="Neu").one()
        assert Team.query.filter_by(challenge_id=neu.id).count() == 0


class TestWettbewerbLoeschen:
    def test_loeschen_nimmt_aufgaben_teams_und_abgaben_mit(
            self, admin, make_challenge, make_task, make_team, database):
        from models import Submission, Task, Team

        challenge = make_challenge()
        task = make_task(challenge)
        team = make_team(challenge, name="Team Blitz")
        database.session.add(Submission(team_id=team.id, task_id=task.id, filename="x.sb3"))
        database.session.commit()

        # Token von der Wettbewerbs-Seite: die Liste zeigt für den aktiven
        # Wettbewerb kein Formular und damit kein Token.
        aktion(admin, f"/admin/challenges/{challenge.id}/delete",
               quelle=f"/admin/wettbewerb/{challenge.id}")

        assert Task.query.count() == 0
        assert Team.query.count() == 0
        assert Submission.query.count() == 0


class TestHinweise:
    def test_hinweis_laesst_sich_umschalten(
            self, admin, make_challenge, make_task, database):
        challenge = make_challenge()
        task = make_task(challenge, hint="Nutzt „wiederhole“.")

        assert task.hint_visible in (False, None)

        aktion(admin, f"/admin/tasks/{task.id}/toggle_hint",
               quelle=f"/admin/challenges/{challenge.id}/tasks")

        database.session.refresh(task)
        assert task.hint_visible is True

    def test_verborgener_hinweis_steht_nicht_auf_der_teamseite(
            self, make_challenge, make_task, logged_in_team):
        challenge = make_challenge()
        make_task(challenge, hint="Geheimtipp")
        client, _team = logged_in_team(challenge)

        assert "Geheimtipp" not in client.get("/challenge").get_data(as_text=True)

    def test_freigeschalteter_hinweis_steht_auf_der_teamseite(
            self, make_challenge, make_task, logged_in_team):
        challenge = make_challenge()
        make_task(challenge, hint="Geheimtipp", hint_visible=True)
        client, _team = logged_in_team(challenge)

        assert "Geheimtipp" in client.get("/challenge").get_data(as_text=True)


class TestEinstellungen:
    def test_name_und_untertitel_werden_gespeichert(self, admin, client, database):
        from models import Settings

        admin.post("/admin/settings", data={
            "csrf_token": csrf_token(admin, "/admin/settings"),
            "site_name": "Calliope-Wettbewerb",
            "tagline": "Wir programmieren den Calliope",
        })

        settings = Settings.get()
        assert settings.site_name == "Calliope-Wettbewerb"
        assert settings.tagline == "Wir programmieren den Calliope"
        assert "Calliope-Wettbewerb" in client.get("/").get_data(as_text=True)


class TestAdminEinstieg:
    """/admin ist die Adresse, die in der Anleitung steht."""

    def test_ohne_anmeldung_fuehrt_admin_zur_anmeldung(self, client, database):
        antwort = client.get("/admin", follow_redirects=True)

        assert antwort.status_code == 200
        assert "Admin" in antwort.get_data(as_text=True)
        assert 'name="password"' in antwort.get_data(as_text=True)

    def test_angemeldet_fuehrt_admin_zur_steuerzentrale(self, admin, make_challenge):
        make_challenge(title="Scratch-Wettbewerb")

        antwort = admin.get("/admin", follow_redirects=True)

        assert antwort.status_code == 200
        assert "Steuerzentrale" in antwort.get_data(as_text=True)

    def test_auch_mit_schraegstrich(self, admin, make_challenge):
        make_challenge()

        antwort = admin.get("/admin/", follow_redirects=True)

        assert "Steuerzentrale" in antwort.get_data(as_text=True)
