#!/usr/bin/env python3
"""Holt die Frontend-Bibliotheken nach static/vendor/.

Die Anwendung läuft ohne Internet, deshalb liegen Bootstrap, EasyMDE,
Font Awesome und die Handschriften als Dateien im Repo. Der Preis dafür:
Sie aktualisieren sich nicht von selbst. Dieses Skript nimmt die Handarbeit ab.

    python werkzeuge/vendor_aktualisieren.py
        Sieht nach, ob es neuere Fassungen gibt. Ändert nichts, wie
        pakete_pruefen.py ohne Schalter. --pruefen tut dasselbe.

    python werkzeuge/vendor_aktualisieren.py --holen
        Holt genau die Fassungen, die in static/vendor/versionen.json stehen,
        und ersetzt die Dateien.

    python werkzeuge/vendor_aktualisieren.py --setzen fontawesome-free=7.3.1
        Trägt eine neue Fassung in versionen.json ein und holt sie. Der Name
        ist der kurze aus --pruefen, ohne Leerzeichen.

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


def nur_zeilenenden_anders(pfad, inhalt):
    """Ob die Datei schon so dasteht, höchstens mit CRLF statt LF.

    Git für Windows checkt Textdateien meist mit CRLF aus (core.autocrlf).
    Würde das Werkzeug sie dann mit dem LF aus dem npm-Paket überschreiben,
    hielte git sie für verändert, und die Startdatei verweigerte
    --aktualisieren. Schriften enthalten Nullbytes und werden nie so
    verglichen.
    """
    if not pfad.exists() or b"\0" in inhalt:
        return False
    return pfad.read_bytes().replace(b"\r\n", b"\n") == inhalt.replace(b"\r\n", b"\n")


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


def schluessel(paket):
    """Der Name, den --setzen annimmt.

    Der Anzeigename taugt dafür nicht: „Font Awesome Free“ hat Leerzeichen,
    und in der PowerShell bekommt man das kaum durch die Anführungszeichen.
    """
    return paket["npm"].split("/")[-1]


def pruefen(liste):
    """Sagt, für welche Pakete es eine neuere Fassung gibt.

    Angezeigt wird der Name, den --setzen auch annimmt - sonst liest man
    hier „Font Awesome Free“ und kommt damit dort nicht weiter.
    """
    neueres = False
    vorschlag = None
    nicht_abgefragt = []
    for paket in liste["pakete"]:
        try:
            daten = paketdaten(paket["npm"])
            neuste = daten["dist-tags"]["latest"]
        except (urllib.error.URLError, KeyError, ValueError) as fehler:
            print(f"  {paket['name']:<20} konnte nicht abgefragt werden: {fehler}")
            nicht_abgefragt.append(schluessel(paket))
            continue

        hier = paket["version"]
        name = schluessel(paket)
        if version_teile(neuste) > version_teile(hier):
            neueres = True
            if vorschlag is None:
                vorschlag = f"{name}={neuste}"
            hinweis = "neuere Fassung"
            if version_teile(neuste)[0] > version_teile(hier)[0]:
                hinweis = "neue Hauptversion - Darstellung vorher prüfen"
            print(f"  {name:<22} {hier:>8}  ->  {neuste:<8}  ({hinweis})")
        else:
            print(f"  {name:<22} {hier:>8}      aktuell")

    if nicht_abgefragt:
        print(f"\nNicht abgefragt: {', '.join(nicht_abgefragt)} - "
              "Internetverbindung prüfen.")
    if neueres:
        print("\nZum Übernehmen:")
        print(f"  python werkzeuge/vendor_aktualisieren.py --setzen {vorschlag}")
    elif not nicht_abgefragt:
        print("\nAlles auf dem neusten Stand.")
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
            inhalt = eintrag.read()
            if nur_zeilenenden_anders(zielpfad, inhalt):
                continue

            vorher = pruefsumme(zielpfad)
            zielpfad.parent.mkdir(parents=True, exist_ok=True)
            zielpfad.write_bytes(inhalt)

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


def vergleichsform(text):
    """Klein geschrieben und ohne Leer- und Bindestriche, zum Nachschlagen."""
    return "".join(str(text).lower().split()).replace("-", "")


def finde_paket(liste, name):
    """Sucht ein Paket am npm-Namen, an der Kurzform oder am Anzeigenamen."""
    gesucht = vergleichsform(name)
    for paket in liste["pakete"]:
        moeglich = {paket["npm"], schluessel(paket), paket["name"]}
        if any(vergleichsform(m) == gesucht for m in moeglich):
            return paket
    return None


def setzen(liste, angaben):
    """Trägt neue Fassungen in versionen.json ein."""
    namen = ", ".join(schluessel(p) for p in liste["pakete"])

    for angabe in angaben:
        if "=" not in angabe:
            print(f"FEHLER: '{angabe}' sieht nicht aus wie paket=version")
            # Der haeufigste Grund: der Anzeigename aus --pruefen wurde
            # uebernommen, und die Leerzeichen darin haben die Eingabe
            # zerlegt - in der PowerShell auch trotz Anfuehrungszeichen.
            if " " in angabe:
                print("        Namen mit Leerzeichen gehen schief. Nimm den")
                print(f"        kurzen Namen, zum Beispiel: {namen.split(', ')[0]}=1.2.3")
            print(f"        Möglich sind: {namen}")
            return False

        name, version = angabe.split("=", 1)
        paket = finde_paket(liste, name)
        if paket is None:
            print(f"FEHLER: '{name}' steht nicht in versionen.json")
            print(f"        Möglich sind: {namen}")
            return False

        print(f"  {paket['name']}: {paket['version']} -> {version}")
        paket["version"] = version

    schreibe_liste(liste)
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Sieht nach, ob es neuere Fassungen der Frontend-Bibliotheken "
                    "gibt. Ohne Schalter ändert es nichts.")
    schalter = parser.add_mutually_exclusive_group()
    # Ohne Schalter wird geprüft, wie bei pakete_pruefen.py. --pruefen bleibt
    # für alle, die es so gewohnt sind.
    schalter.add_argument("--pruefen", action="store_true",
                          help="nur nachsehen, ob es neuere Fassungen gibt "
                               "(wie ohne Schalter)")
    schalter.add_argument("--holen", action="store_true",
                          help="die Fassungen aus versionen.json holen")
    schalter.add_argument("--setzen", nargs="+", metavar="PAKET=VERSION",
                          help="neue Fassung eintragen und holen")
    argumente = parser.parse_args()

    liste = lade_liste()

    if argumente.setzen:
        print("Neue Fassungen eintragen:\n")
        if not setzen(liste, argumente.setzen):
            return 1
        print()
    elif not argumente.holen:
        print("Vergleich mit der npm-Registry:\n")
        pruefen(liste)
        return 0

    print(f"Dateien holen nach {VENDOR.relative_to(WURZEL)}:\n")
    return 0 if aktualisieren(liste) else 1


if __name__ == "__main__":
    sys.exit(main())
