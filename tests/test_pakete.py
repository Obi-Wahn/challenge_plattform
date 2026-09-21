"""Das Werkzeug, das nach neueren Python-Paketen sieht.

Die Fassungen in requirements.txt sind festgenagelt, damit auf dem Schul-PC
genau das läuft, was hier getestet wurde. Der Preis: Niemand sagt einem,
wenn eine Sicherheitskorrektur erschienen ist. Diese Tests prüfen das
Werkzeug, das genau das tut - ohne Internet.
"""

import sys
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL / "werkzeuge"))

import pakete_pruefen as werkzeug  # noqa: E402


class TestZeilenLesen:
    def test_einfache_zeile(self, tmp_path):
        datei = tmp_path / "r.txt"
        datei.write_text("Flask==3.0.0\n", encoding="utf-8")

        assert werkzeug.gepinnte_pakete(datei) == [("Flask", "", "3.0.0", 1)]

    def test_extras_bleiben_erhalten(self, tmp_path):
        datei = tmp_path / "r.txt"
        datei.write_text("qrcode[pil]==8.2\n", encoding="utf-8")

        name, extras, version, _zeile = werkzeug.gepinnte_pakete(datei)[0]
        assert (name, extras, version) == ("qrcode", "[pil]", "8.2")

    def test_kommentare_und_leerzeilen_werden_uebergangen(self, tmp_path):
        datei = tmp_path / "r.txt"
        datei.write_text("# Kommentar\n\nFlask==3.0.0\n\n# noch einer\n",
                         encoding="utf-8")

        assert len(werkzeug.gepinnte_pakete(datei)) == 1

    def test_nicht_gepinnte_zeilen_werden_uebergangen(self, tmp_path):
        """Nur was auf eine feste Fassung genagelt ist, lässt sich vergleichen."""
        datei = tmp_path / "r.txt"
        datei.write_text("Flask>=3.0.0\nrequests\nFlask-WTF==1.2.1\n",
                         encoding="utf-8")

        assert [p[0] for p in werkzeug.gepinnte_pakete(datei)] == ["Flask-WTF"]

    def test_die_echten_dateien_werden_vollstaendig_gelesen(self):
        """Wenn hier etwas fehlt, prüft das Werkzeug es auch nicht."""
        gefunden = set()
        for name in werkzeug.DATEIEN:
            pfad = WURZEL / name
            gefunden.update(p[0] for p in werkzeug.gepinnte_pakete(pfad))

        # Die Pakete, ohne die die Anwendung nicht läuft.
        for pflicht in ["Flask", "Flask-SQLAlchemy", "fpdf2", "waitress", "qrcode"]:
            assert pflicht in gefunden, f"{pflicht} wird nicht geprüft"


class TestVersionenVergleichen:
    @pytest.mark.parametrize("aelter,neuer", [
        ("3.0.0", "3.1.3"),
        ("3.12", "4.1.1"),
        ("1.0.0", "1.0.1"),
        ("3.5.1", "3.10.3"),   # 10 ist größer als 5, nicht kleiner
    ])
    def test_reihenfolge(self, aelter, neuer):
        assert werkzeug.version_teile(neuer) > werkzeug.version_teile(aelter)

    def test_gleiche_fassung_ist_nicht_neuer(self):
        assert not werkzeug.version_teile("3.0.0") > werkzeug.version_teile("3.0.0")

    @pytest.mark.parametrize("version", ["4.0.0a1", "2.1.0b2", "5.0.0rc1", "1.2.dev3"])
    def test_vorabfassungen_werden_erkannt(self, version):
        assert werkzeug.vorabfassung(version)

    @pytest.mark.parametrize("version", ["3.1.3", "4.1.1", "8.2", "0.16.8"])
    def test_fertige_fassungen_sind_keine_vorabfassungen(self, version):
        assert not werkzeug.vorabfassung(version)


class TestPythonAnforderung:
    """Eine neue Fassung nützt nichts, wenn sie ein neueres Python verlangt."""

    @pytest.mark.parametrize("angabe", [">=3.11", ">=3.12", ">= 3.13"])
    def test_zu_neu_wird_gemeldet(self, angabe):
        assert werkzeug.python_zu_neu(angabe)

    @pytest.mark.parametrize("angabe", [">=3.9", ">=3.10", ">=3.8", ""])
    def test_passendes_python_ist_in_ordnung(self, angabe):
        assert not werkzeug.python_zu_neu(angabe)

    def test_mehrere_bedingungen(self):
        assert werkzeug.python_zu_neu(">=3.12,<4.0")
        assert not werkzeug.python_zu_neu(">=3.10,<4.0")

    def test_die_grenze_passt_zur_anwendung(self):
        """Das Werkzeug muss dieselbe Grenze kennen wie der Start der Anwendung."""
        quelltext = (WURZEL / "app.py").read_text(encoding="utf-8")
        gefordert = ".".join(str(t) for t in werkzeug.MINDEST_PYTHON)
        assert f"Python {gefordert}" in quelltext, \
            "app.py und das Werkzeug nennen verschiedene Python-Fassungen"


