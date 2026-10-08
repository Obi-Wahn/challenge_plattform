"""Die Skripte einer Scratch-Abgabe auf der Bewertungsseite.

Der Server liest aus der .sb3 nur die project.json und schreibt die Blöcke
als Text in der Schreibweise von scratchblocks; gezeichnet wird im Browser.
Geprüft wird hier der Text - und dass eine kaputte oder bösartige Datei
weder den Server aufhält noch etwas anderes als Text ergibt.
"""

import io
import json
import zipfile
from pathlib import Path

import pytest

import scratch_skripte
from scratch_skripte import skripte_aus_projekt, skripte_der_abgabe, zeichen_schuetzen
from tests.helpers import csrf_token

BEISPIEL = Path(__file__).resolve().parent.parent / "beispiele" / "scratch-wettbewerb.zip"


class Projekt:
    """Baut eine project.json Block für Block, wie Scratch sie speichert."""

    def __init__(self):
        self.bloecke = {}

    def block(self, opcode, inputs=None, fields=None, oben=None, shadow=False,
              mutation=None):
        kennung = f"b{len(self.bloecke) + 1}"
        self.bloecke[kennung] = {
            "opcode": opcode, "next": None, "parent": None,
            "inputs": inputs or {}, "fields": fields or {},
            "shadow": shadow, "topLevel": oben is not None,
        }
        if oben is not None:
            self.bloecke[kennung]["x"], self.bloecke[kennung]["y"] = oben
        if mutation:
            self.bloecke[kennung]["mutation"] = mutation
        return kennung

    def kette(self, *kennungen):
        for vorher, nachher in zip(kennungen, kennungen[1:]):
            self.bloecke[vorher]["next"] = nachher
        return kennungen[0]

    def daten(self, name="Figur1"):
        return {"targets": [
            {"isStage": True, "name": "Stage", "blocks": {}},
            {"isStage": False, "name": name, "blocks": self.bloecke},
        ]}

    def skripte(self):
        return skripte_aus_projekt(self.daten())[1]["skripte"]


def text(wert):
    return [1, [10, wert]]


def zahl(wert):
    return [1, [4, str(wert)]]


def als_sb3(pfad, daten):
    with zipfile.ZipFile(pfad, "w") as archiv:
        archiv.writestr("project.json", json.dumps(daten))
    return pfad


class TestEchteAbgaben:
    """Die .sb3-Dateien aus dem Beispiel-Wettbewerb, gebaut wie von Scratch."""

    def beispiel(self, tmp_path, name):
        with zipfile.ZipFile(BEISPIEL) as archiv:
            ziel = tmp_path / "abgabe.sb3"
            ziel.write_bytes(archiv.read(f"abgaben/{name}"))
        return ziel

    def test_punkte_sammeln(self, tmp_path):
        figuren, hinweis = skripte_der_abgabe(self.beispiel(tmp_path, "team_1/punkte-sammeln.sb3"))

        assert hinweis == ""
        assert [(f["name"], f["buehne"]) for f in figuren] == [
            ("Stage", True), ("Katze", False), ("Apfel", False)]
        assert figuren[0]["skripte"] == []
        assert figuren[1]["skripte"] == [
            "when flag clicked\n"
            "forever\n"
            "  go to (Mauszeiger v)\n"
            "end"]
        assert figuren[2]["skripte"] == [
            "when flag clicked\n"
            "set [Punkte v] to [0]\n"
            "forever\n"
            "  if <touching (Katze v) ?> then\n"
            "    change [Punkte v] by (1)\n"
            "    go to (Zufallsposition v)\n"
            "  end\n"
            "end"]

    def test_zwei_skripte_in_einer_figur(self, tmp_path):
        figuren, _hinweis = skripte_der_abgabe(self.beispiel(tmp_path, "team_1/farbenstern.sb3"))

        assert figuren[1]["skripte"] == [
            "when flag clicked\nclear graphic effects\nsay [Klick mich an!]",
            "when this sprite clicked\nsay []\nrepeat (10)\n"
            "  change [Farbe v] effect by (25)\n  turn right (36) degrees\nend",
        ]

    def test_jede_beispielabgabe_laesst_sich_lesen(self, tmp_path):
        with zipfile.ZipFile(BEISPIEL) as archiv:
            namen = [n for n in archiv.namelist() if n.endswith(".sb3")]
        assert namen

        for name in namen:
            figuren, hinweis = skripte_der_abgabe(self.beispiel(tmp_path, name.split("/", 1)[1]))
            assert hinweis == "", name
            alles = "\n".join(s for f in figuren for s in f["skripte"])
            assert alles, name
            assert ":: grey" not in alles, f"{name}: unbekannter Block"


