"""Der Starter hinter den drei Startdateien.

Geprüft wird jeder Schritt für sich in einem leeren Verzeichnis, ohne
echtes pip und ohne echtes git: Die werden durch eine Attrappe ersetzt, die
nur mitschreibt, was aufgerufen worden wäre.
"""

import ast
import os
import subprocess
import sys
import types
from pathlib import Path

import pytest
from dotenv import dotenv_values

import starter

ROOT = Path(__file__).resolve().parent.parent


class Aufrufe:
    """Steht für subprocess.run und merkt sich, was aufgerufen wurde."""

    def __init__(self, *ergebnisse):
        self.befehle = []
        self.ergebnisse = list(ergebnisse)

    def __call__(self, befehl, **_):
        self.befehle.append(befehl)
        if self.ergebnisse:
            return self.ergebnisse.pop(0)
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")


def ergebnis(returncode=0, stdout="", stderr=""):
    return types.SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


@pytest.fixture
def ordner(tmp_path):
    """Ein Installationsordner mit dem Nötigsten, ohne .env und ohne .venv."""
    (tmp_path / "requirements.txt").write_text("Flask==3.1.3\n", encoding="utf-8")
    (tmp_path / ".env.example").write_text(
        (ROOT / ".env.example").read_text(encoding="utf-8"), encoding="utf-8"
    )
    return tmp_path


def umgebung_vortaeuschen(basis):
    python = Path(starter.umgebungs_python(str(basis)))
    python.parent.mkdir(parents=True)
    python.write_text("")


class TestPython:
    def test_zu_altes_python_wird_verstaendlich_abgelehnt(self):
        with pytest.raises(starter.Abbruch) as fehler:
            starter.python_pruefen((3, 9, 6))
        assert "3.9.6" in str(fehler.value)
        assert "3.11" in str(fehler.value)
        assert "python.org" in str(fehler.value)

    def test_passendes_python_wird_genannt(self):
        assert starter.python_pruefen((3, 13, 1)) == "3.13.1"

    def test_starter_laesst_sich_auch_mit_altem_python_lesen(self):
        # Sonst scheitert ein zu altes Python schon am Lesen der Datei - mit
        # einem SyntaxError statt mit der Meldung, dass es zu alt ist. Der
        # Platzhalter auf dem Mac etwa ist Python 3.9.
        quelle = (ROOT / "starter.py").read_text(encoding="utf-8")
        ast.parse(quelle, feature_version=(3, 7))

    def test_starter_braucht_nur_die_standardbibliothek(self):
        # Er läuft mit dem Python des Rechners, bevor irgendein Paket
        # installiert ist. plattform/network.py wird erst beim Start geholt und ist
        # selbst nur Standardbibliothek.
        baum = ast.parse((ROOT / "starter.py").read_text(encoding="utf-8"))
        oben = {
            name.name.split(".")[0]
            for knoten in baum.body if isinstance(knoten, ast.Import)
            for name in knoten.names
        }
        assert oben <= {
            "argparse", "getpass", "hashlib", "os", "secrets", "shutil", "socket",
            "subprocess", "sys", "threading", "time", "venv", "webbrowser",
        }


