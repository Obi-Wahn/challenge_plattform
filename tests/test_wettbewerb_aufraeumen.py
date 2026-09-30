"""Aufräumen nach dem Wettbewerb.

Bei einem beendeten Wettbewerb löscht „Aufräumen“ Teams, Namen, Passwörter
und Abgaben samt Dateien; Wettbewerb, Einstellungen und Aufgaben bleiben.
Dazu leeren zwei Knöpfe in den Einstellungen die Protokolldatei und löschen
die Sicherungskopien der Datenbank - dort stehen sonst weiter Teamnamen.
"""

import os
from datetime import datetime, timedelta

from tests.helpers import TMP_DIR, csrf_token


def frisch(challenge):
    from extensions import db
    from models import Challenge

    db.session.expire_all()
    return db.session.get(Challenge, challenge.id)


def posten(admin, pfad, daten=None):
    daten = dict(daten or {})
    daten["csrf_token"] = csrf_token(admin, "/admin/challenges/new")
    return admin.post(pfad, data=daten, follow_redirects=True)


def abgabe_mit_datei(flask_app, database, team, task, punkte=7):
    from models import Submission

    ordner = os.path.join(flask_app.config["UPLOAD_FOLDER"], str(team.id))
    os.makedirs(ordner, exist_ok=True)
    pfad = os.path.join(ordner, f"task_{task.id}_aufraeumen.sb3")
    with open(pfad, "wb") as datei:
        datei.write(b"projekt")
    database.session.add(Submission(team_id=team.id, task_id=task.id, filename=pfad,
                                    points=punkte, feedback="Gut gemacht, Lena!"))
    database.session.commit()
    return pfad


def beendeter_wettbewerb(flask_app, database, make_challenge, make_team, make_task, **kwargs):
    challenge = make_challenge(
        start_time=datetime.now() - timedelta(minutes=90),
        end_time=datetime.now() - timedelta(minutes=5),
        tagline="Herbst 2026",
        **kwargs,
    )
    task = make_task(challenge, title="Die Katze läuft")
    team = make_team(challenge, name="Team Lena")
    team.member_names = "Lena Muster\nTom Beispiel"
    team.members_approved = True
    database.session.commit()
    pfad = abgabe_mit_datei(flask_app, database, team, task)
    return challenge, pfad


class TestAufraeumen:
    def test_teams_und_abgaben_sind_weg(self, admin, flask_app, database, make_challenge,
                                        make_team, make_task):
        from models import Submission, Team

        challenge, pfad = beendeter_wettbewerb(flask_app, database, make_challenge,
                                               make_team, make_task)
        antwort = posten(admin, f"/admin/challenges/{challenge.id}/aufraeumen")

        assert "Aufgeräumt: 1 Team(s) und 1 Abgabe(n)" in antwort.get_data(as_text=True)
        assert Team.query.filter_by(challenge_id=challenge.id).count() == 0
        assert Submission.query.count() == 0
        assert not os.path.exists(pfad), "die Datei der Abgabe muss mitgehen"

    def test_wettbewerb_einstellungen_und_aufgaben_bleiben(
            self, admin, flask_app, database, make_challenge, make_team, make_task):
        challenge, _pfad = beendeter_wettbewerb(
            flask_app, database, make_challenge, make_team, make_task,
            freeze_enabled=True, freeze_minutes=20, announcements_enabled=True)
        posten(admin, f"/admin/challenges/{challenge.id}/aufraeumen")

        challenge = frisch(challenge)
        assert challenge.title == "Test-Wettbewerb"
        assert challenge.tagline == "Herbst 2026"
        assert challenge.end_time is not None
        assert challenge.freeze_enabled and challenge.freeze_minutes == 20
        assert challenge.announcements_enabled
        assert [t.title for t in challenge.tasks] == ["Die Katze läuft"]

    def test_eine_durchsage_faellt_mit_weg(self, admin, flask_app, database, make_challenge,
                                           make_team, make_task):
        challenge, _pfad = beendeter_wettbewerb(
            flask_app, database, make_challenge, make_team, make_task,
            announcements_enabled=True, announcement_text="Lena, bitte zur Tafel",
            announcement_at=datetime.now())
        posten(admin, f"/admin/challenges/{challenge.id}/aufraeumen")
        assert frisch(challenge).announcement_text == ""

    def test_nur_bei_beendetem_wettbewerb(self, admin, flask_app, database, make_challenge,
                                          make_team, make_task):
        from models import Team

        challenge = make_challenge(start_time=datetime.now() - timedelta(minutes=5),
                                   end_time=datetime.now() + timedelta(minutes=40))
        make_team(challenge, name="Team Lena")

        antwort = posten(admin, f"/admin/challenges/{challenge.id}/aufraeumen")
        assert "erst, wenn der Wettbewerb beendet ist" in antwort.get_data(as_text=True)
        assert Team.query.filter_by(challenge_id=challenge.id).count() == 1

    def test_der_knopf_steht_nur_bei_beendeten(self, admin, flask_app, database,
                                               make_challenge, make_team, make_task):
        laufend = make_challenge(title="Laufend", start_time=datetime.now(),
                                 end_time=datetime.now() + timedelta(minutes=40))
        make_team(laufend, name="Team Tom")
        html = admin.get(f"/admin/wettbewerb/{laufend.id}").get_data(as_text=True)
        assert "🧹 Aufräumen" not in html

        beendet, _pfad = beendeter_wettbewerb(flask_app, database, make_challenge,
                                              make_team, make_task, active=False)
        html = admin.get(f"/admin/wettbewerb/{beendet.id}").get_data(as_text=True)
        assert "🧹 Aufräumen" in html
        assert "sichert vorher oben" in html

    def test_ohne_teams_gibt_es_nichts_aufzuraeumen(self, admin, make_challenge):
        challenge = make_challenge(end_time=datetime.now() - timedelta(minutes=5))
        html = admin.get(f"/admin/wettbewerb/{challenge.id}").get_data(as_text=True)
        assert "🧹 Aufräumen" not in html

    def test_nur_fuer_die_lehrkraft(self, client, flask_app, database, make_challenge,
                                    make_team, make_task):
        from models import Team

        challenge, _pfad = beendeter_wettbewerb(flask_app, database, make_challenge,
                                                make_team, make_task)
        client.post(f"/admin/challenges/{challenge.id}/aufraeumen",
                    data={"csrf_token": csrf_token(client, "/admin/login")})
        assert Team.query.count() == 1

    def test_das_protokoll_nennt_zahlen_aber_keine_namen(
            self, admin, flask_app, database, make_challenge, make_team, make_task):
        challenge, _pfad = beendeter_wettbewerb(flask_app, database, make_challenge,
                                                make_team, make_task)
        posten(admin, f"/admin/challenges/{challenge.id}/aufraeumen")

        with open(os.path.join(flask_app.config["LOG_DIR"], "anwendung.log"),
                  encoding="utf-8") as datei:
            zeile = [z for z in datei if "aufgeräumt" in z][-1]
        assert "1 Team(s) und 1 Abgabe(n)" in zeile
        assert "Lena" not in zeile

    def test_rangliste_ist_danach_leer(self, admin, client, flask_app, database,
                                       make_challenge, make_team, make_task):
        challenge, _pfad = beendeter_wettbewerb(flask_app, database, make_challenge,
                                                make_team, make_task)
        posten(admin, f"/admin/challenges/{challenge.id}/aufraeumen")
        html = client.get("/scoreboard").get_data(as_text=True)
        assert "Team Lena" not in html


