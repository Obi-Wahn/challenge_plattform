"""Die mitgelieferten Frontend-Bibliotheken und ihre Versionsliste.

static/vendor/versionen.json hält fest, welche Fassungen im Repo liegen.
Diese Tests sorgen dafür, dass die Liste und der Ordner nicht auseinander
laufen - sonst weiß beim nächsten Sicherheitsupdate niemand mehr, was
eigentlich drin ist. Sie brauchen kein Internet.
"""

import json
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parent.parent
VENDOR = WURZEL / "static" / "vendor"
VERSIONEN = VENDOR / "versionen.json"


@pytest.fixture
def liste():
    with open(VERSIONEN, encoding="utf-8") as f:
        return json.load(f)


def zieldateien(liste):
    for paket in liste["pakete"]:
        for ziel in paket["dateien"].values():
            yield paket, ziel


def test_versionsliste_ist_lesbar(liste):
    assert liste["pakete"], "In versionen.json steht kein Paket"


def test_jedes_paket_hat_name_version_und_lizenz(liste):
    for paket in liste["pakete"]:
        assert paket.get("name"), paket
        assert paket.get("npm"), paket
        assert paket.get("version"), paket
        assert paket.get("lizenz"), f"{paket['name']}: Lizenz fehlt"
        assert paket.get("dateien"), f"{paket['name']}: keine Dateien"


def test_alle_aufgefuehrten_dateien_liegen_auch_da(liste):
    for paket, ziel in zieldateien(liste):
        pfad = VENDOR / ziel
        assert pfad.exists(), f"{paket['name']}: {ziel} fehlt im Ordner"
        assert pfad.stat().st_size > 0, f"{ziel} ist leer"


def test_keine_datei_im_ordner_fehlt_in_der_liste(liste):
    """Sonst liegt etwas im Repo, von dem niemand die Herkunft kennt."""
    aufgefuehrt = {VENDOR / ziel for _paket, ziel in zieldateien(liste)}
    vorhanden = {p for p in VENDOR.rglob("*") if p.is_file() and p != VERSIONEN}

    unbekannt = sorted(str(p.relative_to(VENDOR)) for p in vorhanden - aufgefuehrt)
    assert not unbekannt, (
        "Diese Dateien stehen nicht in versionen.json: " + ", ".join(unbekannt))


def test_die_templates_binden_nur_vorhandene_dateien_ein():
    """Ein Tippfehler im Pfad fiele sonst erst im Browser auf."""
    import re

    templates = WURZEL / "templates"
    muster = re.compile(r"filename='(vendor/[^']+)'")

    fehlend = []
    for datei in templates.rglob("*.html"):
        for treffer in muster.findall(datei.read_text(encoding="utf-8")):
            if not (WURZEL / "static" / treffer).exists():
                fehlend.append(f"{datei.name}: {treffer}")

    assert not fehlend, "Eingebunden, aber nicht vorhanden: " + ", ".join(fehlend)
