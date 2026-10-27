"""Die Skripte der eigenen Abgabe auf der Teamseite.

Dieselbe Anzeige wie auf der Bewertungsseite, aber über eine eigene Route
für Teams. Geprüft wird vor allem, dass ein Team nur seine eigene Abgabe zu
sehen bekommt und eine fremde nicht einmal von einer fehlenden
unterscheiden kann.
"""

import io
import json
import zipfile

from plattform import snap_skripte
from tests.helpers import csrf_token


def sb3(daten):
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w") as archiv:
        archiv.writestr("project.json", json.dumps(daten))
    return puffer.getvalue()


# Eine Figur mit einem Skript: „Wenn die grüne Flagge angeklickt wird,
# sage Hallo!“
PROJEKT = sb3({"targets": [
    {"isStage": True, "name": "Stage", "blocks": {}},
    {"isStage": False, "name": "Katze", "blocks": {
        "a": {"opcode": "event_whenflagclicked", "next": "b", "parent": None,
              "inputs": {}, "fields": {}, "topLevel": True, "x": 0, "y": 0},
        "b": {"opcode": "looks_say", "next": None, "parent": "a",
              "inputs": {"MESSAGE": [1, [10, "Hallo!"]]}, "fields": {}},
    }},
]})

ROBERTA = (b'<export xmlns="http://de.fhg.iais.roberta.blockly"><program>'
           b'<block_set></block_set></program></export>')


def abgeben(client, task, inhalt, endung=".sb3"):
    from plattform.models import Submission

    client.post(f"/submit/{task.id}", data={
        "csrf_token": csrf_token(client, "/challenge"),
        "file": (io.BytesIO(inhalt), f"loesung{endung}"),
    }, content_type="multipart/form-data")
    return Submission.query.filter_by(task_id=task.id).order_by(Submission.id.desc()).first()


def adresse(abgabe):
    return f"/challenge/abgabe/{abgabe.id}/skripte"


class TestEigeneAbgabe:
    def test_die_skripte_kommen_als_json(self, make_challenge, make_task, logged_in_team):
        challenge = make_challenge()
        task = make_task(challenge)
        client, _team = logged_in_team(challenge)
        abgabe = abgeben(client, task, PROJEKT)

        antwort = client.get(adresse(abgabe))

        assert antwort.status_code == 200
        assert antwort.mimetype == "application/json"
        assert antwort.headers["X-Content-Type-Options"] == "nosniff"
        daten = antwort.get_json()
        assert daten["hinweis"] == ""
        assert daten["figuren"][1]["name"] == "Katze"
        assert daten["figuren"][1]["skripte"] == ["when flag clicked\nsay [Hallo!]"]

    def test_auch_snap(self, make_challenge, make_task, logged_in_team):
        from pathlib import Path

        challenge = make_challenge()
        task = make_task(challenge, allowed_extension=".xml")
        client, _team = logged_in_team(challenge)
        datei = Path(__file__).resolve().parent / "snap" / "fang-die-maus.xml"
        abgabe = abgeben(client, task, datei.read_bytes(), ".xml")

        daten = client.get(adresse(abgabe)).get_json()

        assert daten["hinweis"] == ""
        assert any(figur["skripte"] for figur in daten["figuren"])

    def test_auch_nach_dem_ende(self, make_challenge, make_task, logged_in_team, database):
        challenge = make_challenge()
        task = make_task(challenge)
        client, _team = logged_in_team(challenge)
        abgabe = abgeben(client, task, PROJEKT)
        from datetime import datetime, timedelta

        challenge.end_time = datetime.now() - timedelta(minutes=1)
        database.session.commit()
        assert challenge.status() == "finished"


        assert client.get(adresse(abgabe)).status_code == 200


class TestHinweiseOhneDownload:
    """Ein Team kann seine Datei hier nicht herunterladen, also rät ihm der
    Hinweis auch nicht dazu."""

    def test_kaputte_datei(self, make_challenge, make_task, logged_in_team):
        challenge = make_challenge()
        task = make_task(challenge)
        client, _team = logged_in_team(challenge)
        abgabe = abgeben(client, task, b"kaputt")

        daten = client.get(adresse(abgabe)).get_json()

        assert daten["figuren"] == []
        assert daten["hinweis"] == "Die Datei ist kein lesbares Scratch-3-Projekt."

    def test_open_roberta(self, make_challenge, make_task, logged_in_team):
        challenge = make_challenge()
        task = make_task(challenge, allowed_extension=".xml")
        client, _team = logged_in_team(challenge)
        abgabe = abgeben(client, task, ROBERTA, ".xml")

        daten = client.get(adresse(abgabe)).get_json()

        assert daten["hinweis"] == ("Ein Programm aus Open Roberta lässt sich hier "
                                    "nicht als Blöcke anzeigen.")

    def test_die_bewertungsseite_behaelt_den_rat(
            self, admin, make_challenge, make_task, logged_in_team):
        challenge = make_challenge()
        task = make_task(challenge, allowed_extension=".xml")
        client, _team = logged_in_team(challenge)
        abgabe = abgeben(client, task, ROBERTA, ".xml")

        daten = admin.get(f"/admin/submissions/{abgabe.id}/skripte").get_json()

        assert daten["hinweis"] == snap_skripte.OPEN_ROBERTA

    def test_verschwundene_datei(self, make_challenge, make_task, logged_in_team):
        import os

        challenge = make_challenge()
        task = make_task(challenge)
        client, _team = logged_in_team(challenge)
        abgabe = abgeben(client, task, PROJEKT)
        os.remove(abgabe.pfad)

        daten = client.get(adresse(abgabe)).get_json()

        assert daten["hinweis"] == "Die Datei liegt nicht mehr an ihrem Platz."


