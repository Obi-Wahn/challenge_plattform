"""Die Schwierigkeit einer Aufgabe: einfach, mittel, schwer - oder keine Angabe.

Bisher stand sie im Titel der Aufgabe. Als eigene Eigenschaft muss sie durch
alle drei Wege gehen, auf denen eine Aufgabe entsteht - Formular, Bearbeiten,
Einlesen einer Datei - und beim Sichern wieder mitkommen.
"""

import json

import pytest

from models import TASK_DIFFICULTIES
from task_exchange import parse_tasks
from task_rules import clean_task_values
from tests.helpers import csrf_token


def werte(**abweichend):
    """Ein vollständiges Aufgabenformular, mit den Abweichungen des Tests."""
    formular = {
        "title": "Punkte sammeln",
        "description": "Baut ein Spiel.",
        "max_points": "10",
        "allowed_extension": ".sb3",
        "hint": "",
        "difficulty": "",
    }
    formular.update(abweichend)
    return formular


class TestRegeln:
    """clean_task_values, die Prüfung hinter allen drei Wegen."""

    @pytest.mark.parametrize("stufe", list(TASK_DIFFICULTIES))
    def test_die_drei_stufen_gehen_durch(self, stufe):
        geprueft, hinweise, problem = clean_task_values(
            "A", "", 10, ".sb3", "", stufe)

        assert problem is None
        assert hinweise == []
        assert geprueft["difficulty"] == stufe

    def test_ohne_angabe_bleibt_sie_leer(self):
        """Der Normalfall: Aufgaben aus der Zeit vor dem Feld haben keine."""
        geprueft, hinweise, _ = clean_task_values("A", "", 10, ".sb3", "")

        assert geprueft["difficulty"] == ""
        assert hinweise == []

    @pytest.mark.parametrize("eingabe", ["Mittel", " mittel ", "MITTEL"])
    def test_grossschreibung_und_leerzeichen_stoeren_nicht(self, eingabe):
        geprueft, hinweise, _ = clean_task_values("A", "", 10, ".sb3", "", eingabe)

        assert geprueft["difficulty"] == "mittel"
        assert hinweise == []

    def test_unbekannte_stufe_wird_verworfen_und_gemeldet(self):
        """Wie beim Dateiformat: kein Abbruch, aber mit Ansage."""
        geprueft, hinweise, problem = clean_task_values(
            "A", "", 10, ".sb3", "", "sehr schwer")

        assert problem is None
        assert geprueft["difficulty"] == ""
        assert any("sehr schwer" in h for h in hinweise)


class TestFormular:
    """Anlegen und Bearbeiten im Adminbereich."""

    def test_neue_aufgabe_bekommt_die_stufe(self, admin, make_challenge):
        from models import Task

        challenge = make_challenge()
        pfad = f"/admin/challenges/{challenge.id}/tasks"
        admin.post(pfad, data=werte(
            csrf_token=csrf_token(admin, pfad), difficulty="schwer"))

        assert Task.query.filter_by(challenge_id=challenge.id).one().difficulty == "schwer"

    def test_das_formular_bietet_die_drei_stufen_und_keine_angabe(
            self, admin, make_challenge):
        challenge = make_challenge()

        html = admin.get(
            f"/admin/challenges/{challenge.id}/tasks").get_data(as_text=True)

        assert 'name="difficulty"' in html
        assert "keine Angabe" in html
        for stufe in TASK_DIFFICULTIES:
            assert f'value="{stufe}"' in html

    def test_bearbeiten_aendert_die_stufe(self, admin, make_challenge, make_task):
        challenge = make_challenge()
        task = make_task(challenge, difficulty="einfach")
        pfad = f"/admin/tasks/{task.id}/edit"

        admin.post(pfad, data=werte(
            csrf_token=csrf_token(admin, pfad), difficulty="schwer"))

        assert task.difficulty == "schwer"

    def test_bearbeiten_kann_sie_auch_wieder_entfernen(
            self, admin, make_challenge, make_task):
        challenge = make_challenge()
        task = make_task(challenge, difficulty="schwer")
        pfad = f"/admin/tasks/{task.id}/edit"

        admin.post(pfad, data=werte(
            csrf_token=csrf_token(admin, pfad), difficulty=""))

        assert task.difficulty == ""

    def test_das_bearbeiten_formular_zeigt_die_vorhandene_stufe(
            self, admin, make_challenge, make_task):
        challenge = make_challenge()
        task = make_task(challenge, difficulty="mittel")

        html = admin.get(f"/admin/tasks/{task.id}/edit").get_data(as_text=True)

        assert 'value="mittel" selected' in html


