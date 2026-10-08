"""Die Skripte einer Scratch-Abgabe, zum Anzeigen auf der Bewertungsseite.

Eine .sb3 ist eine ZIP-Datei. Darin beschreibt project.json jede Figur und
jeden Block; Bilder und Klänge liegen daneben und werden hier nicht gelesen.
Aus den Blöcken entsteht Text in der Schreibweise von scratchblocks, etwa

    when flag clicked
    forever
      go to (Mauszeiger v)
    end

Im Browser zeichnet die Bibliothek scratchblocks daraus die bunten Blöcke und
übersetzt die Blocktexte ins Deutsche. Ihre Übersetzung kennt aber keine
Auswahlwerte, deshalb stehen die hier schon auf Deutsch (WERTE).

Gelesen wird nur, nichts wird ausgeführt oder gespeichert. Die Datei kommt
von einem Team, also wird jeder Wert geprüft, bevor er benutzt wird.
"""

import json
import zipfile

# Eine echte project.json hat selten mehr als ein paar hundert KB; die
# Bilder und Klänge liegen nicht darin. Die Grenze schützt vor einer
# ZIP-Datei, die beim Entpacken riesig wird.
MAX_PROJECT_JSON = 5 * 1024 * 1024

# So tief stecken Blöcke in echten Projekten nie ineinander. Die Grenze
# fängt eine bearbeitete Datei ab, bevor Python die Rekursion abbricht.
MAX_TIEFE = 50

KEIN_PROJEKT = ("Die Datei ist kein lesbares Scratch-3-Projekt - "
                "zum Ansehen herunterladen und in Scratch öffnen.")

