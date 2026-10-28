"""Die Blöcke einer MakeCode-Abgabe (Calliope mini) als Bilder.

MakeCode legt den Quelltext eines Projekts in jede .hex; der Server liest
daraus die Blöcke und schreibt sie als scratchblocks-Text, gleich auf
Deutsch und in den Farben des Calliope-Editors. tests/makecode/linienfolger.hex
ist eine echte Datei aus MakeCode Calliope 8.1.15 für den Calliope mini 3
mit der Erweiterung MotionKit, gekürzt um den Maschinencode - übrig sind
nur die Zeilen, in denen das Projekt steckt.
"""

import io
import json
import lzma
import re
from pathlib import Path

import pytest

from plattform import makecode_skripte
from plattform.makecode_skripte import (
    KEIN_PROJEKT, OHNE_BLOECKE, OHNE_QUELLTEXT, bloecke_aus_quelltext, gebrauchte_texte, lies_projekt,
    skripte_aus_projekt, skripte_der_abgabe, tabelle,
)
from tests.helpers import csrf_token

LINIENFOLGER = Path(__file__).resolve().parent / "makecode" / "linienfolger.hex"

# Die LED-Muster aus dem Editor: das X von „Nein“ und der Pfeil nach Norden.
NEIN = "1000101010001000101010001"
PFEIL_NORD = "0010001110101010010000100"


def blockly(*bloecke, variablen=""):
    return ('<xml xmlns="https://developers.google.com/blockly/xml">'
            f'<variables>{variablen}</variables>{"".join(bloecke)}</xml>')


def projekt(xml, **weitere):
    return {"main.blocks": xml, "main.ts": "", "pxt.json": "{}", **weitere}


def skripte(xml, **weitere):
    figuren, hinweis = skripte_aus_projekt(projekt(xml, **weitere))
    assert hinweis == ""
    return figuren[0]["skripte"]


def beim_start(*innen):
    inhalt = f'<statement name="HANDLER">{verkettet(*innen)}</statement>' if innen else ""
    return f'<block type="pxt-on-start" x="0" y="0">{inhalt}</block>'


def verkettet(*bloecke):
    """Blöcke untereinander, wie Blockly sie mit <next> schachtelt."""
    if not bloecke:
        return ""
    erster, *rest = bloecke
    weiter = f"<next>{verkettet(*rest)}</next>" if rest else ""
    # <next> gehört ans Ende des äußeren Blocks, hinter alles, was in ihm steckt.
    ende = erster.rindex("</block>")
    return erster[:ende] + weiter + erster[ende:]


def zahl(wert):
    return f'<shadow type="math_number"><field name="NUM">{wert}</field></shadow>'


def mkcd(dateien):
    """Eine .mkcd so, wie MakeCode sie speichert."""
    inhalt = {"meta": {"name": "Probe", "editor": "blocksprj"}, "source": json.dumps(dateien)}
    return lzma.compress(json.dumps(inhalt).encode(), format=lzma.FORMAT_ALONE)


def hex_mit(nutzlast_kopf, nutzlast, typ="0E"):
    """Eine .hex mit eingebettetem Projekt, wie MakeCode sie baut (packSource)."""
    daten = bytes.fromhex("41140E2FB82FA2BB") + bytes([
        len(nutzlast_kopf) & 255, len(nutzlast_kopf) >> 8,
        len(nutzlast) & 255, (len(nutzlast) >> 8) & 255, (len(nutzlast) >> 16) & 255, 0, 0, 0,
    ]) + nutzlast_kopf + nutzlast
    zeilen = [":020000040000FA"]
    for stelle in range(0, len(daten), 16):
        stueck = list(daten[stelle:stelle + 16].ljust(16, b"\0"))
        satz = [0x10, (stelle >> 8) & 255, stelle & 255, int(typ, 16)] + stueck
        zeilen.append(":" + bytes(satz + [(-sum(satz)) & 255]).hex().upper())
    return ("\n".join(zeilen + [":00000001FF"]) + "\n").encode()


