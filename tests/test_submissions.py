"""Abgaben: wann sie erlaubt sind und was eine Korrektur macht."""

from datetime import datetime, timedelta

from tests.helpers import csrf_token


def abgeben(client, task, dateiname="loesung.sb3", inhalt=b"projekt"):
    import io

    return client.post(f"/submit/{task.id}", data={
        "csrf_token": csrf_token(client, "/"),
        "file": (io.BytesIO(inhalt), dateiname),
    }, content_type="multipart/form-data")


def test_abgabe_wird_gespeichert(make_challenge, make_task, logged_in_team, database):
    from models import Submission

    challenge = make_challenge()
    task = make_task(challenge)
    client, team = logged_in_team(challenge)

    antwort = abgeben(client, task)

    assert antwort.status_code == 302
    abgabe = Submission.query.filter_by(team_id=team.id, task_id=task.id).one()
    assert abgabe.points is None
    assert abgabe.filename.endswith("loesung.sb3")


def test_falsches_dateiformat_wird_abgewiesen(make_challenge, make_task, logged_in_team):
    from models import Submission

    challenge = make_challenge()
    task = make_task(challenge, allowed_extension=".sb3")
    client, _team = logged_in_team(challenge)

    antwort = abgeben(client, task, dateiname="loesung.exe")

    assert antwort.status_code == 400
    assert Submission.query.count() == 0


def test_ohne_anmeldung_keine_abgabe(client, make_challenge, make_task):
    challenge = make_challenge()
    task = make_task(challenge)

    assert abgeben(client, task).status_code == 403


def test_aufgabe_aus_fremdem_wettbewerb_wird_abgewiesen(
        make_challenge, make_task, logged_in_team):
    aktuell = make_challenge(title="Aktuell", active=True)
    fremd = make_challenge(title="Fremd", active=False)
    fremde_aufgabe = make_task(fremd)
    client, _team = logged_in_team(aktuell)

    assert abgeben(client, fremde_aufgabe).status_code == 403


def test_team_eines_anderen_wettbewerbs_darf_nicht_abgeben(
        flask_app, make_challenge, make_task, logged_in_team):
    alt = make_challenge(title="Alt", active=True)
    client, _team = logged_in_team(alt)

    alt.active = False
    neu = make_challenge(title="Neu", active=True)
    aufgabe = make_task(neu)

    assert abgeben(client, aufgabe).status_code == 403


def test_pause_sperrt_die_abgabe(make_challenge, make_task, logged_in_team, database):
    challenge = make_challenge()
    task = make_task(challenge)
    client, _team = logged_in_team(challenge)

    challenge.paused = True
    database.session.commit()

    assert abgeben(client, task).status_code == 403


def test_beendeter_wettbewerb_sperrt_die_abgabe(
        make_challenge, make_task, logged_in_team, database):
    challenge = make_challenge()
    task = make_task(challenge)
    client, _team = logged_in_team(challenge)

    challenge.end_time = datetime.now() - timedelta(minutes=1)
    database.session.commit()

    assert abgeben(client, task).status_code == 403


def test_zweite_abgabe_ohne_freigabe_wird_abgewiesen(
        make_challenge, make_task, logged_in_team):
    challenge = make_challenge()
    task = make_task(challenge)
    client, _team = logged_in_team(challenge)

    assert abgeben(client, task).status_code == 302
    assert abgeben(client, task).status_code == 403