# opcode -> Vorlage in der englischen Schreibweise von scratchblocks.
# {NAME} ist ein Eingang, {f:NAME} ein Feld mit Auswahl wie [Punkte v].
BLOECKE = {
    # Bewegung
    "motion_movesteps": "move {STEPS} steps",
    "motion_turnright": "turn right {DEGREES} degrees",
    "motion_turnleft": "turn left {DEGREES} degrees",
    "motion_goto": "go to {TO}",
    "motion_gotoxy": "go to x: {X} y: {Y}",
    "motion_glideto": "glide {SECS} secs to {TO}",
    "motion_glidesecstoxy": "glide {SECS} secs to x: {X} y: {Y}",
    "motion_pointindirection": "point in direction {DIRECTION}",
    "motion_pointtowards": "point towards {TOWARDS}",
    "motion_changexby": "change x by {DX}",
    "motion_setx": "set x to {X}",
    "motion_changeyby": "change y by {DY}",
    "motion_sety": "set y to {Y}",
    "motion_ifonedgebounce": "if on edge, bounce",
    "motion_setrotationstyle": "set rotation style {f:STYLE}",
    "motion_xposition": "(x position)",
    "motion_yposition": "(y position)",
    "motion_direction": "(direction)",
    # Aussehen
    "looks_sayforsecs": "say {MESSAGE} for {SECS} seconds",
    "looks_say": "say {MESSAGE}",
    "looks_thinkforsecs": "think {MESSAGE} for {SECS} seconds",
    "looks_think": "think {MESSAGE}",
    "looks_switchcostumeto": "switch costume to {COSTUME}",
    "looks_nextcostume": "next costume",
    "looks_switchbackdropto": "switch backdrop to {BACKDROP}",
    "looks_switchbackdroptoandwait": "switch backdrop to {BACKDROP} and wait",
    "looks_nextbackdrop": "next backdrop",
    "looks_changesizeby": "change size by {CHANGE}",
    "looks_setsizeto": "set size to {SIZE} %",
    "looks_changeeffectby": "change {f:EFFECT} effect by {CHANGE}",
    "looks_seteffectto": "set {f:EFFECT} effect to {VALUE}",
    "looks_cleargraphiceffects": "clear graphic effects",
    "looks_show": "show",
    "looks_hide": "hide",
    "looks_gotofrontback": "go to {f:FRONT_BACK} layer",
    "looks_goforwardbackwardlayers": "go {f:FORWARD_BACKWARD} {NUM} layers",
    "looks_costumenumbername": "(costume {f:NUMBER_NAME})",
    "looks_backdropnumbername": "(backdrop {f:NUMBER_NAME})",
    "looks_size": "(size)",
    # Klang
    "sound_playuntildone": "play sound {SOUND_MENU} until done",
    "sound_play": "start sound {SOUND_MENU}",
    "sound_stopallsounds": "stop all sounds",
    "sound_changeeffectby": "change {f:EFFECT} effect by {VALUE} :: sound",
    "sound_seteffectto": "set {f:EFFECT} effect to {VALUE} :: sound",
    "sound_cleareffects": "clear sound effects",
    "sound_changevolumeby": "change volume by {VOLUME}",
    "sound_setvolumeto": "set volume to {VOLUME} %",
    "sound_volume": "(volume)",
    # Ereignisse
    "event_whenflagclicked": "when flag clicked",
    "event_whenkeypressed": "when {f:KEY_OPTION} key pressed",
    "event_whenthisspriteclicked": "when this sprite clicked",
    "event_whenstageclicked": "when stage clicked",
    "event_whenbackdropswitchesto": "when backdrop switches to {f:BACKDROP}",
    "event_whengreaterthan": "when {f:WHENGREATERTHANMENU} > {VALUE}",
    "event_whenbroadcastreceived": "when I receive {f:BROADCAST_OPTION}",
    "event_broadcast": "broadcast {BROADCAST_INPUT}",
    "event_broadcastandwait": "broadcast {BROADCAST_INPUT} and wait",
    # Steuerung
    "control_wait": "wait {DURATION} seconds",
    "control_repeat": "repeat {TIMES}",
    "control_forever": "forever",
    "control_if": "if {CONDITION} then",
    "control_if_else": "if {CONDITION} then",
    "control_wait_until": "wait until {CONDITION}",
    "control_repeat_until": "repeat until {CONDITION}",
    "control_while": "while {CONDITION}",
    "control_stop": "stop {f:STOP_OPTION}",
    "control_start_as_clone": "when I start as a clone",
    "control_create_clone_of": "create clone of {CLONE_OPTION}",
    "control_delete_this_clone": "delete this clone",
    # Fühlen
    "sensing_touchingobject": "<touching {TOUCHINGOBJECTMENU} ?>",
    "sensing_touchingcolor": "<touching color {COLOR} ?>",
    "sensing_coloristouchingcolor": "<color {COLOR} is touching {COLOR2} ?>",
    "sensing_distanceto": "(distance to {DISTANCETOMENU})",
    "sensing_askandwait": "ask {QUESTION} and wait",
    "sensing_answer": "(answer)",
    "sensing_keypressed": "<key {KEY_OPTION} pressed?>",
    "sensing_mousedown": "<mouse down?>",
    "sensing_mousex": "(mouse x)",
    "sensing_mousey": "(mouse y)",
    "sensing_setdragmode": "set drag mode {f:DRAG_MODE}",
    "sensing_loudness": "(loudness)",
    "sensing_timer": "(timer)",
    "sensing_resettimer": "reset timer",
    "sensing_of": "({f:PROPERTY} of {OBJECT})",
    "sensing_current": "(current {f:CURRENTMENU})",
    "sensing_dayssince2000": "(days since 2000)",
    "sensing_username": "(username)",
    # Operatoren
    "operator_add": "({NUM1} + {NUM2})",
    "operator_subtract": "({NUM1} - {NUM2})",
    "operator_multiply": "({NUM1} * {NUM2})",
    "operator_divide": "({NUM1} / {NUM2})",
    "operator_random": "(pick random {FROM} to {TO})",
    "operator_gt": "<{OPERAND1} > {OPERAND2}>",
    "operator_lt": "<{OPERAND1} < {OPERAND2}>",
    "operator_equals": "<{OPERAND1} = {OPERAND2}>",
    "operator_and": "<{OPERAND1} and {OPERAND2}>",
    "operator_or": "<{OPERAND1} or {OPERAND2}>",
    "operator_not": "<not {OPERAND}>",
    "operator_join": "(join {STRING1} {STRING2})",
    "operator_letter_of": "(letter {LETTER} of {STRING})",
    "operator_length": "(length of {STRING})",
    "operator_contains": "<{STRING1} contains {STRING2} ?>",
    "operator_mod": "({NUM1} mod {NUM2})",
    "operator_round": "(round {NUM})",
    "operator_mathop": "({f:OPERATOR} of {NUM})",
    # Variablen und Listen
    "data_setvariableto": "set {f:VARIABLE} to {VALUE}",
    "data_changevariableby": "change {f:VARIABLE} by {VALUE}",
    "data_showvariable": "show variable {f:VARIABLE}",
    "data_hidevariable": "hide variable {f:VARIABLE}",
    "data_addtolist": "add {ITEM} to {f:LIST}",
    "data_deleteoflist": "delete {INDEX} of {f:LIST}",
    "data_deletealloflist": "delete all of {f:LIST}",
    "data_insertatlist": "insert {ITEM} at {INDEX} of {f:LIST}",
    "data_replaceitemoflist": "replace item {INDEX} of {f:LIST} with {ITEM}",
    "data_itemoflist": "(item {INDEX} of {f:LIST})",
    "data_itemnumoflist": "(item # of {ITEM} in {f:LIST})",
    "data_lengthoflist": "(length of {f:LIST} :: list)",
    "data_listcontainsitem": "<{f:LIST} contains {ITEM} ? :: list>",
    "data_showlist": "show list {f:LIST}",
    "data_hidelist": "hide list {f:LIST}",
    # Malstift
    "pen_clear": "erase all",
    "pen_stamp": "stamp",
    "pen_penDown": "pen down",
    "pen_penUp": "pen up",
    "pen_setPenColorToColor": "set pen color to {COLOR}",
    "pen_changePenColorParamBy": "change pen {COLOR_PARAM} by {VALUE}",
    "pen_setPenColorParamTo": "set pen {COLOR_PARAM} to {VALUE}",
    "pen_changePenSizeBy": "change pen size by {SIZE}",
    "pen_setPenSizeTo": "set pen size to {SIZE}",
    # Musik
    "music_playDrumForBeats": "play drum {DRUM} for {BEATS} beats",
    "music_restForBeats": "rest for {BEATS} beats",
    "music_playNoteForBeats": "play note {NOTE} for {BEATS} beats",
    "music_setInstrument": "set instrument to {INSTRUMENT}",
    "music_setTempo": "set tempo to {TEMPO}",
    "music_changeTempo": "change tempo by {TEMPO}",
    "music_getTempo": "(tempo)",
}

