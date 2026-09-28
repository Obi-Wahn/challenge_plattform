"""Die Reihenfolge der Aufgaben, die der Admin mit ▲ und ▼ festlegt.

Sie gilt überall, wo Aufgaben der Reihe nach stehen: in der Aufgabenliste,
auf der Teamseite, in der Rangliste (A1, A2 …), im Namen einer
heruntergeladenen Abgabe und in beiden Sicherungen.
"""

import io
import json
import re
import zipfile

import pytest

from models import Challenge, Submission, Task
from tests.helpers import csrf_token


@pytest.fixture
def drei(make_challenge, make_task):
    """Ein Wettbewerb mit drei Aufgaben, wie sie vor dem Feld entstanden: alle auf 0."""
    challenge = make_challenge(title="Reihenfolge")
    for titel in ("Katze", "Gespräch", "Punkte"):
        make_task(challenge, title=titel)
    return challenge


def titel(challenge):
    return [t.title for t in Task.geordnet(challenge.id)]


def verschieben(admin, task, richtung):
    return admin.post(f"/admin/tasks/{task.id}/move", data={
        "csrf_token": csrf_token(admin, f"/admin/challenges/{task.challenge_id}/tasks"),
        "richtung": richtung,
    })


def aufgabe(titel_):
    return Task.query.filter_by(title=titel_).one()


class TestVerschieben:

    def test_ohne_position_gilt_die_reihenfolge_des_anlegens(self, drei):
        assert titel(drei) == ["Katze", "Gespräch", "Punkte"]

    def test_nach_oben(self, admin, drei):
        verschieben(admin, aufgabe("Punkte"), "hoch")

        assert titel(drei) == ["Katze", "Punkte", "Gespräch"]

    def test_nach_unten(self, admin, drei):
        verschieben(admin, aufgabe("Katze"), "runter")

        assert titel(drei) == ["Gespräch", "Katze", "Punkte"]

    def test_danach_sind_die_positionen_lueckenlos(self, admin, drei):
        verschieben(admin, aufgabe("Punkte"), "hoch")

        assert [t.position for t in Task.geordnet(drei.id)] == [1, 2, 3]

    @pytest.mark.parametrize("titel_, richtung", [("Katze", "hoch"), ("Punkte", "runter")])
    def test_am_rand_bleibt_alles_wie_es_ist(self, admin, drei, titel_, richtung):
        antwort = verschieben(admin, aufgabe(titel_), richtung)

        assert antwort.status_code == 302
        assert titel(drei) == ["Katze", "Gespräch", "Punkte"]

    def test_die_verschobene_aufgabe_wird_hervorgehoben(self, admin, drei):
        task = aufgabe("Gespräch")

        antwort = verschieben(admin, task, "hoch")
        assert antwort.headers["Location"].endswith(
            f"/admin/challenges/{drei.id}/tasks?verschoben={task.id}")

        html = admin.get(antwort.headers["Location"]).get_data(as_text=True)
        assert html.count("aufgaben-zeile-verschoben") == 1
        zeile = html.index("aufgaben-zeile-verschoben")
        assert html.index("Gespräch", zeile) < html.index("Katze", zeile)

    def test_andere_wettbewerbe_bleiben_unberuehrt(self, admin, drei, make_challenge, make_task):
        anderer = make_challenge(title="Anderer", active=False)
        make_task(anderer, title="Eins")
        make_task(anderer, title="Zwei")

        verschieben(admin, aufgabe("Punkte"), "hoch")

        assert titel(anderer) == ["Eins", "Zwei"]

    def test_nur_fuer_den_admin(self, client, drei):
        task = aufgabe("Punkte")

        client.post(f"/admin/tasks/{task.id}/move", data={"richtung": "hoch"})

        assert titel(drei) == ["Katze", "Gespräch", "Punkte"]

    def test_ohne_csrf_token_passiert_nichts(self, admin, drei):
        admin.post(f"/admin/tasks/{aufgabe('Punkte').id}/move", data={"richtung": "hoch"})

        assert titel(drei) == ["Katze", "Gespräch", "Punkte"]


class TestNeueAufgaben:

    def test_neue_aufgabe_kommt_ans_ende(self, admin, drei):
        verschieben(admin, aufgabe("Punkte"), "hoch")

        pfad = f"/admin/challenges/{drei.id}/tasks"
        admin.post(pfad, data={
            "csrf_token": csrf_token(admin, pfad), "title": "Neu",
            "max_points": "10", "allowed_extension": ".sb3",
        })

        assert titel(drei) == ["Katze", "Punkte", "Gespräch", "Neu"]

    def test_eingelesene_aufgaben_kommen_ans_ende_in_der_reihenfolge_der_datei(
            self, admin, drei):
        verschieben(admin, aufgabe("Katze"), "runter")
        pfad = f"/admin/challenges/{drei.id}/tasks"
        inhalt = json.dumps([{"titel": "Zweitletzte"}, {"titel": "Letzte"}]).encode()

        admin.post(f"{pfad}/import", data={
            "csrf_token": csrf_token(admin, pfad),
            "file": (io.BytesIO(inhalt), "Aufgaben.json"),
        }, content_type="multipart/form-data")

        assert titel(drei) == ["Gespräch", "Katze", "Punkte", "Zweitletzte", "Letzte"]


