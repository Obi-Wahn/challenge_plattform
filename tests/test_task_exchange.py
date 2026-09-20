"""Aufgaben sichern und wiederverwenden."""

import io
import json

import pytest

from task_exchange import ImportError_, parse_tasks
from tests.helpers import csrf_token


def datei(inhalt, name="Aufgaben.json"):
    if isinstance(inhalt, (dict, list)):
        inhalt = json.dumps(inhalt, ensure_ascii=False).encode("utf-8")
    return (io.BytesIO(inhalt), name)


def einlesen(admin, challenge, inhalt):
    return admin.post(f"/admin/challenges/{challenge.id}/tasks/import", data={
        "csrf_token": csrf_token(admin, f"/admin/challenges/{challenge.id}/tasks"),
        "file": datei(inhalt),
    }, content_type="multipart/form-data", follow_redirects=True)


class TestDateiLesen:
    """parse_tasks ohne Web-Drumherum."""

    def test_liest_den_vollen_rahmen(self):
        tasks, uebersprungen = parse_tasks(json.dumps({"aufgaben": [
            {"titel": "A", "beschreibung": "Text", "punkte": 10,
             "dateiformat": ".sb3", "hinweis": "Tipp"}]}).encode("utf-8"))

        assert uebersprungen == []
        assert tasks == [{"title": "A", "description": "Text", "max_points": 10,
                          "allowed_extension": ".sb3", "hint": "Tipp"}]

    def test_liest_auch_eine_schlichte_liste(self):
        """Damit eine von Hand geschriebene Datei funktioniert."""
        tasks, _ = parse_tasks(b'[{"titel": "A", "punkte": 5, "dateiformat": ".py"}]')

        assert tasks[0]["title"] == "A"

    def test_versteht_auch_englische_feldnamen(self):
        tasks, _ = parse_tasks(b'[{"title": "A", "max_points": 5, "allowed_extension": ".py"}]')

        assert tasks[0]["title"] == "A"
        assert tasks[0]["max_points"] == 5

    def test_byte_order_mark_stoert_nicht(self):
        """Der Windows-Editor schreibt gern eins an den Anfang."""
        roh = '[{"titel": "A", "punkte": 5}]'.encode("utf-8-sig")

        tasks, _ = parse_tasks(roh)

        assert tasks[0]["title"] == "A"

    @pytest.mark.parametrize("roh, erwartet", [
        (b"das ist kein json", "keine gültige JSON-Datei"),
        (b'{"format": "x"}', "keine Liste"),
        (b'{"aufgaben": "keine liste"}', "muss eine Liste sein"),
        (b"[]", "keine verwendbare Aufgabe"),
        (b'[{"punkte": 3}]', "keine verwendbare Aufgabe"),
        (b'"nur ein text"', "keine Aufgaben"),
    ])
    def test_unbrauchbare_dateien_melden_sich_verstaendlich(self, roh, erwartet):
        with pytest.raises(ImportError_) as fehler:
            parse_tasks(roh)

        assert erwartet in str(fehler.value)

    def test_keine_textdatei(self):
        with pytest.raises(ImportError_) as fehler:
            parse_tasks(b"\xff\xfe\x00\x00 keine textdatei")

        assert "keine Textdatei" in str(fehler.value)

    def test_zu_viele_aufgaben_werden_abgelehnt(self):
        viele = {"aufgaben": [{"titel": f"A{i}", "punkte": 1} for i in range(201)]}

        with pytest.raises(ImportError_) as fehler:
            parse_tasks(json.dumps(viele).encode("utf-8"))

        assert "mehr als 200" in str(fehler.value)

    def test_kaputte_eintraege_werden_uebersprungen_und_benannt(self):
        tasks, uebersprungen = parse_tasks(json.dumps({"aufgaben": [
            {"titel": "Gut", "punkte": 10, "dateiformat": ".sb3"},
            {"punkte": 5},
            {"titel": "Punkte kaputt", "punkte": "viele"},
            "kein Eintrag",
        ]}).encode("utf-8"))

        assert [t["title"] for t in tasks] == ["Gut"]
        assert len(uebersprungen) == 3

    def test_unbekanntes_dateiformat_faellt_zurueck_und_wird_gemeldet(self):
        tasks, uebersprungen = parse_tasks(b'[{"titel": "A", "dateiformat": ".exe"}]')

        assert tasks[0]["allowed_extension"] == ".pde"
        assert ".exe" in uebersprungen[0]

    def test_punkte_werden_begrenzt(self):
        tasks, _ = parse_tasks(b'[{"titel": "A", "punkte": 99999}, {"titel": "B", "punkte": -5}]')

        assert [t["max_points"] for t in tasks] == [1000, 0]

    def test_langer_titel_wird_gekuerzt(self):
        tasks, _ = parse_tasks(json.dumps([{"titel": "x" * 500}]).encode("utf-8"))

        assert len(tasks[0]["title"]) == 200


