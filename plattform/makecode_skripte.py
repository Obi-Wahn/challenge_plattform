"""Die Blöcke einer MakeCode-Abgabe (Calliope mini), zum Anzeigen.

MakeCode legt in jede heruntergeladene .hex den ganzen Quelltext, damit
man sie später wieder in den Editor ziehen kann: Hinter einer Kennung
stehen ein kleiner Kopf und die Projektdateien, mit LZMA gepackt. Eine
.mkcd ist dasselbe ohne Maschinencode. Gelesen wird beides hier so, wie
MakeCode es selbst beim Öffnen tut (extractSource in pxtlib/cpp.ts), nur
mit der Standardbibliothek von Python.

Die Blöcke stehen darin als Blockly-XML (main.blocks). Daraus entsteht
scratchblocks-Text wie bei Scratch und Snap!, gleich auf Deutsch und in den
Farben des Calliope-Editors. Die Texte der Grundblöcke kommen aus
makecode_bloecke.json (erzeugt von werkzeuge/makecode_bloecke.py), die von
Erweiterungen wie dem MotionKit aus der Datei selbst: MakeCode legt deren
Quelltext mit hinein.

Die Klammern von MakeCode - „beim Start“, „dauerhaft“, „wenn Knopf …“,
„wiederhole …“ - kennt scratchblocks nicht. Die Antwort nennt sie deshalb
unter "klammern", und _skripte.html meldet sie vor dem Zeichnen an.

Gelesen wird nur, nichts wird ausgeführt oder gespeichert. Der Name des
Projekts und die README, die ein Team selbst eintippt, werden nicht
angezeigt.
"""

import functools
import json
import lzma
import os
import re
import xml.etree.ElementTree as ET

from plattform.models import MAX_ABGABE_BYTES
from plattform.scratch_skripte import MAX_TIEFE
from plattform.scratch_skripte import zeichen_schuetzen as _scratch_schuetzen

# Größer als eine Abgabe kann die Datei nicht sein; die Grenze gilt
# trotzdem, falls eine Datei von Hand in uploads/ gelegt wurde.
MAX_PROJEKT = MAX_ABGABE_BYTES
# Entpackt darf das Projekt höchstens so groß werden. Ein echtes ist selten
# größer als ein paar hundert KB; die Grenze hält eine präparierte Datei
# davon ab, beim Entpacken den Speicher zu füllen.
MAX_ENTPACKT = 8 * 1024 * 1024

KEIN_PROJEKT = ("Die Datei ist kein lesbares MakeCode-Projekt - "
                "zum Ansehen herunterladen und in MakeCode öffnen.")
OHNE_QUELLTEXT = ("In der .hex-Datei steckt kein Projekt aus MakeCode, nur das fertige "
                  "Programm - zum Ansehen herunterladen und auf den Calliope mini kopieren.")
OHNE_BLOECKE = ("Das Projekt wurde in JavaScript oder Python geschrieben, nicht mit Blöcken - "
                "zum Ansehen herunterladen und in MakeCode öffnen.")

TABELLE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "makecode_bloecke.json")

# Wo ein LED-Bildchen (5×5) hingehört, steht dieser Platzhalter im Text;
# die Punkte stehen der Reihe nach unter "leds" in der Antwort, und
# _skripte.html zeichnet sie an seine Stelle.
LED_PLATZHALTER = "▦▦"

_BLOCKLY = "{https://developers.google.com/blockly/xml}"
_DTD = re.compile(r"<!\s*(doctype|entity)", re.IGNORECASE)

# --- Datei lesen ------------------------------------------------------------

_KENNUNG = "41140E2FB82FA2BB"
_KOPFZEILE = re.compile(r":10[0-9A-F]{4}0[0E]" + _KENNUNG + r"([0-9A-F]{4})([0-9A-F]{4})([0-9A-F]{4})", re.I)
_DATENZEILE = re.compile(r":10[0-9A-F]{4}0[0E]([0-9A-F]{32})[0-9A-F]{2}", re.I)


def _klein_endig(hex4):
    """„0201“ aus einer Hex-Zeile als Zahl 0x0102, wie swapBytes in MakeCode."""
    return int(hex4[2:4] + hex4[0:2], 16)


