"""Die Skripte einer Snap!-Abgabe auf der Bewertungsseite.

Snap! speichert ein Projekt als XML. Der Server liest daraus die Skripte und
schreibt sie in derselben Schreibweise wie bei Scratch (scratchblocks);
gezeichnet wird im Browser. Die beiden Dateien unter tests/snap/ sind echte
Exporte aus Snap! 12, nur ohne Vorschaubild. Geprüft wird hier der Text -
und dass eine kaputte oder bösartige Datei weder den Server aufhält noch
etwas anderes als Text ergibt.
"""

import io
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

import snap_skripte
from snap_skripte import skripte_aus_projekt, skripte_der_abgabe
from tests.helpers import csrf_token

ORDNER = Path(__file__).resolve().parent / "snap"


def projekt(skripte="", bloecke="", gemeinsam="", buehne=""):
    """Ein Projekt im Aufbau von Snap! 12 mit einer Figur „Katze“."""
    return (
        '<project name="Probe" app="Snap! 12.2.3, https://snap.berkeley.edu" version="2">'
        '<notes></notes><thumbnail></thumbnail><scenes select="1"><scene name="Probe">'
        f'<blocks>{gemeinsam}</blocks>'
        '<stage name="Stage" width="480" height="360"><pentrails></pentrails>'
        f'<variables></variables><blocks></blocks><scripts>{buehne}</scripts>'
        '<sprites select="1"><sprite name="Katze" idx="1" x="0" y="0">'
        f'<blocks>{bloecke}</blocks><variables></variables><scripts>{skripte}</scripts>'
        '</sprite></sprites></stage><variables></variables></scene></scenes></project>'
    )


def _wurzel(xml):
    return ET.fromstring(xml)


def skripte(xml):
    """Die Skripte der Figur „Katze“."""
    return skripte_aus_projekt(_wurzel(xml))[1]["skripte"]


def skript(*bloecke, x=0, y=0):
    return f'<script x="{x}" y="{y}">{"".join(bloecke)}</script>'


class TestEchteDateien:
    def test_fang_die_maus(self):
        figuren, hinweis = skripte_der_abgabe(ORDNER / "fang-die-maus.xml")

        assert hinweis == ""
        assert [(f["name"], f["buehne"]) for f in figuren] == [
            ("Stage", True), ("Katze", False), ("", False)]
        assert figuren[0]["skripte"] == [
            "when flag clicked\nerase all\nset pen color to [#ff0000]"]
        assert figuren[2]["titel"] == "Eigene Blöcke für alle Figuren"
        assert figuren[2]["skripte"] == [
            "define springe (höhe)\n"
            "change y by (höhe :: variables)\n"
            "wait (0.5) seconds\n"
            "change y by ((0) - (höhe :: variables))"]

        katze = figuren[1]["skripte"]
        # Von oben nach unten, wie die Skripte auf der Fläche liegen.
        assert katze[0].startswith("when flag clicked\nset size to (50) %")
        assert "  if <touching (Mauszeiger v) ?> then\n" in katze[0]
        assert "    go to (Zufallsposition v)\n  else\n  end\nend" in katze[0]
        assert "when this sprite clicked\nask [Wie viel ist 3 + 4?] and wait\n" \
               "if <(answer) = ((3) + (4))> then" in "\n\n".join(katze)
        assert "when I receive [start v]\nrepeat until <touching (Rand v) ?>" in "\n\n".join(katze)

    def test_was_nur_snap_kann(self):
        figuren, _ = skripte_der_abgabe(ORDNER / "fang-die-maus.xml")
        alles = "\n\n".join(figuren[1]["skripte"])

        assert "Skriptvariablen (a :: variables) (b :: variables) :: variables" in alles
        assert "für (i :: variables) = (1) bis (10)\n" \
               "  füge ((i :: variables) * (i :: variables)) zu (liste :: variables) hinzu :: list\n" \
               "end" in alles
        assert "für jedes (item :: variables) von (liste :: variables)\n" in alles
        assert "set [liste v] to (wende ((() + (1)) :: grey ring) an auf (liste :: variables) :: list)" in alles
        # Ein eigener Block in der Farbe seiner Kategorie.
        assert "springe (50) :: motion" in alles
        assert "say (join [Punkte:] (punkte :: variables)) for (2) seconds" in alles

    def test_vieleck_und_raten(self):
        figuren, _ = skripte_der_abgabe(ORDNER / "vieleck-und-raten.xml")
        pfeil = figuren[1]["skripte"]

        # Ein Block, der nur der Figur gehört, steht bei ihr, und zwar zuerst.
        assert pfeil[0] == (
            "define Vieleck (Ecken) (Länge)\n"
            "repeat (Ecken :: variables)\n"
            "  move (Länge :: variables) steps\n"
            "  turn right ((360) / (Ecken :: variables)) degrees\n"
            "end")
        alles = "\n\n".join(pfeil)
        assert "Vieleck (3) (80) :: pen" in alles
        assert "change pen (Farbe v) by (10)" in alles
        assert "say (verbinde [Geschafft nach] (Versuche :: variables) [Versuchen] :: operators)" in alles
        assert "(kombiniere die Elemente von (Reihe :: variables) mit ((() + ()) :: grey ring) :: list)" in alles
        assert "(Zahlen von (1) bis (10) :: list)" in alles
        assert len(figuren) == 2