class TestUmgebung:
    def test_pfad_unter_windows(self):
        pfad = starter.umgebungs_python("C:\\Plattform", betriebssystem="nt")
        assert pfad.endswith(os.path.join(".venv", "Scripts", "python.exe"))

    def test_pfad_unter_linux_und_mac(self):
        pfad = starter.umgebungs_python("/plattform", betriebssystem="posix")
        assert pfad.endswith(os.path.join(".venv", "bin", "python"))

    def test_vorhandene_umgebung_bleibt(self, ordner):
        umgebung_vortaeuschen(ordner)
        angelegt = []
        stand = starter.umgebung_sicherstellen(
            str(ordner), anlegen=angelegt.append, laeuft=lambda basis: True
        )
        assert stand == "vorhanden"
        assert angelegt == []

    def test_uebersicht_nennt_das_python_der_umgebung(self, ordner):
        # Sonst steht oben "Python 3.14" und niemand sieht, dass die
        # Plattform noch im Python 3.13 läuft, mit dem .venv gebaut wurde.
        umgebung_vortaeuschen(ordner)
        (ordner / ".venv" / "pyvenv.cfg").write_text(
            "home = /usr/bin\ninclude-system-site-packages = false\nversion = 3.13.15\n",
            encoding="utf-8",
        )
        stand = starter.umgebung_sicherstellen(str(ordner), laeuft=lambda basis: True)
        assert stand == "vorhanden (Python 3.13)"

    def test_andere_version_wird_nicht_von_selbst_umgebaut(self, ordner):
        # Neu anlegen braucht Internet - im Schulnetz am Wettbewerbstag
        # wäre danach gar keine Umgebung mehr da.
        umgebung_vortaeuschen(ordner)
        (ordner / ".venv" / "pyvenv.cfg").write_text("version = 3.12.4\n", encoding="utf-8")
        angelegt = []
        starter.umgebung_sicherstellen(
            str(ordner), anlegen=angelegt.append, laeuft=lambda basis: True
        )
        assert angelegt == []

    def test_zu_altes_python_in_der_umgebung_wird_neu_angelegt(self, ordner):
        # Eine .venv mit Python 3.10 von vor der Anhebung läuft zwar, aber
        # Markdown 3.11 lässt sich darin nicht installieren.
        umgebung_vortaeuschen(ordner)
        (ordner / ".venv" / "pyvenv.cfg").write_text("version = 3.10.4\n", encoding="utf-8")
        angelegt = []

        def anlegen(pfad):
            angelegt.append(pfad)
            (ordner / ".venv" / "pyvenv.cfg").write_text("version = 3.14.7\n", encoding="utf-8")

        stand = starter.umgebung_sicherstellen(
            str(ordner), anlegen=anlegen, laeuft=lambda basis: True
        )
        assert angelegt == [os.path.join(str(ordner), ".venv")]
        assert stand == "neu angelegt, die alte hatte Python 3.10 (Python 3.14)"

    @pytest.mark.parametrize("zeile, erwartet", [
        ("version = 3.13.15", "3.13"),
        ("version_info = 3.14.7.final.0", "3.14"),
        ("home = /usr/bin", None),
    ])
    def test_version_aus_pyvenv_cfg(self, ordner, zeile, erwartet):
        (ordner / ".venv").mkdir()
        (ordner / ".venv" / "pyvenv.cfg").write_text(zeile + "\n", encoding="utf-8")
        assert starter.umgebungs_version(str(ordner)) == erwartet

    def test_ohne_umgebung_keine_version(self, ordner):
        assert starter.umgebungs_version(str(ordner)) is None

    def test_umgebung_die_nicht_mehr_laeuft_wird_neu_angelegt(self, ordner):
        # Der Fall nach dem Deinstallieren des alten Pythons: Die Datei in
        # .venv gibt es noch, starten lässt sie sich nicht mehr.
        umgebung_vortaeuschen(ordner)
        angelegt = []

        def anlegen(pfad):
            angelegt.append(pfad)
            (ordner / ".venv" / "pyvenv.cfg").write_text("version = 3.14.7\n", encoding="utf-8")

        stand = starter.umgebung_sicherstellen(
            str(ordner), anlegen=anlegen, laeuft=lambda basis: False
        )
        assert angelegt == [os.path.join(str(ordner), ".venv")]
        assert stand == "neu angelegt, die alte lief nicht mehr (Python 3.14)"

    def test_verknuepfung_ins_leere_wird_neu_angelegt(self, ordner):
        # Unter Linux und macOS ist das Python in .venv eine Verknüpfung.
        # Nach dem Deinstallieren zeigt sie ins Leere.
        python = Path(starter.umgebungs_python(str(ordner)))
        python.parent.mkdir(parents=True)
        try:
            python.symlink_to(ordner / "gibt-es-nicht" / "python3.13")
        except (OSError, NotImplementedError):
            pytest.skip("keine symbolischen Verknüpfungen")

        def anlegen(pfad):
            python.unlink()
            python.write_text("")

        stand = starter.umgebung_sicherstellen(str(ordner), anlegen=anlegen)
        assert stand.startswith("neu angelegt")

    def test_nicht_startbares_python_gilt_als_kaputt(self, ordner):
        # Eine leere Datei ist kein Python - wie ein Verweis auf ein
        # deinstalliertes.
        umgebung_vortaeuschen(ordner)
        assert starter.umgebung_laeuft(str(ordner)) is False

    def test_echtes_python_gilt_als_laufend(self, ordner):
        python = Path(starter.umgebungs_python(str(ordner)))
        python.parent.mkdir(parents=True)
        try:
            python.symlink_to(sys.executable)
        except (OSError, NotImplementedError):
            pytest.skip("keine symbolischen Verknüpfungen")
        assert starter.umgebung_laeuft(str(ordner)) is True

    def test_fehlende_umgebung_wird_angelegt(self, ordner):
        def anlegen(pfad):
            umgebung_vortaeuschen(ordner)

        assert starter.umgebung_sicherstellen(str(ordner), anlegen=anlegen) == "angelegt"

    def test_gescheitertes_anlegen_hinterlaesst_nichts_halbes(self, ordner):
        def anlegen(pfad):
            os.makedirs(pfad)
            raise subprocess.CalledProcessError(1, "ensurepip")

        with pytest.raises(starter.Abbruch):
            starter.umgebung_sicherstellen(str(ordner), anlegen=anlegen)
        # Sonst hielte der nächste Start die leere Hülle für fertig.
        assert not (ordner / ".venv").exists()


