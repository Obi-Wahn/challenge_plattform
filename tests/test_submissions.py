"""Abgaben: wann sie erlaubt sind und was eine Korrektur macht."""

from datetime import datetime, timedelta

from tests.conftest import csrf_token


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
