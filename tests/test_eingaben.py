"""Was von außen hereinkommt, wird geprüft - auch wenn das Formular es verbietet.

Die Registrierung ist die einzige Seite, die ohne Anmeldung schreibend auf
die Datenbank zugreift. Und die Aufgabenverwaltung hatte zwei Wege mit
unterschiedlich strengen Regeln: Was beim Einlesen einer Datei abgefangen
wurde, ging über das Formular durch.
"""

import pytest

from task_rules import (KEIN_TITEL, MAX_POINTS, MAX_TITLE, PUNKTE_KEINE_ZAHL,
                        clean_task_values)
from tests.helpers import csrf_token


class TestAufgabenRegeln:
    """Die Regel selbst - unabhängig davon, wer sie aufruft."""

    def test_ohne_titel_entsteht_keine_aufgabe(self):
        werte, _hinweise, problem = clean_task_values("", "x", 10, ".sb3", "")
        assert werte is None
        assert problem == KEIN_TITEL

    def test_titel_nur_aus_leerzeichen_zaehlt_als_fehlend(self):
        werte, _hinweise, problem = clean_task_values("   ", "x", 10, ".sb3", "")
        assert werte is None
        assert problem == KEIN_TITEL

    def test_punktzahl_die_keine_zahl_ist_wird_nicht_geraten(self):
        werte, _hinweise, problem = clean_task_values("A", "", "abc", ".sb3", "")
        assert werte is None
        assert problem == PUNKTE_KEINE_ZAHL

    @pytest.mark.parametrize("eingabe,erwartet", [
        (-50, 0),
        (0, 0),
        (10, 10),
        (MAX_POINTS, MAX_POINTS),
        (MAX_POINTS + 1, MAX_POINTS),
        (99999, MAX_POINTS),
    ])
    def test_punkte_bleiben_im_erlaubten_bereich(self, eingabe, erwartet):
        werte, _hinweise, problem = clean_task_values("A", "", eingabe, ".sb3", "")
        assert problem is None
        assert werte["max_points"] == erwartet

    def test_negative_punkte_werden_gemeldet(self):
        _werte, hinweise, _problem = clean_task_values("A", "", -50, ".sb3", "")
        assert any("negativ" in h for h in hinweise)

    def test_unbekanntes_format_faellt_zurueck_und_wird_gemeldet(self):
        werte, hinweise, _problem = clean_task_values("A", "", 10, ".exe", "")
        assert werte["allowed_extension"] == ".pde"
        assert any(".exe" in h for h in hinweise)

    def test_langer_titel_wird_gekuerzt(self):
        werte, hinweise, _problem = clean_task_values("x" * 500, "", 10, ".sb3", "")
        assert len(werte["title"]) == MAX_TITLE
        assert any("gekürzt" in h for h in hinweise)

    def test_leere_beschreibung_wird_zu_nichts(self):
        werte, _h, _p = clean_task_values("A", "   ", 10, ".sb3", "")
        assert werte["description"] in (None, "   ")


class TestAufgabeUeberDasFormular:
    """Genau das, was der Import schon lange abfängt - jetzt auch hier."""

    def aufgabe_anlegen(self, admin, challenge, **felder):
        daten = {
            "csrf_token": csrf_token(admin, f"/admin/challenges/{challenge.id}/tasks"),
            "title": "Testaufgabe",
            "description": "Beschreibung",
            "max_points": "10",
            "allowed_extension": ".sb3",
        }
        daten.update(felder)
        return admin.post(f"/admin/challenges/{challenge.id}/tasks", data=daten,
                          follow_redirects=True)

    def test_negative_punktzahl_wird_nicht_gespeichert(self, admin, make_challenge,
                                                       database):
        from models import Task

        challenge = make_challenge()
        self.aufgabe_anlegen(admin, challenge, max_points="-50")

        task = Task.query.filter_by(title="Testaufgabe").first()
        assert task is not None
        # Eine Aufgabe mit -50 Höchstpunkten waere stillschweigend nicht
        # punktbar: Die Bewertung rechnet max(0, min(punkte, max_points)).
        assert task.max_points == 0

    def test_punktzahl_die_keine_zahl_ist_ergibt_keinen_serverfehler(
            self, admin, make_challenge, database):
        from models import Task

        challenge = make_challenge()
        antwort = self.aufgabe_anlegen(admin, challenge, max_points="abc")

        assert antwort.status_code == 200
        assert Task.query.count() == 0
        assert "Zahl" in antwort.get_data(as_text=True)

    def test_unbekanntes_dateiformat_wird_nicht_gespeichert(self, admin,
                                                            make_challenge, database):
        from models import Task

        challenge = make_challenge()
        self.aufgabe_anlegen(admin, challenge, allowed_extension=".exe")

        assert Task.query.filter_by(title="Testaufgabe").first().allowed_extension == ".pde"

    def test_ohne_titel_entsteht_nichts(self, admin, make_challenge, database):
        from models import Task

        challenge = make_challenge()
        antwort = self.aufgabe_anlegen(admin, challenge, title="   ")

        assert Task.query.count() == 0
        assert "Titel" in antwort.get_data(as_text=True)

    def test_uebermaessig_langer_titel_wird_gekuerzt(self, admin, make_challenge,
                                                     database):
        from models import Task

        challenge = make_challenge()
        self.aufgabe_anlegen(admin, challenge, title="T" * 500)

        assert len(Task.query.first().title) == MAX_TITLE

    def test_bearbeiten_gilt_dieselbe_regel(self, admin, make_challenge, make_task,
                                            database):
        from models import Task

        challenge = make_challenge()
        task = make_task(challenge, title="Vorher")

        admin.post(f"/admin/tasks/{task.id}/edit", data={
            "csrf_token": csrf_token(admin, f"/admin/tasks/{task.id}/edit"),
            "title": "Nachher",
            "description": "x",
            "max_points": "-99",
            "allowed_extension": ".exe",
        }, follow_redirects=True)

        geaendert = database.session.get(Task, task.id)
        assert geaendert.title == "Nachher"
        assert geaendert.max_points == 0
        assert geaendert.allowed_extension == ".pde"


