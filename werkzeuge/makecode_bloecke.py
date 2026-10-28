#!/usr/bin/env python3
"""Erzeugt plattform/makecode_bloecke.json aus dem Quelltext von MakeCode Calliope.

Die Blockansicht für MakeCode-Abgaben (plattform/makecode_skripte.py) braucht
für jeden Grundblock seinen deutschen Text, seine Farbe und seine Form, dazu
die Texte der Auswahlwerte und die LED-Muster der Symbole. All das steht im
Quelltext des Editors, als Angaben über den Funktionen
(//% blockId=… block="…") und in den Übersetzungen unter _locales/de.

Gebraucht werden drei Klone nebeneinander in einem Ordner, je auf dem Stand,
den der Editor gerade benutzt (steht in pxt-calliope/package.json):

    git clone --depth 1 --branch v8.1.15 https://github.com/microsoft/pxt-calliope
    git clone --depth 1 --branch v13.2.8 https://github.com/microsoft/pxt-common-packages
    git clone --depth 1 --branch v13.1.8 --filter=blob:none --sparse https://github.com/microsoft/pxt
    git -C pxt sparse-checkout set libs/pxt-common

    python werkzeuge/makecode_bloecke.py <Ordner mit den drei Klonen>

Das Skript braucht kein Internet, es liest nur die Klone und schreibt die
Tabelle neu. Danach `pytest` und eine Abgabe einmal ansehen.
Alle drei Projekte stehen unter der MIT-Lizenz.
"""

import argparse
import json
import re
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

from plattform.makecode_skripte import TABELLE, bloecke_aus_quelltext  # noqa: E402

# Pakete, deren Blöcke ein Calliope-Projekt ohne Erweiterung zeigen kann.
PAKETE = ["core", "core-mini-codal", "funk", "microphone"]

# Blöcke, für die MakeCode Calliope keine deutsche Übersetzung im Quelltext
# mitbringt (der Editor holt sie aus einem Übersetzungsdienst). Von Hand
# übersetzt, nah an der Wortwahl der übrigen Blöcke; die Eingänge müssen
# dieselben bleiben wie im Original.
ERGAENZUNG = {
    "radio_datagram_send": "Funk sende Zahl %value",
    "radio_datagram_send_string": "Funk sende Zeichenfolge %msg",
    "radio_datagram_send_value": "Funk sende|Wert %name|= %value",
    "radio_set_group": "Funk setze Gruppe %ID",
    "radio_set_transmit_power": "Funk setze Sendeleistung %power",
    "radio_set_frequency_band": "Funk setze Frequenzband %band",
    "radio_set_transmit_serial_number": "Funk setze Seriennummer übertragen %transmit",
    "radio_on_number": "wenn Datenpaket empfangen",
    "radio_on_number_drag": "wenn Datenpaket empfangen",
    "radio_on_string": "wenn Datenpaket empfangen",
    "radio_on_string_drag": "wenn Datenpaket empfangen",
    "radio_on_value": "wenn Datenpaket empfangen",
    "radio_on_value_drag": "wenn Datenpaket empfangen",
    "radio_on_buffer": "wenn Datenpaket empfangen",
    "radio_on_buffer_drag": "wenn Datenpaket empfangen",
    "radio_on_packet": "wenn Datenpaket empfangen",
    "radio_datagram_received_event": "Funk wenn Daten empfangen",
    "radio_datagram_receive": "Funk empfange Zahl",
    "radio_datagram_receive_string": "Funk empfange Zeichenfolge",
    "radio_datagram_rssi": "Funk empfangene Signalstärke",
    "radio_received_packet": "empfangenes Paket %type=radio_packet_property",
    "radio_write_packet_serial": "Funk schreibe empfangenes Paket an seriell",
    "radio_write_value_serial": "Funk schreibe Wert an seriell",
    "music_playable_play": "spiele $toPlay $playbackMode",
    "music_playable_play_default_bkg": "spiele $toPlay $playbackMode",
    "music_string_playable": "Melodie $melody im Tempo $bpm|(bpm)",
    "music_sound_is_playing": "Ton wird abgespielt",
    "music_set_built_in_speaker_enable": "eingebauten Lautsprecher $enabled",
    "soundExpression_playSoundEffect": "spiele Sound $sound $mode",
    "synth_set_volume": "setze Lautstärke %volume",
    "melody_on_event": "Musik bei %value",
    "pin_set_audio_pin_enabled": "Audio-Pin aktivieren $enabled",
    "input_logo_event": "wenn Logo $action",
    "input_logo_is_pressed": "Logo ist gedrückt",
    "device_set_led_colors": "setze LEDs auf %color1=colorNumberPicker %color2=colorNumberPicker "
                             "%color3=colorNumberPicker || Helligkeit %brightness",
    "motor_on": "Motor an mit %percent \\%",
    "block_dual_motor": "Motor %motor|mit %percent \\%",
    "string_split": "teile %this=text|bei %separator",
    "string_charcode_at": "Zeichencode von $this=text|an Position $index",
    "device_plot_bar_graph": "zeichne Balkendiagramm von $value bis $high|| seriell ausgeben $valueToConsole",
    "device_touch_set_type": "setze %name auf Berührungsmodus %mode",
}

