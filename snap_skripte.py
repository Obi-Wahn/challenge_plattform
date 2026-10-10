"""Die Skripte einer Snap!-Abgabe, zum Anzeigen auf der Bewertungsseite.

Snap! speichert ein Projekt als XML. Jede Figur trägt ihre Skripte unter
<scripts>, jeder Block steht als <block s="forward"><l>10</l></block> darin,
die Eingänge in der Reihenfolge, in der sie im Block stehen. Kostüme und
Klänge liegen als Text im selben XML und werden hier übergangen.

Daraus entsteht derselbe scratchblocks-Text wie bei einer .sb3 (siehe
scratch_skripte.py), und die Bewertungsseite zeichnet ihn mit derselben
Bibliothek. Blöcke, die es auch in Scratch gibt, stehen dabei in der
englischen Schreibweise von scratchblocks und erscheinen übersetzt, also so,
wie Scratch sie zeigt. Blöcke, die nur Snap! kennt, etwa „wende … an auf“,
stehen gleich auf Deutsch, in der Übersetzung von Snap! selbst.

Open Roberta speichert ebenfalls als .xml. Dessen Dateien werden erkannt und
mit einem Hinweis abgewiesen.

Gelesen wird nur, nichts wird ausgeführt oder gespeichert. Die Datei kommt
von einem Team, also wird jeder Wert geprüft, bevor er benutzt wird.
"""

import re
import xml.etree.ElementTree as ET

from models import MAX_ABGABE_BYTES
from scratch_skripte import MAX_TIEFE, zeichen_schuetzen

# Größer als eine Abgabe kann die Datei nicht sein; die Grenze gilt
# trotzdem, falls eine Datei von Hand in uploads/ gelegt wurde.
MAX_PROJEKT = MAX_ABGABE_BYTES

KEIN_PROJEKT = ("Die Datei ist kein lesbares Snap!-Projekt - "
                "zum Ansehen herunterladen und in Snap! öffnen.")
OPEN_ROBERTA = ("Ein Programm aus Open Roberta lässt sich hier nicht als Blöcke "
                "anzeigen - zum Ansehen herunterladen und in Open Roberta öffnen.")

# Snap! schreibt weder DOCTYPE noch Entitäten. Eine Datei, die welche
# enthält, ist bearbeitet und wird gar nicht erst gelesen; so kann keine
# Entität beim Einlesen zu Gigabyte anwachsen.
_DTD = re.compile(rb"<!\s*(doctype|entity)", re.IGNORECASE)