class TestNurDieEigene:
    def test_eine_fremde_abgabe_gibt_es_nicht(
            self, make_challenge, make_task, logged_in_team):
        challenge = make_challenge()
        task = make_task(challenge)
        blitz, _ = logged_in_team(challenge, name="Team Blitz")
        donner, _ = logged_in_team(challenge, name="Team Donner")
        fremde = abgeben(blitz, task, PROJEKT)

        antwort = donner.get(adresse(fremde))

        # Wie bei einer Nummer, die es gar nicht gibt.
        assert antwort.status_code == 404
        assert donner.get(f"/challenge/abgabe/{fremde.id + 99}/skripte").status_code == 404
        assert b"Katze" not in antwort.data

    def test_ohne_anmeldung_gibt_es_nichts(
            self, client, make_challenge, make_task, logged_in_team):
        challenge = make_challenge()
        task = make_task(challenge)
        team_client, _ = logged_in_team(challenge)
        abgabe = abgeben(team_client, task, PROJEKT)

        assert client.get(adresse(abgabe)).status_code == 404

    def test_die_lehrkraft_nimmt_dafuer_die_bewertungsseite(
            self, admin, make_challenge, make_task, logged_in_team):
        challenge = make_challenge()
        task = make_task(challenge)
        team_client, _ = logged_in_team(challenge)
        abgabe = abgeben(team_client, task, PROJEKT)

        assert admin.get(adresse(abgabe)).status_code == 404

    def test_ein_inaktiver_wettbewerb_zeigt_nichts(
            self, make_challenge, make_task, logged_in_team, database):
        challenge = make_challenge()
        task = make_task(challenge)
        client, _ = logged_in_team(challenge)
        abgabe = abgeben(client, task, PROJEKT)
        challenge.active = False
        database.session.commit()

        assert client.get(adresse(abgabe)).status_code == 404


class TestTeamseite:
    def test_knopf_und_bibliothek_bei_scratch(self, make_challenge, make_task, logged_in_team):
        challenge = make_challenge()
        task = make_task(challenge)
        client, _ = logged_in_team(challenge)
        abgabe = abgeben(client, task, PROJEKT)

        html = client.get("/challenge").get_data(as_text=True)

        assert "🧩 Unsere Skripte anzeigen" in html
        assert f'data-skripte-url="{adresse(abgabe)}"' in html
        assert f'id="skripte-inhalt-{abgabe.id}"' in html
        assert "vendor/scratchblocks/scratchblocks.min.js" in html
        assert "vendor/scratchblocks/translations.js" in html
        # Nur die Blöcke, keine Datei zum Herunterladen.
        assert "/download" not in html

    def test_nichts_davon_ohne_abgabe(self, make_challenge, make_task, logged_in_team):
        challenge = make_challenge()
        make_task(challenge)
        client, _ = logged_in_team(challenge)

        html = client.get("/challenge").get_data(as_text=True)

        assert "Unsere Skripte anzeigen" not in html
        assert "scratchblocks.min.js" not in html

    def test_nichts_davon_bei_anderen_formaten(self, make_challenge, make_task, logged_in_team):
        challenge = make_challenge()
        task = make_task(challenge, allowed_extension=".py")
        client, _ = logged_in_team(challenge)
        abgeben(client, task, b"print(1)", ".py")

        html = client.get("/challenge").get_data(as_text=True)

        assert "✔ Abgegeben" in html
        assert "Unsere Skripte anzeigen" not in html
        assert "scratchblocks.min.js" not in html

    def test_nur_unter_der_abgegebenen_aufgabe(self, make_challenge, make_task, logged_in_team):
        challenge = make_challenge()
        erste = make_task(challenge, title="Erste")
        make_task(challenge, title="Zweite")
        client, _ = logged_in_team(challenge)
        abgeben(client, erste, PROJEKT)

        html = client.get("/challenge").get_data(as_text=True)

        assert html.count("🧩 Unsere Skripte anzeigen") == 1