class TestBloecke:
    def test_sonst_falls_aus_snap_10(self):
        """Snap! 10 hängt an „falls“ beliebig viele „sonst falls“ an."""
        falls = (
            '<block s="doIf"><block s="reportMouseDown"/>'
            '<script><block s="forward"><l>1</l></block></script>'
            '<list><block s="reportShown"/><script><block s="show"/></script>'
            '<l><bool>true</bool></l><script><block s="hide"/></script></list></block>')

        assert skripte(projekt(skript(falls))) == [
            "if <mouse down?> then\n"
            "  move (1) steps\n"
            "else\n"
            "  if <angezeigt? :: looks> then\n"
            "    show\n"
            "  else\n"
            "    hide\n"
            "  end\n"
            "end"]

    def test_falls_aus_aelteren_versionen(self):
        falls = '<block s="doIf"><l/><script><block s="show"/></script></block>'

        assert skripte(projekt(skript(falls))) == ["if <> then\n  show\nend"]

    def test_mehr_als_zwei_summanden(self):
        summe = ('<block s="forward"><block s="reportVariadicSum"><list>'
                 '<l>1</l><l>2</l><l>3</l></list></block></block>')

        assert skripte(projekt(skript(summe))) == ["move ((1) + (2) + (3) :: operators) steps"]

    def test_summe_einer_liste(self):
        summe = '<block s="forward"><block s="reportVariadicSum"><block var="zahlen"/></block></block>'

        assert skripte(projekt(skript(summe))) == ["move (Summe (zahlen :: variables) :: operators) steps"]

    def test_vergleich_ist_ein_wahrheitswert(self):
        warte = ('<block s="doWaitUntil"><autolambda><block s="reportVariadicLessThan"><list>'
                 '<block var="x"/><l>5</l></list></block></autolambda></block>')

        assert skripte(projekt(skript(warte))) == ["wait until <(x :: variables) < (5)>"]

    @pytest.mark.parametrize("wahl, text", [
        ("all", "stop [alles v]"),
        ("this script", "stop [dieses Skript v]"),
        ("other scripts in sprite", "stop [andere Skripte der Figur v] :: stack"),
    ])
    def test_stoppe(self, wahl, text):
        stoppe = f'<block s="doStopThis"><l><option>{wahl}</option></l></block>'

        assert skripte(projekt(skript(stoppe))) == [text]

    def test_wenn_ich_gedrueckt_werde(self):
        hut = '<block s="receiveInteraction"><l><option>pressed</option></l></block>'

        assert skripte(projekt(skript(hut))) == ["Wenn ich [gedrückt v] werde :: events hat"]

    def test_warp_ist_eine_klammer(self):
        warp = '<block s="doWarp"><script><block s="forward"><l>5</l></block></script></block>'

        assert skripte(projekt(skript(warp))) == ["Warp\n  move (5) steps\nend"]

    def test_befehle_im_ring(self):
        ring = ('<block s="doRun"><block s="reifyScript"><script><block s="show"/>'
                '<block s="hide"/></script><list></list></block><list></list></block>')

        assert skripte(projekt(skript(ring))) == ["führe ({show\nhide} :: grey ring) aus :: control"]

    def test_unbekannte_bloecke_sind_grau(self):
        fremd = '<block s="doShowTable"><block var="liste"/></block>'

        assert skripte(projekt(skript(fremd))) == ["doShowTable (liste :: variables) :: grey"]

    def test_eigener_block_mit_klammer(self):
        definition = ('<block-definition s="zweimal %&apos;aktion&apos;" type="command" category="control">'
                      '<inputs><input type="%cs"></input></inputs></block-definition>')
        aufruf = '<custom-block s="zweimal %cs"><script><block s="show"/></script></custom-block>'

        figuren = skripte_aus_projekt(_wurzel(projekt(skript(aufruf), gemeinsam=definition)))

        assert figuren[1]["skripte"] == ["zweimal {show} :: control"]
        assert figuren[2]["skripte"] == ["define zweimal (aktion)"]

    def test_reihenfolge_von_oben_nach_unten(self):
        unten = skript('<block s="hide"/>', x=0, y=300)
        oben = skript('<block s="show"/>', x=200, y=10)

        assert skripte(projekt(unten + oben)) == ["show", "hide"]

    def test_kommentare_stoeren_nicht(self):
        mit = skript('<block s="show"><comment w="90">Merke!</comment></block>') + \
              '<comment x="5" y="5" w="90">lose</comment>'

        assert skripte(projekt(mit)) == ["show"]