# Blöcke mit Klammer: die Eingänge, in denen die eingeschlossenen Blöcke
# hängen. Ein zweiter Eingang ist der „sonst“-Teil.
KLAMMERN = {
    "control_repeat": ("SUBSTACK",),
    "control_forever": ("SUBSTACK",),
    "control_if": ("SUBSTACK",),
    "control_if_else": ("SUBSTACK", "SUBSTACK2"),
    "control_repeat_until": ("SUBSTACK",),
    "control_while": ("SUBSTACK",),
}

# Spitze Eingänge: Bleiben sie leer, zeigt Scratch ein leeres Sechseck.
BEDINGUNGEN = {"CONDITION", "OPERAND", "OPERAND1", "OPERAND2"}

# Feste Auswahlwerte so, wie das deutsche Scratch sie zeigt - je Feld, denn
# eine Variable darf zum Beispiel auch „all“ heißen. Die Werte mit
# Unterstrichen stehen in den Auswahlmenüs mehrerer Blöcke.
MENUEZIELE = {
    "_mouse_": "Mauszeiger", "_random_": "Zufallsposition", "_edge_": "Rand",
    "_stage_": "Bühne", "_myself_": "mich selbst",
}
WERTE = {
    "KEY_OPTION": {
        "space": "Leertaste", "up arrow": "Pfeil nach oben",
        "down arrow": "Pfeil nach unten", "left arrow": "Pfeil nach links",
        "right arrow": "Pfeil nach rechts", "any": "beliebige",
    },
    "EFFECT": {
        "COLOR": "Farbe", "FISHEYE": "Fischauge", "WHIRL": "Wirbel",
        "PIXELATE": "Pixel", "MOSAIC": "Mosaik", "BRIGHTNESS": "Helligkeit",
        "GHOST": "Durchsichtigkeit", "PITCH": "Höhe",
        "PAN": "Aussteuern links/rechts",
    },
    "CURRENTMENU": {
        "YEAR": "Jahr", "MONTH": "Monat", "DATE": "Datum",
        "DAYOFWEEK": "Wochentag", "HOUR": "Stunde", "MINUTE": "Minute",
        "SECOND": "Sekunde",
    },
    "WHENGREATERTHANMENU": {"LOUDNESS": "Lautstärke", "TIMER": "Stoppuhr"},
    "STYLE": {
        "left-right": "links-rechts", "don't rotate": "nicht drehen",
        "all around": "rundherum",
    },
    "FRONT_BACK": {"front": "vorderste", "back": "hinterste"},
    "FORWARD_BACKWARD": {"forward": "nach vorne", "backward": "nach hinten"},
    "NUMBER_NAME": {"number": "Nummer", "name": "Name"},
    "DRAG_MODE": {"draggable": "ziehbar", "not draggable": "nicht ziehbar"},
    "OPERATOR": {
        "abs": "Betrag", "floor": "abrunden", "ceiling": "aufrunden",
        "sqrt": "Wurzel",
    },
    "PROPERTY": {
        "x position": "x-Position", "y position": "y-Position",
        "direction": "Richtung", "costume #": "Kostümnummer",
        "costume name": "Kostümname", "size": "Größe", "volume": "Lautstärke",
        "backdrop #": "Bühnenbildnummer", "backdrop name": "Bühnenbildname",
    },
    "BACKDROP": {
        "next backdrop": "nächstes Bühnenbild",
        "previous backdrop": "vorheriges Bühnenbild",
        "random backdrop": "zufälliges Bühnenbild",
    },
    "colorParam": {
        "color": "Farbe", "saturation": "Sättigung",
        "brightness": "Helligkeit", "transparency": "Transparenz",
    },
}

