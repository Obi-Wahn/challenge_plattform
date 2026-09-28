"""Prüft die Protokolldatei.

Sie ist dafür da, dass eine Störung am Wettbewerbstag nachvollziehbar
bleibt, auch wenn niemand das Terminalfenster im Blick hatte.
"""

import logging
import os

from app import LOG_HANDLER_NAME, configure_logging


def logdatei(flask_app):
    return os.path.join(flask_app.config["LOG_DIR"], "anwendung.log")


def inhalt(flask_app):
    pfad = logdatei(flask_app)
    if not os.path.exists(pfad):
        return ""
    with open(pfad, encoding="utf-8") as datei:
        return datei.read()


class TestEinrichtung:
    def test_datei_wird_angelegt(self, flask_app):
        flask_app.logger.info("Prüfzeile")
        assert os.path.exists(logdatei(flask_app))

    def test_schreibt_nicht_in_die_laufende_installation(self, flask_app):
        # Wäre LOG_DIR nicht umgebogen, liefe dieser Test in logs/ des Repos.
        assert flask_app.config["LOG_DIR"].startswith(os.path.dirname(
            flask_app.config["UPLOAD_FOLDER"]))

    def test_zweiter_aufruf_haengt_keinen_zweiten_handler_an(self, flask_app):
        vorher = [h for h in flask_app.logger.handlers if h.name == LOG_HANDLER_NAME]
        configure_logging(flask_app)
        nachher = [h for h in flask_app.logger.handlers if h.name == LOG_HANDLER_NAME]
        assert len(vorher) == len(nachher) == 1

    def test_datei_rotiert_statt_unbegrenzt_zu_wachsen(self, flask_app):
        handler = next(h for h in flask_app.logger.handlers if h.name == LOG_HANDLER_NAME)
        assert handler.maxBytes > 0
        assert handler.backupCount > 0

    def test_waitress_meldungen_landen_in_derselben_datei(self, flask_app):
        handler = next(h for h in flask_app.logger.handlers if h.name == LOG_HANDLER_NAME)
        assert handler in logging.getLogger("waitress").handlers


class TestInhalt:
    def test_meldung_steht_mit_zeitstempel_in_der_datei(self, flask_app):
        flask_app.logger.warning("Testmeldung 12345")
        text = inhalt(flask_app)
        assert "Testmeldung 12345" in text
        # Ohne Zeitstempel ist im Nachhinein nicht zuzuordnen, wann es war.
        zeile = [z for z in text.splitlines() if "Testmeldung 12345" in z][-1]
        assert zeile[:4].isdigit(), f"kein Datum am Zeilenanfang: {zeile!r}"
        assert "WARNING" in zeile

    def test_unbehandelter_fehler_wird_protokolliert(self, flask_app, monkeypatch,
                                                      make_challenge):
        """Der eigentliche Zweck: Ein Absturz einer Seite hinterlässt eine Spur.

        Geprüft an einer echten Seite - die Rangliste wird von innen heraus
        zum Scheitern gebracht, statt eine Testroute anzulegen.
        """
        make_challenge(active=True)

        def kaputt(challenge):
            raise RuntimeError("Absicht: kaputte Rangliste")

        monkeypatch.setattr("blueprints.public.get_standings", kaputt)

        # Flask reicht Ausnahmen im Testmodus sonst durch, statt sie zu
        # protokollieren - im echten Betrieb ist es andersherum.
        monkeypatch.setitem(flask_app.config, "PROPAGATE_EXCEPTIONS", False)

        antwort = flask_app.test_client().get("/scoreboard")
        assert antwort.status_code == 500

        text = inhalt(flask_app)
        assert "Absicht: kaputte Rangliste" in text
        assert "Traceback" in text, "ohne Traceback ist die Spur wertlos"
        assert "/scoreboard" in text, "ohne die Adresse ist unklar, wo es knallte"

    def test_normale_seiten_erzeugen_keine_fehlermeldung(self, flask_app):
        vorher = inhalt(flask_app)
        flask_app.test_client().get("/")
        neu = inhalt(flask_app)[len(vorher):]
        assert "ERROR" not in neu