class TestPakete:
    def test_erster_start_installiert(self, ordner):
        umgebung_vortaeuschen(ordner)
        aufrufe = Aufrufe()

        assert starter.pakete_sicherstellen(str(ordner), ausfuehren=aufrufe) == "installiert"
        befehl = aufrufe.befehle[0]
        assert befehl[0] == starter.umgebungs_python(str(ordner))
        assert befehl[1:4] == ["-m", "pip", "install"]
        assert befehl[-1] == os.path.join(str(ordner), "requirements.txt")

    def test_zweiter_start_installiert_nicht_noch_einmal(self, ordner):
        umgebung_vortaeuschen(ordner)
        aufrufe = Aufrufe()
        starter.pakete_sicherstellen(str(ordner), ausfuehren=aufrufe)

        assert starter.pakete_sicherstellen(str(ordner), ausfuehren=aufrufe) == "aktuell"
        assert len(aufrufe.befehle) == 1

    def test_geaenderte_requirements_werden_nachinstalliert(self, ordner):
        # Der Fall nach einem Update: neue Paketfassungen.
        umgebung_vortaeuschen(ordner)
        aufrufe = Aufrufe()
        starter.pakete_sicherstellen(str(ordner), ausfuehren=aufrufe)
        (ordner / "requirements.txt").write_text("Flask==3.2.0\n", encoding="utf-8")

        assert starter.pakete_sicherstellen(str(ordner), ausfuehren=aufrufe) == "installiert"
        assert len(aufrufe.befehle) == 2

    def test_gescheiterte_installation_wird_beim_naechsten_mal_wiederholt(self, ordner):
        umgebung_vortaeuschen(ordner)
        aufrufe = Aufrufe(ergebnis(returncode=1))

        with pytest.raises(starter.Abbruch) as fehler:
            starter.pakete_sicherstellen(str(ordner), ausfuehren=aufrufe)
        assert "Internet" in str(fehler.value)

        assert starter.pakete_sicherstellen(str(ordner), ausfuehren=aufrufe) == "installiert"
        assert len(aufrufe.befehle) == 2


class TestKonfiguration:
    def test_fehlende_env_wird_angelegt(self, ordner):
        stand = starter.konfiguration_sicherstellen(
            str(ordner), passwort_holen=lambda: "Sommerfest2026"
        )

        assert stand == "angelegt"
        werte = dotenv_values(ordner / ".env")
        assert werte["ADMIN_PASSWORD"] == "Sommerfest2026"
        assert len(werte["SECRET_KEY"]) == 64
        assert werte["SECRET_KEY"] not in starter.PLATZHALTER
        # Der Rest der Vorlage bleibt samt Erklärungen stehen.
        assert "LAN_ADRESSE" in (ordner / ".env").read_text(encoding="utf-8")
        assert werte["FLASK_DEBUG"] == "false"

    @pytest.mark.parametrize("passwort", [
        "mit Leerzeichen", "dollar$HOME", "raute#drin",
        'an"führung', "back\\slash", "ümläüt",
    ])
    def test_passwort_kommt_bei_der_anwendung_so_an_wie_getippt(self, ordner, passwort):
        starter.konfiguration_sicherstellen(str(ordner), passwort_holen=lambda: passwort)
        assert dotenv_values(ordner / ".env")["ADMIN_PASSWORD"] == passwort

    def test_jede_installation_bekommt_einen_eigenen_schluessel(self, tmp_path, ordner):
        zweiter = tmp_path / "zweiter"
        zweiter.mkdir()
        (zweiter / ".env.example").write_text(
            (ordner / ".env.example").read_text(encoding="utf-8"), encoding="utf-8"
        )
        starter.konfiguration_sicherstellen(str(ordner), passwort_holen=lambda: "a")
        starter.konfiguration_sicherstellen(str(zweiter), passwort_holen=lambda: "a")

        assert (dotenv_values(ordner / ".env")["SECRET_KEY"]
                != dotenv_values(zweiter / ".env")["SECRET_KEY"])

    def test_vorhandene_env_mit_eigenen_werten_bleibt_unberuehrt(self, ordner):
        inhalt = f"ADMIN_PASSWORD=meins\nSECRET_KEY={'k' * 40}\n"
        (ordner / ".env").write_text(inhalt, encoding="utf-8")

        def nicht_fragen():
            raise AssertionError("Bei eigenem Passwort wird nicht nach dem Passwort gefragt.")

        assert starter.konfiguration_sicherstellen(str(ordner), passwort_holen=nicht_fragen) == "vorhanden"
        assert (ordner / ".env").read_text(encoding="utf-8") == inhalt


