"""Welcher Stand der Plattform läuft - etwa "1.5.1 (Stand 27.09.2026)".

Die Nummer pflegt niemand von Hand, sie kommt aus den Tags vX.Y.Z, die
beim Release angelegt werden. Woher genau, hängt davon ab, wie die
Plattform auf den Rechner kam:

- Mit git geholt: git selbst weiß es (git describe).
- Als ZIP von GitHub: GitHub trägt es beim Packen in stand.txt ein. Die
  Datei ist in .gitattributes mit export-subst markiert, und die
  $Format:...$-Platzhalter darin werden dabei ersetzt. Im Repository
  selbst bleiben sie stehen.

Weiß keiner von beiden etwas, etwa bei einem von Hand kopierten Ordner,
ist der Stand "unbekannt". Der Start läuft trotzdem.

Nur Standardbibliothek und nichts, was ein altes Python nicht lesen kann:
Der Starter holt diese Datei mit dem Python des Rechners.
"""

import os
import re
import shutil
import subprocess

BASIS = os.path.dirname(os.path.abspath(__file__))
STAND_DATEI = "stand.txt"
UNBEKANNT = "unbekannt"

# Nur Release-Tags zählen, falls je ein anderer Tag dazukommt.
TAG_MUSTER = "v[0-9]*"

# "v1.5.1" oder, mit Änderungen nach dem Tag, "v1.5.1-3-g87d9a11".
BESCHREIBUNG = re.compile(r"^v?(\d+(?:\.\d+)*)(?:-(\d+)-g[0-9a-f]+)?$")
DATUM = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


def git_befragen(basis=BASIS, ausfuehren=subprocess.run):
    """Beschreibung und Datum des Commits aus git, oder (None, None)."""
    if not os.path.isdir(os.path.join(basis, ".git")) or shutil.which("git") is None:
        return None, None

    def frage(*befehl):
        try:
            ergebnis = ausfuehren(
                ["git", *befehl], cwd=basis, capture_output=True, text=True, timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if ergebnis.returncode != 0:
            return None
        return ergebnis.stdout.strip() or None

    return (
        frage("describe", "--tags", "--match", TAG_MUSTER),
        frage("log", "-1", "--format=%cs"),
    )


def datei_lesen(basis=BASIS):
    """Beschreibung und Datum aus stand.txt, oder (None, None).

    Stehen dort noch die Platzhalter, ist es kein ZIP von GitHub.
    """
    werte = {}
    try:
        with open(os.path.join(basis, STAND_DATEI), encoding="utf-8") as datei:
            for eintrag in datei:
                if eintrag.startswith("#"):
                    continue
                name, _, wert = eintrag.partition(":")
                wert = wert.strip()
                if wert and "$Format" not in wert:
                    werte[name.strip()] = wert
    except OSError:
        pass
    return werte.get("beschreibung"), werte.get("datum")


def lesbar(beschreibung, datum):
    """Aus "v1.5.1-3-g87d9a11" und "2026-09-30" wird "1.5.1 + 3 Änderungen (Stand 30.09.2026)"."""
    version = None
    treffer = BESCHREIBUNG.match(beschreibung or "")
    if treffer:
        version = treffer.group(1)
        danach = int(treffer.group(2) or 0)
        if danach == 1:
            version += " + 1 Änderung"
        elif danach > 1:
            version += f" + {danach} Änderungen"

    tag = None
    treffer = DATUM.match(datum or "")
    if treffer:
        jahr, monat, tag_im_monat = treffer.groups()
        tag = f"{tag_im_monat}.{monat}.{jahr}"

    if version and tag:
        return f"{version} (Stand {tag})"
    if version:
        return version
    if tag:
        return f"Stand {tag}"
    return UNBEKANNT


def ermitteln(basis=BASIS, ausfuehren=subprocess.run):
    """Der laufende Stand als Text für Übersicht und Protokoll."""
    beschreibung, datum = git_befragen(basis, ausfuehren)
    if beschreibung is None or datum is None:
        aus_datei = datei_lesen(basis)
        beschreibung = beschreibung or aus_datei[0]
        datum = datum or aus_datei[1]
    return lesbar(beschreibung, datum)
