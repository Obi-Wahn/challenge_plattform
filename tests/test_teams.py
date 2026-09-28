"""Teams gehören zu dem Wettbewerb, für den sie angelegt wurden."""

from tests.helpers import csrf_token


def registrieren(client, name, passwort="geheim"):
    return client.post("/", data={
        "csrf_token": csrf_token(client, "/"),
        "team": name,
        "password": passwort,
    })


def anmelden(client, name, passwort="geheim"):
    return client.post("/login", data={
        "csrf_token": csrf_token(client, "/login"),
        "team": name,
        "password": passwort,
    })


def test_registrierung_bindet_das_team_an_den_aktiven_wettbewerb(client, make_challenge):
    from models import Team

    challenge = make_challenge()
    antwort = registrieren(client, "Die Pixelpiraten")

    assert antwort.status_code == 302
    assert "/challenge" in antwort.headers["Location"]

    team = Team.query.filter_by(name="Die Pixelpiraten").one()
    assert team.challenge_id == challenge.id


def test_ohne_wettbewerb_entsteht_kein_team(client, database):
    from models import Team

    antwort = registrieren(client, "Verfrüht")

    assert antwort.status_code == 200
    assert "Aktuell läuft kein Wettbewerb" in antwort.get_data(as_text=True)
    assert Team.query.count() == 0


def test_teamname_ist_im_selben_wettbewerb_nur_einmal_zu_haben(client, make_challenge):
    make_challenge()
    registrieren(client, "Team Blitz")

    zweiter = client.application.test_client()
    antwort = registrieren(zweiter, "Team Blitz")

    assert "Teamname vergeben" in antwort.get_data(as_text=True)


def test_derselbe_name_darf_in_zwei_wettbewerben_vorkommen(flask_app, make_challenge):
    from models import Team

    erster = make_challenge(title="Frühjahr", active=True)
    registrieren(flask_app.test_client(), "Team Blitz")

    erster.active = False
    zweiter = make_challenge(title="Herbst", active=True)
    registrieren(flask_app.test_client(), "Team Blitz", "anderes")

    teams = Team.query.filter_by(name="Team Blitz").all()
    assert len(teams) == 2
    assert {t.challenge_id for t in teams} == {erster.id, zweiter.id}


def test_anmeldung_sucht_nur_im_aktuellen_wettbewerb(flask_app, make_challenge, make_team):
    alt = make_challenge(title="Alt", active=False)
    make_team(alt, name="Team Blitz", password="altes-passwort")

    neu = make_challenge(title="Neu", active=True)
    make_team(neu, name="Team Blitz", password="neues-passwort")

    client = flask_app.test_client()
    assert "Ungültig" in anmelden(client, "Team Blitz", "altes-passwort").get_data(as_text=True)
    assert anmelden(client, "Team Blitz", "neues-passwort").status_code == 302


def test_falsches_passwort_wird_abgewiesen(client, make_challenge, make_team):
    challenge = make_challenge()
    make_team(challenge, name="Team Blitz", password="richtig")

    antwort = anmelden(client, "Team Blitz", "falsch")

    assert antwort.status_code == 200
    assert "Ungültig" in antwort.get_data(as_text=True)


def test_team_aus_altem_wettbewerb_wird_abgemeldet(flask_app, make_challenge, logged_in_team):
    """Wird ein anderer Wettbewerb aktiviert, gilt die alte Anmeldung nicht mehr."""
    alt = make_challenge(title="Alt", active=True)
    client, _team = logged_in_team(alt)

    assert client.get("/challenge").status_code == 200

    alt.active = False
    make_challenge(title="Neu", active=True)

    antwort = client.get("/challenge")
    assert antwort.status_code == 302
    assert antwort.headers["Location"].endswith("/")


def test_abmelden_raeumt_die_sitzung(client, make_challenge):
    make_challenge()
    registrieren(client, "Team Blitz")

    client.get("/logout")

    assert client.get("/challenge").status_code == 302


class TestTeamVerwaltungImAdmin:
    def test_liste_zeigt_nur_teams_des_aktuellen_wettbewerbs(
            self, admin, make_challenge, make_team):
        alt = make_challenge(title="Alt", active=False)
        make_team(alt, name="Altes Team")
        aktuell = make_challenge(title="Aktuell", active=True)
        make_team(aktuell, name="Aktuelles Team")

        html = admin.get("/admin/teams").get_data(as_text=True)

        assert "Aktuelles Team" in html
        assert "Altes Team" not in html

    def test_passwort_zuruecksetzen(self, flask_app, admin, make_challenge, make_team):
        challenge = make_challenge()
        team = make_team(challenge, name="Team Blitz", password="vergessen")

        admin.post(f"/admin/team/{team.id}/reset_password", data={
            "csrf_token": csrf_token(admin, "/admin/teams"),
            "new_password": "neues-passwort",
        })

        assert anmelden(flask_app.test_client(), "Team Blitz", "neues-passwort").status_code == 302

    def test_leeres_passwort_aendert_nichts(self, admin, make_challenge, make_team):
        challenge = make_challenge()
        team = make_team(challenge, name="Team Blitz", password="bleibt")

        antwort = admin.post(f"/admin/team/{team.id}/reset_password", data={
            "csrf_token": csrf_token(admin, "/admin/teams"),
            "new_password": "   ",
        }, follow_redirects=True)

        assert "nicht geändert" in antwort.get_data(as_text=True)
        assert team.check_password("bleibt")

    def test_team_loeschen_nimmt_seine_abgaben_mit(
            self, admin, make_challenge, make_task, make_team, database):
        """Früher scheiterte das an der Fremdschlüssel-Beziehung."""
        from models import Submission

        challenge = make_challenge()
        task = make_task(challenge)
        team = make_team(challenge, name="Team Blitz")
        database.session.add(Submission(team_id=team.id, task_id=task.id, filename="x.sb3"))
        database.session.commit()
        team_id = team.id

        antwort = admin.post(f"/admin/team/delete/{team_id}", data={
            "csrf_token": csrf_token(admin, "/admin/teams"),
        })

        assert antwort.status_code == 302
        assert Submission.query.filter_by(team_id=team_id).count() == 0