# ----------------------------------------------------- Die einzelnen Ereignisse
#
# Was hier geprüft wird, hat Tobias am 26.09.2026 festgelegt: Ins Protokoll
# geht, was etwas anlegt, ändert oder wegnimmt, und was schiefgeht. Der
# gewöhnliche Betrieb bleibt still - eine eingegangene Abgabe, eine Anmeldung,
# eine Bewertung, ein Seitenaufruf. Die Klasse TestWasStillBleibt am Ende hält
# genau diese Entscheidung fest: Sie ist der Grund, warum die Datei am
# Wettbewerbstag noch zu lesen ist.

import pytest

from tests.helpers import csrf_token


@pytest.fixture
def protokoll(flask_app):
    """Gibt den Text zurück, der seit dem letzten Blick dazugekommen ist."""
    class Mitschrift:
        def __init__(self):
            self.stand = len(inhalt(flask_app))

        def neu(self):
            text = inhalt(flask_app)[self.stand:]
            self.stand += len(text)
            return text

    return Mitschrift()


def neuer_wettbewerb(admin, titel="Protokollwettbewerb", **felder):
    daten = {
        "csrf_token": csrf_token(admin, "/admin/challenges/new"),
        "title": titel,
    }
    daten.update(felder)
    return admin.post("/admin/challenges/new", data=daten)