class TestSichern:
    def test_alle_aufgaben_eines_wettbewerbs(self, admin, make_challenge, make_task):
        challenge = make_challenge(title="Scratch-Wettbewerb")
        make_task(challenge, title="Katze läuft im Kreis")
        make_task(challenge, title="Musik machen 🎵")

        antwort = admin.get(f"/admin/challenges/{challenge.id}/tasks/export")

        assert antwort.mimetype == "application/json"
        assert "Aufgaben_Scratch-Wettbewerb.json" in antwort.headers["Content-Disposition"]

        daten = json.loads(antwort.data.decode("utf-8"))
        assert daten["format"] == "coding-wettbewerb-aufgaben"
        assert [a["titel"] for a in daten["aufgaben"]] == [
            "Katze läuft im Kreis", "Musik machen 🎵"]

    def test_umlaute_bleiben_lesbar(self, admin, make_challenge, make_task):
        challenge = make_challenge()
        make_task(challenge, hint="Nutzt „wiederhole“.")

        text = admin.get(f"/admin/challenges/{challenge.id}/tasks/export").data.decode("utf-8")

        assert "„wiederhole“" in text

    def test_keine_abgaben_und_keine_punktstaende(self, admin, make_challenge, make_task):
        challenge = make_challenge()
        make_task(challenge)

        daten = json.loads(
            admin.get(f"/admin/challenges/{challenge.id}/tasks/export").data)

        assert set(daten) == {"format", "version", "exportiert_am", "wettbewerb", "aufgaben"}

    def test_sichtbarkeit_des_hinweises_wandert_nicht_mit(
            self, admin, make_challenge, make_task):
        challenge = make_challenge()
        make_task(challenge, hint="Tipp", hint_visible=True)

        daten = json.loads(
            admin.get(f"/admin/challenges/{challenge.id}/tasks/export").data)

        assert "hinweis_sichtbar" not in daten["aufgaben"][0]
        assert "hint_visible" not in daten["aufgaben"][0]

    def test_einzelne_aufgabe(self, admin, make_challenge, make_task):
        challenge = make_challenge()
        make_task(challenge, title="Erste")
        zweite = make_task(challenge, title="Zweite")

        antwort = admin.get(f"/admin/tasks/{zweite.id}/export")

        assert "Aufgabe_Zweite.json" in antwort.headers["Content-Disposition"]
        daten = json.loads(antwort.data)
        assert [a["titel"] for a in daten["aufgaben"]] == ["Zweite"]

    def test_ohne_aufgaben_gibt_es_nichts_zu_sichern(self, admin, make_challenge):
        challenge = make_challenge()

        antwort = admin.get(f"/admin/challenges/{challenge.id}/tasks/export",
                            follow_redirects=True)

        assert "noch keine Aufgaben" in antwort.get_data(as_text=True)

    def test_unbekannte_aufgabe_ergibt_404(self, admin, database):
        assert admin.get("/admin/tasks/9999/export").status_code == 404

    def test_nur_fuer_den_admin(self, client, make_challenge, make_task):
        challenge = make_challenge()
        task = make_task(challenge)

        assert client.get(f"/admin/tasks/{task.id}/export").status_code == 302
        assert client.get(f"/admin/challenges/{challenge.id}/tasks/export").status_code == 302