_MUSTER = re.compile(r"case\s+IconNames\.(\w+)\s*:\s*return\s+images\.createImage\(`([^`]*)`")


def dateien_eines_pakets(calliope, paket, gesucht):
    """Die Quelltexte eines Pakets, wie MakeCode sie zusammensucht."""
    ordner = calliope / "libs" / paket
    beschreibung = json.loads((ordner / "pxt.json").read_text(encoding="utf-8"))
    weitere = []
    if beschreibung.get("additionalFilePath"):
        # „../../node_modules/pxt-common-packages/libs/radio“ -> Klon daneben
        teile = Path(beschreibung["additionalFilePath"]).parts
        weitere.append(gesucht["pxt-common-packages"].joinpath(*teile[teile.index("pxt-common-packages") + 1:]))
    weitere += [gesucht["pxt-common-packages"] / "libs" / "base", gesucht["pxt"] / "libs" / "pxt-common"]
    texte = []
    for name in beschreibung.get("files", []):
        if not name.endswith(".ts"):
            continue
        for kandidat in [ordner, *weitere]:
            if (kandidat / name).is_file():
                texte.append((kandidat / name).read_text(encoding="utf-8"))
                break
    return texte


def uebersetzungen(calliope):
    texte = {}
    for datei in sorted((calliope / "libs").glob("*/_locales/de/*-strings.json")):
        texte.update(json.loads(datei.read_text(encoding="utf-8")))
    return texte


def symbole(calliope):
    """Die LED-Muster der Symbole aus icons.ts: Name -> 25 Mal 0 oder 1."""
    quelltext = (calliope / "libs" / "core" / "icons.ts").read_text(encoding="utf-8")
    muster = {}
    for name, bild in _MUSTER.findall(quelltext):
        punkte = [zeichen == "#" for zeichen in bild if zeichen in "#."]
        if len(punkte) == 25:
            muster[f"IconNames.{name}"] = "".join("1" if punkt else "0" for punkt in punkte)
    return muster


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("ordner", type=Path, help="Ordner mit pxt-calliope, pxt-common-packages und pxt")
    args = parser.parse_args()

    gesucht = {name: args.ordner / name for name in ("pxt-calliope", "pxt-common-packages", "pxt")}
    for name, pfad in gesucht.items():
        if not pfad.is_dir():
            sys.exit(f"{name} fehlt unter {args.ordner}")
    calliope = gesucht["pxt-calliope"]
    ziel = json.loads((calliope / "pxtarget.json").read_text(encoding="utf-8"))
    stand = json.loads((calliope / "package.json").read_text(encoding="utf-8"))["version"]

    # Farben der Kategorien wie im Editor; ein Namensraum kann eine eigene nennen.
    kategorien = {name: farbe.lower() for name, farbe in ziel["appTheme"]["blockColors"].items()}

    quellen = []
    for paket in PAKETE:
        quellen += dateien_eines_pakets(calliope, paket, gesucht)
    bloecke, werte = bloecke_aus_quelltext(quellen, uebersetzungen(calliope), kategorien)
    for block_id, text in ERGAENZUNG.items():
        if block_id in bloecke:
            bloecke[block_id]["text"] = text

    tabelle = {
        "quelle": f"MakeCode Calliope {stand} (github.com/microsoft/pxt-calliope, MIT-Lizenz), "
                  "erzeugt von werkzeuge/makecode_bloecke.py",
        "kategorien": kategorien,
        "bloecke": dict(sorted(bloecke.items())),
        "werte": dict(sorted(werte.items())),
        "symbole": dict(sorted(symbole(calliope).items())),
    }
    with open(TABELLE, "w", encoding="utf-8") as datei:
        json.dump(tabelle, datei, ensure_ascii=False, indent=1)
        datei.write("\n")
    print(f"{len(bloecke)} Blöcke, {len(werte)} Auswahlwerte, {len(tabelle['symbole'])} Symbole "
          f"aus MakeCode Calliope {stand} -> {Path(TABELLE).relative_to(WURZEL)}")


if __name__ == "__main__":
    main()
