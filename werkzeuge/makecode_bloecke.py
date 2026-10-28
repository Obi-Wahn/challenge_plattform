#!/usr/bin/env python3
"""Erzeugt plattform/makecode_bloecke.json aus dem Quelltext von MakeCode Calliope.

Die Blockansicht für MakeCode-Abgaben (plattform/makecode_skripte.py) braucht
für jeden Grundblock seinen deutschen Text, seine Farbe und seine Form, dazu
die Texte der Auswahlwerte und die LED-Muster der Symbole. Form, Farbe und
englischer Text stehen im Quelltext des Editors, als Angaben über den
Funktionen (//% blockId=… block="…").

Die deutschen Texte lädt der Editor beim Start live von MakeCode, und nur
diese stimmen mit dem überein, was im Editor zu sehen ist. Die älteren
Übersetzungen unter _locales/de im Quelltext dienen nur als Rückfall. Das
Skript lädt die Live-Texte nach <Ordner>/uebersetzungen (dafür braucht es
einmal Netz zu makecode.calliope.cc); liegen sie dort schon, nimmt es sie.

Gebraucht werden drei Klone nebeneinander in einem Ordner, je auf dem Stand,
den der Editor gerade benutzt (steht in pxt-calliope/package.json):

    git clone --depth 1 --branch v8.1.15 https://github.com/microsoft/pxt-calliope
    git clone --depth 1 --branch v13.2.8 https://github.com/microsoft/pxt-common-packages
    git clone --depth 1 --branch v13.1.8 --filter=blob:none --sparse https://github.com/microsoft/pxt
    git -C pxt sparse-checkout set libs/pxt-common

    python werkzeuge/makecode_bloecke.py <Ordner mit den drei Klonen>

Danach `pytest` und eine Abgabe einmal ansehen.
Alle drei Projekte stehen unter der MIT-Lizenz.
"""

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

from plattform.makecode_skripte import TABELLE, bloecke_aus_quelltext, gebrauchte_texte  # noqa: E402

# Woher der deutsche Editor seine Texte holt (pxtlib/util.ts,
# downloadLiveTranslationsAsync); „strings.json“ und „target-strings.json“
# enthalten die eingebauten Blöcke wie „wiederhole“ und „wenn … dann“.
LIVE = "https://makecode.calliope.cc/api/translations?lang=de&approved=true&filename="

# Pakete, deren Blöcke ein Calliope-Projekt ohne Erweiterung zeigen kann.
PAKETE = ["core", "core-mini-codal", "funk", "microphone"]

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


def live_texte(ordner, dateiname):
    """Eine Datei mit Live-Übersetzungen, aus dem Ordner oder frisch geladen."""
    ziel = ordner / dateiname.replace("/", "_")
    if not ziel.is_file():
        ordner.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(LIVE + urllib.parse.quote(dateiname, safe=""), timeout=30) as antwort:
            ziel.write_bytes(antwort.read())
    texte = json.loads(ziel.read_text(encoding="utf-8"))
    return {k: v for k, v in texte.items() if isinstance(v, str) and v}


def uebersetzungen(calliope, ordner, ziel_id):
    """Die deutschen Texte der Pakete: aus dem Quelltext, darüber die Live-Texte."""
    texte = {}
    for datei in sorted((calliope / "libs").glob("*/_locales/de/*-strings.json")):
        texte.update(json.loads(datei.read_text(encoding="utf-8")))
    for paket in PAKETE:
        name = json.loads((calliope / "libs" / paket / "pxt.json").read_text(encoding="utf-8"))["name"]
        texte.update(live_texte(ordner, f"{ziel_id}/{name}-strings.json"))
    return texte


def editor_texte(ordner, ziel_id):
    """Die Texte der eingebauten Blöcke, die die Blockansicht braucht."""
    alle = {**live_texte(ordner, "strings.json"), **live_texte(ordner, f"{ziel_id}/target-strings.json")}
    return {schluessel: alle[schluessel] for schluessel in sorted(gebrauchte_texte()) if schluessel in alle}


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
    parser.add_argument("--neu-laden", action="store_true", help="Live-Übersetzungen neu herunterladen")
    args = parser.parse_args()

    gesucht = {name: args.ordner / name for name in ("pxt-calliope", "pxt-common-packages", "pxt")}
    for name, pfad in gesucht.items():
        if not pfad.is_dir():
            sys.exit(f"{name} fehlt unter {args.ordner}")
    calliope = gesucht["pxt-calliope"]
    ziel = json.loads((calliope / "pxtarget.json").read_text(encoding="utf-8"))
    stand = json.loads((calliope / "package.json").read_text(encoding="utf-8"))["version"]
    live = args.ordner / "uebersetzungen"
    if args.neu_laden:
        for datei in live.glob("*.json"):
            datei.unlink()

    # Farben der Kategorien wie im Editor; ein Namensraum kann eine eigene nennen.
    kategorien = {name: farbe.lower() for name, farbe in ziel["appTheme"]["blockColors"].items()}

    quellen = []
    for paket in PAKETE:
        quellen += dateien_eines_pakets(calliope, paket, gesucht)
    bloecke, werte = bloecke_aus_quelltext(quellen, uebersetzungen(calliope, live, ziel["id"]), kategorien)

    tabelle = {
        "quelle": f"MakeCode Calliope {stand} (github.com/microsoft/pxt-calliope, MIT-Lizenz), "
                  "deutsche Texte live von makecode.calliope.cc, erzeugt von werkzeuge/makecode_bloecke.py",
        "kategorien": kategorien,
        "texte": editor_texte(live, ziel["id"]),
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