# Die Wahl bei „stoppe“ ändert die Form des Blocks: Nur „andere Skripte“
# lässt unten etwas anhängen. scratchblocks erkennt das am englischen Text,
# der deutsche braucht den Hinweis auf die Form.
STOPP = {
    "all": ("alles", ""),
    "this script": ("dieses Skript", ""),
    "other scripts in sprite": ("andere Skripte der Figur", " :: stack"),
    "other scripts in stage": ("andere Skripte der Bühne", " :: stack"),
}


def zeichen_schuetzen(text):
    """Text eines Teams so, dass scratchblocks ihn nicht als Syntax liest.

    Klammern würden sonst einen Eingang öffnen, ein „ v“ am Ende machte ein
    Auswahlfeld daraus, ein # am Anfang eine Farbe, ein @ ein Symbol.
    Zeilenumbrüche hätten einen neuen Block begonnen.
    """
    text = " ".join(str(text).split())
    for zeichen in "\\[]()<>@#":
        text = text.replace(zeichen, "\\" + zeichen)
    text = text.replace("::", ":\\:")
    if text.endswith(" v"):
        text = text[:-1] + "\\v"
    return text


class _Wandler:
    """Wandelt die Blöcke einer Figur in scratchblocks-Text."""

    def __init__(self, bloecke):
        self.bloecke = bloecke
        self.besucht = set()

    def block(self, block_id):
        if not isinstance(block_id, str):
            return None
        block = self.bloecke.get(block_id)
        return block if isinstance(block, dict) else None

    @staticmethod
    def teil(block, schluessel):
        wert = block.get(schluessel)
        return wert if isinstance(wert, dict) else {}

    def feldwert(self, block, name):
        feld = self.teil(block, "fields").get(name)
        if not isinstance(feld, list) or not feld or feld[0] is None:
            return ""
        wert = str(feld[0])
        if wert in MENUEZIELE:
            return MENUEZIELE[wert]
        return WERTE.get(name, {}).get(wert, wert)

    def auswahl(self, block, name):
        return f"[{zeichen_schuetzen(self.feldwert(block, name))} v]"

    def eingang(self, block, name, tiefe):
        wert = self.teil(block, "inputs").get(name)
        leer = "<>" if name in BEDINGUNGEN else "()"
        if not isinstance(wert, list) or len(wert) < 2:
            return leer
        # [Art, Inhalt, Schatten]: Liegt ein Block auf dem Eingang, steht er
        # an zweiter Stelle; der Schatten ist der Wert, der darunter läge.
        inhalt = wert[1] if wert[1] is not None else (wert[2] if len(wert) > 2 else None)
        if inhalt is None:
            return leer
        return self.wert(inhalt, tiefe)

    def wert(self, inhalt, tiefe):
        if isinstance(inhalt, str):
            return self.reporter(inhalt, tiefe + 1)
        if not isinstance(inhalt, list) or len(inhalt) < 2:
            return "()"
        art, text = inhalt[0], zeichen_schuetzen(inhalt[1])
        if art in (4, 5, 6, 7, 8):  # Zahlen, Winkel
            return f"({text})"
        if art == 9:  # Farbe, als #rrggbb - das # bleibt hier ungeschützt
            return f"[{text.replace(chr(92) + '#', '#')}]"
        if art == 10:
            return f"[{text}]"
        if art == 11:  # Nachricht
            return f"({text} v)"
        if art == 12:
            return f"({text} :: variables)"
        if art == 13:
            return f"({text} :: list)"
        return "()"

    def reporter(self, block_id, tiefe):
        block = self.block(block_id)
        # Jeder Block steht nur an einer Stelle. Zeigt eine bearbeitete Datei
        # im Kreis auf sich selbst, endet es hier.
        if block is None or tiefe > MAX_TIEFE or block_id in self.besucht:
            return "()"
        self.besucht.add(block_id)
        opcode = block.get("opcode")
        if opcode == "data_variable":
            return f"({zeichen_schuetzen(self.feldwert(block, 'VARIABLE'))} :: variables)"
        if opcode == "data_listcontents":
            return f"({zeichen_schuetzen(self.feldwert(block, 'LIST'))} :: list)"
        if opcode == "argument_reporter_string_number":
            return f"({zeichen_schuetzen(self.feldwert(block, 'VALUE'))} :: custom-arg)"
        if opcode == "argument_reporter_boolean":
            return f"<{zeichen_schuetzen(self.feldwert(block, 'VALUE'))} :: custom-arg>"

        # Ein Auswahlmenü („gehe zu (Mauszeiger v)“) ist in der Datei ein
        # eigener Schattenblock mit genau einem Feld.
        felder = self.teil(block, "fields")
        if block.get("shadow") and not self.teil(block, "inputs") and len(felder) == 1:
            name = next(iter(felder))
            return f"({zeichen_schuetzen(self.feldwert(block, name))} v)"
        return self.zeile(block, tiefe)

    def zeile(self, block, tiefe):
        opcode = block.get("opcode")
        opcode = opcode if isinstance(opcode, str) else ""
        if opcode == "procedures_call":
            return self.aufruf(block, tiefe)
        if opcode == "procedures_definition":
            return self.definition(block)
        if opcode == "control_stop":
            wert = self.teil(block, "fields").get("STOP_OPTION")
            text, form = STOPP.get(wert[0] if isinstance(wert, list) and wert else "",
                                   (self.feldwert(block, "STOP_OPTION"), ""))
            return f"stop [{zeichen_schuetzen(text)} v]{form}"

        vorlage = BLOECKE.get(opcode)
        if vorlage is None:
            # Ein Block aus einer Erweiterung, die hier niemand kennt: grau,
            # mit seinem internen Namen und den Werten, die darin stehen.
            werte = [self.eingang(block, name, tiefe) for name in self.teil(block, "inputs")
                     if name not in ("SUBSTACK", "SUBSTACK2")]
            return " ".join([zeichen_schuetzen(opcode) or "?", *werte]) + " :: grey"

        ausgabe, rest = [], vorlage
        while "{" in rest:
            vorne, _, rest = rest.partition("{")
            name, _, rest = rest.partition("}")
            ausgabe.append(vorne)
            if name.startswith("f:"):
                ausgabe.append(self.auswahl(block, name[2:]))
            else:
                ausgabe.append(self.eingang(block, name, tiefe))
        ausgabe.append(rest)
        return "".join(ausgabe)

    def mutation(self, block, schluessel):
        """Eine Liste aus der Beschreibung eines eigenen Blocks."""
        try:
            wert = json.loads(self.teil(block, "mutation").get(schluessel) or "[]")
        except (TypeError, ValueError):
            return []
        return wert if isinstance(wert, list) else []

    def eigener_block(self, block, einsetzen):
        """Der Text eines eigenen Blocks, die Platzhalter ersetzt."""
        proccode = str(self.teil(block, "mutation").get("proccode", ""))
        teile, nummer = [], 0
        for stueck in proccode.split():
            if stueck in ("%s", "%n", "%b"):
                teile.append(einsetzen(nummer, stueck == "%b"))
                nummer += 1
            else:
                teile.append(zeichen_schuetzen(stueck))
        return " ".join(teile)

    def aufruf(self, block, tiefe):
        kennungen = self.mutation(block, "argumentids")

        def einsetzen(nummer, wahrheitswert):
            if nummer >= len(kennungen):
                return "<>" if wahrheitswert else "()"
            wert = self.eingang(block, str(kennungen[nummer]), tiefe)
            return "<>" if wahrheitswert and wert == "()" else wert

        return self.eigener_block(block, einsetzen) + " :: custom"

    def definition(self, block):
        eingang = self.teil(block, "inputs").get("custom_block")
        kopf = self.block(eingang[1]) if isinstance(eingang, list) and len(eingang) > 1 else None
        if kopf is None:
            return "define"
        namen = self.mutation(kopf, "argumentnames")

        def einsetzen(nummer, wahrheitswert):
            name = zeichen_schuetzen(namen[nummer]) if nummer < len(namen) else ""
            return f"<{name}>" if wahrheitswert else f"({name})"

        return "define " + self.eigener_block(kopf, einsetzen)

    def stapel(self, block_id, einzug="", tiefe=0):
        """Die Zeilen eines Skripts ab block_id, eingerückt je Klammer."""
        zeilen = []
        while tiefe < MAX_TIEFE and block_id not in self.besucht:
            block = self.block(block_id)
            if block is None:
                break
            self.besucht.add(block_id)
            zeilen.append(einzug + self.zeile(block, tiefe))

            klammern = KLAMMERN.get(block.get("opcode"))
            if klammern:
                for nummer, name in enumerate(klammern):
                    if nummer:
                        zeilen.append(einzug + "else")
                    innen = self.teil(block, "inputs").get(name)
                    if isinstance(innen, list) and len(innen) > 1:
                        zeilen += self.stapel(innen[1], einzug + "  ", tiefe + 1)
                zeilen.append(einzug + "end")

            block_id = block.get("next")
        return zeilen


