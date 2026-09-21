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


class TestNamenDieManEintippenKann:
    """Was --pruefen anzeigt, muss --setzen auch annehmen.

    Vorher zeigte --pruefen „Font Awesome Free“ an; --setzen nahm nur den
    npm-Namen. Wer die Anzeige abtippte, scheiterte an den Leerzeichen -
    in der PowerShell auch mit Anführungszeichen.
    """

    def werkzeug(self):
        import sys

        sys.path.insert(0, str(WURZEL / "werkzeuge"))
        import vendor_aktualisieren

        return vendor_aktualisieren

    def test_angezeigter_name_enthaelt_keine_leerzeichen(self, liste):
        w = self.werkzeug()
        for paket in liste["pakete"]:
            name = w.schluessel(paket)
            assert " " not in name, f"{name!r} lässt sich nicht eintippen"
            assert name, "leerer Name"

    def test_jeder_angezeigte_name_wird_gefunden(self, liste):
        """Der Kern: Anzeige und Eingabe müssen zusammenpassen."""
        w = self.werkzeug()
        for paket in liste["pakete"]:
            gefunden = w.finde_paket(liste, w.schluessel(paket))
            assert gefunden is paket, f"{w.schluessel(paket)!r} wird nicht gefunden"

    @pytest.mark.parametrize("schreibweise", [
        "fontawesome-free",
        "@fortawesome/fontawesome-free",
        "Font Awesome Free",
        "FONTAWESOME-FREE",
        "fontawesomefree",
    ])
    def test_alle_schreibweisen_finden_dasselbe_paket(self, liste, schreibweise):
        w = self.werkzeug()
        paket = w.finde_paket(liste, schreibweise)

        assert paket is not None, f"{schreibweise!r} wurde nicht gefunden"
        assert paket["name"] == "Font Awesome Free"

    def test_unbekannter_name_wird_nicht_erraten(self, liste):
        w = self.werkzeug()
        assert w.finde_paket(liste, "gibtsnicht") is None

    def test_fehlermeldung_nennt_die_moeglichen_namen(self, liste, capsys):
        w = self.werkzeug()

        assert w.setzen(liste, ["Font Awesome Free"]) is False
        ausgabe = capsys.readouterr().out
        assert "fontawesome-free" in ausgabe
        assert "Leerzeichen" in ausgabe

    def test_eintragen_veraendert_nur_das_gemeinte_paket(self, liste, monkeypatch):
        w = self.werkzeug()
        vorher = {p["name"]: p["version"] for p in liste["pakete"]}

        # Nicht in die echte versionen.json schreiben.
        monkeypatch.setattr(w, "schreibe_liste", lambda _liste: None)
        assert w.setzen(liste, ["fontawesome-free=7.3.1"]) is True

        nachher = {p["name"]: p["version"] for p in liste["pakete"]}
        geaendert = {k for k in vorher if vorher[k] != nachher[k]}
        assert geaendert == {"Font Awesome Free"}
        assert nachher["Font Awesome Free"] == "7.3.1"
