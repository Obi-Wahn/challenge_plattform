"""Die Teamseite merkt von selbst, wenn sie veraltet ist.

Vorher fragte die Wettbewerbsseite den Server nach dem Laden nie wieder etwas:
Der einzige Zeitgeber zeichnete die Uhr. Drückte die Lehrkraft ⏸ Pause, sah ein
Team mit offener Seite davon nichts, bis es selbst neu lud - ohne einen Anlass
dazu zu haben.

Jetzt liefert der Server eine kurze Kennung dessen mit, was die Seite zeigt
(`seitenstand()`), und die Seite fragt sie im Takt nach. Ist sie eine andere
geworden, lädt die Seite neu. Diese Tests prüfen die Kennung und die Route, die
sie ausgibt - was der Browser daraus macht, steht in challenge.html.
"""

from datetime import datetime, timedelta

from tests.helpers import csrf_token


def frisch(challenge):
    """Den Wettbewerb neu aus der Datenbank holen."""
    from extensions import db
    from models import Challenge

    db.session.expire_all()
    return db.session.get(Challenge, challenge.id)


def stand_von(challenge):
    """Die Kennung, wie der Server sie gerade bilden würde."""
    from blueprints.challenge import seitenstand
    from extensions import db

    db.session.expire_all()
    return seitenstand(challenge)


def geholter_stand(client):
    """Die Kennung, wie ein offener Browser sie über die Route bekommt."""
    antwort = client.get("/challenge/stand")
    assert antwort.status_code == 200
    return antwort.get_json()


class TestDieStandRoute:
    def test_ohne_anmeldung_sagt_sie_es(self, client, make_challenge):
        """Kein angemeldetes Team heißt: Diese Seite gehört auf die Startseite."""
        make_challenge(start_time=datetime.now() - timedelta(minutes=5))

        daten = geholter_stand(client)

        assert daten == {"angemeldet": False}

    def test_ohne_wettbewerb_sagt_sie_es_auch(self, client):
        """Auch ohne jeden Wettbewerb antwortet sie, statt zu scheitern."""
        daten = geholter_stand(client)

        assert daten == {"angemeldet": False}

    def test_ein_angemeldetes_team_bekommt_den_stand(self, make_challenge, logged_in_team):
        challenge = make_challenge(start_time=datetime.now() - timedelta(minutes=5))
        client, _ = logged_in_team(challenge)

        daten = geholter_stand(client)

        assert daten["angemeldet"] is True
        assert daten["stand"] == stand_von(challenge)

    def test_die_antwort_wird_nicht_zwischengespeichert(self, make_challenge, logged_in_team):
        """Eine gecachte Antwort wäre das Gegenteil des Zwecks."""
        challenge = make_challenge(start_time=datetime.now() - timedelta(minutes=5))
        client, _ = logged_in_team(challenge)

        antwort = client.get("/challenge/stand")

        assert antwort.headers["Cache-Control"] == "no-store"

    def test_nach_dem_loeschen_des_wettbewerbs_gilt_die_anmeldung_nicht_mehr(
        self, admin, make_challenge, logged_in_team
    ):
        """Der Fall, in dem die Seite auf die Startseite gehört."""
        challenge = make_challenge(start_time=datetime.now() - timedelta(minutes=5))
        client, _ = logged_in_team(challenge)
        assert geholter_stand(client)["angemeldet"] is True

        admin.post(f"/admin/challenges/{challenge.id}/delete", data={
            "csrf_token": csrf_token(admin, "/admin/challenges/new"),
        })

        assert geholter_stand(client) == {"angemeldet": False}