class TestKorrektur:
    def test_freigabe_erlaubt_genau_eine_weitere_abgabe(
            self, admin, make_challenge, make_task, logged_in_team, database):
        from models import Submission

        challenge = make_challenge()
        task = make_task(challenge)
        client, team = logged_in_team(challenge)
        abgeben(client, task, inhalt=b"erster versuch")

        abgabe = Submission.query.one()
        admin.post(f"/admin/submissions/{abgabe.id}/allow_resubmit", data={
            "csrf_token": csrf_token(admin, "/admin/submissions"),
        })

        assert abgeben(client, task, inhalt=b"zweiter versuch").status_code == 302
        # Die Freigabe ist damit aufgebraucht.
        assert abgeben(client, task, inhalt=b"dritter versuch").status_code == 403

    def test_korrektur_loescht_die_alte_bewertung(
            self, admin, make_challenge, make_task, logged_in_team, database):
        """Die Abgabe muss zurück in die Warteschlange der Lehrkraft."""
        from models import Submission

        challenge = make_challenge()
        task = make_task(challenge)
        client, _team = logged_in_team(challenge)
        abgeben(client, task)

        abgabe = Submission.query.one()
        abgabe.points = 7
        abgabe.feedback = "Gut gemacht"
        abgabe.resubmit_allowed = True
        database.session.commit()

        abgeben(client, task, inhalt=b"neue fassung")

        database.session.refresh(abgabe)
        assert abgabe.points is None
        assert abgabe.feedback is None
        assert abgabe.resubmit_allowed is False

    def test_korrektur_legt_keine_zweite_abgabe_an(
            self, admin, make_challenge, make_task, logged_in_team, database):
        from models import Submission

        challenge = make_challenge()
        task = make_task(challenge)
        client, _team = logged_in_team(challenge)
        abgeben(client, task)

        abgabe = Submission.query.one()
        abgabe.resubmit_allowed = True
        database.session.commit()

        abgeben(client, task, dateiname="andere.sb3")

        assert Submission.query.count() == 1


class TestBewertung:
    def test_punkte_und_feedback_werden_gespeichert(
            self, admin, make_challenge, make_task, logged_in_team, database):
        from models import Submission

        challenge = make_challenge()
        task = make_task(challenge, max_points=10)
        client, _team = logged_in_team(challenge)
        abgeben(client, task)
        abgabe = Submission.query.one()

        admin.post("/admin/submissions", data={
            "csrf_token": csrf_token(admin, "/admin/submissions"),
            "submission_id": abgabe.id,
            "points": "8",
            "feedback": "Schön gelöst",
        })

        database.session.refresh(abgabe)
        assert abgabe.points == 8
        assert abgabe.feedback == "Schön gelöst"

    def test_punkte_werden_auf_das_maximum_begrenzt(
            self, admin, make_challenge, make_task, logged_in_team, database):
        from models import Submission

        challenge = make_challenge()
        task = make_task(challenge, max_points=10)
        client, _team = logged_in_team(challenge)
        abgeben(client, task)
        abgabe = Submission.query.one()

        admin.post("/admin/submissions", data={
            "csrf_token": csrf_token(admin, "/admin/submissions"),
            "submission_id": abgabe.id,
            "points": "999",
        })

        database.session.refresh(abgabe)
        assert abgabe.points == 10

    def test_negative_punkte_werden_zu_null(
            self, admin, make_challenge, make_task, logged_in_team, database):
        from models import Submission

        challenge = make_challenge()
        task = make_task(challenge, max_points=10)
        client, _team = logged_in_team(challenge)
        abgeben(client, task)
        abgabe = Submission.query.one()

        admin.post("/admin/submissions", data={
            "csrf_token": csrf_token(admin, "/admin/submissions"),
            "submission_id": abgabe.id,
            "points": "-5",
        })

        database.session.refresh(abgabe)
        assert abgabe.points == 0

    def test_bewertungsliste_zeigt_nur_den_aktuellen_wettbewerb(
            self, admin, flask_app, make_challenge, make_task, logged_in_team, database):
        alt = make_challenge(title="Alt", active=True)
        alte_aufgabe = make_task(alt, title="Alte Aufgabe")
        client, _team = logged_in_team(alt, name="Altes Team")
        abgeben(client, alte_aufgabe)

        alt.active = False
        neu = make_challenge(title="Neu", active=True)
        make_task(neu, title="Neue Aufgabe")
        database.session.commit()

        html = admin.get("/admin/submissions").get_data(as_text=True)

        assert "Altes Team" not in html
        assert "Alte Aufgabe" not in html