# Blocknamen von Snap! -> Vorlage in der Schreibweise von scratchblocks.
# Jeder Platzhalter nimmt den nächsten Eingang des Blocks:
#   {n} Zahl      {s} Text      {b} Bedingung     {d} Auswahl wie (Mauszeiger v)
#   {f} feste Auswahl wie [Farbe v]   {v} Name einer Variablen   {u} neue Variable
#   {l} Liste     {farbe} Farbe       {r} Ring („wende … an“)     {c} Klammer
#   {*s} {*l} {*u} beliebig viele Eingänge   {x} Eingang, der nicht erscheint
BLOECKE = {
    # Bewegung
    "forward": "move {n} steps",
    "turn": "turn right {n} degrees",
    "turnLeft": "turn left {n} degrees",
    "setHeading": "point in direction {n}",
    "doFaceTowards": "point towards {d}",
    "gotoXY": "go to x: {n} y: {n}",
    "doGotoObject": "go to {d}",
    "doGlide": "glide {n} secs to x: {n} y: {n}",
    "changeXPosition": "change x by {n}",
    "setXPosition": "set x to {n}",
    "changeYPosition": "change y by {n}",
    "setYPosition": "set y to {n}",
    "bounceOffEdge": "if on edge, bounce",
    "getPosition": "(Position :: motion)",
    "xPosition": "(x position)",
    "yPosition": "(y position)",
    "direction": "(direction)",
    # Aussehen
    "doSwitchToCostume": "switch costume to {d}",
    "doWearNextCostume": "next costume",
    "getCostumeIdx": "(costume [Nummer v])",
    "doSayFor": "say {s} for {n} seconds",
    "bubble": "say {s}",
    "doThinkFor": "think {s} for {n} seconds",
    "doThink": "think {s}",
    "changeEffect": "change {f} effect by {n}",
    "setEffect": "set {f} effect to {n}",
    "getEffect": "({f} -Effekt :: looks)",
    "clearEffects": "clear graphic effects",
    "changeScale": "change size by {n}",
    "setScale": "set size to {n} %",
    "getScale": "(size)",
    "show": "show",
    "hide": "hide",
    "reportShown": "<angezeigt? :: looks>",
    "goToLayer": "go to {f} layer",
    "comeToFront": "go to [vorderste v] layer",
    "goBack": "go [nach hinten v] {n} layers",
    # Klang
    "playSound": "start sound {d}",
    "doPlaySoundUntilDone": "play sound {d} until done",
    "doStopAllSounds": "stop all sounds",
    "doRest": "rest for {n} beats",
    "doPlayNote": "play note {n} for {n} beats",
    "doSetInstrument": "set instrument to {d}",
    "doChangeTempo": "change tempo by {n}",
    "doSetTempo": "set tempo to {n}",
    "getTempo": "(tempo)",
    "changeVolume": "change volume by {n}",
    "setVolume": "set volume to {n} %",
    "getVolume": "(volume)",
    "playFreq": "spiele Frequenz {n} Hz :: sound",
    "stopFreq": "stoppe Frequenz :: sound",
    # Malstift
    "clear": "erase all",
    "down": "pen down",
    "up": "pen up",
    "getPenDown": "<Stift unten? :: pen>",
    "setColor": "set pen color to {farbe}",
    "setPenColorDimension": "set pen {d} to {n}",
    "changePenColorDimension": "change pen {d} by {n}",
    "setHue": "set pen (Farbe v) to {n}",
    "changeHue": "change pen (Farbe v) by {n}",
    "setBrightness": "set pen (Helligkeit v) to {n}",
    "changeBrightness": "change pen (Helligkeit v) by {n}",
    "changeSize": "change pen size by {n}",
    "setSize": "set pen size to {n}",
    "doStamp": "stamp",
    "floodFill": "male aus :: pen",
    "write": "schreibe {s} Größe {n} :: pen",
    "setBackgroundColor": "setze Hintergrundfarbe auf {farbe} :: pen",
    # Ereignisse und Steuerung
    "receiveGo": "when flag clicked",
    "receiveKey": "when {f} key pressed{x}",
    "receiveMessage": "when I receive {f}{x}",
    "receiveCondition": "Wenn {b} :: events hat",
    "receiveConditionEvent": "Wenn {b} :: events hat",
    "doBroadcast": "broadcast {d}{x}",
    "doBroadcastAndWait": "broadcast {d}{x} and wait",
    "doWait": "wait {n} seconds",
    "doWaitUntil": "wait until {b}",
    "doForever": "forever{c}",
    "doRepeat": "repeat {n}{c}",
    "doUntil": "repeat until {b}{c}",
    "doIfElse": "if {b} then{c}{c}",
    "reportIfElse": "(falls {b} dann {s} sonst {s} :: control)",
    "doRun": "führe {r} aus{*s} :: control",
    "fork": "starte {r}{*s} :: control",
    "evaluate": "(rufe {r} auf{*s} :: control)",
    "doReport": "berichte {s} :: control cap",
    "doPauseAll": "pausiere alles :: control",
    "receiveOnClone": "when I start as a clone",
    "createClone": "create clone of {d}",
    "newClone": "(neuer Klon von {d} :: control)",
    "removeClone": "delete this clone",
    # Fühlen
    "reportTouchingObject": "<touching {d} ?>",
    "reportTouchingColor": "<touching color {farbe} ?>",
    "reportColorIsTouchingColor": "<color {farbe} is touching {farbe} ?>",
    "doAsk": "ask {s} and wait",
    "getLastAnswer": "(answer)",
    "reportLastAnswer": "(answer)",
    "reportMouseX": "(mouse x)",
    "reportMouseY": "(mouse y)",
    "reportMousePosition": "(Mausposition :: sensing)",
    "reportMouseDown": "<mouse down?>",
    "reportKeyPressed": "<key {d} pressed?>",
    "reportDistanceTo": "(distance to {d})",
    "reportRelationTo": "({f} zu {d} :: sensing)",
    "doResetTimer": "reset timer",
    "getTimer": "(timer)",
    "reportTimer": "(timer)",
    "reportAttributeOf": "({f} of {d})",
    "reportDate": "(current {f})",
    "reportGet": "(Attribut {f} :: sensing)",
    # Operatoren
    "reportSum": "({n} + {n})",
    "reportDifference": "({n} - {n})",
    "reportProduct": "({n} * {n})",
    "reportQuotient": "({n} / {n})",
    "reportModulus": "({n} mod {n})",
    "reportPower": "({n} ^ {n} :: operators)",
    "reportRound": "(round {n})",
    "reportMonadic": "({f} of {n})",
    "reportRandom": "(pick random {n} to {n})",
    "reportLessThan": "<{n} < {n}>",
    "reportEquals": "<{n} = {n}>",
    "reportGreaterThan": "<{n} > {n}>",
    "reportAnd": "<{b} and {b}>",
    "reportOr": "<{b} or {b}>",
    "reportNot": "<not {b}>",
    "reportTrue": "<wahr :: operators>",
    "reportFalse": "<falsch :: operators>",
    "reportLetter": "(letter {n} of {s})",
    "reportStringSize": "(length of {s})",
    "reportTextSplit": "(trenne {s} nach {d} :: operators)",
    "reportUnicode": "(Unicode Wert von {s} :: operators)",
    "reportUnicodeAsLetter": "(Unicode {n} als Buchstabe :: operators)",
    "reportIsA": "<ist {s} ein(e) {f} ? :: operators>",
    # Variablen
    "doSetVar": "set {v} to {s}",
    "doChangeVar": "change {v} by {n}",
    "doShowVar": "show variable {v}",
    "doHideVar": "hide variable {v}",
    "doDeclareVariables": "Skriptvariablen{*u} :: variables",
    # Listen
    "reportNewList": "(Liste{*s} :: list)",
    "reportListItem": "(Element {n} von {l} :: list)",
    "reportCDR": "(alles außer dem ersten von {l} :: list)",
    "reportCONS": "({s} am Anfang von {l} :: list)",
    "reportListLength": "(Länge von {l} :: list)",
    "reportListAttribute": "({f} von {l} :: list)",
    "reportListContainsItem": "<{l} enthält {s} :: list>",
    "reportListIsEmpty": "<ist {l} leer? :: list>",
    "reportListIndex": "(Index von {s} in {l} :: list)",
    "doAddToList": "füge {s} zu {l} hinzu :: list",
    "doDeleteFromList": "entferne {n} aus {l} :: list",
    "doInsertInList": "füge {s} als {n} in {l} ein :: list",
    "doReplaceInList": "ersetze Element {n} in {l} durch {s} :: list",
    "reportNumbers": "(Zahlen von {n} bis {n} :: list)",
    "reportConcatenatedLists": "(verbinde{*l} :: list)",
    "reportMap": "(wende {r} an auf {l} :: list)",
    "reportKeep": "(behalte Elemente, die {r} aus {l} :: list)",
    "reportFindFirst": "(finde das erste Element, das {r} in {l} :: list)",
    "reportCombine": "(kombiniere die Elemente von {l} mit {r} :: list)",
    # Klammern, die Scratch nicht kennt. Die Bewertungsseite meldet sie
    # scratchblocks als eigene Blöcke an (SNAP_KLAMMERN in review.html), der
    # Text muss deshalb genau so bleiben.
    "doFor": "für {u} = {n} bis {n}{c}",
    "doForEach": "für jedes {u} von {l}{c}",
    "doWarp": "Warp{c}",
}

