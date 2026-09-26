"""Der Starter hinter den drei Startdateien.

Geprüft wird jeder Schritt für sich in einem leeren Verzeichnis, ohne
echtes pip und ohne echtes git: Die werden durch eine Attrappe ersetzt, die
nur mitschreibt, was aufgerufen worden wäre.
"""

import ast
import os
import subprocess
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
        assert "3.10" in str(fehler.value)
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
        # installiert ist. network.py wird erst beim Start geholt und ist
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
        assert starter.umgebung_sicherstellen(str(ordner), anlegen=angelegt.append) == "vorhanden"
        assert angelegt == []

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

    def test_vorhandene_env_wird_nie_angefasst(self, ordner):
        (ordner / ".env").write_text("ADMIN_PASSWORD=meins\nSECRET_KEY=abc\n", encoding="utf-8")

        def nicht_fragen():
            raise AssertionError("Bei vorhandener .env wird nicht nach dem Passwort gefragt.")

        assert starter.konfiguration_sicherstellen(str(ordner), passwort_holen=nicht_fragen) == "vorhanden"
        assert (ordner / ".env").read_text(encoding="utf-8") == "ADMIN_PASSWORD=meins\nSECRET_KEY=abc\n"

    def test_platzhalter_aus_der_vorlage_wird_angemahnt(self, ordner):
        (ordner / ".env").write_text(
            (ordner / ".env.example").read_text(encoding="utf-8"), encoding="utf-8"
        )
        stand = starter.konfiguration_sicherstellen(str(ordner), passwort_holen=None)
        assert "Platzhalter" in stand

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
        aufrufe = Aufrufe()

        assert starter.aktualisieren(str(ordner), ausfuehren=aufrufe) == "aktualisiert"
        # Nur vorspulen: Ein Merge könnte Konflikte in den Ordner schreiben.
        assert aufrufe.befehle[-1] == ["git", "pull", "--ff-only"]

    def test_gescheitertes_pull_wird_gemeldet(self, ordner, monkeypatch):
        (ordner / ".git").mkdir()
        monkeypatch.setattr(starter.shutil, "which", lambda _: "/usr/bin/git")
        aufrufe = Aufrufe(ergebnis(), ergebnis(returncode=1))

        with pytest.raises(starter.Abbruch):
            starter.aktualisieren(str(ordner), ausfuehren=aufrufe)

    def test_dateien_mit_nutzerdaten_liegen_nicht_im_repository(self):
        # Darauf verlässt sich das Aktualisieren mit git: Was nicht im
        # Repository liegt, kann ein pull nicht überschreiben.
        ignoriert = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        for eintrag in (".env", "data/*.db", "uploads/", ".venv/"):
            assert eintrag in ignoriert


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
        assert text.index("where py ") < text.index("where python ")

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
