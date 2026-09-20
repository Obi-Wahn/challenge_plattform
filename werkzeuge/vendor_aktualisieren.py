#!/usr/bin/env python3
"""Holt die Frontend-Bibliotheken nach static/vendor/.

Die Anwendung läuft ohne Internet, deshalb liegen Bootstrap, EasyMDE,
Font Awesome und die Handschriften als Dateien im Repo. Der Preis dafür:
Sie aktualisieren sich nicht von selbst. Dieses Skript nimmt die Handarbeit ab.

    python werkzeuge/vendor_aktualisieren.py --pruefen
        Sieht nach, ob es neuere Fassungen gibt. Ändert nichts.

    python werkzeuge/vendor_aktualisieren.py
        Holt genau die Fassungen, die in static/vendor/versionen.json stehen,
        und ersetzt die Dateien.

    python werkzeuge/vendor_aktualisieren.py --setzen bootstrap=5.3.8
        Trägt eine neue Fassung in versionen.json ein und holt sie.

Nach einem Update lohnt sich ein Blick auf die Seiten und ein Durchlauf der
Tests - eine neue Hauptversion kann Darstellung oder Bedienung ändern.

Gebraucht wird nur Python und eine Internetverbindung; die Dateien kommen aus
der npm-Registry, es muss kein npm installiert sein.
"""

import argparse
import base64
import hashlib
import io
import json
import shutil
import sys
import tarfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
VENDOR = WURZEL / "static" / "vendor"
VERSIONEN = VENDOR / "versionen.json"
REGISTRY = "https://registry.npmjs.org"


def lade_liste():
    with open(VERSIONEN, encoding="utf-8") as f:
        return json.load(f)


def schreibe_liste(liste):
    with open(VERSIONEN, "w", encoding="utf-8") as f:
        json.dump(liste, f, ensure_ascii=False, indent=2)
        f.write("\n")


def hole(url):
    with urllib.request.urlopen(url, timeout=60) as antwort:
        return antwort.read()


def paketdaten(npm_name, version=None):
    """Die Angaben der npm-Registry zu einem Paket."""
    pfad = urllib.parse.quote(npm_name, safe="@")
    url = f"{REGISTRY}/{pfad}" + (f"/{version}" if version else "")
    return json.loads(hole(url))


def pruefe_integritaet(rohdaten, erwartet):
    """Vergleicht den Download mit der Prüfsumme der Registry."""
    if not erwartet or not erwartet.startswith("sha512-"):
        return # ältere Pakete führen keine an
    soll = base64.b64decode(erwartet[len("sha512-"):])
    ist = hashlib.sha512(rohdaten).digest()
    if soll != ist:
        raise RuntimeError("Prüfsumme stimmt nicht - Download verworfen")


def pruefsumme(pfad):
    if not pfad.exists():
        return None
    return hashlib.sha256(pfad.read_bytes()).hexdigest()[:12]


def version_teile(version):
    """'5.3.10' -> (5, 3, 10), damit sich Fassungen vergleichen lassen."""
    teile = []
    for stueck in version.split("."):
        ziffern = ""
        for zeichen in stueck:
            if not zeichen.isdigit():
                break
            ziffern += zeichen
        teile.append(int(ziffern) if ziffern else 0)
    return tuple(teile)


def pruefen(liste):
    """Sagt, für welche Pakete es eine neuere Fassung gibt."""
    neueres = False
    for paket in liste["pakete"]:
        try:
            daten = paketdaten(paket["npm"])
            neuste = daten["dist-tags"]["latest"]
        except (urllib.error.URLError, KeyError, ValueError) as fehler:
            print(f"  {paket['name']:<20} konnte nicht abgefragt werden: {fehler}")
            continue

        hier = paket["version"]
        if version_teile(neuste) > version_teile(hier):
            neueres = True
            hinweis = "neuere Fassung"
            if version_teile(neuste)[0] > version_teile(hier)[0]:
                hinweis = "neue Hauptversion - Darstellung vorher prüfen"
            print(f"  {paket['name']:<20} {hier:>8}  ->  {neuste:<8}  ({hinweis})")
        else:
            print(f"  {paket['name']:<20} {hier:>8}      aktuell")

    if neueres:
        print("\nZum Übernehmen zum Beispiel:")
        print("  python werkzeuge/vendor_aktualisieren.py --setzen bootstrap=5.3.8")
        print("  python werkzeuge/vendor_aktualisieren.py")
    return neueres