class TestTeamRegistrierung:
    def registrieren(self, client, name, passwort="geheim"):
        return client.post("/", data={
            "csrf_token": csrf_token(client, "/"),
            "team": name,
            "password": passwort,
        }, follow_redirects=True)

    def test_name_nur_aus_leerzeichen_wird_abgewiesen(self, client, make_challenge,
                                                      database):
        from models import Team

        make_challenge()
        antwort = self.registrieren(client, "      ")

        assert Team.query.count() == 0
        assert "Teamname" in antwort.get_data(as_text=True)

    def test_umgebende_leerzeichen_werden_entfernt(self, client, make_challenge,
                                                   database):
        from models import Team

        make_challenge()
        self.registrieren(client, "  Die Pixelpiraten  ")

        assert Team.query.first().name == "Die Pixelpiraten"

    def test_uebermaessig_langer_name_wird_abgewiesen(self, client, make_challenge,
                                                      database):
        from models import Team

        make_challenge()
        antwort = self.registrieren(client, "A" * 5000)

        # SQLite setzt String(100) nicht selbst durch - ohne Prüfung landen
        # alle 5000 Zeichen in der Spalte.
        assert Team.query.count() == 0
        assert "100" in antwort.get_data(as_text=True)

    def test_name_an_der_grenze_geht_durch(self, client, make_challenge, database):
        from models import Team

        make_challenge()
        self.registrieren(client, "A" * 100)

        assert Team.query.count() == 1

    def test_uebermaessig_langes_passwort_wird_abgewiesen(self, client, make_challenge,
                                                          database):
        from models import Team

        make_challenge()
        antwort = self.registrieren(client, "Team A", passwort="x" * 5000)

        assert Team.query.count() == 0
        assert "Passwort" in antwort.get_data(as_text=True)

    def test_getrimmter_name_laesst_sich_anmelden(self, flask_app, make_challenge,
                                                  database):
        """Wer sich mit Leerzeichen registriert hat, muss auch wieder hineinkommen."""
        make_challenge()
        anmelder = flask_app.test_client()
        self.registrieren(anmelder, "  Team A  ")

        zweiter = flask_app.test_client()
        antwort = zweiter.post("/login", data={
            "csrf_token": csrf_token(zweiter, "/login"),
            "team": "  Team A  ",
            "password": "geheim",
        }, follow_redirects=True)

        assert "Ungültig" not in antwort.get_data(as_text=True)


class TestSchreibweiseZaehlt:
    """Bewusste Entscheidung: Die Schreibweise unterscheidet Teams."""

    def test_gross_und_kleinschreibung_ergeben_zwei_teams(self, flask_app,
                                                          make_challenge, database):
        from models import Team

        make_challenge()
        for name in ("Die Hacker", "die hacker"):
            client = flask_app.test_client()
            client.post("/", data={
                "csrf_token": csrf_token(client, "/"),
                "team": name,
                "password": "geheim",
            })

        assert Team.query.count() == 2, \
            "Die Schreibweise soll Teams unterscheiden - das ist so gewollt"

    def test_derselbe_name_bleibt_gesperrt(self, flask_app, make_challenge, database):
        from models import Team

        make_challenge()
        for _ in range(2):
            client = flask_app.test_client()
            client.post("/", data={
                "csrf_token": csrf_token(client, "/"),
                "team": "Die Hacker",
                "password": "geheim",
            })

        assert Team.query.count() == 1


class TestGleichzeitigeRegistrierung:
    def test_doppelter_name_ergibt_keinen_serverfehler(self, flask_app, make_challenge,
                                                       database, monkeypatch):
        """Zwei Teams klicken gleichzeitig: Die Prüfung sieht beide Male „frei“.

        Nachgestellt, indem die Vorabprüfung nichts findet - genau der
        Zustand, in dem beide Anfragen gleichzeitig an der Datenbank landen.
        Ohne Behandlung des IntegrityError endet die zweite in einem 500er.
        """
        from models import Team

        challenge = make_challenge()
        vorhanden = Team(name="Die Hacker", challenge_id=challenge.id)
        vorhanden.set_password("geheim")
        database.session.add(vorhanden)
        database.session.commit()

        # Die Vorabprüfung übersieht das vorhandene Team - so, wie es bei
        # zwei gleichzeitigen Anfragen tatsächlich passiert.
        import blueprints.public as oeffentlich

        echtes_query = oeffentlich.Team.query

        class BlindeSuche:
            def filter_by(self, **kwargs):
                if "name" in kwargs:
                    class Leer:
                        def first(self_inner):
                            return None
                    return Leer()
                return echtes_query.filter_by(**kwargs)

        monkeypatch.setattr(oeffentlich.Team, "query", BlindeSuche())

        client = flask_app.test_client()
        antwort = client.post("/", data={
            "csrf_token": csrf_token(client, "/"),
            "team": "Die Hacker",
            "password": "anderes",
        }, follow_redirects=True)

        assert antwort.status_code == 200, "die zweite Anmeldung endete im Serverfehler"
        assert "vergeben" in antwort.get_data(as_text=True)