class TestMehrereSzenen:
    def test_jede_figur_nennt_ihre_szene(self):
        einzeln = projekt(skript('<block s="show"/>'))
        szene = einzeln[einzeln.index("<scene "):einzeln.index("</scenes>")]
        doppelt = einzeln.replace("</scenes>", szene.replace('name="Probe"', 'name="Zwei"') + "</scenes>")

        figuren = skripte_aus_projekt(_wurzel(doppelt))

        assert [f["titel"] for f in figuren] == [
            "Szene „Probe“ · Bühne", "Szene „Probe“ · Figur „Katze“",
            "Szene „Zwei“ · Bühne", "Szene „Zwei“ · Figur „Katze“"]


class TestTextAusDerDatei:
    def test_sonderzeichen_werden_geschuetzt(self):
        sage = '<block s="bubble"><l>(x) [y] &lt;b&gt;</l></block>'

        assert skripte(projekt(skript(sage))) == [r"say [\(x\) \[y\] \<b\>]"]

    def test_variablennamen_werden_geschuetzt(self):
        setze = '<block s="doSetVar"><l>a v</l><l>1</l></block>'

        assert skripte(projekt(skript(setze))) == [r"set [a \v v] to [1]"]

    def test_farbe(self):
        farbe = '<block s="setColor"><color>300,0,-5,1</color></block>'

        assert skripte(projekt(skript(farbe))) == ["set pen color to [#ff0000]"]

    def test_kaputte_farbe(self):
        farbe = '<block s="setColor"><color>rot</color></block>'

        assert skripte(projekt(skript(farbe))) == ["set pen color to [#000000]"]

    def test_tief_verschachtelt(self):
        innen = '<block s="show"/>'
        for _ in range(500):
            innen = f'<block s="doForever"><script>{innen}</script></block>'

        ergebnis = skripte(projekt(skript(innen)))

        assert ergebnis[0].count("forever") <= snap_skripte.MAX_TIEFE + 1


class TestDatei:
    def schreibe(self, tmp_path, inhalt):
        pfad = tmp_path / "abgabe.xml"
        pfad.write_bytes(inhalt if isinstance(inhalt, bytes) else inhalt.encode())
        return pfad

    def test_kein_xml(self, tmp_path):
        assert skripte_der_abgabe(self.schreibe(tmp_path, b"\x00\x01kaputt")) == (
            [], snap_skripte.KEIN_PROJEKT)

    def test_anderes_xml(self, tmp_path):
        assert skripte_der_abgabe(self.schreibe(tmp_path, "<html><body/></html>")) == (
            [], snap_skripte.KEIN_PROJEKT)

    def test_open_roberta(self, tmp_path):
        roberta = ('<export xmlns="http://de.fhg.iais.roberta.blockly"><program>'
                   '<block_set/></program></export>')

        assert skripte_der_abgabe(self.schreibe(tmp_path, roberta)) == (
            [], snap_skripte.OPEN_ROBERTA)

    def test_entitaeten_werden_nicht_gelesen(self, tmp_path):
        bombe = ('<?xml version="1.0"?><!DOCTYPE project [<!ENTITY a "aaaaaaaaaa">'
                 '<!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">]>'
                 + projekt(skript('<block s="bubble"><l>&b;</l></block>')))

        assert skripte_der_abgabe(self.schreibe(tmp_path, bombe)) == (
            [], snap_skripte.KEIN_PROJEKT)

    def test_zu_grosse_datei(self, tmp_path, monkeypatch):
        monkeypatch.setattr(snap_skripte, "MAX_PROJEKT", 100)

        assert skripte_der_abgabe(self.schreibe(tmp_path, projekt())) == (
            [], snap_skripte.KEIN_PROJEKT)

    def test_projekt_aus_der_cloud(self, tmp_path):
        """Die Cloud von Snap! legt das Projekt in <snapdata>."""
        verpackt = "<snapdata>" + projekt(skript('<block s="show"/>')) + "<media/></snapdata>"

        figuren, hinweis = skripte_der_abgabe(self.schreibe(tmp_path, verpackt))

        assert hinweis == ""
        assert figuren[1]["skripte"] == ["show"]

    def test_projekt_vor_snap_7_ohne_szenen(self, tmp_path):
        alt = ('<project name="alt" version="1"><stage name="Stage"><scripts></scripts>'
               '<sprites><sprite name="Figur"><scripts><script x="0" y="0">'
               '<block s="receiveGo"/><block s="doForever"><script><block s="turn">'
               '<l>15</l></block></script></block></script></scripts></sprite></sprites>'
               '</stage><blocks></blocks></project>')

        figuren, _ = skripte_der_abgabe(self.schreibe(tmp_path, alt))

        assert figuren[1]["skripte"] == ["when flag clicked\nforever\n  turn right (15) degrees\nend"]

    def test_fehlende_datei(self, tmp_path):
        assert skripte_der_abgabe(tmp_path / "gibt-es-nicht.xml") == ([], snap_skripte.KEIN_PROJEKT)