def hole_paket(paket):
    """Lädt ein Paket und legt die gebrauchten Dateien ab."""
    daten = paketdaten(paket["npm"], paket["version"])
    rohdaten = hole(daten["dist"]["tarball"])
    pruefe_integritaet(rohdaten, daten["dist"].get("integrity"))

    geaendert = []
    with tarfile.open(fileobj=io.BytesIO(rohdaten), mode="r:gz") as archiv:
        for quelle, ziel in paket["dateien"].items():
            eintrag = archiv.extractfile(f"package/{quelle}")
            if eintrag is None:
                raise RuntimeError(f"{quelle} steckt nicht in {paket['npm']}")

            zielpfad = VENDOR / ziel
            vorher = pruefsumme(zielpfad)
            zielpfad.parent.mkdir(parents=True, exist_ok=True)
            with open(zielpfad, "wb") as f:
                shutil.copyfileobj(eintrag, f)

            nachher = pruefsumme(zielpfad)
            if vorher != nachher:
                geaendert.append(ziel)

    return geaendert


def aktualisieren(liste):
    insgesamt = []
    for paket in liste["pakete"]:
        print(f"  {paket['name']} {paket['version']} …", end=" ", flush=True)
        try:
            geaendert = hole_paket(paket)
        except Exception as fehler:
            print(f"FEHLER: {fehler}")
            return False
        print(("geändert: " + ", ".join(geaendert)) if geaendert else "unverändert")
        insgesamt += geaendert

    if insgesamt:
        print(f"\n{len(insgesamt)} Datei(en) ersetzt. Jetzt bitte:")
        print("  pytest")
        print("  python app.py   und die Seiten im Browser ansehen")
    else:
        print("\nAlles war schon auf dem Stand aus versionen.json.")
    return True


def setzen(liste, angaben):
    """Trägt neue Fassungen in versionen.json ein."""
    bekannt = {p["npm"]: p for p in liste["pakete"]}
    kurz = {p["npm"].split("/")[-1]: p for p in liste["pakete"]}

    for angabe in angaben:
        if "=" not in angabe:
            print(f"FEHLER: '{angabe}' sieht nicht aus wie paket=version")
            return False
        name, version = angabe.split("=", 1)
        paket = bekannt.get(name) or kurz.get(name)
        if paket is None:
            print(f"FEHLER: '{name}' steht nicht in versionen.json")
            print("        bekannt sind: " + ", ".join(sorted(kurz)))
            return False
        print(f"  {paket['name']}: {paket['version']} -> {version}")
        paket["version"] = version

    schreibe_liste(liste)
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Holt die Frontend-Bibliotheken nach static/vendor/.")
    parser.add_argument("--pruefen", action="store_true",
                        help="nur nachsehen, ob es neuere Fassungen gibt")
    parser.add_argument("--setzen", nargs="+", metavar="PAKET=VERSION",
                        help="neue Fassung eintragen und holen")
    argumente = parser.parse_args()

    liste = lade_liste()

    if argumente.pruefen:
        print("Vergleich mit der npm-Registry:\n")
        pruefen(liste)
        return 0

    if argumente.setzen:
        print("Neue Fassungen eintragen:\n")
        if not setzen(liste, argumente.setzen):
            return 1
        print()

    print(f"Dateien holen nach {VENDOR.relative_to(WURZEL)}:\n")
    return 0 if aktualisieren(liste) else 1


if __name__ == "__main__":
    sys.exit(main())