# Blöcke mit mehreren Eingängen, die Snap! als einen Block mit Pfeilen
# zeigt: (Zeichen dazwischen, Text, wenn der Block eine Liste bekommt).
# Bei zwei Eingängen entspricht das dem Block aus Scratch.
VARIADISCH = {
    "reportVariadicSum": ("+", "Summe", "n"),
    "reportVariadicProduct": ("*", "Produkt", "n"),
    "reportVariadicMin": ("min", "Minimum", "n"),
    "reportVariadicMax": ("max", "Maximum", "n"),
    "reportVariadicEquals": ("=", "alle =", "n"),
    "reportVariadicNotEquals": ("≠", "Nachbarn ≠", "n"),
    "reportVariadicLessThan": ("<", "alle <", "n"),
    "reportVariadicGreaterThan": (">", "alle >", "n"),
    "reportVariadicLessThanOrEquals": ("≤", "alle ≤", "n"),
    "reportVariadicGreaterThanOrEquals": ("≥", "alle ≥", "n"),
    "reportVariadicIsIdentical": ("identisch mit", "alle identisch", "n"),
    "reportVariadicAnd": ("and", "alle", "b"),
    "reportVariadicOr": ("or", "irgendein", "b"),
    "reportJoinWords": ("", "verbinde", "s"),
}
# Diese Zeichen kennt scratchblocks bei zwei Eingängen als Block aus Scratch.
SCRATCH_ZEICHEN = {"+", "*", "=", "<", ">", "and", "or"}
WAHRHEITSWERTE = {
    "reportVariadicEquals", "reportVariadicNotEquals", "reportVariadicLessThan",
    "reportVariadicGreaterThan", "reportVariadicLessThanOrEquals",
    "reportVariadicGreaterThanOrEquals", "reportVariadicIsIdentical",
    "reportVariadicAnd", "reportVariadicOr",
}