class TestAufbauUndVerwaltung:
    def test_wettbewerb_angelegt(self, admin, protokoll):
        neuer_wettbewerb(admin, "Scratch-Tag")
        assert "Wettbewerb angelegt: „Scratch-Tag“" in protokoll.neu()

    def test_uebernommene_teams_stehen_mit_anzahl_da(self, admin, protokoll,
                                                     make_challenge, make_team):
        alt = make_challenge(title="Wettbewerb davor")
        make_team(alt, name="Team Eins")
        make_team(alt, name="Team Zwei")
        protokoll.neu()

        neuer_wettbewerb(admin, "Zweiter Tag", copy_teams="1")

        zeilen = protokoll.neu()
        assert "Teams übernommen aus „Wettbewerb davor“: 2 Team(s)" in zeilen

    def test_wettbewerb_bearbeitet(self, admin, protokoll, make_challenge):
        challenge = make_challenge(title="Vorher")
        protokoll.neu()

        admin.post(f"/admin/challenges/{challenge.id}/edit", data={
            "csrf_token": csrf_token(admin, f"/admin/challenges/{challenge.id}/edit"),
            "title": "Nachher",
        })

        assert "Wettbewerb bearbeitet: „Nachher“" in protokoll.neu()

    def test_wettbewerb_aktiv_geschaltet(self, admin, protokoll, make_challenge):
        challenge = make_challenge(title="Der nächste", active=False)
        protokoll.neu()

        admin.post(f"/admin/challenge/{challenge.id}/activate", data={
            "csrf_token": csrf_token(admin, "/admin/challenges/new"),
        })

        assert "Wettbewerb aktiv geschaltet: „Der nächste“" in protokoll.neu()

    def test_geloeschter_wettbewerb_hinterlaesst_seinen_umfang(
            self, admin, protokoll, make_challenge, make_team, make_task):
        """Nach dem Löschen sagt nur noch das Protokoll, was da verschwunden ist."""
        challenge = make_challenge(title="Weg damit")
        make_team(challenge, name="Team Eins")
        make_task(challenge, title="Aufgabe Eins")
        protokoll.neu()

        admin.post(f"/admin/challenges/{challenge.id}/delete", data={
            "csrf_token": csrf_token(admin, "/admin/challenges/new"),
        })

        zeile = protokoll.neu()
        assert "Wettbewerb gelöscht: „Weg damit“" in zeile
        assert "1 Team(s) und 1 Aufgabe(n)" in zeile

    def test_team_angelegt(self, protokoll, client, make_challenge):
        make_challenge(title="Anmeldetag")
        client.post("/", data={
            "csrf_token": csrf_token(client, "/"),
            "team": "Die Pixelpiraten",
            "password": "geheim123",
        })

        zeile = protokoll.neu()
        assert "Team angelegt: „Die Pixelpiraten“" in zeile
        assert "Anmeldetag" in zeile

    def test_team_geloescht(self, admin, protokoll, make_challenge, make_team):
        challenge = make_challenge()
        team = make_team(challenge, name="Team Weg")
        protokoll.neu()

        admin.post(f"/admin/team/delete/{team.id}", data={
            "csrf_token": csrf_token(admin, "/admin/challenges/new"),
        })

        assert "Team gelöscht: „Team Weg“" in protokoll.neu()

    def test_zurueckgesetztes_passwort_steht_nicht_in_der_datei(
            self, admin, protokoll, make_challenge, make_team):
        """Die Protokolldatei liegt offen im Verzeichnis - ohne Passwörter."""
        challenge = make_challenge()
        team = make_team(challenge, name="Team Neu")
        protokoll.neu()

        admin.post(f"/admin/team/{team.id}/reset_password", data={
            "csrf_token": csrf_token(admin, "/admin/challenges/new"),
            "new_password": "supergeheim42",
        })

        zeile = protokoll.neu()
        assert "Passwort von Team „Team Neu“" in zeile
        assert "zurückgesetzt" in zeile
        assert "supergeheim42" not in zeile

    def test_aufgabe_angelegt_bearbeitet_geloescht(self, admin, protokoll,
                                                  make_challenge, database):
        from models import Task

        challenge = make_challenge(title="Aufgabentag")
        protokoll.neu()

        admin.post(f"/admin/challenges/{challenge.id}/tasks", data={
            "csrf_token": csrf_token(admin, f"/admin/challenges/{challenge.id}/tasks"),
            "title": "Katze bewegen",
            "max_points": "10",
            "allowed_extension": ".sb3",
        })
        assert "Aufgabe angelegt: „Katze bewegen“" in protokoll.neu()

        task = Task.query.filter_by(title="Katze bewegen").one()
        admin.post(f"/admin/tasks/{task.id}/edit", data={
            "csrf_token": csrf_token(admin, f"/admin/tasks/{task.id}/edit"),
            "title": "Katze tanzen lassen",
            "max_points": "10",
            "allowed_extension": ".sb3",
        })
        assert "Aufgabe bearbeitet: „Katze tanzen lassen“" in protokoll.neu()

        admin.post(f"/admin/tasks/{task.id}/delete", data={
            "csrf_token": csrf_token(admin, f"/admin/challenges/{challenge.id}/tasks"),
        })
        assert "Aufgabe gelöscht: „Katze tanzen lassen“" in protokoll.neu()

    def test_aufgaben_gesichert_und_eingelesen(self, admin, protokoll,
                                              make_challenge, make_task):
        import io

        challenge = make_challenge(title="Vorlage")
        make_task(challenge, title="Aufgabe Eins")
        make_task(challenge, title="Aufgabe Zwei")
        protokoll.neu()

        antwort = admin.get(f"/admin/challenges/{challenge.id}/tasks/export")
        assert "Aufgaben gesichert: 2 aus Wettbewerb „Vorlage“" in protokoll.neu()

        ziel = make_challenge(title="Neu", active=False)
        admin.post(f"/admin/challenges/{ziel.id}/tasks/import", data={
            "csrf_token": csrf_token(admin, f"/admin/challenges/{ziel.id}/tasks"),
            "file": (io.BytesIO(antwort.data), "Aufgaben.json"),
        }, content_type="multipart/form-data")

        assert "Aufgaben eingelesen: 2 in Wettbewerb „Neu“" in protokoll.neu()

    def test_geaenderte_einstellungen_nennen_nur_die_felder(self, admin, protokoll):
        admin.post("/admin/settings", data={
            "csrf_token": csrf_token(admin, "/admin/settings"),
            "site_name": "Coder-Cup",
            "signature_name": "T. Henze",
            "certificate_orientation": "portrait",
        })

        zeile = protokoll.neu()
        assert "Einstellungen geändert:" in zeile
        assert "Standardname" in zeile
        assert "Unterschrift" in zeile
        assert "Ausrichtung der Urkunden" in zeile
        # Der Wert selbst gehört nicht in die Datei, nur das geänderte Feld.
        assert "T. Henze" not in zeile

    def test_ungeaenderte_einstellungen_schreiben_keine_zeile(self, admin, protokoll):
        from models import Settings

        vorhanden = Settings.get()
        admin.post("/admin/settings", data={
            "csrf_token": csrf_token(admin, "/admin/settings"),
            "site_name": vorhanden.site_name,
            "tagline": vorhanden.tagline,
            "signature_name": vorhanden.signature_name,
            "signature_font": vorhanden.signature_font,
            "certificate_orientation": vorhanden.certificate_orientation,
        })

        assert "Einstellungen geändert" not in protokoll.neu()