class TestFassungEintragen:
    def setzen_in(self, tmp_path, monkeypatch, inhalt, angabe, datei="requirements.txt"):
        (tmp_path / datei).write_text(inhalt, encoding="utf-8")
        monkeypatch.setattr(werkzeug, "WURZEL", tmp_path)
        rueckgabe = werkzeug.setzen(angabe)
        return rueckgabe, (tmp_path / datei).read_text(encoding="utf-8")

    def test_fassung_wird_ersetzt(self, tmp_path, monkeypatch):
        rueckgabe, inhalt = self.setzen_in(
            tmp_path, monkeypatch, "Flask==3.0.0\nWerkzeug==3.0.1\n", "Flask=3.1.3")

        assert rueckgabe == 0
        assert "Flask==3.1.3" in inhalt
        assert "Werkzeug==3.0.1" in inhalt, "ein anderes Paket wurde mitverändert"

    def test_extras_bleiben_stehen(self, tmp_path, monkeypatch):
        _rueckgabe, inhalt = self.setzen_in(
            tmp_path, monkeypatch, "qrcode[pil]==8.2\n", "qrcode=8.3")

        assert "qrcode[pil]==8.3" in inhalt

    def test_schreibweise_des_namens_ist_egal(self, tmp_path, monkeypatch):
        _rueckgabe, inhalt = self.setzen_in(
            tmp_path, monkeypatch, "Flask-WTF==1.2.1\n", "flask-wtf=1.3.0")

        # Die Schreibweise aus der Datei bleibt erhalten.
        assert "Flask-WTF==1.3.0" in inhalt

    def test_kommentare_bleiben_erhalten(self, tmp_path, monkeypatch):
        _rueckgabe, inhalt = self.setzen_in(
            tmp_path, monkeypatch,
            "# Zusätzlich zum Testen\npytest==9.1.1\n", "pytest=9.2.0")

        assert inhalt.startswith("# Zusätzlich zum Testen\n")
        assert "pytest==9.2.0" in inhalt

    def test_unbekanntes_paket_meldet_fehler(self, tmp_path, monkeypatch):
        rueckgabe, inhalt = self.setzen_in(
            tmp_path, monkeypatch, "Flask==3.0.0\n", "GibtsNicht=1.0")

        assert rueckgabe == 1
        assert inhalt == "Flask==3.0.0\n", "die Datei wurde angefasst"

    def test_ohne_gleichheitszeichen_meldet_fehler(self, tmp_path, monkeypatch):
        rueckgabe, _inhalt = self.setzen_in(
            tmp_path, monkeypatch, "Flask==3.0.0\n", "Flask")

        assert rueckgabe == 1


class TestPruefenOhneInternet:
    def test_ein_nicht_erreichbares_pypi_bricht_nicht_ab(self, monkeypatch, capsys):
        """Am Wettbewerbstag ohne Netz darf das Werkzeug nicht mit Absturz enden."""
        import urllib.error

        def kein_netz(name):
            raise urllib.error.URLError("kein Netz")

        monkeypatch.setattr(werkzeug, "pypi_daten", kein_netz)

        assert werkzeug.pruefen() is False
        ausgabe = capsys.readouterr().out
        assert "konnte nicht abgefragt werden" in ausgabe
        assert "Internetverbindung" in ausgabe

    def test_neuere_fassung_wird_gemeldet(self, monkeypatch, capsys):
        def erfunden(name):
            return {"info": {"version": "99.0.0", "requires_python": ">=3.10"}}

        monkeypatch.setattr(werkzeug, "pypi_daten", erfunden)

        assert werkzeug.pruefen() is True
        ausgabe = capsys.readouterr().out
        assert "99.0.0" in ausgabe
        assert "neue Hauptversion" in ausgabe
        assert "--setzen" in ausgabe

    def test_zu_neues_python_wird_gemeldet(self, monkeypatch, capsys):
        def erfunden(name):
            return {"info": {"version": "99.0.0", "requires_python": ">=3.13"}}

        monkeypatch.setattr(werkzeug, "pypi_daten", erfunden)
        werkzeug.pruefen()

        assert "braucht Python" in capsys.readouterr().out

    def test_vorabfassungen_werden_nicht_vorgeschlagen(self, monkeypatch, capsys):
        def erfunden(name):
            return {"info": {"version": "99.0.0a1", "requires_python": ">=3.10"}}

        monkeypatch.setattr(werkzeug, "pypi_daten", erfunden)

        assert werkzeug.pruefen() is False
        assert "99.0.0a1" not in capsys.readouterr().out