class TestBloecke:
    def test_falls_sonst_mit_eingerueckten_bloecken(self):
        p = Projekt()
        bedingung = p.block("sensing_mousedown")
        ja = p.block("looks_say", {"MESSAGE": text("ja")})
        nein = p.kette(p.block("looks_say", {"MESSAGE": text("nein")}), p.block("looks_hide"))
        p.block("control_if_else", {"CONDITION": [2, bedingung], "SUBSTACK": [2, ja],
                                    "SUBSTACK2": [2, nein]}, oben=(0, 0))

        assert p.skripte() == [
            "if <mouse down?> then\n  say [ja]\nelse\n  say [nein]\n  hide\nend"]

    def test_leere_bedingung_bleibt_ein_sechseck(self):
        p = Projekt()
        p.block("control_if", oben=(0, 0))

        assert p.skripte() == ["if <> then\nend"]

    def test_block_auf_einem_eingang_verdeckt_den_schatten(self):
        p = Projekt()
        zufall = p.block("operator_random", {"FROM": zahl(1), "TO": zahl(6)})
        p.block("motion_movesteps", {"STEPS": [3, zufall, [4, "10"]]}, oben=(0, 0))

        assert p.skripte() == ["move (pick random (1) to (6)) steps"]

    def test_variablen_und_listen(self):
        p = Projekt()
        variable = p.block("data_variable", fields={"VARIABLE": ["Punkte", "v1"]})
        laenge = p.block("data_lengthoflist", fields={"LIST": ["Namen", "l1"]})
        p.kette(
            p.block("data_addtolist", {"ITEM": [3, variable, [10, ""]]},
                    {"LIST": ["Namen", "l1"]}, oben=(0, 0)),
            p.block("looks_say", {"MESSAGE": [3, laenge, [10, ""]]}),
            p.block("looks_say", {"MESSAGE": [3, [12, "Zeit", "v2"], [10, ""]]}),
        )

        assert p.skripte() == [
            "add (Punkte :: variables) to [Namen v]\n"
            "say (length of [Namen v] :: list)\n"
            "say (Zeit :: variables)"]

    def test_eigener_block_mit_definition_und_aufruf(self):
        p = Projekt()
        kopf = p.block("procedures_prototype", shadow=True, mutation={
            "proccode": "springe %s hoch %b", "argumentnames": '["Höhe", "schnell"]',
            "argumentids": '["a1", "a2"]'})
        hoehe = p.block("argument_reporter_string_number", fields={"VALUE": ["Höhe", None]})
        p.kette(p.block("procedures_definition", {"custom_block": [1, kopf]}, oben=(0, 0)),
                p.block("motion_changeyby", {"DY": [3, hoehe, [4, "10"]]}))
        p.block("procedures_call", {"a1": zahl(30)}, oben=(0, 100), mutation={
            "proccode": "springe %s hoch %b", "argumentids": '["a1", "a2"]'})

        assert p.skripte() == [
            "define springe (Höhe) hoch <schnell>\nchange y by (Höhe :: custom-arg)",
            "springe (30) hoch <> :: custom",
        ]

    def test_nachricht_senden_und_empfangen(self):
        p = Projekt()
        p.block("event_whenbroadcastreceived", fields={"BROADCAST_OPTION": ["los", "m1"]},
                oben=(0, 0))
        p.block("event_broadcast", {"BROADCAST_INPUT": [1, [11, "los", "m1"]]}, oben=(0, 50))

        assert p.skripte() == ["when I receive [los v]", "broadcast (los v)"]

    def test_unbekannter_block_erscheint_grau_mit_seinem_namen(self):
        p = Projekt()
        p.block("videoSensing_videoToggle", {"VIDEO_STATE": zahl(1)}, oben=(0, 0))

        assert p.skripte() == ["videoSensing_videoToggle (1) :: grey"]

    def test_skripte_stehen_von_oben_nach_unten(self):
        p = Projekt()
        p.block("looks_hide", oben=(0, 300))
        p.block("looks_show", oben=(500, 10))
        p.block("looks_nextcostume", oben=(0, 10))

        assert p.skripte() == ["next costume", "show", "hide"]

    def test_die_buehne_steht_vorne(self):
        daten = Projekt().daten()
        daten["targets"].reverse()

        assert [f["buehne"] for f in skripte_aus_projekt(daten)] == [True, False]