class TestAnmeldungGeschlossen:
    """Ein beendeter oder pausierter Wettbewerb nimmt keine neuen Teams mehr an.

    Nach dem Ende hängt die Rangliste am Beamer: Ein Team, das sich dann noch
    anmeldet, stünde mit null Punkten mitten in der Siegerehrung - und auf der
    Urkundenliste, denn die zählt jedes Team des Wettbewerbs, auch eines ohne
    Abgabe. In der Pause sieht die Lehrkraft nicht auf den Bildschirm.
    """

    def beendet(self, challenge, database):
        from datetime import datetime, timedelta

        challenge.end_time = datetime.now() - timedelta(minutes=1)
        database.session.commit()

    def test_die_startseite_zeigt_nach_dem_ende_kein_formular(
            self, client, make_challenge, database):
        challenge = make_challenge()
        self.beendet(challenge, database)

        html = client.get("/").get_data(as_text=True)

        assert "Registrierung geschlossen" in html
        assert "Der Wettbewerb ist beendet" in html
        assert 'name="team"' not in html
        # Der Weg zur eigenen Urkunde muss offen bleiben.
        assert "Hier anmelden" in html

    def test_die_startseite_zeigt_in_der_pause_kein_formular(
            self, client, make_challenge, database):
        challenge = make_challenge()
        challenge.paused = True
        database.session.commit()

        html = client.get("/").get_data(as_text=True)

        assert "Registrierung geschlossen" in html
        assert "pausiert" in html
        assert 'name="team"' not in html

    def test_ein_von_hand_abgeschicktes_formular_wird_abgewiesen(
            self, client, make_challenge, database):
        """Das Formular ist weg - der POST kommt trotzdem an und muss scheitern."""
        from models import Team

        challenge = make_challenge()
        # Token holen, solange die Seite noch eines zeigt.
        marke = csrf_token(client, "/")
        self.beendet(challenge, database)

        antwort = client.post("/", data={
            "csrf_token": marke,
            "team": "Die Nachzügler",
            "password": "geheim",
        })

        assert antwort.status_code == 200, "kein Redirect - es wurde nichts angelegt"
        assert "Der Wettbewerb ist beendet" in antwort.get_data(as_text=True)
        assert Team.query.count() == 0

    def test_in_der_pause_ebenso(self, client, make_challenge, database):
        from models import Team

        challenge = make_challenge()
        marke = csrf_token(client, "/")
        challenge.paused = True
        database.session.commit()

        antwort = client.post("/", data={
            "csrf_token": marke,
            "team": "Die Nachzügler",
            "password": "geheim",
        })

        assert antwort.status_code == 200
        assert "pausiert" in antwort.get_data(as_text=True)
        assert Team.query.count() == 0

    def test_vor_dem_start_bleibt_die_anmeldung_offen(
            self, client, make_challenge, database):
        """Genau dann melden sich die Teams an."""
        from datetime import datetime, timedelta
        from models import Team

        challenge = make_challenge()
        challenge.start_time = datetime.now() + timedelta(hours=1)
        database.session.commit()

        html = client.get("/").get_data(as_text=True)
        assert 'name="team"' in html

        assert registrieren(client, "Die Frühen").status_code == 302
        assert Team.query.count() == 1

    def test_ohne_wettbewerb_bleibt_das_formular_stehen(self, client):
        """Frische Installation: Die Lehrkraft soll die Anmeldung ansehen können."""
        html = client.get("/").get_data(as_text=True)

        assert "Registrierung geschlossen" not in html
        assert 'name="team"' in html

    def test_ein_angemeldetes_team_kommt_nach_dem_ende_weiter_hinein(
            self, client, make_challenge, make_team, database):
        challenge = make_challenge()
        make_team(challenge, name="Die Pixelpiraten", password="geheim")
        self.beendet(challenge, database)

        antwort = anmelden(client, "Die Pixelpiraten")

        assert antwort.status_code == 302
        assert "/challenge" in antwort.headers["Location"]