def _aus_hex(text):
    """(Kopf, gepackter Text) aus einer .hex, oder None ohne eingebettetes Projekt.

    Die Daten stehen als gewöhnliche Zeilen (Typ 00) oder als Zeilen vom Typ
    0E am Ende, je nachdem, ob MakeCode sie in den Speicher des Calliope
    gelegt hat. Andere Zeilen dazwischen zählen nicht.
    """
    puffer, rest, kopf_laenge = None, 0, 0
    for zeile in text.splitlines():
        zeile = zeile.strip()
        if puffer is None:
            treffer = _KOPFZEILE.match(zeile)
            if treffer:
                kopf_laenge = _klein_endig(treffer[1])
                rest = kopf_laenge + _klein_endig(treffer[2]) + (_klein_endig(treffer[3]) << 16)
                if rest > MAX_PROJEKT:
                    return None
                puffer = bytearray()
            continue
        if rest <= 0:
            break
        treffer = _DATENZEILE.match(zeile)
        if treffer:
            stueck = bytes.fromhex(treffer[1])[:rest]
            puffer += stueck
            rest -= len(stueck)
    if puffer is None or rest > 0:
        return None
    return bytes(puffer[:kopf_laenge]), bytes(puffer[kopf_laenge:])


def _entpacken(daten):
    """Mit LZMA gepackten Text entpacken, oder None, wenn das nicht geht."""
    entpacker = lzma.LZMADecompressor(format=lzma.FORMAT_ALONE)
    try:
        roh = entpacker.decompress(daten, max_length=MAX_ENTPACKT)
    except lzma.LZMAError:
        return None
    if not entpacker.eof:
        # Zu groß oder abgeschnitten.
        return None
    return roh.decode("utf-8", errors="replace")


def _json(text):
    try:
        return json.loads(text)
    except (TypeError, ValueError, RecursionError):
        return None


def _nur_texte(dateien):
    """Die Projektdateien als {Name: Text}; alles andere fällt weg."""
    if not isinstance(dateien, dict):
        return None
    return {name: inhalt for name, inhalt in dateien.items()
            if isinstance(name, str) and isinstance(inhalt, str)}


def lies_projekt(pfad):
    """Die Dateien eines MakeCode-Projekts als ({Name: Text}, Hinweis).

    Ohne lesbares Projekt ist das Erste None und der Hinweis sagt, warum.
    """
    try:
        with open(pfad, "rb") as datei:
            roh = datei.read(MAX_PROJEKT + 1)
    except OSError:
        return None, KEIN_PROJEKT
    if len(roh) > MAX_PROJEKT:
        return None, KEIN_PROJEKT

    if roh[:1] == b":":
        eingebettet = _aus_hex(roh.decode("ascii", errors="replace"))
        if eingebettet is None:
            return None, OHNE_QUELLTEXT
        kopf_roh, gepackt = eingebettet
        kopf = _json(kopf_roh.decode("utf-8", errors="replace"))
        if not isinstance(kopf, dict):
            return None, KEIN_PROJEKT
        if kopf.get("compression") == "LZMA":
            text = _entpacken(gepackt)
            laenge = kopf.get("headerSize") or kopf.get("metaSize") or 0
            if text is None or not isinstance(laenge, int) or laenge < 0:
                return None, KEIN_PROJEKT
            dateien = _json(text[laenge:])
        elif not kopf.get("compression"):
            dateien = _json(gepackt.decode("utf-8", errors="replace"))
        else:
            return None, KEIN_PROJEKT
    else:
        # .mkcd: {"meta": …, "source": "<die Dateien als JSON>"}, gepackt.
        text = _entpacken(roh)
        projekt = _json(text) if text is not None else None
        quelle = projekt.get("source") if isinstance(projekt, dict) else None
        dateien = _json(quelle) if isinstance(quelle, str) else quelle

    dateien = _nur_texte(dateien)
    if dateien is None:
        return None, KEIN_PROJEKT
    return dateien, ""


# --- Blöcke aus Quelltext (Kernbibliothek und Erweiterungen) ---------------

_NAMESPACE = re.compile(r"^\s*(?:export\s+)?(?:declare\s+)?namespace\s+([\w.]+)")
_ENUM = re.compile(r"^\s*(?:export\s+)?(?:declare\s+)?(?:const\s+)?enum\s+(\w+)")
_KLASSE = re.compile(r"^\s*(?:export\s+)?(?:declare\s+)?(?:interface|class)\s+(\w+)")
_FUNKTION = re.compile(r"^\s*(?:export\s+)?(?:declare\s+)?(?:static\s+)?(?:function\s+)?(\w+)\s*(?:<[^>(]*>)?\s*\(")
_EIGENSCHAFT = re.compile(r"^\s*(?:readonly\s+)?(\w+)\??\s*:\s*([\w.]+)\s*;")
_MITGLIED = re.compile(r"^\s*(\w+)\s*(?:=|,|$)")
_ATTRIBUT = re.compile(r'([\w.]+)\s*=\s*("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|\S+)')
PLATZHALTER = re.compile(r"[%$](\w+)(?:=[\w.]+)?(?:\([^)]*\))?")