# Kategorien von Snap! -> Farben von scratchblocks, für eigene Blöcke.
KATEGORIEN = {
    "motion": "motion", "looks": "looks", "sound": "sound", "pen": "pen",
    "control": "control", "sensing": "sensing", "operators": "operators",
    "variables": "variables", "lists": "list", "other": "grey",
}

# Auswahlwerte so, wie das deutsche Scratch sie zeigt, und wo Scratch den
# Wert nicht kennt, so wie das deutsche Snap!.
WERTE = {
    # Ziele
    "mouse-pointer": "Mauszeiger", "random position": "Zufallsposition",
    "center": "Mitte", "edge": "Rand", "myself": "mich selbst",
    "pen trails": "Malspuren", "any message": "eine beliebige Nachricht",
    # Tasten
    "space": "Leertaste", "up arrow": "Pfeil nach oben",
    "down arrow": "Pfeil nach unten", "left arrow": "Pfeil nach links",
    "right arrow": "Pfeil nach rechts", "any key": "beliebige", "enter": "Eingabetaste",
    # Effekte
    "ghost": "Durchsichtigkeit", "color": "Farbe", "brightness": "Helligkeit",
    "fisheye": "Fischauge", "whirl": "Wirbel", "pixelate": "Pixel",
    "mosaic": "Mosaik", "saturation": "Sättigung", "negative": "Farbumkehr",
    "comic": "Moire", "duplicate": "Duplizieren", "confetti": "Farbverschiebung",
    # Malstift
    "hue": "Farbe", "transparency": "Transparenz",
    # Ebenen
    "front": "vorderste", "back": "hinterste",
    # Zeit
    "year": "Jahr", "month": "Monat", "date": "Datum", "day of week": "Wochentag",
    "hour": "Stunde", "minute": "Minute", "second": "Sekunde",
    "time in milliseconds": "Zeit in Millisekunden",
    # Eigenschaften
    "x position": "x-Position", "y position": "y-Position",
    "direction": "Richtung", "costume #": "Kostümnummer",
    "costume name": "Kostümname", "size": "Größe", "volume": "Lautstärke",
    "distance": "Entfernung", "width": "Breite", "height": "Höhe",
    # Rechnen
    "sqrt": "Wurzel", "abs": "Betrag", "floor": "abrunden",
    "ceiling": "aufrunden", "e^": "e ^", "10^": "10 ^", "2^": "2 ^",
    # Listen und Text
    "length": "Länge", "rank": "Rang", "dimensions": "Dimensionen",
    "flatten": "Auflistung", "columns": "Spalten", "reverse": "Umkehrung",
    "lines": "Zeilen", "sorted": "Sortierung", "shuffled": "Mischung",
    "last": "letztes", "random": "zufällig", "all": "alle",
    "lower case": "Kleinbuchstaben", "upper case": "Großbuchstaben",
    "letter": "Buchstabe", "word": "Wort", "line": "Zeilenvorschub",
    "number": "Zahl", "text": "Text", "Boolean": "Boole", "list": "Liste",
}

# „Wenn ich … werde“: angeklickt ist der Block aus Scratch.
INTERAKTIONEN = {
    "pressed": "gedrückt", "dropped": "abgestellt",
    "mouse-entered": "vom Mauszeiger betreten",
    "mouse-departed": "vom Mauszeiger verlassen",
    "scrolled-up": "nach oben gescrollt", "scrolled-down": "nach unten gescrollt",
    "stopped": "gestoppt",
}

# Wie bei Scratch ändert die Wahl bei „stoppe“ die Form des Blocks.
STOPP = {
    "all": ("alles", ""),
    "all scenes": ("alle Szenen", ""),
    "this script": ("dieses Skript", ""),
    "this block": ("diesen Block", ""),
    "all but this script": ("alles außer diesem Skript", " :: stack"),
    "other scripts in sprite": ("andere Skripte der Figur", " :: stack"),
}

# Ältere Snap!-Versionen hatten eigene Blöcke zum Stoppen.
STOPP_ALT = {"doStopAll": "all", "doStop": "this script", "doStopBlock": "this block"}

# Was in einem Block steht, aber kein Eingang ist.
KEINE_EINGAENGE = {"comment", "receiver", "variables"}

# Platzhalter in Vorlagen und in eigenen Blöcken.
_PLATZHALTER = re.compile(r"\{(\*?[a-z]+)\}")
_PARAMETER = re.compile(r"%'([^']*)'")