class TestWasDenStandAendert:
    """Alles hier ist ein Grund, die offene Seite eines Teams neu zu laden."""

    def test_die_pause(self, admin, make_challenge):
        challenge = make_challenge(
            start_time=datetime.now() - timedelta(minutes=5),
            end_time=datetime.now() + timedelta(minutes=30),
        )
        vorher = stand_von(challenge)

        admin.post(f"/admin/challenges/{challenge.id}/pause", data={
            "csrf_token": csrf_token(admin, "/admin/challenges/new"),
        })

        assert frisch(challenge).paused, "Der Wettbewerb wurde gar nicht pausiert"
        assert stand_von(challenge) != vorher

    def test_das_fortsetzen(self, admin, make_challenge):
        challenge = make_challenge(
            start_time=datetime.now() - timedelta(minutes=5),
            end_time=datetime.now() + timedelta(minutes=30),
            paused=True,
            paused_at=datetime.now(),
        )
        pausiert = stand_von(challenge)

        admin.post(f"/admin/challenges/{challenge.id}/resume", data={
            "csrf_token": csrf_token(admin, "/admin/challenges/new"),
        })

        assert not frisch(challenge).paused, "Die Pause läuft noch"
        assert stand_von(challenge) != pausiert

    def test_ein_freigeschalteter_hinweis(self, admin, make_challenge, make_task):
        """Das war bisher die Zeile in der Anleitung, die nicht stimmte."""
        challenge = make_challenge(start_time=datetime.now() - timedelta(minutes=5))
        task = make_task(challenge, hint="Schau dir die Schleife an.")
        vorher = stand_von(challenge)

        admin.post(f"/admin/tasks/{task.id}/toggle_hint", data={
            "csrf_token": csrf_token(admin, "/admin/challenges/new"),
        })

        from extensions import db
        from models import Task
        db.session.expire_all()
        assert db.session.get(Task, task.id).hint_visible, "Der Hinweis ist nicht frei"
        assert stand_von(challenge) != vorher

    def test_eine_neue_aufgabe(self, make_challenge, make_task):
        challenge = make_challenge(start_time=datetime.now() - timedelta(minutes=5))
        make_task(challenge, title="Erste")
        vorher = stand_von(challenge)

        make_task(challenge, title="Zweite")

        assert stand_von(challenge) != vorher

    def test_eine_neue_dauer(self, admin, make_challenge):
        """Die Uhr im Browser weiß nichts von einer verschobenen Endzeit."""
        challenge = make_challenge(start_time=datetime.now() - timedelta(minutes=5),
                                   end_time=datetime.now() + timedelta(minutes=10))
        vorher = stand_von(challenge)

        admin.post(f"/admin/challenges/{challenge.id}/jetzt-starten", data={
            "csrf_token": csrf_token(admin, "/admin/challenges/new"),
            "duration_minutes": "45",
        })

        neu = frisch(challenge)
        assert neu.duration_minutes == 45, "Die Dauer wurde nicht gesetzt"
        assert stand_von(challenge) != vorher

    def test_das_ende_des_wettbewerbs(self, admin, make_challenge):
        challenge = make_challenge(start_time=datetime.now() - timedelta(minutes=5),
                                   end_time=datetime.now() + timedelta(minutes=30))
        vorher = stand_von(challenge)

        admin.post(f"/admin/challenges/{challenge.id}/finish", data={
            "csrf_token": csrf_token(admin, "/admin/challenges/new"),
        })

        assert frisch(challenge).status() == "finished", "Der Wettbewerb läuft noch"
        assert stand_von(challenge) != vorher