class TestAuswahlwerte:
    """scratchblocks übersetzt Blocktexte, aber keine Auswahlwerte."""

    def test_menues_stehen_auf_deutsch(self):
        p = Projekt()
        taste = p.block("sensing_keyoptions", fields={"KEY_OPTION": ["space", None]}, shadow=True)
        klon = p.block("control_create_clone_of_menu",
                       fields={"CLONE_OPTION": ["_myself_", None]}, shadow=True)
        p.kette(
            p.block("event_whenkeypressed", fields={"KEY_OPTION": ["up arrow", None]}, oben=(0, 0)),
            p.block("looks_changeeffectby", {"CHANGE": zahl(25)}, {"EFFECT": ["GHOST", None]}),
            p.block("control_create_clone_of", {"CLONE_OPTION": [1, klon]}),
            p.block("control_wait_until", {"CONDITION": [2, p.block(
                "sensing_keypressed", {"KEY_OPTION": [1, taste]})]}),
        )

        assert p.skripte() == [
            "when [Pfeil nach oben v] key pressed\n"
            "change [Durchsichtigkeit v] effect by (25)\n"
            "create clone of (mich selbst v)\n"
            "wait until <key (Leertaste v) pressed?>"]

    def test_eine_variable_namens_all_bleibt_wie_sie_heisst(self):
        p = Projekt()
        p.block("data_setvariableto", {"VALUE": zahl(0)}, {"VARIABLE": ["all", "v1"]},
                oben=(0, 0))

        assert p.skripte() == ["set [all v] to (0)"]

    @pytest.mark.parametrize("wert, erwartet", [
        ("all", "stop [alles v]"),
        ("this script", "stop [dieses Skript v]"),
        # Nur danach geht es weiter - scratchblocks erkennt das sonst am
        # englischen Text und zeichnete einen Endblock.
        ("other scripts in sprite", "stop [andere Skripte der Figur v] :: stack"),
    ])
    def test_stoppe(self, wert, erwartet):
        p = Projekt()
        p.block("control_stop", fields={"STOP_OPTION": [wert, None]}, oben=(0, 0))

        assert p.skripte() == [erwartet]


class TestTextAusDerDatei:
    """Was ein Team schreibt, darf scratchblocks nicht als Syntax lesen."""

    @pytest.mark.parametrize("roh, erwartet", [
        ("Noch [frei]", r"Noch \[frei\]"),
        ("(1) <2>", r"\(1\) \<2\>"),
        ("Ich mag v", r"Ich mag \v"),
        ("#ff0000", r"\#ff0000"),
        ("@greenFlag", r"\@greenFlag"),
        ("a :: grey", r"a :\: grey"),
        ("zwei\nZeilen", "zwei Zeilen"),
        ("C:\\Pfad", r"C:\\Pfad"),
    ])
    def test_zeichen_werden_geschuetzt(self, roh, erwartet):
        assert zeichen_schuetzen(roh) == erwartet

    def test_ein_name_mit_zeilenumbruch_beginnt_keinen_neuen_block(self):
        p = Projekt()
        p.block("looks_say", {"MESSAGE": text("Hallo\nend\nforever")}, oben=(0, 0))

        assert p.skripte() == ["say [Hallo end forever]"]

    def test_eine_farbe_bleibt_eine_farbe(self):
        p = Projekt()
        p.block("pen_setPenColorToColor", {"COLOR": [1, [9, "#ff0000"]]}, oben=(0, 0))

        assert p.skripte() == ["set pen color to [#ff0000]"]