class TestBeispielwerteErsetzen:
    """Beispielwerte und kurze Schlüssel in einer vorhandenen .env.

    Mit einem bekannten SECRET_KEY kann sich jeder ein Cookie als Lehrkraft
    unterschreiben. Der Starter ersetzt ihn deshalb selbst, beim Passwort
    fragt er nach.
    """

    def env(self, ordner, inhalt):
        (ordner / ".env").write_text(inhalt, encoding="utf-8")
        return ordner / ".env"

    def test_vorlage_unveraendert_kopiert(self, ordner, monkeypatch):
        monkeypatch.delenv("SECRET_KEY", raising=False)
        monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
        vorlage = (ordner / ".env.example").read_text(encoding="utf-8")
        datei = self.env(ordner, vorlage)

        stand = starter.konfiguration_sicherstellen(
            str(ordner), passwort_holen=lambda: "Sommerfest2026")

        werte = dotenv_values(datei)
        assert len(werte["SECRET_KEY"]) == 64
        assert werte["ADMIN_PASSWORD"] == "Sommerfest2026"
        assert "neuer Schlüssel" in stand and "neues Admin-Passwort" in stand
        # Die Erklärungen der Vorlage bleiben stehen.
        assert "LAN_ADRESSE" in datei.read_text(encoding="utf-8")
        assert werte["FLASK_DEBUG"] == "false"

    @pytest.mark.parametrize("schluessel", [
        "change-this-in-production-random-string", "dein-geheimer-schluessel",
        "geheim", "",
    ])
    def test_schwacher_schluessel_wird_ohne_rueckfrage_ersetzt(self, ordner, monkeypatch, schluessel):
        monkeypatch.delenv("SECRET_KEY", raising=False)
        monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
        datei = self.env(ordner, f"# meine Notiz\nSECRET_KEY={schluessel}\nADMIN_PASSWORD='meins'\nPORT=8002\n")

        def nicht_fragen():
            raise AssertionError("Das Passwort ist in Ordnung, gefragt wird nicht.")

        stand = starter.konfiguration_sicherstellen(str(ordner), passwort_holen=nicht_fragen)

        werte = dotenv_values(datei)
        assert len(werte["SECRET_KEY"]) == 64
        assert werte["ADMIN_PASSWORD"] == "meins"
        assert werte["PORT"] == "8002"
        assert datei.read_text(encoding="utf-8").startswith("# meine Notiz\n")
        assert stand == "vorhanden, neuer Schlüssel (Teams melden sich einmal neu an)"

    def test_fehlender_schluessel_kommt_dazu(self, ordner, monkeypatch):
        monkeypatch.delenv("SECRET_KEY", raising=False)
        monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
        datei = self.env(ordner, "ADMIN_PASSWORD=meins\n")
        starter.konfiguration_sicherstellen(str(ordner), passwort_holen=None)
        assert len(dotenv_values(datei)["SECRET_KEY"]) == 64

    def test_doppelter_eintrag_wird_ueberall_ersetzt(self, ordner, monkeypatch):
        # python-dotenv nimmt den letzten - der darf nicht der alte bleiben.
        monkeypatch.delenv("SECRET_KEY", raising=False)
        monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
        datei = self.env(ordner, "SECRET_KEY=kurz\nADMIN_PASSWORD=meins\nSECRET_KEY=auch-kurz\n")
        starter.konfiguration_sicherstellen(str(ordner), passwort_holen=None)
        text = datei.read_text(encoding="utf-8")
        assert "kurz" not in text
        assert len(dotenv_values(datei)["SECRET_KEY"]) == 64

    def test_beispielpasswort_aus_der_readme_wird_erfragt(self, ordner, monkeypatch):
        monkeypatch.delenv("SECRET_KEY", raising=False)
        monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
        schluessel = "s" * 64
        datei = self.env(ordner, f"SECRET_KEY={schluessel}\nADMIN_PASSWORD=dein-sicheres-passwort\n")

        stand = starter.konfiguration_sicherstellen(str(ordner), passwort_holen=lambda: "o$ter#hase")

        werte = dotenv_values(datei)
        assert werte["ADMIN_PASSWORD"] == "o$ter#hase"
        assert werte["SECRET_KEY"] == schluessel
        assert stand == "vorhanden, neues Admin-Passwort"

    def test_werte_aus_der_umgebung_bleiben_unberuehrt(self, ordner, monkeypatch):
        # Was der Rechner selbst setzt, gilt vor der .env - die Datei zu
        # ändern hätte keine Wirkung, die Rückfrage nur Verwirrung.
        monkeypatch.setenv("SECRET_KEY", "x" * 64)
        monkeypatch.setenv("ADMIN_PASSWORD", "aus-dem-dienst")
        inhalt = "SECRET_KEY=kurz\n"
        datei = self.env(ordner, inhalt)
        assert starter.konfiguration_sicherstellen(str(ordner), passwort_holen=None) == "vorhanden"
        assert datei.read_text(encoding="utf-8") == inhalt

    def test_env_mit_bom_aus_dem_windows_editor(self, ordner, monkeypatch):
        monkeypatch.delenv("SECRET_KEY", raising=False)
        monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
        datei = ordner / ".env"
        datei.write_bytes("SECRET_KEY=kurz\nADMIN_PASSWORD=meins\n".encode("utf-8-sig"))
        starter.konfiguration_sicherstellen(str(ordner), passwort_holen=None)
        text = datei.read_text(encoding="utf-8")
        assert text.count("SECRET_KEY=") == 1
        assert len(dotenv_values(datei)["SECRET_KEY"]) == 64

    @pytest.mark.skipif(os.name == "nt", reason="Dateirechte gibt es so nur unter Linux und macOS")
    def test_geaenderte_env_ist_nur_fuer_den_besitzer_lesbar(self, ordner, monkeypatch):
        monkeypatch.delenv("SECRET_KEY", raising=False)
        monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
        datei = self.env(ordner, "SECRET_KEY=kurz\nADMIN_PASSWORD=meins\n")
        datei.chmod(0o644)
        starter.konfiguration_sicherstellen(str(ordner), passwort_holen=None)
        assert datei.stat().st_mode & 0o777 == 0o600

    def test_beispielwerte_wie_in_config(self):
        # starter.py kann plattform/config.py nicht laden, deshalb steht die Liste
        # zweimal. Sie darf nicht auseinanderlaufen.
        from plattform import config
        assert starter.PLATZHALTER == config.PLATZHALTER
        assert starter.MIN_SCHLUESSEL == config.MIN_SCHLUESSEL

    def test_beispielwerte_aus_vorlage_und_anleitung_sind_erfasst(self):
        root = Path(starter.__file__).parent
        vorlage = dotenv_values(root / ".env.example")
        assert vorlage["SECRET_KEY"] in starter.PLATZHALTER
        assert vorlage["ADMIN_PASSWORD"] in starter.PLATZHALTER
        texte = [(root / "README.md").read_text(encoding="utf-8"),
                 (root / "docs" / "ENTWICKLUNG.md").read_text(encoding="utf-8")]
        assert any("SECRET_KEY=" in text for text in texte)
        for zeile in "\n".join(texte).splitlines():
            zeile = zeile.strip()
            if zeile.startswith(("SECRET_KEY=", "ADMIN_PASSWORD=")):
                assert zeile.split("=", 1)[1] in starter.PLATZHALTER, zeile

    def test_anlass_steht_vor_der_frage(self, capsys):
        eingaben = iter(["neu", "neu"])
        starter.passwort_erfragen(eingabe=lambda _: next(eingaben), anlass=starter.BEISPIEL_PASSWORT)
        assert "Beispielwert" in capsys.readouterr().out