def _eingaenge(element):
    return [kind for kind in element if kind.tag not in KEINE_EINGAENGE]


def _wahr(element):
    """Ob ein Eingang das feste „wahr“ ist (das „sonst“ in Snap! 10)."""
    wert = element.find("bool") if element.tag == "l" else None
    return wert is not None and (wert.text or "").strip() == "true"


class _Wandler:
    """Wandelt die Skripte eines Projekts in scratchblocks-Text."""

    def __init__(self, eigene):
        # Text eines eigenen Blocks, wie er im Aufruf steht -> (Art, Farbe)
        self.eigene = eigene

    # Werte in Eingängen ------------------------------------------------

    @staticmethod
    def literal(element):
        """(Text, ist Auswahl) eines <l>, oder (None, False), wenn es leer ist."""
        auswahl = element.find("option")
        if auswahl is not None:
            return auswahl.text or "", True
        wahrheit = element.find("bool")
        if wahrheit is not None:
            return ("wahr" if (wahrheit.text or "").strip() == "true" else "falsch"), True
        text = element.text or ""
        return (text, False) if text.strip() else (None, False)

    def wert(self, element, art, tiefe):
        """Ein Eingang in Klammern, je nach Art des Platzhalters."""
        leer = {"b": "<>", "s": "[]", "f": "[ v]", "v": "[ v]", "farbe": "[#000000]"}.get(art, "()")
        if element is None:
            return leer
        if tiefe > MAX_TIEFE:
            return "(…)"
        if element.tag in ("block", "custom-block"):
            return self.reporter(element, tiefe + 1)
        if element.tag == "autolambda":
            innen = _eingaenge(element)
            return self.wert(innen[0], art, tiefe + 1) if innen else leer
        if element.tag == "color":
            return self.farbe(element.text)
        if element.tag == "list":
            return " ".join(self.wert(kind, art, tiefe + 1) for kind in _eingaenge(element)) or leer
        if element.tag == "script":
            return self.eingebettet(element, tiefe + 1)
        if element.tag != "l":
            return leer

        text, ist_auswahl = self.literal(element)
        if text is None:
            return leer
        if ist_auswahl and element.find("bool") is not None:
            return f"<{text} :: operators>"
        if art in ("d", "f") or ist_auswahl:
            text = WERTE.get(text, text)
        text = zeichen_schuetzen(text)
        if art == "b":
            return leer
        if art == "u":
            return f"({text} :: variables)"
        if art in ("f", "v"):
            return f"[{text} v]"
        if art == "d" or ist_auswahl:
            return f"({text} v)"
        if art == "s":
            return f"[{text}]"
        return f"({text})"

    @staticmethod
    def farbe(text):
        """„255,0,0,1“ aus Snap! als [#ff0000] für scratchblocks."""
        teile = (text or "").split(",")
        try:
            rot, gruen, blau = (max(0, min(255, round(float(teil)))) for teil in teile[:3])
        except ValueError:
            return "[#000000]"
        return f"[#{rot:02x}{gruen:02x}{blau:02x}]"

    def eingebettet(self, skript, tiefe):
        """Ein ganzes Skript als Eingang, in geschweiften Klammern."""
        zeilen = self.stapel(skript, "", tiefe + 1)
        return "{" + "\n".join(zeilen) + "}"

    def ring(self, element, tiefe):
        """Ein Ring wie in „wende ( ) an auf“, grau wie in Snap!."""
        if element is None or element.tag != "block" or element.get("s") not in (
                "reifyScript", "reifyReporter", "reifyPredicate"):
            # Statt eines Rings steht eine Variable oder ein Block darin.
            return self.wert(element, "s", tiefe)
        teile = _eingaenge(element)
        innen = teile[0] if teile else None
        if element.get("s") == "reifyScript":
            inhalt = self.eingebettet(innen, tiefe) if innen is not None and innen.tag == "script" else "{}"
        else:
            inhalt = self.wert(innen, "b" if element.get("s") == "reifyPredicate" else "s", tiefe + 1)
            if innen is not None and innen.tag == "script":
                # Bis Snap! 8 stand der Block in einem <script>.
                bloecke = _eingaenge(innen)
                inhalt = self.reporter(bloecke[0], tiefe + 1) if bloecke else "()"
        namen = self.vielfach(teile[1] if len(teile) > 1 else None, "u", tiefe)
        zusatz = f" Eingaben:{namen}" if namen else ""
        return f"({inhalt}{zusatz} :: grey ring)"

    def vielfach(self, element, art, tiefe):
        """Beliebig viele Eingänge, je mit Leerzeichen davor."""
        if element is None:
            return ""
        if element.tag != "list":
            return " " + self.wert(element, art, tiefe)
        return "".join(" " + self.wert(kind, art, tiefe + 1) for kind in _eingaenge(element))

    # Blöcke ------------------------------------------------------------

    def reporter(self, block, tiefe):
        """Ein Block, der in einem Eingang steckt."""
        if block.tag == "block" and "var" in block.attrib:
            return f"({zeichen_schuetzen(block.get('var'))} :: variables)"
        text, _ = self.zeile(block, tiefe)
        if text.startswith(("(", "<")) and text.endswith((")", ">")):
            return text
        art = self.eigene.get(block.get("s", ""), ("reporter", ""))[0] if block.tag == "custom-block" else "reporter"
        return f"<{text}>" if art == "predicate" else f"({text})"

    def zeile(self, block, tiefe):
        """(Text eines Blocks, Liste der Skripte in seinen Klammern)."""
        if tiefe > MAX_TIEFE:
            return "…", []
        if block.tag == "custom-block":
            return self.eigener_aufruf(block, tiefe), []
        if block.tag != "block":
            return "()", []
        if "var" in block.attrib:
            return f"({zeichen_schuetzen(block.get('var'))} :: variables)", []

        name = block.get("s") or ""
        eingaenge = _eingaenge(block)
        if name in VARIADISCH:
            return self.variadisch(name, eingaenge, tiefe), []
        if name in ("doStopThis", *STOPP_ALT):
            return self.stopp(name, eingaenge), []
        if name == "receiveInteraction":
            return self.interaktion(eingaenge), []
        if name in ("reifyScript", "reifyReporter", "reifyPredicate"):
            return self.ring(block, tiefe), []
        if name == "reportTextAttribute":
            text, _ = self.literal(eingaenge[0]) if eingaenge and eingaenge[0].tag == "l" else (None, False)
            if text == "length":
                return f"(length of {self.wert(eingaenge[1] if len(eingaenge) > 1 else None, 's', tiefe)})", []
            return self.ausfuellen("({f} von Text {s} :: operators)", eingaenge, tiefe)

        vorlage = BLOECKE.get(name)
        if vorlage is None:
            # Ein Block, den diese Liste nicht kennt: grau, mit seinem
            # Namen aus Snap! und den Werten, die darin stehen.
            werte = [self.eingebettet(kind, tiefe) if kind.tag == "script" else self.wert(kind, "s", tiefe)
                     for kind in eingaenge]
            return " ".join([zeichen_schuetzen(name) or "?", *werte]) + " :: grey", []
        return self.ausfuellen(vorlage, eingaenge, tiefe)

    def ausfuellen(self, vorlage, eingaenge, tiefe):
        """Setzt die Eingänge der Reihe nach in die Vorlage ein."""
        rest = list(eingaenge)
        klammern = []

        def einsetzen(treffer):
            art = treffer.group(1)
            if art.startswith("*"):
                # Nimmt alles, was übrig ist.
                teile, rest[:] = rest[:], []
                return "".join(self.vielfach(teil, art[1:], tiefe) for teil in teile)
            element = rest.pop(0) if rest else None
            if art == "x":
                return ""
            if art == "c":
                klammern.append(element)
                return ""
            if art == "r":
                return self.ring(element, tiefe)
            return self.wert(element, art, tiefe)

        return _PLATZHALTER.sub(einsetzen, vorlage), klammern

    def variadisch(self, name, eingaenge, tiefe):
        zeichen, sammel, art = VARIADISCH[name]
        wahrheit = name in WAHRHEITSWERTE
        auf, zu = ("<", ">") if wahrheit else ("(", ")")
        liste = eingaenge[0] if eingaenge else None
        if liste is not None and liste.tag != "list":
            # Zugeklappt: Der Block rechnet mit einer ganzen Liste.
            return f"{auf}{sammel} {self.wert(liste, 'l', tiefe)} :: operators{zu}"
        teile = [self.wert(kind, art, tiefe + 1) for kind in (_eingaenge(liste) if liste is not None else [])]
        while len(teile) < 2:
            teile.append("<>" if art == "b" else "()")
        if name == "reportJoinWords":
            if len(teile) == 2:
                return f"(join {teile[0]} {teile[1]})"
            return f"(verbinde {' '.join(teile)} :: operators)"
        if len(teile) == 2 and zeichen in SCRATCH_ZEICHEN:
            return f"{auf}{teile[0]} {zeichen} {teile[1]}{zu}"
        return f"{auf}{f' {zeichen} '.join(teile)} :: operators{zu}"

    def stopp(self, name, eingaenge):
        if name in STOPP_ALT:
            wahl = STOPP_ALT[name]
        else:
            wahl, _ = self.literal(eingaenge[0]) if eingaenge and eingaenge[0].tag == "l" else ("", False)
        text, form = STOPP.get(wahl or "", (WERTE.get(wahl or "", wahl or ""), ""))
        return f"stop [{zeichen_schuetzen(text)} v]{form}"

    def interaktion(self, eingaenge):
        wahl, _ = self.literal(eingaenge[0]) if eingaenge and eingaenge[0].tag == "l" else ("", False)
        if wahl in (None, "", "clicked"):
            return "when this sprite clicked"
        text = INTERAKTIONEN.get(wahl, wahl)
        return f"Wenn ich [{zeichen_schuetzen(text)} v] werde :: events hat"

    def eigener_aufruf(self, block, tiefe):
        """Der Aufruf eines eigenen Blocks, in der Farbe seiner Kategorie."""
        spec = block.get("s") or ""
        _art, kategorie = self.eigene.get(spec, ("command", "grey"))
        eingaenge = _eingaenge(block)
        teile, nummer = [], 0
        for stueck in spec.split():
            if stueck.startswith("%") and len(stueck) > 1:
                element = eingaenge[nummer] if nummer < len(eingaenge) else None
                nummer += 1
                if element is not None and element.tag == "script":
                    teile.append(self.eingebettet(element, tiefe))
                elif stueck in ("%b", "%boolUE"):
                    teile.append(self.wert(element, "b", tiefe))
                elif stueck in ("%n",):
                    teile.append(self.wert(element, "n", tiefe))
                elif stueck in ("%repRing", "%cmdRing", "%predRing"):
                    teile.append(self.ring(element, tiefe))
                elif stueck.startswith("%mult"):
                    teile.append(self.vielfach(element, "s", tiefe).strip() or "()")
                else:
                    teile.append(self.wert(element, "s", tiefe))
            else:
                teile.append(zeichen_schuetzen(stueck))
        return " ".join(teile) + f" :: {kategorie or 'grey'}"

    def wenn(self, bedingung, skript, weitere, einzug, tiefe):
        """„falls“ samt „sonst falls“ aus Snap! 10, geschachtelt wie in Scratch."""
        zeilen = [f"{einzug}if {self.wert(bedingung, 'b', tiefe)} then"]
        zeilen += self.stapel(skript, einzug + "  ", tiefe + 1)
        if len(weitere) >= 2:
            naechste, rumpf, rest = weitere[0], weitere[1], weitere[2:]
            zeilen.append(einzug + "else")
            if _wahr(naechste) and len(rest) < 2:
                zeilen += self.stapel(rumpf, einzug + "  ", tiefe + 1)
            else:
                zeilen += self.wenn(naechste, rumpf, rest, einzug + "  ", tiefe + 1)
        zeilen.append(einzug + "end")
        return zeilen

    def stapel(self, skript, einzug="", tiefe=0):
        """Die Zeilen eines <script>, eingerückt je Klammer."""
        zeilen = []
        if skript is None or skript.tag != "script" or tiefe > MAX_TIEFE:
            return zeilen
        for block in skript:
            if block.tag not in ("block", "custom-block"):
                continue
            if block.tag == "block" and block.get("s") == "doIf":
                teile = _eingaenge(block)
                weitere = _eingaenge(teile[2]) if len(teile) > 2 and teile[2].tag == "list" else []
                zeilen += self.wenn(teile[0] if teile else None, teile[1] if len(teile) > 1 else None,
                                    weitere, einzug, tiefe)
                continue
            text, klammern = self.zeile(block, tiefe)
            zeilen.append(einzug + text)
            if klammern:
                for nummer, innen in enumerate(klammern):
                    if nummer:
                        zeilen.append(einzug + "else")
                    zeilen += self.stapel(innen, einzug + "  ", tiefe + 1)
                zeilen.append(einzug + "end")
        return zeilen

    def skripte(self, behaelter):
        """Die Skripte unter <scripts>, von oben nach unten wie in Snap!."""
        if behaelter is None:
            return []

        def lage(skript):
            try:
                return float(skript.get("y", 0)), float(skript.get("x", 0))
            except ValueError:
                return 0.0, 0.0

        texte = []
        for skript in sorted((kind for kind in behaelter if kind.tag == "script"), key=lage):
            zeilen = self.stapel(skript)
            if zeilen:
                texte.append("\n".join(zeilen))
        return texte

    def definitionen(self, behaelter):
        """Eigene Blöcke unter <blocks>, je als „Definiere“ mit Inhalt."""
        texte = []
        for definition in behaelter if behaelter is not None else []:
            if definition.tag != "block-definition":
                continue
            # re.split mit Gruppe: Text und Eingänge im Wechsel.
            teile = _PARAMETER.split(definition.get("s") or "")
            kopf = " ".join(
                (f"({zeichen_schuetzen(teil)})" if nummer % 2 else zeichen_schuetzen(teil))
                for nummer, teil in enumerate(teile) if nummer % 2 or teil.strip())
            zeilen = [f"define {kopf}"]
            zeilen += self.stapel(definition.find("script"), "", 1)
            texte.append("\n".join(zeilen))
        return texte