class TestWettbewerbstag:
    """Am Tag selbst steht drin, was schiefging - und der freigeschaltete Tipp.

    Beides sind die Fragen danach: „Wir haben doch abgegeben!" und „Wann kam
    die Hilfe?" Der gewöhnliche Betrieb bleibt still, siehe TestWasStillBleibt.
    """

    def abgeben(self, client, task, dateiname="loesung.sb3", inhalt=b"projekt"):
        import io

        # Das Token kommt von der Anmeldeseite, nicht von der Startseite: Die zeigt
        # ihr Formular - und damit ihr Token - nicht mehr, wenn der Wettbewerb
        # beendet oder pausiert ist, und genau das prüfen manche dieser Tests.
        return client.post(f"/submit/{task.id}", data={
            "csrf_token": csrf_token(client, "/login"),
            "file": (io.BytesIO(inhalt), dateiname),
        }, content_type="multipart/form-data")

    def test_falsche_endung(self, protokoll, make_challenge, make_task, logged_in_team):
        challenge = make_challenge()
        task = make_task(challenge, title="Katze bewegen", allowed_extension=".sb3")
        client, _ = logged_in_team(challenge, name="Team Blitz")
        protokoll.neu()

        self.abgeben(client, task, dateiname="hausaufgabe.docx")

        zeile = protokoll.neu()
        assert "Abgabe abgelehnt" in zeile
        assert "Team „Team Blitz“" in zeile
        assert "Aufgabe „Katze bewegen“" in zeile
        assert "hausaufgabe.docx" in zeile
        assert ".sb3" in zeile

    def test_pausierter_wettbewerb(self, protokoll, make_challenge, make_task,
                                   logged_in_team, database):
        challenge = make_challenge()
        task = make_task(challenge)
        client, _ = logged_in_team(challenge)
        challenge.paused = True
        database.session.commit()
        protokoll.neu()

        self.abgeben(client, task)

        assert "pausiert oder beendet" in protokoll.neu()

    def test_freigeschalteter_tipp(self, admin, protokoll, make_challenge, make_task):
        challenge = make_challenge()
        task = make_task(challenge, title="Katze bewegen",
                         hint="Schau in die Anleitung.")
        protokoll.neu()

        admin.post(f"/admin/tasks/{task.id}/toggle_hint", data={
            "csrf_token": csrf_token(admin, f"/admin/challenges/{challenge.id}/tasks"),
        })

        zeile = protokoll.neu()
        assert "Tipp freigeschaltet" in zeile
        assert "Katze bewegen" in zeile

    def test_wieder_verborgener_tipp(self, admin, protokoll, make_challenge, make_task):
        """Auch das Zurücknehmen steht drin - sonst bliebe die Datei im Irrtum."""
        challenge = make_challenge()
        task = make_task(challenge, title="Katze bewegen",
                         hint="Schau in die Anleitung.", hint_visible=True)
        protokoll.neu()

        admin.post(f"/admin/tasks/{task.id}/toggle_hint", data={
            "csrf_token": csrf_token(admin, f"/admin/challenges/{challenge.id}/tasks"),
        })

        assert "Tipp verborgen" in protokoll.neu()

    def test_keine_datei_ausgewaehlt(self, protokoll, make_challenge, make_task,
                                    logged_in_team):
        challenge = make_challenge()
        task = make_task(challenge)
        client, _ = logged_in_team(challenge)
        protokoll.neu()

        client.post(f"/submit/{task.id}", data={
            "csrf_token": csrf_token(client, "/"),
        }, content_type="multipart/form-data")

        assert "keine Datei" in protokoll.neu()

    def test_zweite_abgabe_ohne_freigabe(self, protokoll, make_challenge, make_task,
                                         logged_in_team):
        challenge = make_challenge()
        task = make_task(challenge)
        client, _ = logged_in_team(challenge)
        self.abgeben(client, task)
        protokoll.neu()

        self.abgeben(client, task)

        assert "schon abgegeben" in protokoll.neu()

    def test_zu_grosse_datei(self, flask_app, protokoll, make_challenge, make_task,
                             logged_in_team):
        """Die Ablehnung passiert vor der Route - trotzdem soll sie festgehalten sein."""
        challenge = make_challenge()
        task = make_task(challenge)
        client, _ = logged_in_team(challenge)
        protokoll.neu()

        grenze = flask_app.config["MAX_CONTENT_LENGTH"]
        antwort = self.abgeben(client, task, inhalt=b"x" * (grenze + 1000))
        assert antwort.status_code == 413

        zeile = protokoll.neu()
        assert "Abgabe abgelehnt: Datei zu groß" in zeile
        assert f"/submit/{task.id}" in zeile

    def test_zurueckgesetzte_abgabe(self, admin, protokoll, make_challenge, make_task,
                                    logged_in_team, database):
        from models import Submission

        challenge = make_challenge()
        task = make_task(challenge, title="Katze bewegen")
        client, _ = logged_in_team(challenge, name="Team Blitz")
        self.abgeben(client, task)
        abgabe = Submission.query.one()
        protokoll.neu()

        admin.post(f"/admin/reset/{abgabe.id}", data={
            "csrf_token": csrf_token(admin, "/admin/submissions"),
        })

        zeile = protokoll.neu()
        assert "Abgabe zurückgesetzt: Team „Team Blitz“" in zeile
        assert "Katze bewegen" in zeile

    def test_falsches_admin_passwort_mit_adresse(self, client, protokoll):
        client.post("/admin/login", data={
            "csrf_token": csrf_token(client, "/admin/login"),
            "password": "geraten",
        })

        zeile = protokoll.neu()
        assert "Admin-Anmeldung fehlgeschlagen" in zeile
        assert "WARNING" in zeile
        assert "127.0.0.1" in zeile
        assert "geraten" not in zeile, "das geratene Passwort gehört nicht ins Protokoll"

    def test_richtiges_admin_passwort_schreibt_keine_zeile(self, admin, protokoll):
        assert "Admin-Anmeldung" not in protokoll.neu()