class TestEinlesen:
    def test_aufgaben_kommen_im_anderen_wettbewerb_an(
            self, admin, make_challenge, make_task, database):
        from models import Task

        quelle = make_challenge(title="Quelle")
        make_task(quelle, title="Katze läuft im Kreis", max_points=10,
                  allowed_extension=".sb3", hint="Tipp", hint_visible=True)
        gesichert = admin.get(f"/admin/challenges/{quelle.id}/tasks/export").data

        ziel = make_challenge(title="Ziel", active=False)
        antwort = einlesen(admin, ziel, gesichert)

        assert "1 Aufgabe(n)" in antwort.get_data(as_text=True)
        eingelesen = Task.query.filter_by(challenge_id=ziel.id).one()
        assert eingelesen.title == "Katze läuft im Kreis"
        assert eingelesen.max_points == 10
        assert eingelesen.allowed_extension == ".sb3"
        assert eingelesen.hint == "Tipp"

    def test_hinweise_starten_verborgen(self, admin, make_challenge, make_task, database):
        from models import Task

        quelle = make_challenge(title="Quelle")
        make_task(quelle, hint="Tipp", hint_visible=True)
        gesichert = admin.get(f"/admin/challenges/{quelle.id}/tasks/export").data

        ziel = make_challenge(title="Ziel", active=False)
        einlesen(admin, ziel, gesichert)

        assert Task.query.filter_by(challenge_id=ziel.id).one().hint_visible in (False, None)

    def test_einlesen_haengt_an_statt_zu_ersetzen(
            self, admin, make_challenge, make_task, database):
        from models import Task

        challenge = make_challenge()
        make_task(challenge, title="War schon da")

        einlesen(admin, challenge, [{"titel": "Kommt dazu", "punkte": 5}])

        titel = [t.title for t in Task.query.filter_by(challenge_id=challenge.id).all()]
        assert titel == ["War schon da", "Kommt dazu"]

    def test_die_quelle_bleibt_unveraendert(
            self, admin, make_challenge, make_task, database):
        from models import Task

        quelle = make_challenge(title="Quelle")
        make_task(quelle, title="Original")
        gesichert = admin.get(f"/admin/challenges/{quelle.id}/tasks/export").data

        ziel = make_challenge(title="Ziel", active=False)
        einlesen(admin, ziel, gesichert)

        assert Task.query.filter_by(challenge_id=quelle.id).count() == 1

    def test_ohne_datei_gibt_es_einen_hinweis(self, admin, make_challenge):
        challenge = make_challenge()

        antwort = admin.post(f"/admin/challenges/{challenge.id}/tasks/import", data={
            "csrf_token": csrf_token(admin, f"/admin/challenges/{challenge.id}/tasks"),
        }, follow_redirects=True)

        assert "keine Datei" in antwort.get_data(as_text=True)

    def test_kaputte_datei_fuehrt_nicht_zu_einem_fehler(self, admin, make_challenge):
        challenge = make_challenge()

        antwort = einlesen(admin, challenge, b"das ist kein json")

        assert antwort.status_code == 200
        assert "Import nicht möglich" in antwort.get_data(as_text=True)

    def test_teilweise_brauchbare_datei_meldet_beides(
            self, admin, make_challenge, database):
        from models import Task

        challenge = make_challenge()

        antwort = einlesen(admin, challenge, {"aufgaben": [
            {"titel": "Gut", "punkte": 10, "dateiformat": ".sb3"},
            {"punkte": 5},
            {"titel": "Falsches Format", "punkte": 5, "dateiformat": ".exe"},
        ]})

        text = antwort.get_data(as_text=True)
        assert "2 Aufgabe(n)" in text
        assert "Übersprungen" in text
        assert Task.query.filter_by(title="Falsches Format").one().allowed_extension == ".pde"


class TestAufgabenSeite:
    def test_bietet_sichern_und_einlesen_an(self, admin, make_challenge, make_task):
        challenge = make_challenge()
        task = make_task(challenge)

        html = admin.get(f"/admin/challenges/{challenge.id}/tasks").get_data(as_text=True)

        assert "Alle Aufgaben sichern" in html
        assert "Datei einlesen" in html
        assert f"/admin/tasks/{task.id}/export" in html

    def test_nennt_den_wettbewerb(self, admin, make_challenge):
        challenge = make_challenge(title="Scratch-Wettbewerb")

        html = admin.get(f"/admin/challenges/{challenge.id}/tasks").get_data(as_text=True)

        assert "Scratch-Wettbewerb" in html

    def test_zeigt_die_vorhandenen_aufgaben_vor_dem_formular(
            self, admin, make_challenge, make_task):
        challenge = make_challenge()
        make_task(challenge)

        html = admin.get(f"/admin/challenges/{challenge.id}/tasks").get_data(as_text=True)

        assert html.index("Vorhandene Aufgaben") < html.index("Neue Aufgabe anlegen")