class TestPasswortAbfrage:
    def test_passwort_wird_zweimal_abgefragt_bis_es_passt(self, capsys):
        eingaben = iter(["", "eins", "zwei", "o'brien", "a${B}", "richtig", "richtig"])
        assert starter.passwort_erfragen(eingabe=lambda _: next(eingaben)) == "richtig"
        ausgabe = capsys.readouterr().out
        assert "nicht leer" in ausgabe
        assert "nicht überein" in ausgabe
        assert ausgabe.count("ohne ' und ohne ${") == 2


class TestAktualisieren:
    def test_zip_installation_bekommt_die_anleitung(self, ordner):
        aufrufe = Aufrufe()
        with pytest.raises(starter.Abbruch) as fehler:
            starter.aktualisieren(str(ordner), ausfuehren=aufrufe)

        text = str(fehler.value)
        for muss_hinueber in ("data/", "uploads/", ".env"):
            assert muss_hinueber in text
        assert aufrufe.befehle == []

    def test_eigene_aenderungen_verhindern_das_aktualisieren(self, ordner, monkeypatch):
        (ordner / ".git").mkdir()
        monkeypatch.setattr(starter.shutil, "which", lambda _: "/usr/bin/git")
        aufrufe = Aufrufe(ergebnis(stdout=" M templates/index.html\n"))

        with pytest.raises(starter.Abbruch) as fehler:
            starter.aktualisieren(str(ordner), ausfuehren=aufrufe)
        assert "templates/index.html" in str(fehler.value)
        assert not any("pull" in befehl for befehl in aufrufe.befehle)

    def test_saubere_git_installation_wird_vorgespult(self, ordner, monkeypatch):
        (ordner / ".git").mkdir()
        monkeypatch.setattr(starter.shutil, "which", lambda _: "/usr/bin/git")
        aufrufe = Aufrufe(
            ergebnis(), ergebnis(stdout="alt\n"), ergebnis(), ergebnis(stdout="neu\n"),
        )

        assert starter.aktualisieren(str(ordner), ausfuehren=aufrufe) == "aktualisiert"
        # Nur vorspulen: Ein Merge könnte Konflikte in den Ordner schreiben.
        assert ["git", "pull", "--ff-only"] in aufrufe.befehle

    def test_ohne_neue_fassung_heisst_es_schon_aktuell(self, ordner, monkeypatch):
        # Sonst stünde "aktualisiert" direkt unter "Already up to date.".
        (ordner / ".git").mkdir()
        monkeypatch.setattr(starter.shutil, "which", lambda _: "/usr/bin/git")
        aufrufe = Aufrufe(
            ergebnis(), ergebnis(stdout="gleich\n"), ergebnis(), ergebnis(stdout="gleich\n"),
        )

        assert starter.aktualisieren(str(ordner), ausfuehren=aufrufe) == "schon aktuell"

    def test_unbekannter_stand_gilt_als_aktualisiert(self, ordner, monkeypatch):
        (ordner / ".git").mkdir()
        monkeypatch.setattr(starter.shutil, "which", lambda _: "/usr/bin/git")
        aufrufe = Aufrufe(
            ergebnis(), ergebnis(returncode=128), ergebnis(), ergebnis(returncode=128),
        )

        assert starter.aktualisieren(str(ordner), ausfuehren=aufrufe) == "aktualisiert"

    def test_gescheitertes_pull_wird_gemeldet(self, ordner, monkeypatch):
        (ordner / ".git").mkdir()
        monkeypatch.setattr(starter.shutil, "which", lambda _: "/usr/bin/git")
        aufrufe = Aufrufe(ergebnis(), ergebnis(stdout="alt\n"), ergebnis(returncode=1))

        with pytest.raises(starter.Abbruch):
            starter.aktualisieren(str(ordner), ausfuehren=aufrufe)

    def test_dateien_mit_nutzerdaten_liegen_nicht_im_repository(self):
        # Darauf verlässt sich das Aktualisieren mit git: Was nicht im
        # Repository liegt, kann ein pull nicht überschreiben.
        ignoriert = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        for eintrag in (".env", "data/*.db", "uploads/", ".venv/"):
            assert eintrag in ignoriert