def _attribute(zeilen):
    """Die Angaben aus //%-Zeilen als {Name: Wert}."""
    werte = {}
    for treffer in _ATTRIBUT.finditer(" ".join(zeilen)):
        wert = treffer[2]
        if wert[:1] in "\"'":
            wert = wert[1:-1].replace('\\"', '"').replace("\\'", "'")
        werte[treffer[1]] = wert
    return werte


def _namen(text):
    return [treffer[1] for treffer in PLATZHALTER.finditer(text)]


def _uebernehmen(deutsch, original):
    """Die Übersetzung mit den Namen der Eingänge aus dem Original.

    Die Werte in der Datei tragen die Namen des Originals. Manche
    Übersetzung schreibt sie anders („%intervall“ statt „%interval“);
    dann gilt die Reihenfolge, so wie im Editor. Passt nicht einmal die
    Zahl, bleibt es beim Original.
    """
    if not deutsch:
        return original
    namen, eigene = _namen(original), _namen(deutsch)
    if sorted(namen) == sorted(eigene):
        return deutsch
    if len(namen) != len(eigene):
        return original
    folge = iter(namen)
    return PLATZHALTER.sub(lambda treffer: treffer[0].replace(treffer[1], next(folge), 1), deutsch)


def _form(signatur, angaben):
    """Wie der Block aussieht, aus der Signatur der Funktion."""
    if angaben.get("handlerStatement") in ("1", "true"):
        return "klammer"
    if re.search(r"(=>\s*void|:\s*Action)\s*\)\s*[:;{]?", signatur):
        return "hut"
    rueckgabe = re.search(r"\)\s*:\s*([\w.<>\[\]| ]+)", signatur)
    typ = rueckgabe[1].strip() if rueckgabe else "void"
    if typ == "void":
        return "stapel"
    if typ == "boolean":
        return "bedingung"
    return "wert"


def bloecke_aus_quelltext(quellen, uebersetzung=None, farben=None):
    """Blöcke und Auswahlwerte aus MakeCode-Quelltext (.ts, .d.ts).

    quellen: Texte der Dateien. uebersetzung: {"basic.showIcon|block": "…"}
    aus _locales/de. farben: Farbe je Namensraum, falls die Quelle keine
    nennt. Ergebnis: ({blockId: {"text", "farbe", "form"}}, {"Enum.Wert": Text}).
    Eine Übersetzung gilt nur, wenn sie dieselben Eingänge nennt wie das
    Original - sonst fänden sich die Werte aus der Datei nicht wieder.
    """
    uebersetzung = uebersetzung or {}
    farben = dict(farben or {})
    bloecke, werte, vorlaeufig = {}, {}, []

    for quelle in quellen:
        stapel = []          # (Art, Name, Tiefe der Klammern)
        tiefe = 0
        angaben = []
        zeilen = quelle.splitlines()
        nummer = 0
        while nummer < len(zeilen):
            zeile = zeilen[nummer]
            nummer += 1
            rein = zeile.strip()
            if rein.startswith("//%"):
                angaben.append(rein[3:])
                continue
            if not rein or rein.startswith(("/*", "*", "//")):
                continue

            ns = next((name for art, name, _ in reversed(stapel) if art in ("ns", "klasse")), "")
            enum = stapel[-1][1] if stapel and stapel[-1][0] == "enum" else None
            treffer_ns, treffer_enum = _NAMESPACE.match(zeile), _ENUM.match(zeile)
            treffer_klasse = _KLASSE.match(zeile)
            attribute = _attribute(angaben)

            if treffer_ns:
                name = treffer_ns[1]
                if attribute.get("color"):
                    farben[name] = attribute["color"].lower()
                stapel.append(("ns", name, tiefe))
            elif treffer_enum:
                name = f"{ns}.{treffer_enum[1]}" if ns else treffer_enum[1]
                stapel.append(("enum", name, tiefe))
            elif treffer_klasse:
                stapel.append(("klasse", treffer_klasse[1], tiefe))
            elif enum and _MITGLIED.match(zeile) and "block" in attribute:
                schluessel = f"{enum}.{_MITGLIED.match(zeile)[1]}"
                werte[schluessel] = uebersetzung.get(schluessel + "|block", attribute["block"])
            elif "blockId" in attribute and "block" in attribute and _EIGENSCHAFT.match(zeile):
                name, typ = _EIGENSCHAFT.match(zeile).groups()
                text = _uebernehmen(uebersetzung.get(f"{ns}.{name}|block" if ns else f"{name}|block"), attribute["block"])
                bereich = attribute.get("blockNamespace") or ns.split(".")[0]
                vorlaeufig.append((attribute["blockId"], {"text": text, "form": "bedingung" if typ == "boolean" else "wert"},
                                   attribute.get("color"), bereich))
            elif "blockId" in attribute and "block" in attribute and _FUNKTION.match(zeile):
                funktion = _FUNKTION.match(zeile)[1]
                signatur = zeile
                while ")" not in signatur.split("(", 1)[-1] and nummer < len(zeilen):
                    signatur += " " + zeilen[nummer].strip()
                    nummer += 1
                # Die Rückgabe kann noch auf der nächsten Zeile stehen.
                if not re.search(r"\)\s*[:;{]", signatur) and nummer < len(zeilen):
                    signatur += " " + zeilen[nummer].strip()
                text = _uebernehmen(uebersetzung.get(f"{ns}.{funktion}|block" if ns else f"{funktion}|block"), attribute["block"])
                eintrag = {"text": text, "form": _form(signatur, attribute)}
                if attribute.get("imageLiteral"):
                    eintrag["bild"] = True
                bereich = attribute.get("blockNamespace") or ns.split(".")[0]
                vorlaeufig.append((attribute["blockId"], eintrag, attribute.get("color"), bereich))

            tiefe += zeile.count("{") - zeile.count("}")
            while stapel and tiefe <= stapel[-1][2] and "}" in zeile:
                stapel.pop()
            angaben = []

    for block_id, eintrag, eigene, bereich in vorlaeufig:
        farbe = (eigene or farben.get(bereich) or farben.get(bereich.lower()) or "#888888").lower()
        farbe = farbe if farbe.startswith("#") else "#" + farbe
        bloecke[block_id] = {**eintrag, "farbe": farbe}
    return bloecke, werte