class TestAnzeige:
    """Wo das Schild steht - und wo nicht."""

    def test_in_der_aufgabenliste(self, admin, make_challenge, make_task):
        challenge = make_challenge()
        make_task(challenge, title="Würfel", difficulty="mittel")

        html = admin.get(
            f"/admin/challenges/{challenge.id}/tasks").get_data(as_text=True)

        assert "aufgabe-schwierigkeit-mittel" in html
        assert TASK_DIFFICULTIES["mittel"] in html

    def test_ohne_angabe_steht_kein_leeres_schild_in_der_liste(
            self, admin, make_challenge, make_task):
        challenge = make_challenge()
        make_task(challenge, title="Würfel")

        html = admin.get(
            f"/admin/challenges/{challenge.id}/tasks").get_data(as_text=True)

        assert "aufgabe-schwierigkeit" not in html

    def test_in_der_aufgabenliste_der_wettbewerbsseite(
            self, admin, make_challenge, make_task):
        """Dieselbe Angabe auf allen Seiten, die Aufgaben auflisten.

        Die Aufgabenliste auf der Wettbewerbsseite zeigte nur Punkte und
        Dateiformat, während Aufgabenverwaltung und Teamseite das Schild schon
        trugen.
        """
        challenge = make_challenge()
        make_task(challenge, title="Würfel", difficulty="einfach")

        html = admin.get(f"/admin/wettbewerb/{challenge.id}").get_data(as_text=True)

        assert "aufgabe-schwierigkeit-einfach" in html
        assert TASK_DIFFICULTIES["einfach"] in html

    def test_ohne_angabe_steht_dort_kein_leeres_schild(
            self, admin, make_challenge, make_task):
        challenge = make_challenge()
        make_task(challenge, title="Würfel")

        html = admin.get(f"/admin/wettbewerb/{challenge.id}").get_data(as_text=True)

        assert "aufgabe-schwierigkeit" not in html

    def test_auf_der_wettbewerbsseite_der_teams(
            self, make_challenge, make_task, logged_in_team):
        challenge = make_challenge()
        make_task(challenge, title="Würfel", difficulty="schwer")
        client, _team = logged_in_team(challenge)

        html = client.get("/challenge").get_data(as_text=True)

        assert "aufgabe-schwierigkeit-schwer" in html
        assert "schwer" in html

    def test_sie_stehen_zwischen_einleitung_und_aufgabentext(
            self, make_challenge, make_task, logged_in_team):
        """Erst der Satz, worum es geht, dann die Angaben, dann der Rest.

        So sehen die Teams beim Überfliegen, was eine Aufgabe bringt und wie
        schwer sie ist, ohne den ganzen Text zu lesen.
        """
        challenge = make_challenge()
        make_task(challenge, title="Würfel", difficulty="mittel",
                  description="Baut einen Würfel.\n\n**Das soll passieren:**\n\n* Er zeigt Augen.")
        client, _team = logged_in_team(challenge)

        html = client.get("/challenge").get_data(as_text=True)

        assert (html.index("Baut einen Würfel.")
                < html.index("Max. Punkte")
                < html.index("Das soll passieren"))
        assert (html.index("Baut einen Würfel.")
                < html.index("aufgabe-schwierigkeit")
                < html.index("Das soll passieren"))

    def test_ohne_einleitenden_absatz_stehen_sie_unter_dem_titel(
            self, make_challenge, make_task, logged_in_team):
        """Fängt der Text mit einer Liste an, gibt es keinen Satz davor."""
        challenge = make_challenge()
        make_task(challenge, title="Würfel", difficulty="mittel",
                  description="* Er zeigt Augen.\n* Er würfelt zufällig.")
        client, _team = logged_in_team(challenge)

        html = client.get("/challenge").get_data(as_text=True)

        assert html.index("Max. Punkte") < html.index("Er zeigt Augen.")

    def test_eine_aufgabe_ohne_text_zeigt_nur_die_angaben(
            self, make_challenge, make_task, logged_in_team):
        challenge = make_challenge()
        make_task(challenge, title="Würfel", difficulty="mittel", description=None)
        client, _team = logged_in_team(challenge)

        antwort = client.get("/challenge")

        assert antwort.status_code == 200
        assert "Max. Punkte" in antwort.get_data(as_text=True)

    def test_ohne_angabe_steht_kein_leeres_schild_auf_der_teamseite(
            self, make_challenge, make_task, logged_in_team):
        challenge = make_challenge()
        make_task(challenge, title="Würfel")
        client, _team = logged_in_team(challenge)

        html = client.get("/challenge").get_data(as_text=True)

        assert "aufgabe-schwierigkeit" not in html