class Prozess:
    """Steht für subprocess.Popen und merkt sich den Befehl."""

    def __init__(self, code=0, unterbrochen=False):
        self.code = code
        self.unterbrochen = unterbrochen
        self.befehl = None
        self.cwd = None

    def __call__(self, befehl, cwd=None):
        self.befehl, self.cwd = befehl, cwd
        return self

    def wait(self):
        if self.unterbrochen:
            self.unterbrochen = False
            raise KeyboardInterrupt
        return self.code


class TestNachDemAktualisieren:
    """Nach einem Update übernimmt die neue Fassung von starter.py."""

    @pytest.fixture
    def schritte(self, monkeypatch):
        gelaufen = []
        for name in ("umgebung_sicherstellen", "pakete_sicherstellen",
                     "konfiguration_sicherstellen", "datenbank_stand", "version_ermitteln"):
            monkeypatch.setattr(starter, name, lambda name=name: gelaufen.append(name) or "ok")
        monkeypatch.setattr(starter, "starten", lambda browser: gelaufen.append("starten") or 0)
        return gelaufen

    def test_neue_fassung_startet_statt_der_alten(self, monkeypatch, schritte):
        neu = []
        monkeypatch.setattr(starter, "aktualisieren", lambda: "aktualisiert")
        monkeypatch.setattr(starter, "neu_starten", lambda browser: neu.append(browser) or 0)

        assert starter.main(["--aktualisieren", "--ohne-browser"]) == 0
        assert neu == [False]
        assert schritte == []

    def test_ohne_neue_fassung_geht_es_gleich_weiter(self, monkeypatch, schritte):
        monkeypatch.setattr(starter, "aktualisieren", lambda: "schon aktuell")
        monkeypatch.setattr(starter, "neu_starten", lambda browser: pytest.fail("kein Neustart"))

        assert starter.main(["--aktualisieren"]) == 0
        assert schritte[-1] == "starten"

    def test_neustart_ohne_erneutes_aktualisieren(self, ordner):
        prozess = Prozess()
        assert starter.neu_starten(str(ordner), starten_mit=prozess) == 0
        assert prozess.befehl == [sys.executable, os.path.join(str(ordner), "starter.py")]
        assert prozess.cwd == str(ordner)

    def test_ohne_browser_bleibt_ohne_browser(self, ordner):
        prozess = Prozess()
        starter.neu_starten(str(ordner), browser=False, starten_mit=prozess)
        assert prozess.befehl[-1] == "--ohne-browser"

    def test_fehler_der_neuen_fassung_kommt_durch(self, ordner):
        # Die Startdatei hält das Fenster dann offen, damit man die Meldung liest.
        assert starter.neu_starten(str(ordner), starten_mit=Prozess(code=1)) == 1

    def test_strg_c_beendet_ohne_fehler(self, ordner):
        # Die neue Fassung beendet die Plattform selbst; die alte wartet
        # nur darauf und meldet keinen Abbruch.
        prozess = Prozess(unterbrochen=True)
        assert starter.neu_starten(str(ordner), starten_mit=prozess) == 0