@functools.lru_cache(maxsize=1)
def tabelle():
    """Die Tabelle der Grundblöcke aus makecode_bloecke.json."""
    with open(TABELLE, encoding="utf-8") as datei:
        return json.load(datei)


def _erweiterungen(dateien):
    """Blöcke der Erweiterungen, die MakeCode in die Datei gelegt hat."""
    paket = _json(dateien.get("_packaged-extensions.json", "")) or {}
    quellen, uebersetzung = [], {}
    for erweiterung in paket.values() if isinstance(paket, dict) else []:
        if not isinstance(erweiterung, dict):
            continue
        for name, inhalt in erweiterung.items():
            if not isinstance(inhalt, str):
                continue
            # Wie der Editor auf Deutsch: nur _locales/de, nicht de-de.
            if re.fullmatch(r"_locales/de/[^/]*-strings\.json", name):
                texte = _json(inhalt)
                if isinstance(texte, dict):
                    uebersetzung.update({k: v for k, v in texte.items() if isinstance(v, str)})
            elif name.endswith(".ts") and len(inhalt) <= MAX_PROJEKT:
                quellen.append(inhalt)
    return bloecke_aus_quelltext(quellen, uebersetzung, tabelle()["kategorien"])


# --- Blockly-XML in scratchblocks-Text --------------------------------------

# Farben der Kategorien, die nicht aus einem Namensraum kommen.
def _farbe(kategorie):
    return tabelle()["kategorien"].get(kategorie, "#888888")


# Blöcke, die MakeCode selbst mitbringt und nicht aus der Bibliothek kommen.
# Die Texte folgen dem deutschen Calliope-Editor. Platzhalter wie oben;
# „hut“ und „klammer“ haben eine Klammer, „hut“ ist dabei oben glatt und
# unten geschlossen wie die Ereignisblöcke im Editor.
EINGEBAUT = {
    "pxt-on-start": ("beim Start", "basic", "hut"),
    "controls_repeat_ext": ("wiederhole %TIMES mal mache", "loops", "klammer"),
    "device_while": ("während %COND mache", "loops", "klammer"),
    "controls_while": ("während %COND mache", "loops", "klammer"),
    "pxt_controls_for": ("für %VAR von 0 bis %TO mache", "loops", "klammer"),
    "controls_simple_for": ("für %VAR von 0 bis %TO mache", "loops", "klammer"),
    "pxt_controls_for_of": ("für Element %VAR von %LIST mache", "loops", "klammer"),
    "controls_for_of": ("für Element %VAR von %LIST mache", "loops", "klammer"),
    "pxt_pause_until": ("pausiere bis %PREDICATE", "loops", "stapel"),
    "break_keyword": ("abbrechen", "loops", "stapel"),
    "continue_keyword": ("fortsetzen", "loops", "stapel"),
    "logic_negate": ("nicht %BOOL", "logic", "bedingung"),
    "logic_compare": ("%A %OP %B", "logic", "bedingung"),
    "logic_operation": ("%A %OP %B", "logic", "bedingung"),
    "math_arithmetic": ("%A %OP %B", "math", "wert"),
    "math_modulo": ("Rest von %DIVIDEND ÷ %DIVISOR", "math", "wert"),
    "math_op2": ("%op von %x und %y", "math", "wert"),
    "math_op3": ("Absolutwert von %x", "math", "wert"),
    "math_js_op": ("%OP %ARG0", "math", "wert"),
    "math_js_round": ("%OP %ARG0", "math", "wert"),
    "variables_set": ("setze %VAR auf %VALUE", "variables", "stapel"),
    "variables_change": ("ändere %VAR um %VALUE", "variables", "stapel"),
    "text_length": ("Länge von %VALUE", "text", "wert"),
    "lists_index_get": ("%LIST Wert an Position %INDEX", "arrays", "wert"),
    "lists_index_set": ("%LIST setze Wert an Position %INDEX auf %VALUE", "arrays", "stapel"),
    "lists_length": ("Länge des Arrays %VALUE", "arrays", "wert"),
    "function_definition": ("Funktion %function_name", "functions", "hut"),
    "procedures_defnoreturn": ("Funktion %NAME", "functions", "hut"),
    "function_return": ("Rückgabe %RETURN_VALUE", "functions", "stapel"),
}