class TestUeberall:
    """Nach dem Umsortieren: Punkte hoch, also Katze, Punkte, Gespräch."""

    @pytest.fixture
    def umsortiert(self, admin, drei):
        verschieben(admin, aufgabe("Punkte"), "hoch")
        return drei

    @staticmethod
    def reihenfolge_in(html, namen):
        stellen = [html.index(name) for name in namen]
        return stellen == sorted(stellen)

    def test_aufgabenliste(self, admin, umsortiert):
        html = admin.get(f"/admin/challenges/{umsortiert.id}/tasks").get_data(as_text=True)

        assert self.reihenfolge_in(html, ["Katze", "Punkte", "Gespräch"])

    def test_erste_und_letzte_haben_je_einen_abgeschalteten_knopf(self, admin, umsortiert):
        html = admin.get(f"/admin/challenges/{umsortiert.id}/tasks").get_data(as_text=True)

        assert html.count('value="hoch"') == 3
        assert html.count('value="runter"') == 3
        assert html.count("disabled>▲") == 1
        assert html.count("disabled>▼") == 1

    def test_teamseite(self, umsortiert, logged_in_team):
        client, _ = logged_in_team(umsortiert)

        html = client.get("/challenge").get_data(as_text=True)

        assert self.reihenfolge_in(html, ["Katze", "Punkte", "Gespräch"])

    def test_rangliste_nummeriert_in_der_neuen_reihenfolge(self, client, umsortiert, make_team):
        make_team(umsortiert, name="Team Blitz")

        html = client.get("/scoreboard").get_data(as_text=True)

        assert "A1: Katze" in html
        assert "A2: Punkte" in html
        assert "A3: Gespräch" in html

    def test_download_name_traegt_die_neue_nummer(self, admin, umsortiert, logged_in_team):
        client, _ = logged_in_team(umsortiert, name="Pixel")
        client.post(f"/submit/{aufgabe('Punkte').id}", data={
            "csrf_token": csrf_token(client, "/"),
            "file": (io.BytesIO(b"projekt"), "loesung.sb3"),
        }, content_type="multipart/form-data")

        antwort = admin.get(f"/admin/download/{Submission.query.one().id}")

        assert "Pixel_A2.sb3" in antwort.headers["Content-Disposition"]

    def test_aufgaben_json(self, admin, umsortiert):
        antwort = admin.get(f"/admin/challenges/{umsortiert.id}/tasks/export")

        daten = json.loads(antwort.data)
        assert [a["titel"] for a in daten["aufgaben"]] == ["Katze", "Punkte", "Gespräch"]

    def test_zip_sicherung_hin_und_zurueck(self, admin, umsortiert):
        antwort = admin.get(f"/admin/challenges/{umsortiert.id}/sichern")
        daten = json.loads(zipfile.ZipFile(io.BytesIO(antwort.data)).read("wettbewerb.json"))
        assert [a["titel"] for a in daten["aufgaben"]] == ["Katze", "Punkte", "Gespräch"]

        admin.post("/admin/challenges/einlesen", data={
            "csrf_token": csrf_token(admin, "/admin/challenges/new"),
            "file": (io.BytesIO(antwort.data), "Sicherung.zip"),
        }, content_type="multipart/form-data")

        kopie = Challenge.query.filter(Challenge.id != umsortiert.id).one()
        assert titel(kopie) == ["Katze", "Punkte", "Gespräch"]


class TestTitelInDerRangliste:
    """Unter Einstellungen → Rangliste lassen sich die Titel abschalten."""

    def einstellen(self, admin, an):
        from models import Settings

        vorhanden = Settings.get()
        daten = {
            "csrf_token": csrf_token(admin, "/admin/settings"),
            "site_name": vorhanden.site_name,
            "certificate_orientation": vorhanden.certificate_orientation,
        }
        if an:
            daten["scoreboard_task_titles"] = "1"
        admin.post("/admin/settings", data=daten)

    def test_voreingestellt_stehen_die_titel_da(self, client, drei, make_team):
        make_team(drei, name="Team Blitz")

        html = client.get("/scoreboard").get_data(as_text=True)

        assert "A1: Katze" in html

    def test_abgeschaltet_steht_nur_die_nummer(self, admin, client, drei, make_team):
        make_team(drei, name="Team Blitz")
        self.einstellen(admin, an=False)

        html = client.get("/scoreboard").get_data(as_text=True)

        assert ">A1: Katze<" not in html
        assert "ranglisten-aufgabe" not in html
        assert re.search(r">\s*A1\s*</th>", html)
        assert re.search(r">\s*A3\s*</th>", html)

    def test_wieder_eingeschaltet(self, admin, client, drei, make_team):
        make_team(drei, name="Team Blitz")
        self.einstellen(admin, an=False)
        self.einstellen(admin, an=True)

        assert "A2: Gespräch" in client.get("/scoreboard").get_data(as_text=True)

    def test_der_schalter_steht_in_den_einstellungen(self, admin):
        html = admin.get("/admin/settings").get_data(as_text=True)

        assert 'name="scoreboard_task_titles"' in html
        assert "Aufgabentitel über den Spalten zeigen" in html