class TestAbruf:
    def abgabe(self, make_challenge, make_task, logged_in_team, inhalt):
        from models import Submission

        challenge = make_challenge()
        task = make_task(challenge, allowed_extension=".xml")
        client, _team = logged_in_team(challenge)
        client.post(f"/submit/{task.id}", data={
            "csrf_token": csrf_token(client, "/"),
            "file": (io.BytesIO(inhalt), "loesung.xml"),
        }, content_type="multipart/form-data")
        return Submission.query.one()

    def test_die_skripte_kommen_als_json(self, admin, make_challenge, make_task, logged_in_team):
        abgabe = self.abgabe(make_challenge, make_task, logged_in_team,
                             (ORDNER / "vieleck-und-raten.xml").read_bytes())

        antwort = admin.get(f"/admin/submissions/{abgabe.id}/skripte")

        assert antwort.status_code == 200
        assert antwort.mimetype == "application/json"
        assert antwort.headers["X-Content-Type-Options"] == "nosniff"
        daten = antwort.get_json()
        assert daten["hinweis"] == ""
        assert daten["figuren"][1]["name"] == "Pfeil"

    def test_open_roberta_sagt_das(self, admin, make_challenge, make_task, logged_in_team):
        abgabe = self.abgabe(make_challenge, make_task, logged_in_team,
                             b'<export xmlns="http://de.fhg.iais.roberta.blockly"/>')

        daten = admin.get(f"/admin/submissions/{abgabe.id}/skripte").get_json()

        assert daten == {"figuren": [], "hinweis": snap_skripte.OPEN_ROBERTA}

    def test_die_bewertungsseite_bietet_den_knopf_an(
            self, admin, make_challenge, make_task, logged_in_team):
        self.abgabe(make_challenge, make_task, logged_in_team,
                    (ORDNER / "fang-die-maus.xml").read_bytes())

        html = admin.get("/admin/submissions").get_data(as_text=True)

        assert "Skripte anzeigen" in html
        assert "zum Ansehen herunterladen" not in html
        assert "vendor/scratchblocks/scratchblocks.min.js" in html
        # Die Klammern, die nur Snap! kennt, meldet die Seite scratchblocks an.
        for text in ("für %1 = %2 bis %3", "für jedes %1 von %2", '"Warp"'):
            assert text in html


class TestKlammernPassenZurSeite:
    def test_die_seite_kennt_jede_klammer_aus_snap(self):
        """Steht der Text nicht genau so in review.html, fehlt die Klammer."""
        seite = (Path(__file__).resolve().parent.parent / "templates" / "admin" / "review.html").read_text()
        for name in ("doFor", "doForEach", "doWarp"):
            vorlage = snap_skripte.BLOECKE[name]
            nummer = iter(range(1, 10))
            text = re.sub(r"\{[a-z]+\}",
                          lambda t: "" if t.group() == "{c}" else f"%{next(nummer)}", vorlage)
            assert f'"{text}"' in seite, name