def gepackt(dateien, kopf=None):
    kopf_text = json.dumps(kopf or {"name": "Probe", "editor": "blocksprj"})
    programm = json.dumps(dateien)
    meta = json.dumps({"compression": "LZMA", "headerSize": len(kopf_text),
                       "textSize": len(programm), "name": "Probe"}).encode()
    return meta, lzma.compress((kopf_text + programm).encode(), format=lzma.FORMAT_ALONE)


class TestEchteDatei:
    def test_linienfolger(self):
        figuren, hinweis = skripte_der_abgabe(LINIENFOLGER)

        assert hinweis == ""
        assert len(figuren) == 1
        figur = figuren[0]
        assert figur["titel"] == "Programm"
        start, dauerhaft, knopf = figur["skripte"]
        # „beim Start“ und „dauerhaft“ liegen oben nebeneinander, der Knopf darunter.
        assert start == (
            "beim Start :: #54c9c9\n"
            "zeige Symbol [▦▦ v] :: #54c9c9\n"
            "pausiere \\(ms\\) (1000 v) :: #54c9c9\n"
            "Bildschirminhalt löschen :: #54c9c9\n"
            "setze [richtung v] auf (3) :: #a80000\n"
            "end")
        assert knopf == (
            "wenn Knopf [A v] (geklickt :: #a1005b reporter) :: #c90072\n"
            "zeige Symbol [▦▦ v] für (1000) ms :: #54c9c9\n"
            "setze [los v] auf <[wahr v] :: #006970> :: #a80000\n"
            "end")
        assert dauerhaft.startswith(
            "dauerhaft :: #54c9c9\nBildschirminhalt löschen :: #54c9c9\n"
            "während (los :: #a80000) mache :: #107c10\n")

    def test_bloecke_der_erweiterung(self):
        figuren, _ = skripte_der_abgabe(LINIENFOLGER)
        dauerhaft = figuren[0]["skripte"][1]

        # Text und Farbe kommen aus dem MotionKit, das in der Datei steckt.
        assert "Motor [beide v] Richtung [vorwärts v] Tempo (60) :: #6476fd" in dauerhaft
        assert "<(Linienfolger [links v] Status :: #6476fd reporter) [= v] (1) :: #006970>" in dauerhaft

    def test_sonst_wenn_wie_im_editor(self):
        figuren, _ = skripte_der_abgabe(LINIENFOLGER)
        dauerhaft = figuren[0]["skripte"][1]

        # Im „sonst“ steckt in der Datei ein weiteres „wenn“; der Editor zeigt
        # daraus eine Reihe von „sonst wenn“, ohne „sonst“.
        assert dauerhaft.count("sonst wenn ") == 5
        assert "sonst ::" not in dauerhaft
        assert dauerhaft.endswith("end\nend\nend")

    def test_klammern_glatt_und_leds(self):
        figuren, _ = skripte_der_abgabe(LINIENFOLGER)
        figur = figuren[0]

        assert figur["klammern"] == [
            ["beim Start", "c-block cap"],
            ["dauerhaft", "c-block cap"],
            ["sonst wenn %1 dann", "celse"],
            ["wenn %1 dann", "c-block"],
            ["wenn Knopf %1 %2", "c-block cap"],
            ["während %1 mache", "c-block"],
        ]
        assert figur["glatt"] == [True, True, True]
        assert figur["leds"] == [[NEIN], [], [PFEIL_NORD]]

    def test_name_und_readme_bleiben_draussen(self):
        dateien, _ = lies_projekt(LINIENFOLGER)
        assert json.loads(dateien["pxt.json"])["name"] == "motionkit_linienfolger"

        figuren, _ = skripte_der_abgabe(LINIENFOLGER)
        assert "motionkit_linienfolger" not in json.dumps(figuren)

    def test_als_mkcd(self, tmp_path):
        dateien, _ = lies_projekt(LINIENFOLGER)
        datei = tmp_path / "linienfolger.mkcd"
        datei.write_bytes(mkcd(dateien))

        assert skripte_der_abgabe(datei) == skripte_der_abgabe(LINIENFOLGER)

    def test_quelltext_in_gewoehnlichen_zeilen(self, tmp_path):
        # Kleine Projekte legt MakeCode in den Speicher, als Zeilen vom Typ 00.
        meta, daten = gepackt(projekt(blockly(beim_start())))
        datei = tmp_path / "klein.hex"
        datei.write_bytes(hex_mit(meta, daten, typ="00"))

        figuren, hinweis = skripte_der_abgabe(datei)
        assert hinweis == ""
        assert figuren[0]["skripte"] == ["beim Start :: #54c9c9\nend"]