def _eigene_bloecke(wurzel):
    """Alle eigenen Blöcke: Aufruftext -> (Art, Farbe).

    In der Definition steht „springe %'Höhe'“, im Aufruf „springe %n“. Die
    Art jedes Eingangs steht unter <inputs> in derselben Reihenfolge.
    """
    eigene = {}
    for definition in wurzel.iter("block-definition"):
        arten = [eingang.get("type") or "%s" for eingang in definition.iterfind("inputs/input")]
        zaehler = iter(arten)
        aufruf = _PARAMETER.sub(lambda _treffer: next(zaehler, "%s"), definition.get("s") or "")
        eigene[aufruf] = (definition.get("type") or "command",
                          KATEGORIEN.get(definition.get("category") or "other", "grey"))
    return eigene


def skripte_aus_projekt(wurzel):
    """Die Figuren eines Projekts mit ihren Skripten als scratchblocks-Text.

    Ergebnis wie bei skripte_aus_projekt() in scratch_skripte.py: eine Liste
    von {"name", "buehne", "skripte"}, je Szene die Bühne zuerst. Eigene
    Blöcke, die allen Figuren gehören, stehen am Ende unter einem eigenen
    "titel"; hat das Projekt mehrere Szenen, trägt jeder Eintrag einen
    "titel" mit der Szene.
    """
    wandler = _Wandler(_eigene_bloecke(wurzel))
    szenen = list(wurzel.iter("scene")) or [wurzel]
    mehrere = len(szenen) > 1
    figuren = []
    for szene in szenen:
        vorsatz = f"Szene „{szene.get('name', '')}“ · " if mehrere else ""
        buehne = szene.find("stage")
        if buehne is None:
            continue
        objekte = [(buehne, True)] + [(figur, False) for figur in buehne.iterfind("sprites/sprite")]
        for objekt, ist_buehne in objekte:
            eintrag = {
                "name": str(objekt.get("name", "")),
                "buehne": ist_buehne,
                "skripte": wandler.definitionen(objekt.find("blocks")) + wandler.skripte(objekt.find("scripts")),
            }
            if mehrere:
                eintrag["titel"] = vorsatz + ("Bühne" if ist_buehne else f"Figur „{eintrag['name']}“")
            figuren.append(eintrag)

        gemeinsam = wandler.definitionen(szene.find("blocks"))
        if gemeinsam:
            figuren.append({"name": "", "buehne": False, "skripte": gemeinsam,
                            "titel": vorsatz + "Eigene Blöcke für alle Figuren"})
    return figuren