class TestStart:
    def test_port_kommt_aus_der_env(self, ordner, monkeypatch):
        monkeypatch.delenv("PORT", raising=False)
        (ordner / ".env").write_text("PORT='8002'\n", encoding="utf-8")
        assert starter.port_ermitteln(str(ordner)) == 8002
        # Die Umgebung des Starters bleibt, wie sie war.
        assert "PORT" not in os.environ

    def test_ohne_eintrag_bleibt_es_bei_8000(self, ordner, monkeypatch):
        monkeypatch.delenv("PORT", raising=False)
        assert starter.port_ermitteln(str(ordner)) == 8000

    def test_belegter_port_wird_erklaert_statt_zu_scheitern(self, ordner, monkeypatch):
        monkeypatch.setattr(starter, "port_ermitteln", lambda basis: 8000)
        monkeypatch.setattr(starter, "port_belegt", lambda port: True)
        gestartet = []
        monkeypatch.setattr(starter.subprocess, "Popen", lambda *a, **k: gestartet.append(a))

        with pytest.raises(starter.Abbruch) as fehler:
            starter.starten(str(ordner))
        assert "8000" in str(fehler.value)
        assert gestartet == []

    def test_browser_geht_auf_sobald_der_server_antwortet(self, monkeypatch):
        geoeffnet = []
        antworten = iter([False, False, True])
        monkeypatch.setattr(starter, "port_belegt", lambda port: next(antworten))
        monkeypatch.setattr(starter.time, "sleep", lambda _: None)
        monkeypatch.setattr(starter.webbrowser, "open", geoeffnet.append)
        server = types.SimpleNamespace(poll=lambda: None)

        faeden = []
        monkeypatch.setattr(
            starter.threading, "Thread",
            lambda target, daemon: faeden.append(target) or types.SimpleNamespace(start=lambda: None),
        )
        starter.browser_oeffnen_wenn_bereit(8000, server)
        faeden[0]()

        assert geoeffnet == ["http://localhost:8000"]

    def test_kein_browser_wenn_der_server_vorher_abstuerzt(self, monkeypatch):
        geoeffnet = []
        monkeypatch.setattr(starter, "port_belegt", lambda port: False)
        monkeypatch.setattr(starter.webbrowser, "open", geoeffnet.append)
        server = types.SimpleNamespace(poll=lambda: 1)

        faeden = []
        monkeypatch.setattr(
            starter.threading, "Thread",
            lambda target, daemon: faeden.append(target) or types.SimpleNamespace(start=lambda: None),
        )
        starter.browser_oeffnen_wenn_bereit(8000, server)
        faeden[0]()

        assert geoeffnet == []