class TestKaputteDateien:
    @pytest.mark.parametrize("inhalt, hinweis", [
        (b":020000040000FA\n:1000000000040020810A000015070000610A0000BA\n:00000001FF\n", OHNE_QUELLTEXT),
        (b"", KEIN_PROJEKT),
        (b"kein MakeCode", KEIN_PROJEKT),
        (b"PK\x03\x04 eine ZIP-Datei", KEIN_PROJEKT),
        (lzma.compress(b"{kein json", format=lzma.FORMAT_ALONE), KEIN_PROJEKT),
        (lzma.compress(b'{"source": 5}', format=lzma.FORMAT_ALONE), KEIN_PROJEKT),
    ])
    def test_hinweis_statt_fehler(self, tmp_path, inhalt, hinweis):
        datei = tmp_path / "abgabe.hex"
        datei.write_bytes(inhalt)

        assert skripte_der_abgabe(datei) == ([], hinweis)

    def test_abgeschnittene_hex(self, tmp_path):
        zeilen = LINIENFOLGER.read_text().splitlines()
        datei = tmp_path / "halb.hex"
        datei.write_text("\n".join(zeilen[:len(zeilen) // 2]) + "\n")

        assert skripte_der_abgabe(datei) == ([], OHNE_QUELLTEXT)

    def test_entpackt_zu_gross(self, tmp_path, monkeypatch):
        monkeypatch.setattr(makecode_skripte, "MAX_ENTPACKT", 10_000)
        datei = tmp_path / "riesig.mkcd"
        datei.write_bytes(lzma.compress(b" " * 50_000, format=lzma.FORMAT_ALONE))

        assert skripte_der_abgabe(datei) == ([], KEIN_PROJEKT)

    def test_entitaeten_werden_nicht_gelesen(self):
        xml = ('<!DOCTYPE xml [<!ENTITY a "aaaaaaaaaa">]>'
               + blockly(beim_start()))
        assert skripte_aus_projekt(projekt(xml)) == ([], KEIN_PROJEKT)

    def test_kaputtes_xml(self):
        assert skripte_aus_projekt(projekt("<xml><block")) == ([], KEIN_PROJEKT)

    def test_nur_python(self):
        dateien = {"main.py": "basic.show_number(1)", "main.ts": "basic.showNumber(1)"}
        assert skripte_aus_projekt(dateien) == ([], OHNE_BLOECKE)

    def test_sehr_tief_geschachtelt(self):
        innen = "".join('<block type="controls_repeat_ext"><statement name="DO">' for _ in range(300))
        aussen = "".join("</statement></block>" for _ in range(300))
        figuren, hinweis = skripte_aus_projekt(projekt(blockly(innen + aussen)))

        assert hinweis == ""
        assert figuren[0]["skripte"]


class TestBloecke:
    def test_unbekannter_block_grau_mit_namen(self):
        block = f'<block type="erfunden_block"><value name="X">{zahl(3)}</value></block>'
        assert skripte(blockly(beim_start(block))) == [
            "beim Start :: #54c9c9\nerfunden_block (3) :: #bbbbbb\nend"]

    def test_zeige_leds(self):
        bild = ("`\n# . . . #\n. # . # .\n. . # . .\n. # . # .\n# . . . #\n`")
        block = f'<block type="device_show_leds"><field name="LEDS">{bild}</field></block>'
        figuren, _ = skripte_aus_projekt(projekt(blockly(beim_start(block))))

        assert figuren[0]["skripte"] == ["beim Start :: #54c9c9\nzeige LEDs [▦▦] :: #54c9c9\nend"]
        assert figuren[0]["leds"] == [[NEIN]]

    def test_optionale_eingaenge_nur_wenn_aufgeklappt(self):
        ohne = f'<block type="device_show_number"><value name="number">{zahl(7)}</value></block>'
        mit = ('<block type="device_show_number">'
               f'<value name="number">{zahl(7)}</value><value name="interval">{zahl(150)}</value></block>')

        assert skripte(blockly(beim_start(ohne, mit))) == [
            "beim Start :: #54c9c9\n"
            "zeige Zahl (7) :: #54c9c9\n"
            "zeige Zahl (7) in einem Intervall von (150) ms :: #54c9c9\n"
            "end"]

    def test_zugeklappt_trotz_eingang_in_der_datei(self):
        # Der Editor behält den Eingang in der Datei, auch wenn er mit ⊖ zu
        # ist; maßgeblich ist die Zahl offener Eingänge in der Mutation.
        def block(offen):
            return ('<block type="device_show_number">'
                    f'<mutation xmlns="http://www.w3.org/1999/xhtml" _expanded="{offen}" _input_init="true"></mutation>'
                    f'<value name="number">{zahl(7)}</value><value name="interval">{zahl(150)}</value></block>')

        assert skripte(blockly(beim_start(block(0), block(1)))) == [
            "beim Start :: #54c9c9\n"
            "zeige Zahl (7) :: #54c9c9\n"
            "zeige Zahl (7) in einem Intervall von (150) ms :: #54c9c9\n"
            "end"]

    def test_schleifen_und_sonst(self):
        wiederhole = (f'<block type="controls_repeat_ext"><value name="TIMES">{zahl(4)}</value>'
                      '<statement name="DO"><block type="device_clear_display"></block></statement></block>')
        wenn = ('<block type="controls_if"><mutation else="1"></mutation>'
                '<value name="IF0"><shadow type="logic_boolean"><field name="BOOL">TRUE</field></shadow></value>'
                '<statement name="ELSE"><block type="device_clear_display"></block></statement></block>')
        figuren, _ = skripte_aus_projekt(projekt(blockly(beim_start(wiederhole, wenn))))

        assert figuren[0]["skripte"] == [
            "beim Start :: #54c9c9\n"
            "(4) -mal wiederholen mache :: #107c10\n"
            "Bildschirminhalt löschen :: #54c9c9\n"
            "end\n"
            "wenn <[wahr v] :: #006970> dann :: #006970\n"
            "ansonsten :: #006970\n"
            "Bildschirminhalt löschen :: #54c9c9\n"
            "end\n"
            "end"]
        assert ["%1 -mal wiederholen mache", "c-block"] in figuren[0]["klammern"]
        assert ["ansonsten", "celse"] in figuren[0]["klammern"]

    def test_rechnen_und_zufall(self):
        rechnen = ('<block type="math_arithmetic"><field name="OP">MULTIPLY</field>'
                   f'<value name="A">{zahl(2)}</value><value name="B">'
                   f'<block type="device_random"><value name="min">{zahl(1)}</value>'
                   f'<value name="limit">{zahl(6)}</value></block></value></block>')
        setze = ('<block type="variables_set"><field name="VAR">wurf</field>'
                 f'<value name="VALUE">{rechnen}</value></block>')

        assert skripte(blockly(beim_start(setze))) == [
            "beim Start :: #54c9c9\n"
            "setze [wurf v] auf ((2) [× v] (wähle eine zufällige Zahl von (1) bis (6) :: #712672 reporter)"
            " :: #712672 reporter) :: #a80000\n"
            "end"]

    def test_wert_eines_ereignisses(self):
        block = '<block type="radio_on_number_drag"><field name="HANDLER_DRAG_PARAM_receivedNumber">receivedNumber</field></block>'
        assert skripte(blockly(block)) == [
            "wenn Datenpaket über Funk empfangen (receivedNumber :: #a80000) :: #e3008c\nend"]

    def test_text_eines_teams_wird_nicht_zu_syntax(self):
        setze = ('<block type="variables_set"><field name="VAR">a) v</field>'
                 '<value name="VALUE"><shadow type="text"><field name="TEXT">[▦▦] :: x</field></shadow></value></block>')
        figuren, _ = skripte_aus_projekt(projekt(blockly(beim_start(setze))))

        assert figuren[0]["skripte"] == [
            "beim Start :: #54c9c9\nsetze [a\\) \\v v] auf [\\[□□\\] :\\: x] :: #a80000\nend"]
        assert figuren[0]["leds"] == [[]]

    def test_lose_bloecke_ohne_klammer(self):
        loser = '<block type="device_clear_display" x="0" y="900"></block>'
        figuren, _ = skripte_aus_projekt(projekt(blockly(beim_start(), loser)))

        assert figuren[0]["skripte"] == ["beim Start :: #54c9c9\nend", "Bildschirminhalt löschen :: #54c9c9"]
        assert figuren[0]["glatt"] == [True, False]


class TestQuelltext:
    QUELLE = '''
//% color=#123456 weight=10
namespace probe {
    export enum Seite {
        //% block="links"
        Links,
        //% block="right"
        Rechts = 2
    }
    //% blockId=probe_fahre block="drive %seite|speed %tempo"
    export function fahre(seite: Seite, tempo: number): void {
    }
    //% blockId=probe_frei block="is free"
    export function frei(): boolean { return true }
    //% blockId=probe_wenn block="on obstacle"
    export function wennHindernis(body: () => void): void {}
    //% blockId=probe_abstand block="distance" color=#ff0000
    export function abstand(): number { return 0 }
}
'''

    def test_bloecke_und_werte(self):
        uebersetzung = {"probe.fahre|block": "fahre %richtung|mit %geschwindigkeit",
                        "probe.Seite.Rechts|block": "rechts"}
        bloecke, werte = bloecke_aus_quelltext([self.QUELLE], uebersetzung)

        # Die Übersetzung nennt die Eingänge anders; es gilt die Reihenfolge.
        assert bloecke["probe_fahre"] == {"text": "fahre %seite|mit %tempo", "form": "stapel", "farbe": "#123456"}
        assert bloecke["probe_frei"]["form"] == "bedingung"
        assert bloecke["probe_wenn"]["form"] == "hut"
        assert bloecke["probe_abstand"] == {"text": "distance", "form": "wert", "farbe": "#ff0000"}
        assert werte == {"probe.Seite.Links": "links", "probe.Seite.Rechts": "rechts"}

    def test_falsche_zahl_der_eingaenge_bleibt_beim_original(self):
        bloecke, _ = bloecke_aus_quelltext([self.QUELLE], {"probe.fahre|block": "fahre %seite"})
        assert bloecke["probe_fahre"]["text"] == "drive %seite|speed %tempo"


class TestTabelle:
    def test_jeder_block_ist_vollstaendig(self):
        daten = tabelle()
        assert "MIT" in daten["quelle"]
        for block_id, eintrag in daten["bloecke"].items():
            assert eintrag["text"], block_id
            assert eintrag["form"] in ("stapel", "wert", "bedingung", "hut", "klammer"), block_id
            assert len(eintrag["farbe"]) == 7 and eintrag["farbe"].startswith("#"), block_id

    def test_symbole_sind_fuenf_mal_fuenf(self):
        symbole = tabelle()["symbole"]
        assert symbole["IconNames.No"] == NEIN
        assert symbole["IconNames.ArrowNorth"] == PFEIL_NORD
        assert all(len(muster) == 25 and set(muster) <= {"0", "1"} for muster in symbole.values())

    def test_grundbloecke_auf_deutsch(self):
        bloecke = tabelle()["bloecke"]
        assert bloecke["device_forever"]["text"] == "dauerhaft"
        assert bloecke["device_button_selected_event"]["form"] == "hut"
        assert bloecke["radio_datagram_send"]["text"] == "sende Zahl %value über Funk"

    def test_texte_wie_im_editor(self):
        # Die Live-Übersetzungen, nicht die älteren aus dem Quelltext
        # („Button … ist gedrückt“, „zeige Zeichenfolge“).
        bloecke = tabelle()["bloecke"]
        assert bloecke["device_get_button2"]["text"] == "Knopf|%NAME|ist geklickt"
        assert bloecke["device_print_message"]["text"].startswith("zeige|Text %text ||")
        assert tabelle()["texte"]["repeat %1 times"] == "%1-mal wiederholen"

    def test_alle_editor_texte_in_der_tabelle(self):
        # Nur reine Zeichen wie „=“ oder „%1 %2“ übersetzt der Editor nicht.
        fehlen = gebrauchte_texte() - set(tabelle()["texte"])
        assert all(not re.search(r"[A-Za-z]", schluessel.replace("%", "")) for schluessel in fehlen), fehlen


def abgeben(client, task, inhalt, endung=".hex"):
    from plattform.models import Submission

    client.post(f"/submit/{task.id}", data={
        "csrf_token": csrf_token(client, "/challenge"),
        "file": (io.BytesIO(inhalt), f"loesung{endung}"),
    }, content_type="multipart/form-data")
    return Submission.query.filter_by(task_id=task.id).order_by(Submission.id.desc()).first()


class TestSeiten:
    def test_bewertungsseite(self, admin, make_challenge, make_task, logged_in_team):
        challenge = make_challenge()
        task = make_task(challenge, allowed_extension=".hex")
        client, _team = logged_in_team(challenge)
        abgabe = abgeben(client, task, LINIENFOLGER.read_bytes())

        seite = admin.get("/admin/submissions").get_data(as_text=True)
        assert "🧩 Skripte" in seite
        assert "scratchblocks.min.js" in seite

        daten = admin.get(f"/admin/submissions/{abgabe.id}/skripte").get_json()
        assert daten["hinweis"] == ""
        assert daten["figuren"][0]["skripte"][0].startswith("beim Start")
        assert ["beim Start", "c-block cap"] in daten["figuren"][0]["klammern"]

    def test_teamseite(self, make_challenge, make_task, logged_in_team):
        challenge = make_challenge()
        task = make_task(challenge, allowed_extension=".mkcd")
        client, _team = logged_in_team(challenge)
        dateien, _ = lies_projekt(LINIENFOLGER)
        abgabe = abgeben(client, task, mkcd(dateien), ".mkcd")

        assert "🧩 Unsere Skripte anzeigen" in client.get("/challenge").get_data(as_text=True)
        daten = client.get(f"/challenge/abgabe/{abgabe.id}/skripte").get_json()
        assert len(daten["figuren"][0]["skripte"]) == 3

    def test_hinweis_fuer_teams_ohne_download(self, make_challenge, make_task, logged_in_team):
        challenge = make_challenge()
        task = make_task(challenge, allowed_extension=".hex")
        client, _team = logged_in_team(challenge)
        abgabe = abgeben(client, task, b":020000040000FA\n:00000001FF\n")

        daten = client.get(f"/challenge/abgabe/{abgabe.id}/skripte").get_json()
        assert daten == {"figuren": [], "hinweis":
                         "In der .hex-Datei steckt kein Projekt aus MakeCode, nur das fertige Programm."}