class TestSichernUndEinlesen:
    """Die Schwierigkeit reist in der JSON-Datei mit."""

    def test_sichern_nennt_die_stufe(self, admin, make_challenge, make_task):
        challenge = make_challenge()
        make_task(challenge, title="Würfel", difficulty="mittel")

        daten = json.loads(
            admin.get(f"/admin/challenges/{challenge.id}/tasks/export").data)

        assert daten["aufgaben"][0]["schwierigkeit"] == "mittel"

    def test_ohne_angabe_steht_der_schluessel_leer_in_der_datei(
            self, admin, make_challenge, make_task):
        challenge = make_challenge()
        make_task(challenge, title="Würfel")

        daten = json.loads(
            admin.get(f"/admin/challenges/{challenge.id}/tasks/export").data)

        assert daten["aufgaben"][0]["schwierigkeit"] == ""

    def test_einlesen_uebernimmt_die_stufe(self):
        tasks, uebersprungen = parse_tasks(
            b'[{"titel": "A", "punkte": 5, "schwierigkeit": "schwer"}]')

        assert uebersprungen == []
        assert tasks[0]["difficulty"] == "schwer"

    def test_einlesen_versteht_auch_den_englischen_schluessel(self):
        tasks, _ = parse_tasks(b'[{"title": "A", "max_points": 5, "difficulty": "einfach"}]')

        assert tasks[0]["difficulty"] == "einfach"

    def test_eine_alte_datei_ohne_den_schluessel_laesst_sich_einlesen(self):
        """Der eigentliche Punkt: nichts an bestehenden Dateien muss sich ändern."""
        tasks, uebersprungen = parse_tasks(json.dumps({
            "format": "coding-wettbewerb-aufgaben",
            "version": 1,
            "aufgaben": [{"titel": "A", "punkte": 5, "dateiformat": ".sb3"}],
        }).encode("utf-8"))

        assert uebersprungen == []
        assert tasks[0]["difficulty"] == ""

    def test_unbekannte_stufe_in_der_datei_wird_gemeldet(self):
        tasks, uebersprungen = parse_tasks(
            b'[{"titel": "A", "punkte": 5, "schwierigkeit": "mittelschwer"}]')

        assert tasks[0]["difficulty"] == ""
        assert any("mittelschwer" in h for h in uebersprungen)

    def test_der_weg_durch_die_anwendung(self, admin, make_challenge, database):
        """Sichern und in einem anderen Wettbewerb wieder einlesen."""
        from models import Task

        quelle = make_challenge(title="Quelle")
        database.session.add(Task(challenge_id=quelle.id, title="Würfel",
                                  max_points=10, allowed_extension=".hex",
                                  difficulty="mittel"))
        database.session.commit()
        datei = admin.get(f"/admin/challenges/{quelle.id}/tasks/export").data

        ziel = make_challenge(title="Ziel", active=False)
        import io
        admin.post(f"/admin/challenges/{ziel.id}/tasks/import", data={
            "csrf_token": csrf_token(admin, f"/admin/challenges/{ziel.id}/tasks"),
            "file": (io.BytesIO(datei), "Aufgaben.json"),
        }, content_type="multipart/form-data", follow_redirects=True)

        assert Task.query.filter_by(challenge_id=ziel.id).one().difficulty == "mittel"


class TestBeispieldateien:
    """Die mitgelieferten Sätze zeigen, wie das Feld gemeint ist."""

    def test_jede_beispielaufgabe_hat_eine_gueltige_stufe(self):
        from pathlib import Path

        ordner = Path(__file__).resolve().parent.parent / "beispiele"
        for datei in sorted(ordner.glob("*.json")):
            tasks, uebersprungen = parse_tasks(datei.read_bytes())
            assert uebersprungen == [], f"{datei.name}: {uebersprungen}"
            for task in tasks:
                assert task["difficulty"] in TASK_DIFFICULTIES, \
                    f"{datei.name}: {task['title']}"