class TestWasDenStandNichtAendert:
    """Ein Neuladen mitten im Arbeiten kostet mehr, als es hier brächte."""

    def test_eine_bewertung_nicht(self, admin, make_challenge, make_task,
                                  logged_in_team, upload):
        challenge = make_challenge(start_time=datetime.now() - timedelta(minutes=5))
        task = make_task(challenge)
        client, _ = logged_in_team(challenge)
        client.post(f"/submit/{task.id}", data={
            "csrf_token": csrf_token(client, "/challenge"),
            "file": upload(),
        }, content_type="multipart/form-data")

        from models import Submission
        submission = Submission.query.first()
        vorher = stand_von(challenge)

        admin.post("/admin/submissions", data={
            "csrf_token": csrf_token(admin, "/admin/challenges/new"),
            "submission_id": str(submission.id),
            "points": "8",
            "feedback": "Schön gemacht.",
        })

        from extensions import db
        db.session.expire_all()
        bewertet = db.session.get(Submission, submission.id)
        assert bewertet.points == 8, "Die Abgabe wurde gar nicht bewertet"
        assert stand_von(challenge) == vorher

    def test_das_bloße_vergehen_von_zeit_nicht(self, make_challenge):
        """Sonst lüde die Seite im Takt neu, ohne dass sich etwas getan hat."""
        challenge = make_challenge(start_time=datetime.now() - timedelta(minutes=5),
                                   end_time=datetime.now() + timedelta(minutes=30))

        assert stand_von(challenge) == stand_von(challenge)

    def test_die_pause_und_das_fortsetzen_heben_sich_auf(self, admin, make_challenge):
        """Nach der Pause steht wieder derselbe Stand wie davor - bis auf die
        verschobene Endzeit, die ja gerade mitzählt."""
        challenge = make_challenge(start_time=datetime.now() - timedelta(minutes=5))
        vorher = stand_von(challenge)

        token = csrf_token(admin, "/admin/challenges/new")
        admin.post(f"/admin/challenges/{challenge.id}/pause", data={"csrf_token": token})
        admin.post(f"/admin/challenges/{challenge.id}/resume", data={"csrf_token": token})

        assert stand_von(challenge) == vorher


class TestDieSeiteBringtDieAbfrageMit:
    def test_der_stand_steht_in_der_seite(self, make_challenge, logged_in_team):
        challenge = make_challenge(start_time=datetime.now() - timedelta(minutes=5))
        client, _ = logged_in_team(challenge)

        html = client.get("/challenge").get_data(as_text=True)

        assert stand_von(challenge) in html
        assert "/challenge/stand" in html

    def test_auch_ohne_gesetzte_zeit(self, make_challenge, logged_in_team):
        """Die Abfrage hängt nicht an der Uhr: Ohne Zeit gibt es keine, die
        Pause muss aber trotzdem ankommen."""
        challenge = make_challenge()
        client, _ = logged_in_team(challenge)

        html = client.get("/challenge").get_data(as_text=True)

        assert "/challenge/stand" in html


class TestDerPausenkasten:
    def test_er_steht_in_der_pause_auf_der_seite(self, make_challenge, logged_in_team):
        challenge = make_challenge(
            start_time=datetime.now() - timedelta(minutes=5),
            end_time=datetime.now() + timedelta(minutes=30),
            paused=True,
            paused_at=datetime.now(),
        )
        client, _ = logged_in_team(challenge)

        html = client.get("/challenge").get_data(as_text=True)

        assert "pause-kasten" in html
        assert "Kurze Pause" in html

    def test_ohne_pause_fehlt_er(self, make_challenge, logged_in_team):
        challenge = make_challenge(start_time=datetime.now() - timedelta(minutes=5))
        client, _ = logged_in_team(challenge)

        html = client.get("/challenge").get_data(as_text=True)

        assert "pause-kasten" not in html

    def test_die_aufgaben_bleiben_in_der_pause_lesbar(self, make_challenge, make_task,
                                                     logged_in_team):
        """Die bewusste Entscheidung gegen einen blockierenden Vollbildschirm:
        nachdenken und nachlesen darf ein Team, nur abgeben nicht."""
        challenge = make_challenge(start_time=datetime.now() - timedelta(minutes=5),
                                   paused=True, paused_at=datetime.now())
        make_task(challenge, title="Hüpfende Katze")
        client, _ = logged_in_team(challenge)

        html = client.get("/challenge").get_data(as_text=True)

        assert "Hüpfende Katze" in html
        assert "pause-kasten" in html