def _zahl(wert):
    return wert if isinstance(wert, (int, float)) else 0


def skripte_aus_projekt(projekt):
    """Die Figuren eines Projekts mit ihren Skripten als scratchblocks-Text.

    Ergebnis: eine Liste von {"name", "buehne", "skripte"}, die Bühne zuerst
    wie in Scratch. Die Skripte stehen in der Reihenfolge, in der sie auf
    der Arbeitsfläche von oben nach unten liegen.
    """
    figuren = []
    ziele = projekt.get("targets") if isinstance(projekt, dict) else None
    for ziel in ziele if isinstance(ziele, list) else []:
        if not isinstance(ziel, dict):
            continue
        bloecke = ziel.get("blocks")
        bloecke = bloecke if isinstance(bloecke, dict) else {}
        wandler = _Wandler(bloecke)

        oben = sorted(
            ((_zahl(block.get("y")), _zahl(block.get("x")), block_id)
             for block_id, block in bloecke.items()
             if isinstance(block, dict) and block.get("topLevel") and not block.get("shadow")),
            key=lambda eintrag: eintrag[:2])
        skripte = []
        for _y, _x, block_id in oben:
            zeilen = wandler.stapel(block_id)
            if zeilen:
                skripte.append("\n".join(zeilen))

        figuren.append({
            "name": str(ziel.get("name", "")),
            "buehne": bool(ziel.get("isStage")),
            "skripte": skripte,
        })
    figuren.sort(key=lambda figur: not figur["buehne"])
    return figuren


def lies_projekt(pfad):
    """Die project.json einer .sb3 als Daten, oder None, wenn das nicht geht."""
    try:
        with zipfile.ZipFile(pfad) as archiv:
            info = archiv.getinfo("project.json")
            if info.file_size > MAX_PROJECT_JSON:
                return None
            with archiv.open(info) as datei:
                # Die Angabe im Verzeichnis der ZIP-Datei kann gelogen sein.
                roh = datei.read(MAX_PROJECT_JSON + 1)
    except (OSError, KeyError, zipfile.BadZipFile, RuntimeError, NotImplementedError):
        return None
    if len(roh) > MAX_PROJECT_JSON:
        return None
    try:
        return json.loads(roh)
    except (ValueError, RecursionError):
        return None


def skripte_der_abgabe(pfad):
    """Die Skripte einer .sb3-Abgabe zum Anzeigen, als (Figuren, Hinweis)."""
    projekt = lies_projekt(pfad)
    if not isinstance(projekt, dict) or not isinstance(projekt.get("targets"), list):
        return [], KEIN_PROJEKT
    return skripte_aus_projekt(projekt), ""