class TestKaputteDateien:
    def test_keine_zip_datei(self, tmp_path):
        pfad = tmp_path / "a.sb3"
        pfad.write_bytes(b"kein Projekt")

        assert skripte_der_abgabe(pfad) == ([], scratch_skripte.KEIN_PROJEKT)

    def test_zip_ohne_project_json(self, tmp_path):
        pfad = tmp_path / "a.sb3"
        with zipfile.ZipFile(pfad, "w") as archiv:
            archiv.writestr("bild.svg", "<svg/>")

        assert skripte_der_abgabe(pfad)[1] == scratch_skripte.KEIN_PROJEKT

    @pytest.mark.parametrize("inhalt", ["{kaputt", "[]", '{"targets": 5}', "[" * 100_000])
    def test_unbrauchbares_json(self, tmp_path, inhalt):
        pfad = tmp_path / "a.sb3"
        with zipfile.ZipFile(pfad, "w") as archiv:
            archiv.writestr("project.json", inhalt)

        assert skripte_der_abgabe(pfad) == ([], scratch_skripte.KEIN_PROJEKT)

    def test_zu_grosse_project_json_wird_nicht_gelesen(self, tmp_path, monkeypatch):
        monkeypatch.setattr(scratch_skripte, "MAX_PROJECT_JSON", 1000)
        pfad = als_sb3(tmp_path / "a.sb3", {"targets": [], "x": "y" * 2000})

        assert skripte_der_abgabe(pfad)[1] == scratch_skripte.KEIN_PROJEKT

    def test_seltsame_werte_ueberall(self):
        daten = {"targets": [
            None, 5, {"name": None, "blocks": [1, 2]},
            {"name": "X", "blocks": {
                "a": "kein Block", "b": [12, "lose Variable", "v1", 0, 0],
                "c": {"opcode": None, "topLevel": True, "inputs": "x", "fields": 3},
                "d": {"opcode": "looks_say", "topLevel": True, "y": "oben",
                      "inputs": {"MESSAGE": [1]}},
                "e": {"opcode": "procedures_call", "topLevel": True,
                      "mutation": {"proccode": "tu %s", "argumentids": "{kaputt"}},
            }},
        ]}

        figuren = skripte_aus_projekt(daten)

        assert figuren[-1]["skripte"] == ["? :: grey", "say ()", "tu () :: custom"]

    def test_bloecke_im_kreis(self):
        p = Projekt()
        a = p.block("looks_show", oben=(0, 0))
        b = p.block("looks_hide")
        p.kette(a, b)
        p.bloecke[b]["next"] = a
        selbst = p.block("operator_add", oben=(0, 100))
        p.bloecke[selbst]["inputs"] = {"NUM1": [3, selbst, [4, "1"]],
                                       "NUM2": [3, selbst, [4, "1"]]}

        assert p.skripte() == ["show\nhide", "(() + ())"]

    def test_tief_verschachtelt(self):
        p = Projekt()
        innen = None
        for _ in range(5000):
            innen = p.block("control_forever", {"SUBSTACK": [2, innen]} if innen else None)
        p.bloecke[innen]["topLevel"] = True
        p.bloecke[innen]["x"] = p.bloecke[innen]["y"] = 0
        zahl_innen = None
        for _ in range(5000):
            zahl_innen = p.block("operator_round", {"NUM": [3, zahl_innen, [4, "1"]]}
                                 if zahl_innen else None)
        p.block("motion_movesteps", {"STEPS": [3, zahl_innen, [4, "1"]]}, oben=(0, 100))

        skripte = p.skripte()

        assert len(skripte) == 2
        assert skripte[0].count("forever") == scratch_skripte.MAX_TIEFE