# Blöcke mit beliebig vielen Eingängen, siehe _Wandler.aufruf().
AUFRUFE = {"text_join", "lists_create_with", "function_call", "function_call_output",
           "procedures_callnoreturn", "procedures_callreturn"}

# Auswahlwerte der eingebauten Blöcke, so wie der Editor sie zeigt.
AUSWAHL = {
    "EQ": "=", "NEQ": "≠", "LT": "<", "LTE": "≤", "GT": ">", "GTE": "≥",
    "AND": "und", "OR": "oder", "TRUE": "wahr", "FALSE": "falsch",
    "ADD": "+", "MINUS": "-", "MULTIPLY": "×", "DIVIDE": "÷", "POWER": "**",
    "min": "min", "max": "max",
    "sqrt": "Quadratwurzel", "sin": "sin", "cos": "cos", "tan": "tan",
    "atan2": "atan2", "idiv": "ganzzahlige Division", "imul": "ganzzahlige Multiplikation",
    "round": "runden", "ceil": "aufrunden", "floor": "abrunden", "trunc": "abschneiden",
}

# Schatten, die nur eine Zahl tragen. Bei manchen öffnet der Editor eine
# Auswahl (Zeit, Takt), das zeigt der Pfeil.
ZAHLEN = {"math_number", "math_integer", "math_whole_number", "math_number_minmax",
          "speedPicker", "turnRatioPicker", "protractorPicker", "brightnessPicker"}
ZAHLEN_MIT_AUSWAHL = {"timePicker"}


def zeichen_schuetzen(text):
    """Wie in scratch_skripte, dazu kann kein Text eines Teams ein LED-Bildchen werden."""
    return _scratch_schuetzen(text).replace("▦", "□")


def _dunkler(farbe, anteil=0.8):
    """#rrggbb etwas dunkler."""
    try:
        werte = [int(farbe[stelle:stelle + 2], 16) for stelle in (1, 3, 5)]
    except ValueError:
        return farbe
    return "#" + "".join(f"{round(wert * anteil):02x}" for wert in werte)


def _kinder(block, art):
    return [kind for kind in block if kind.tag == _BLOCKLY + art]


def _benannt(block, art, name):
    return next((kind for kind in _kinder(block, art) if kind.get("name") == name), None)


def _mutation(block):
    # Manche Blöcke schreiben ihre Mutation im XHTML-Namensraum.
    return next((kind for kind in block if kind.tag.rsplit("}", 1)[-1] == "mutation"), None)


def _ganzzahl(text):
    try:
        return int(text or 0)
    except ValueError:
        return 0