class TestZumAbschluss:
    def test_urkunden_fuer_alle_teams(self, admin, protokoll, make_challenge, make_team):
        challenge = make_challenge(title="Calliope-Tag")
        make_team(challenge, name="Team Eins")
        make_team(challenge, name="Team Zwei")
        protokoll.neu()

        antwort = admin.get("/admin/urkunden.pdf")
        assert antwort.status_code == 200

        zeile = protokoll.neu()
        assert "Urkunden erzeugt: 2 Team(s)" in zeile
        assert "Calliope-Tag" in zeile
        assert "format" in zeile, "die Ausrichtung gehört dazu"

    def test_einzelne_urkunde(self, admin, protokoll, make_challenge, make_team):
        challenge = make_challenge(title="Calliope-Tag")
        team = make_team(challenge, name="Team Eins")
        protokoll.neu()

        assert admin.get(f"/admin/urkunden/{team.id}.pdf").status_code == 200

        assert "Urkunde erzeugt: Team „Team Eins“" in protokoll.neu()

    def test_gescheiterte_urkunde_nennt_das_team(self, admin, protokoll, monkeypatch,
                                                make_challenge, make_team):
        challenge = make_challenge(title="Calliope-Tag")
        team = make_team(challenge, name="Team Eins")
        protokoll.neu()

        def kaputt(*args, **kwargs):
            raise RuntimeError("Absicht: kaputte Urkunde")

        monkeypatch.setattr("blueprints.admin.build_certificates_for", kaputt)
        monkeypatch.setitem(admin.application.config, "PROPAGATE_EXCEPTIONS", False)

        assert admin.get(f"/admin/urkunden/{team.id}.pdf").status_code == 500

        zeile = protokoll.neu()
        assert "Urkunde konnte nicht erzeugt werden" in zeile
        assert "Team Eins" in zeile