class TestAbruf:
    def abgabe(self, make_challenge, make_task, logged_in_team, inhalt, endung=".sb3"):
        from models import Submission

        challenge = make_challenge()
        task = make_task(challenge, allowed_extension=endung)
        client, _team = logged_in_team(challenge)
        client.post(f"/submit/{task.id}", data={
            "csrf_token": csrf_token(client, "/"),
            "file": (io.BytesIO(inhalt), f"loesung{endung}"),
        }, content_type="multipart/form-data")
        return Submission.query.one()

    def sb3(self, daten):
        puffer = io.BytesIO()
        with zipfile.ZipFile(puffer, "w") as archiv:
            archiv.writestr("project.json", json.dumps(daten))
        return puffer.getvalue()

    def test_die_skripte_kommen_als_json(self, admin, make_challenge, make_task, logged_in_team):
        p = Projekt()
        p.block("looks_say", {"MESSAGE": text("<script>alert(1)</script>")}, oben=(0, 0))
        abgabe = self.abgabe(make_challenge, make_task, logged_in_team, self.sb3(p.daten("<b>")))

        antwort = admin.get(f"/admin/submissions/{abgabe.id}/skripte")

        assert antwort.status_code == 200
        assert antwort.mimetype == "application/json"
        assert antwort.headers["X-Content-Type-Options"] == "nosniff"
        daten = antwort.get_json()
        assert daten["hinweis"] == ""
        assert daten["figuren"][1]["name"] == "<b>"
        assert daten["figuren"][1]["skripte"] == [r"say [\<script\>alert\(1\)\</script\>]"]

    def test_eine_kaputte_datei_sagt_das(self, admin, make_challenge, make_task, logged_in_team):
        abgabe = self.abgabe(make_challenge, make_task, logged_in_team, b"kaputt")

        daten = admin.get(f"/admin/submissions/{abgabe.id}/skripte").get_json()

        assert daten["figuren"] == []
        assert "herunterladen" in daten["hinweis"]

    def test_eine_verschwundene_datei_sagt_das(
            self, admin, make_challenge, make_task, logged_in_team):
        import os

        abgabe = self.abgabe(make_challenge, make_task, logged_in_team, self.sb3({"targets": []}))
        os.remove(abgabe.pfad)

        daten = admin.get(f"/admin/submissions/{abgabe.id}/skripte").get_json()

        assert "nicht mehr" in daten["hinweis"]

    def test_andere_formate_werden_nicht_als_zip_gelesen(
            self, admin, make_challenge, make_task, logged_in_team):
        abgabe = self.abgabe(make_challenge, make_task, logged_in_team, b"print(1)", ".py")

        daten = admin.get(f"/admin/submissions/{abgabe.id}/skripte").get_json()

        assert daten["figuren"] == []
        assert ".sb3" in daten["hinweis"]

    def test_ohne_anmeldung_gibt_es_nichts(
            self, client, admin, make_challenge, make_task, logged_in_team):
        abgabe = self.abgabe(make_challenge, make_task, logged_in_team, self.sb3({"targets": []}))

        antwort = client.get(f"/admin/submissions/{abgabe.id}/skripte")

        assert antwort.status_code == 302
        assert "/admin/login" in antwort.headers["Location"]


class TestDieBibliothek:
    def test_sie_wird_nur_mit_scratch_abgaben_geladen(
            self, admin, make_challenge, make_task, logged_in_team):
        challenge = make_challenge()
        task = make_task(challenge, allowed_extension=".py")
        client, _team = logged_in_team(challenge)
        client.post(f"/submit/{task.id}", data={
            "csrf_token": csrf_token(client, "/"),
            "file": (io.BytesIO(b"print(1)"), "loesung.py"),
        }, content_type="multipart/form-data")

        html = admin.get("/admin/submissions").get_data(as_text=True)

        assert "scratchblocks.min.js" not in html

    def test_mit_scratch_abgabe_wird_sie_geladen(
            self, admin, make_challenge, make_task, logged_in_team):
        abgabe = TestAbruf().abgabe(make_challenge, make_task, logged_in_team, b"x")
        assert abgabe

        html = admin.get("/admin/submissions").get_data(as_text=True)

        assert "vendor/scratchblocks/scratchblocks.min.js" in html
        assert "vendor/scratchblocks/translations.js" in html