class TestLangeDateinamen:
    """Ein absurd langer Dateiname darf die Abgabe nicht scheitern lassen.

    Dateisysteme lassen meist 255 Zeichen je Namensbestandteil zu. Darüber
    scheitert das Speichern mit einem OSError - und für das Team sähe das
    aus wie eine kaputte Seite, mitten im Wettbewerb.
    """

    def test_ein_sehr_langer_name_wird_gekuerzt_statt_abgewiesen(
            self, make_challenge, make_task, logged_in_team, database):
        import os

        from models import Submission

        challenge = make_challenge()
        task = make_task(challenge)
        client, team = logged_in_team(challenge)

        antwort = abgeben(client, task, dateiname="x" * 300 + ".sb3")

        assert antwort.status_code == 302
        abgabe = Submission.query.filter_by(team_id=team.id, task_id=task.id).one()
        # Die Datei liegt wirklich da - genau das schlug vorher fehl.
        assert os.path.exists(abgabe.filename)

    def test_die_endung_bleibt_erhalten(
            self, make_challenge, make_task, logged_in_team, database):
        from models import Submission

        challenge = make_challenge()
        task = make_task(challenge)
        client, team = logged_in_team(challenge)

        abgeben(client, task, dateiname="y" * 300 + ".sb3")

        abgabe = Submission.query.filter_by(team_id=team.id, task_id=task.id).one()
        # Der Download in der Verwaltung nimmt die Endung aus diesem Namen.
        assert abgabe.filename.endswith(".sb3")

    def test_der_abgelegte_name_haelt_die_grenze_ein(
            self, make_challenge, make_task, logged_in_team, database):
        import os

        from blueprints.challenge import MAX_DATEINAME
        from models import Submission

        challenge = make_challenge()
        task = make_task(challenge)
        client, team = logged_in_team(challenge)

        abgeben(client, task, dateiname="z" * 300 + ".sb3")

        abgabe = Submission.query.filter_by(team_id=team.id, task_id=task.id).one()
        name = os.path.basename(abgabe.filename)
        # "task_<nummer>_" kommt noch davor, deshalb etwas Luft nach oben.
        assert len(name) <= MAX_DATEINAME + 20

    def test_ein_gewoehnlicher_name_bleibt_wie_er_ist(
            self, make_challenge, make_task, logged_in_team, database):
        from models import Submission

        challenge = make_challenge()
        task = make_task(challenge)
        client, team = logged_in_team(challenge)

        abgeben(client, task, dateiname="loesung.sb3")

        abgabe = Submission.query.filter_by(team_id=team.id, task_id=task.id).one()
        assert abgabe.filename.endswith("loesung.sb3")


class TestGekuerzterDateiname:
    def test_kurze_namen_bleiben_unveraendert(self):
        from blueprints.challenge import gekuerzter_dateiname

        assert gekuerzter_dateiname("loesung.sb3") == "loesung.sb3"

    def test_lange_namen_werden_auf_die_grenze_gebracht(self):
        from blueprints.challenge import MAX_DATEINAME, gekuerzter_dateiname

        ergebnis = gekuerzter_dateiname("a" * 300 + ".sb3")

        assert len(ergebnis) == MAX_DATEINAME
        assert ergebnis.endswith(".sb3")

    def test_auch_eine_absurde_endung_wird_mitgekuerzt(self):
        """Was länger ist als jede erlaubte Endung, ist auch nur Name."""
        from blueprints.challenge import MAX_DATEINAME, gekuerzter_dateiname

        ergebnis = gekuerzter_dateiname("a.b" + "c" * 400)

        assert len(ergebnis) <= MAX_DATEINAME

    def test_ein_name_ohne_punkt_wird_einfach_gekuerzt(self):
        from blueprints.challenge import MAX_DATEINAME, gekuerzter_dateiname

        ergebnis = gekuerzter_dateiname("a" * 300)

        assert len(ergebnis) == MAX_DATEINAME
