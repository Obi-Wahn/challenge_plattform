#!/usr/bin/env python3
"""Sieht nach, ob es neuere Fassungen der Python-Pakete gibt.

Die Pakete in requirements.txt sind auf feste Fassungen genagelt - so läuft
auf dem Schul-PC genau das, was hier getestet wurde. Der Preis dafür: Sie
aktualisieren sich nicht von selbst, und niemand sagt einem, wenn eine
Sicherheitskorrektur erschienen ist.

    python werkzeuge/pakete_pruefen.py
        Fragt bei PyPI nach und zeigt, wofür es etwas Neueres gibt.
        Ändert nichts.

    python werkzeuge/pakete_pruefen.py --setzen Flask=3.1.3
        Trägt eine Fassung in die requirements-Datei ein, in der das Paket
        steht. Installiert wird danach von Hand:
            pip install -r requirements.txt -r requirements-dev.txt
            pytest

Gemeldet wird auch, wenn eine neue Fassung ein neueres Python verlangt, als
die Anwendung voraussetzt - dann bringt das Aktualisieren nichts, solange
der Schul-PC nicht mitzieht.

Das Skript braucht Internet. Also am heimischen Rechner ausführen, nicht
während eines Wettbewerbs.
"""

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
DATEIEN = ["requirements.txt", "requirements-dev.txt"]
PYPI = "https://pypi.org/pypi"

# Das Python, das die Anwendung voraussetzt. Steht auch in app.py - dort
# bricht der Start darunter ab.
MINDEST_PYTHON = (3, 10)

# "Flask==3.0.0" oder "qrcode[pil]==8.2"
ZEILE = re.compile(r"^([A-Za-z0-9._-]+)(\[[^\]]*\])?==([^\s#]+)")


def gepinnte_pakete(pfad):
    """Die Pakete einer requirements-Datei als (name, extras, version, zeile)."""
    pakete = []
    for nummer, zeile in enumerate(pfad.read_text(encoding="utf-8").splitlines(), 1):
        treffer = ZEILE.match(zeile.strip())
        if treffer:
            pakete.append((treffer.group(1), treffer.group(2) or "",
                           treffer.group(3), nummer))
    return pakete


def pypi_daten(name):
    url = f"{PYPI}/{urllib.parse.quote(name)}/json"
    with urllib.request.urlopen(url, timeout=30) as antwort:
        return json.loads(antwort.read())


def version_teile(version):
    """'3.1.3' -> (3, 1, 3), damit sich Fassungen vergleichen lassen."""
    teile = []
    for stueck in version.split("."):
        ziffern = ""
        for zeichen in stueck:
            if not zeichen.isdigit():
                break
            ziffern += zeichen
        teile.append(int(ziffern) if ziffern else 0)
    return tuple(teile)


def vorabfassung(version):
    """Alpha, Beta, Release Candidate - nichts, was hier laufen soll."""
    return bool(re.search(r"(a|b|rc|dev)\d*$", version))


def python_zu_neu(requires_python):
    """True, wenn die Fassung ein neueres Python verlangt, als wir voraussetzen."""
    if not requires_python:
        return False
    for bedingung in requires_python.split(","):
        treffer = re.match(r"\s*>=\s*([\d.]+)", bedingung)
        if treffer and version_teile(treffer.group(1)) > MINDEST_PYTHON:
            return True
    return False


def pruefen():
    """Zeigt für jedes gepinnte Paket, ob es etwas Neueres gibt."""
    print("Vergleich mit PyPI:\n")
    neueres = []
    fehler = []

    for name_datei in DATEIEN:
        pfad = WURZEL / name_datei
        if not pfad.exists():
            continue

        print(f"  {name_datei}")
        for name, extras, hier, _zeile in gepinnte_pakete(pfad):
            try:
                daten = pypi_daten(name)
                neuste = daten["info"]["version"]
                braucht = daten["info"].get("requires_python") or ""
            except (urllib.error.URLError, KeyError, ValueError) as problem:
                print(f"    {name + extras:<22} konnte nicht abgefragt werden: {problem}")
                fehler.append(name)
                continue

            if vorabfassung(neuste) or version_teile(neuste) <= version_teile(hier):
                print(f"    {name + extras:<22} {hier:>10}      aktuell")
                continue

            hinweise = []
            if version_teile(neuste)[0] > version_teile(hier)[0]:
                hinweise.append("neue Hauptversion - Änderungsliste lesen")
            if python_zu_neu(braucht):
                hinweise.append(f"braucht Python {braucht} - die Anwendung "
                                f"setzt {'.'.join(map(str, MINDEST_PYTHON))} voraus")

            anhang = f"  ({' · '.join(hinweise)})" if hinweise else ""
            print(f"    {name + extras:<22} {hier:>10}  ->  {neuste}{anhang}")
            neueres.append((name, neuste))
        print()

    if fehler:
        print(f"Nicht abgefragt: {', '.join(fehler)} - Internetverbindung prüfen.\n")

    if neueres:
        beispiel_name, beispiel_version = neueres[0]
        print("Zum Übernehmen, eines nach dem anderen:")
        print(f"  python werkzeuge/pakete_pruefen.py --setzen {beispiel_name}={beispiel_version}")
        print("  pip install -r requirements.txt -r requirements-dev.txt")
        print("  pytest")
        print("\nEines nach dem anderen deshalb, weil sich bei einem Fehlschlag "
              "sonst nicht sagen lässt, welches Paket ihn verursacht hat.")
    else:
        print("Alles auf dem neusten Stand.")

    return bool(neueres)


def setzen(angabe):
    """Trägt eine Fassung in die Datei ein, in der das Paket steht."""
    if "=" not in angabe:
        print("Erwartet wird zum Beispiel: --setzen Flask=3.1.3")
        return 1

    name, version = angabe.split("=", 1)
    name, version = name.strip(), version.strip()

    for name_datei in DATEIEN:
        pfad = WURZEL / name_datei
        if not pfad.exists():
            continue

        zeilen = pfad.read_text(encoding="utf-8").splitlines(keepends=True)
        for stelle, zeile in enumerate(zeilen):
            treffer = ZEILE.match(zeile.strip())
            if treffer and treffer.group(1).lower() == name.lower():
                extras = treffer.group(2) or ""
                alt = treffer.group(3)
                zeilen[stelle] = f"{treffer.group(1)}{extras}=={version}\n"
                pfad.write_text("".join(zeilen), encoding="utf-8")
                print(f"{treffer.group(1)}{extras}: {alt} -> {version} ({name_datei})")
                print("\nJetzt installieren und testen:")
                print("  pip install -r requirements.txt -r requirements-dev.txt")
                print("  pytest")
                return 0

    print(f"{name} steht in keiner der Dateien: {', '.join(DATEIEN)}")
    return 1


def main():
    zerleger = argparse.ArgumentParser(
        description="Sieht nach, ob es neuere Fassungen der Python-Pakete gibt."
    )
    zerleger.add_argument("--setzen", metavar="PAKET=FASSUNG",
                          help="Trägt eine Fassung in die requirements-Datei ein.")
    argumente = zerleger.parse_args()

    if argumente.setzen:
        return setzen(argumente.setzen)

    pruefen()
    return 0


if __name__ == "__main__":
    sys.exit(main())