class TestWasStillBleibt:
    """Der gewöhnliche Betrieb schreibt nichts - sonst ist die Datei unlesbar.

    Tobias hat das am 26.09.2026 entschieden, nachdem eine erste Liste auch
    eingegangene Abgaben, die Zeitsteuerung und jede Bewertung enthielt: Was
    normalerweise klappt, braucht keine Zeile, nur der Fehler ist wichtig.
    """

    def abgeben(self, client, task):
        import io

        return client.post(f"/submit/{task.id}", data={
            "csrf_token": csrf_token(client, "/"),
            "file": (io.BytesIO(b"projekt"), "loesung.sb3"),
        }, content_type="multipart/form-data")

    def test_eingegangene_abgabe(self, protokoll, make_challenge, make_task,
                                 logged_in_team):
        challenge = make_challenge()
        task = make_task(challenge)
        client, _ = logged_in_team(challenge)
        protokoll.neu()

        assert self.abgeben(client, task).status_code == 302
        assert protokoll.neu().strip() == ""

    def test_reihenfolge_der_aufgaben(self, admin, protokoll, make_challenge, make_task):
        """Tobias am 28.09.2026: Umsortieren legt nichts an und nimmt nichts weg."""
        challenge = make_challenge()
        make_task(challenge, title="Erste")
        zweite = make_task(challenge, title="Zweite")
        protokoll.neu()

        admin.post(f"/admin/tasks/{zweite.id}/move", data={
            "csrf_token": csrf_token(admin, f"/admin/challenges/{challenge.id}/tasks"),
            "richtung": "hoch",
        })

        assert zweite.position == 1
        assert protokoll.neu().strip() == ""

    def test_anmeldung_eines_teams(self, flask_app, protokoll, make_challenge, make_team):
        challenge = make_challenge()
        make_team(challenge, name="Team Blitz", password="geheim")
        client = flask_app.test_client()
        protokoll.neu()

        client.post("/login", data={
            "csrf_token": csrf_token(client, "/login"),
            "team": "Team Blitz",
            "password": "geheim",
        })
        client.get("/logout")

        assert protokoll.neu().strip() == ""

    def test_zeitsteuerung(self, admin, protokoll, make_challenge):
        challenge = make_challenge()
        protokoll.neu()

        for weg, daten in (
            ("jetzt-starten", {"duration_minutes": "45"}),
            ("pause", {}),
            ("resume", {}),
            ("finish", {}),
            ("reopen", {}),
        ):
            felder = {"csrf_token": csrf_token(admin, "/admin/challenges/new")}
            felder.update(daten)
            admin.post(f"/admin/challenges/{challenge.id}/{weg}", data=felder)

        assert protokoll.neu().strip() == ""

    def test_bewertung(self, admin, protokoll, make_challenge, make_task,
                       logged_in_team):
        from models import Submission

        challenge = make_challenge()
        task = make_task(challenge, max_points=10)
        client, _ = logged_in_team(challenge)
        self.abgeben(client, task)
        abgabe = Submission.query.one()
        protokoll.neu()

        admin.post("/admin/submissions", data={
            "csrf_token": csrf_token(admin, "/admin/submissions"),
            "submission_id": str(abgabe.id),
            "points": "8",
            "feedback": "Schön gemacht.",
        })

        assert protokoll.neu().strip() == ""

    def test_namensfreigabe(self, admin, protokoll, make_challenge, make_team):
        challenge = make_challenge()
        team = make_team(challenge, name="Team Blitz")
        protokoll.neu()

        admin.post(f"/admin/team/{team.id}/namen", data={
            "csrf_token": csrf_token(admin, "/admin/challenges/new"),
            "member_names": "Anna, Ben",
            "freigeben": "1",
        })

        assert protokoll.neu().strip() == ""

    def test_seitenaufrufe(self, admin, protokoll, make_challenge, make_team):
        challenge = make_challenge()
        make_team(challenge, name="Team Blitz")
        protokoll.neu()

        for adresse in ("/", "/scoreboard", "/siegerehrung", "/admin/dashboard",
                        "/admin/teams", "/admin/submissions", "/admin/urkunden"):
            assert admin.get(adresse).status_code in (200, 302)

        assert protokoll.neu().strip() == ""