class _Wandler:

    def __init__(self, bloecke, werte):
        self.bloecke = bloecke
        self.werte = werte
        self.symbole = tabelle()["symbole"]
        # Klammern, die der Browser vor dem Zeichnen anmelden muss: Vorlage -> Form
        self.klammern = {}
        # Die LED-Bildchen des Skripts, das gerade entsteht, der Reihe nach
        self.leds = []

    # Felder und Eingänge -------------------------------------------------

    def feldwert(self, feld):
        """Ein Feld mit Auswahl wie [links v], LED-Bildchen oder Text."""
        wert = feld.text or ""
        if feld.get("name") == "VAR":
            return f"[{zeichen_schuetzen(wert)} v]"
        if wert in self.symbole:
            return self.led([punkt == "1" for punkt in self.symbole[wert]], auswahl=True)
        if wert in AUSWAHL:
            return f"[{AUSWAHL[wert]} v]"
        if wert in self.werte:
            return f"[{zeichen_schuetzen(self.werte[wert])} v]"
        if re.fullmatch(r"[A-Za-z_]\w*(\.\w+)+", wert):
            # Ein Wert aus einer Aufzählung ohne eigenen Text: der Name.
            return f"[{zeichen_schuetzen(wert.rsplit('.', 1)[-1])} v]"
        if re.fullmatch(r"0x[0-9a-fA-F]{6}|#[0-9a-fA-F]{6}", wert):
            return f"[#{wert[-6:].lower()}]"
        return f"[{zeichen_schuetzen(wert)}]"

    def eingang(self, block, name, tiefe):
        """Was in einem Eingang oder Feld namens name steht."""
        wert = _benannt(block, "value", name)
        if wert is not None:
            innen = wert.find(_BLOCKLY + "block")
            if innen is None:
                innen = wert.find(_BLOCKLY + "shadow")
            return self.ausdruck(innen, tiefe + 1) if innen is not None else "()"
        feld = _benannt(block, "field", name)
        if feld is not None:
            return self.feldwert(feld)
        return None

    def ausdruck(self, block, tiefe):
        """Ein Block, der in einem Eingang steckt."""
        if tiefe > MAX_TIEFE:
            return "(…)"
        art = block.get("type") or ""
        felder = _kinder(block, "field")
        if art == "variables_get":
            feld = _benannt(block, "field", "VAR")
            name = zeichen_schuetzen(feld.text if feld is not None else "")
            return f"({name} :: {_farbe('variables')})"
        if art == "logic_boolean":
            feld = _benannt(block, "field", "BOOL")
            return f"<{self.feldwert(feld) if feld is not None else '[ v]'} :: {_farbe('logic')}>"
        if art == "text":
            feld = _benannt(block, "field", "TEXT")
            return f"[{zeichen_schuetzen(feld.text if feld is not None else '')}]"
        if block.tag == _BLOCKLY + "shadow" or art in ZAHLEN or art in ZAHLEN_MIT_AUSWAHL:
            einfach = self.schatten(block, art, felder)
            if einfach is not None:
                return einfach
        text, farbe, form = self.zeile(block, tiefe)
        if block.tag == _BLOCKLY + "shadow":
            # Etwa „geklickt“ in „wenn Knopf A geklickt“: im Editor dunkler
            # als der Block, in dem es steht.
            farbe = _dunkler(farbe)
        if form == "bedingung":
            return f"<{text} :: {farbe}>"
        return f"({text} :: {farbe} reporter)"

    def schatten(self, block, art, felder):
        """Ein Schatten mit nur einem Wert, so schlicht wie im Editor."""
        if art in ZAHLEN or art in ZAHLEN_MIT_AUSWAHL:
            zahl = zeichen_schuetzen(felder[0].text if felder else "0")
            return f"({zahl} v)" if art in ZAHLEN_MIT_AUSWAHL else f"({zahl})"
        if art == "text":
            return f"[{zeichen_schuetzen(felder[0].text if felder else '')}]"
        if art == "colorNumberPicker" and felder:
            return self.feldwert(felder[0])
        if len(felder) == 1 and not _kinder(block, "value"):
            # Auswahl wie die Note bei „spiele Note“ oder die Pin-Nummer.
            inhalt = self.feldwert(felder[0])
            if inhalt.endswith(" v]"):
                return "(" + inhalt[1:-1] + ")"
            return inhalt
        return None

    # Blöcke ------------------------------------------------------------------

    def beschreibung(self, art):
        """(Vorlage, Farbe, Form, mit Bild) eines Blocks."""
        if art in EINGEBAUT:
            text, kategorie, form = EINGEBAUT[art]
            return text, _farbe(kategorie), form, False
        eintrag = self.bloecke.get(art)
        if eintrag:
            return eintrag["text"], eintrag["farbe"], eintrag["form"], eintrag.get("bild", False)
        return None, "#bbbbbb", "stapel", False

    def ausfuellen(self, vorlage, block, tiefe):
        """(Text, Vorlage für scratchblocks) mit den Werten des Blocks.

        Was hinter „||“ steht, zeigt der Editor erst, wenn jemand den Block
        mit ⊕ aufgeklappt hat; dann steht der Eingang auch in der Datei.
        """
        grund, _, extra = vorlage.partition("||")
        teile = []

        def text(stueck):
            stueck = re.sub(r"\\+%", "%", stueck)
            if stueck.strip():
                teile.append(("text", " ".join(stueck.split())))

        # re.split mit Gruppe: Text und Namen der Eingänge im Wechsel.
        zerlegt = PLATZHALTER.split(grund.replace("|", " "))
        for nummer, stueck in enumerate(zerlegt):
            if nummer % 2 == 0:
                text(stueck)
            else:
                teile.append(("eingang", self.eingang(block, stueck, tiefe) or "()"))
        zerlegt = PLATZHALTER.split(extra.replace("|", " "))
        for nummer in range(1, len(zerlegt), 2):
            wert = self.eingang(block, zerlegt[nummer], tiefe)
            if wert is None:
                break
            text(zerlegt[nummer - 1])
            teile.append(("eingang", wert))
            if nummer + 2 >= len(zerlegt):
                text(zerlegt[nummer + 1])

        geschrieben, anmelden, nummer = [], [], 0
        for art, wert in teile:
            if art == "text":
                geschrieben.append(zeichen_schuetzen(wert))
                anmelden.append(wert)
            else:
                geschrieben.append(wert)
                nummer += 1
                anmelden.append(f"%{nummer}")
        return " ".join(geschrieben), " ".join(anmelden)

    def aufruf(self, block, art, tiefe):
        """Blöcke mit beliebig vielen Eingängen: Funktionsaufruf, „verbinde“, Array."""
        werte = [self.eingang(block, kind.get("name"), tiefe) or "()" for kind in _kinder(block, "value")]
        if art in ("text_join", "lists_create_with"):
            kopf = "verbinde" if art == "text_join" else "Array von"
            kategorie = "text" if art == "text_join" else "arrays"
            return " ".join([kopf, *werte]), _farbe(kategorie), "wert"
        mutation = _mutation(block)
        name = mutation.get("name", "") if mutation is not None else ""
        feld = _benannt(block, "field", "function_name") or _benannt(block, "field", "NAME")
        if not name and feld is not None:
            name = feld.text or ""
        form = "stapel" if art in ("function_call", "procedures_callnoreturn") else "wert"
        return " ".join(["Aufruf", zeichen_schuetzen(name), *werte]), _farbe("functions"), form

    def zeile(self, block, tiefe):
        """(Text, Farbe, Form) eines Blocks, ohne die Klammern darin."""
        art = block.get("type") or ""
        if art in AUFRUFE:
            return self.aufruf(block, art, tiefe)
        vorlage, farbe, form, bild = self.beschreibung(art)
        if vorlage is None:
            # Ein Block, den die Tabelle nicht kennt: grau, mit seinem Namen.
            werte = [self.eingang(block, kind.get("name"), tiefe) or "()"
                     for kind in block if kind.tag in (_BLOCKLY + "value", _BLOCKLY + "field")]
            return " ".join([zeichen_schuetzen(art) or "?", *werte]), farbe, form
        text, anmelden = self.ausfuellen(vorlage, block, tiefe)
        if bild:
            text += " " + self.led_bild(block)
        # Werte, die ein Ereignis mitbringt, etwa „receivedNumber“ bei
        # „wenn Datenpaket empfangen“, stehen als Variablen dahinter.
        for feld in _kinder(block, "field"):
            if (feld.get("name") or "").startswith("HANDLER_DRAG_PARAM_"):
                text += f" ({zeichen_schuetzen(feld.text or '')} :: {_farbe('variables')})"
        if form in ("hut", "klammer"):
            self.klammern[anmelden] = "c-block cap" if form == "hut" else "c-block"
        return text, farbe, form

    def led_bild(self, block):
        """Das Bild eines Blocks wie „zeige LEDs“ als Raster."""
        feld = _benannt(block, "field", "LEDS")
        if feld is not None:
            punkte = [zeichen == "#" for zeichen in (feld.text or "") if zeichen in "#."]
        else:
            punkte = []
            for zeile in range(5):
                for spalte in range(5):
                    einzeln = _benannt(block, "field", f"LED{spalte}{zeile}")
                    punkte.append(einzeln is not None and (einzeln.text or "").upper() == "TRUE")
        return self.led(punkte, auswahl=False)

    def led(self, punkte, auswahl):
        """Platzhalter für ein Bildchen; die Punkte merkt sich self.leds."""
        self.leds.append("".join("1" if punkt else "0" for punkt in (list(punkte) + [False] * 25)[:25]))
        return f"[{LED_PLATZHALTER} v]" if auswahl else f"[{LED_PLATZHALTER}]"

    def wenn(self, block, tiefe):
        """„wenn … dann“ mit allen „sonst wenn“ und „sonst“.

        Steht im „sonst“ nur ein weiteres „wenn“, macht der Editor daraus eine
        Reihe von „sonst wenn“, und so steht es auch hier.
        """
        logik = _farbe("logic")
        zeilen, erstes = [], True
        while True:
            mutation = _mutation(block)
            weitere = _ganzzahl(mutation.get("elseif")) if mutation is not None else 0
            mit_sonst = mutation is not None and mutation.get("else") == "1"
            for nummer in range(weitere + 1):
                bedingung = self.eingang(block, f"IF{nummer}", tiefe) or "<>"
                kopf = "wenn %1 dann" if erstes else "sonst wenn %1 dann"
                self.klammern[kopf] = "c-block" if erstes else "celse"
                zeilen.append(kopf.replace("%1", bedingung) + f" :: {logik}")
                zeilen += self.mund(block, f"DO{nummer}", tiefe)
                erstes = False
            sonst = _benannt(block, "statement", "ELSE") if mit_sonst else None
            innen = sonst.find(_BLOCKLY + "block") if sonst is not None else None
            if (innen is not None and innen.get("type") == "controls_if"
                    and innen.find(_BLOCKLY + "next") is None and tiefe < MAX_TIEFE):
                block, tiefe = innen, tiefe + 1
                continue
            if mit_sonst:
                self.klammern["sonst"] = "celse"
                zeilen.append(f"sonst :: {logik}")
                zeilen += self.mund(block, "ELSE", tiefe)
            zeilen.append("end")
            return zeilen

    def mund(self, block, name, tiefe):
        """Die Blöcke in der Klammer namens name."""
        klammer = _benannt(block, "statement", name)
        innen = klammer.find(_BLOCKLY + "block") if klammer is not None else None
        return self.stapel(innen, tiefe + 1)

    def stapel(self, block, tiefe=0):
        """Ein Block und alles, was unter ihm hängt, als Zeilen."""
        zeilen = []
        while block is not None and tiefe <= MAX_TIEFE:
            if block.get("type") == "controls_if":
                zeilen += self.wenn(block, tiefe)
            else:
                text, farbe, form = self.zeile(block, tiefe)
                if form == "bedingung":
                    zeilen.append(f"<{text} :: {farbe}>")
                elif form == "wert":
                    zeilen.append(f"({text} :: {farbe} reporter)")
                else:
                    zeilen.append(f"{text} :: {farbe}")
                if form in ("hut", "klammer"):
                    erste = next(iter(_kinder(block, "statement")), None)
                    zeilen += self.mund(block, erste.get("name"), tiefe) if erste is not None else []
                    zeilen.append("end")
            weiter = block.find(_BLOCKLY + "next")
            block = weiter.find(_BLOCKLY + "block") if weiter is not None else None
            tiefe += 1
        return zeilen