def lies_projekt(pfad):
    """Das XML einer Abgabe als (Wurzel, Hinweis); die Wurzel ist None, wenn das nicht geht."""
    try:
        with open(pfad, "rb") as datei:
            roh = datei.read(MAX_PROJEKT + 1)
    except OSError:
        return None, KEIN_PROJEKT
    if len(roh) > MAX_PROJEKT or _DTD.search(roh):
        return None, KEIN_PROJEKT
    try:
        wurzel = ET.fromstring(roh)
    except (ET.ParseError, ValueError, RecursionError):
        return None, KEIN_PROJEKT

    # Open Roberta schreibt <export xmlns="http://de.fhg.iais.roberta.blockly">.
    name = wurzel.tag.rsplit("}", 1)[-1]
    if name == "export" or "roberta" in wurzel.tag.lower():
        return None, OPEN_ROBERTA
    if name == "snapdata":
        # So sieht ein Projekt aus der Cloud von Snap! aus.
        wurzel = wurzel.find("project")
    if wurzel is None or wurzel.tag != "project":
        return None, KEIN_PROJEKT
    return wurzel, ""


def skripte_der_abgabe(pfad):
    """Die Skripte einer Snap!-Abgabe zum Anzeigen, als (Figuren, Hinweis)."""
    wurzel, hinweis = lies_projekt(pfad)
    if wurzel is None:
        return [], hinweis
    return skripte_aus_projekt(wurzel), ""