class TestProtokollLeeren:
    def pfad(self, flask_app):
        return os.path.join(flask_app.config["LOG_DIR"], "anwendung.log")

    def test_leert_die_datei_und_schreibt_danach_weiter(self, admin, flask_app):
        from protokoll import ereignis

        ereignis("Team angelegt: „Team Lena“ von 10.0.0.23")
        alt = self.pfad(flask_app) + ".1"
        with open(alt, "w", encoding="utf-8") as datei:
            datei.write("älterer Stand mit Team Lena\n")

        posten(admin, "/admin/protokoll-leeren")

        with open(self.pfad(flask_app), encoding="utf-8") as datei:
            text = datei.read()
        assert "Team Lena" not in text
        assert "10.0.0.23" not in text
        assert "Protokolldatei geleert" in text
        assert "\x00" not in text, "der Handler muss am Anfang weiterschreiben"
        assert not os.path.exists(alt)

        ereignis("Danach geht es weiter")
        with open(self.pfad(flask_app), encoding="utf-8") as datei:
            assert "Danach geht es weiter" in datei.read()

    def test_die_einstellungen_zeigen_den_knopf(self, admin):
        html = admin.get("/admin/settings").get_data(as_text=True)
        assert "🧹 Protokoll leeren" in html
        assert "🧹 Kopien löschen" in html

    def test_nur_fuer_die_lehrkraft(self, client, flask_app):
        from protokoll import ereignis

        ereignis("Bleibt stehen: Team Tom")
        client.post("/admin/protokoll-leeren",
                    data={"csrf_token": csrf_token(client, "/admin/login")})
        with open(self.pfad(flask_app), encoding="utf-8") as datei:
            assert "Bleibt stehen: Team Tom" in datei.read()


class TestSicherungskopienLoeschen:
    def kopie(self, name):
        pfad = os.path.join(TMP_DIR, name)
        with open(pfad, "wb") as datei:
            datei.write(b"SQLite format 3\x00")
        return pfad

    def test_loescht_nur_die_kopien(self, admin):
        kopie = self.kopie("test-vor-spalten-2026-09-28-0830.db")
        fremd = self.kopie("andere-datei.db")
        try:
            html = admin.get("/admin/settings").get_data(as_text=True)
            assert "test-vor-spalten-2026-09-28-0830.db" in html

            antwort = posten(admin, "/admin/sicherungskopien-loeschen")
            assert "1 Sicherungskopie(n) gelöscht" in antwort.get_data(as_text=True)
            assert not os.path.exists(kopie)
            assert os.path.exists(fremd), "nur Kopien nach dem Muster, nichts sonst"
            assert os.path.exists(os.path.join(TMP_DIR, "test.db")), "die Datenbank bleibt"
        finally:
            for pfad in (kopie, fremd):
                if os.path.exists(pfad):
                    os.remove(pfad)

    def test_ohne_kopien_ist_der_knopf_aus(self, admin):
        html = admin.get("/admin/settings").get_data(as_text=True)
        start = html.index("🧹 Kopien löschen")
        assert "disabled" in html[html.rindex("<button", 0, start):start]