class TestStartdateien:
    """Die drei Brücken: klein, und alle rufen denselben Starter."""

    @pytest.mark.parametrize("name", ["start_windows.bat", "start_macos.command", "start_linux.sh"])
    def test_ruft_den_starter_mit_allen_argumenten(self, name):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "starter.py" in text
        assert ("%*" if name.endswith(".bat") else '"$@"') in text

    @pytest.mark.parametrize("name", ["start_windows.bat", "start_macos.command", "start_linux.sh"])
    def test_arbeitet_im_eigenen_ordner(self, name):
        # Per Doppelklick ist das Arbeitsverzeichnis sonst irgendwo.
        text = (ROOT / name).read_text(encoding="utf-8")
        assert ('cd /d "%~dp0"' if name.endswith(".bat") else 'cd "$(dirname "$0")"') in text

    def test_windows_datei_kommt_ohne_umlaute_aus(self):
        # Die Eingabeaufforderung liest die Datei in ihrer eigenen Codepage.
        (ROOT / "start_windows.bat").read_bytes().decode("ascii")

    def test_windows_datei_nimmt_zuerst_den_py_starter(self):
        text = (ROOT / "start_windows.bat").read_text(encoding="utf-8")
        assert text.index("py -3 -c ") < text.index("python -c ") < text.index("python3 -c ")

    def test_windows_datei_probiert_python_wirklich_aus(self):
        # "where py" fand bei Tobias ein py, das cmd dann nicht starten konnte.
        text = (ROOT / "start_windows.bat").read_text(encoding="utf-8")
        assert "where " not in text
        for kandidat in ("py -3", "python", "python3"):
            assert f'{kandidat} -c "pass" >nul 2>nul && set "PYTHON={kandidat}"' in text

    @pytest.mark.parametrize("name", ["start_macos.command", "start_linux.sh"])
    def test_unix_dateien_sind_reines_sh(self, name):
        # Kein bash: Auf dem Mac ist bash veraltet, anderswo fehlt es.
        assert (ROOT / name).read_text(encoding="utf-8").startswith("#!/bin/sh\n")

    @pytest.mark.parametrize("name", ["start_macos.command", "start_linux.sh"])
    def test_unix_dateien_sind_ausfuehrbar_eingecheckt(self, name):
        modus = subprocess.run(
            ["git", "ls-files", "-s", name], cwd=ROOT, capture_output=True, text=True
        ).stdout
        if not modus:
            pytest.skip("nicht in einem git-Checkout")
        assert modus.startswith("100755")

    @pytest.mark.parametrize("name", ["start_macos.command", "start_linux.sh"])
    def test_unix_dateien_sind_gueltiges_sh(self, name):
        if os.name == "nt":
            pytest.skip("kein sh unter Windows")
        subprocess.run(["sh", "-n", str(ROOT / name)], check=True)

    def test_zeilenenden_sind_festgelegt(self):
        regeln = (ROOT / ".gitattributes").read_text(encoding="utf-8")
        assert "*.bat      text eol=crlf" in regeln
        assert "*.sh       text eol=lf" in regeln
        assert "*.command  text eol=lf" in regeln