def _lage(block):
    """Wo ein Skript liegt: in Streifen von oben nach unten, darin von links nach rechts.

    Skripte nebeneinander liegen selten auf den Punkt gleich hoch; was
    ungefähr auf einer Höhe beginnt, zählt als eine Reihe.
    """
    try:
        return round(float(block.get("y", 0)) / 200), float(block.get("x", 0))
    except ValueError:
        return 0, 0.0


def skripte_aus_projekt(dateien):
    """(Figuren, Hinweis) aus den Dateien eines Projekts.

    Wie bei Scratch eine Liste von {"name", "buehne", "skripte"}, hier mit nur
    einem Eintrag, denn ein MakeCode-Projekt hat keine Figuren. Für
    _skripte.html trägt er zusätzlich "klammern" ([[Vorlage, Form], …]), je
    Skript die Punkte seiner LED-Bildchen unter "leds" und unter "glatt", ob
    es mit einem Ereignisblock beginnt, der oben glatt ist.
    """
    xml = dateien.get("main.blocks", "")
    if not xml.strip():
        if dateien.get("main.py", "").strip() or dateien.get("main.ts", "").strip():
            return [], OHNE_BLOECKE
        return [], KEIN_PROJEKT
    if _DTD.search(xml):
        return [], KEIN_PROJEKT
    try:
        wurzel = ET.fromstring(xml)
    except (ET.ParseError, ValueError, RecursionError):
        return [], KEIN_PROJEKT

    grund = tabelle()
    bloecke, werte = _erweiterungen(dateien)
    wandler = _Wandler({**grund["bloecke"], **bloecke}, {**grund["werte"], **werte})
    skripte, leds, glatt = [], [], []
    for block in sorted(_kinder(wurzel, "block"), key=_lage):
        wandler.leds = []
        zeilen = wandler.stapel(block)
        if zeilen:
            skripte.append("\n".join(zeilen))
            leds.append(wandler.leds)
            glatt.append(wandler.beschreibung(block.get("type") or "")[2] == "hut")
    figur = {"name": "", "buehne": False, "titel": "Programm", "skripte": skripte,
             "klammern": sorted([vorlage, form] for vorlage, form in wandler.klammern.items()),
             "leds": leds, "glatt": glatt}
    return [figur], ""


def skripte_der_abgabe(pfad):
    """Die Blöcke einer MakeCode-Abgabe zum Anzeigen, als (Figuren, Hinweis)."""
    dateien, hinweis = lies_projekt(pfad)
    if dateien is None:
        return [], hinweis
    return skripte_aus_projekt(dateien)
