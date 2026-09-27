"""Welcher Stand der Plattform läuft - aus git oder aus der stand.txt eines ZIPs.

git wird dabei nicht wirklich gefragt: Eine Attrappe steht für
subprocess.run und antwortet, was git geantwortet hätte.
"""

import ast
import subprocess
import types
from pathlib import Path

import pytest

import stand
import starter

ROOT = Path(__file__).resolve().parent.parent


def antwort(stdout="", returncode=0):
    return types.SimpleNamespace(returncode=returncode, stdout=stdout, stderr="")


class Git:
    """Antwortet auf describe und log wie git, merkt sich die Befehle."""

    def __init__(self, beschreibung=None, datum=None):
        self.antworten = {"describe": beschreibung, "log": datum}
        self.befehle = []

    def __call__(self, befehl, **_):
        self.befehle.append(befehl)
        wert = self.antworten[befehl[1]]
        return antwort(wert + "\n") if wert else antwort(returncode=128)


@pytest.fixture
def git_ordner(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr(stand.shutil, "which", lambda _: "/usr/bin/git")
    return tmp_path


def stand_datei(ordner, beschreibung, datum):
    (ordner / "stand.txt").write_text(
        f"# Kommentar: bleibt außen vor\nbeschreibung: {beschreibung}\ndatum: {datum}\n",
        encoding="utf-8",
    )


class TestLesbar:
    def test_genau_ein_release(self):
        assert stand.lesbar("v1.5.1", "2026-09-27") == "1.5.1 (Stand 27.09.2026)"

    def test_aenderungen_nach_dem_release(self):
        assert stand.lesbar("v1.5.1-3-g87d9a11", "2026-09-30") == (
            "1.5.1 + 3 Änderungen (Stand 30.09.2026)"
        )

    def test_eine_aenderung_in_der_einzahl(self):
        assert stand.lesbar("v1.5.1-1-g87d9a11", "2026-09-28") == (
            "1.5.1 + 1 Änderung (Stand 28.09.2026)"
        )

    def test_ohne_datum(self):
        assert stand.lesbar("v1.5.1", None) == "1.5.1"

    def test_ohne_tag_bleibt_das_datum(self):
        # Etwa ein git clone mit --depth 1: Die Tags fehlen, der Commit nicht.
        assert stand.lesbar(None, "2026-09-27") == "Stand 27.09.2026"

    def test_nichts_bekannt(self):
        assert stand.lesbar(None, None) == "unbekannt"

    def test_fremde_beschreibung_wird_nicht_ausgegeben(self):
        assert stand.lesbar("irgendwas", "gestern") == "unbekannt"


class TestGit:
    def test_git_installation(self, git_ordner):
        git = Git("v1.5.1-2-gabc1234", "2026-09-29")
        assert stand.ermitteln(git_ordner, git) == "1.5.1 + 2 Änderungen (Stand 29.09.2026)"
        # Nur Release-Tags zählen, und auch die, die GitHub ohne Anmerkung anlegt.
        assert git.befehle[0] == ["git", "describe", "--tags", "--match", "v[0-9]*"]

    def test_ohne_git_ordner_wird_git_nicht_gefragt(self, tmp_path):
        git = Git("v1.5.1", "2026-09-27")
        assert stand.ermitteln(tmp_path, git) == "unbekannt"
        assert git.befehle == []

    def test_ohne_git_programm(self, git_ordner, monkeypatch):
        monkeypatch.setattr(stand.shutil, "which", lambda _: None)
        git = Git("v1.5.1", "2026-09-27")
        assert stand.ermitteln(git_ordner, git) == "unbekannt"
        assert git.befehle == []

    def test_git_scheitert(self, git_ordner):
        def kaputt(befehl, **_):
            raise subprocess.TimeoutExpired(befehl, 10)

        assert stand.ermitteln(git_ordner, kaputt) == "unbekannt"


class TestZip:
    def test_von_github_ausgefuellt(self, tmp_path):
        stand_datei(tmp_path, "v1.5.1", "2026-09-27")
        assert stand.ermitteln(tmp_path) == "1.5.1 (Stand 27.09.2026)"

    def test_platzhalter_zaehlen_nicht(self, tmp_path):
        stand_datei(tmp_path, "$Format:%(describe:tags=true)$", "$Format:%cs$")
        assert stand.ermitteln(tmp_path) == "unbekannt"

    def test_ohne_tag_im_zip(self, tmp_path):
        # GitHub lässt die Beschreibung leer, wenn es keinen Tag davor gibt.
        stand_datei(tmp_path, "", "2026-09-27")
        assert stand.ermitteln(tmp_path) == "Stand 27.09.2026"

    def test_git_ohne_tags_holt_den_rest_nicht_aus_den_platzhaltern(self, git_ordner):
        stand_datei(git_ordner, "$Format:%(describe)$", "$Format:%cs$")
        assert stand.ermitteln(git_ordner, Git(None, "2026-09-27")) == "Stand 27.09.2026"


class TestDateiImRepository:
    def test_platzhalter_und_export_subst(self):
        # Ohne den Eintrag in .gitattributes füllt GitHub nichts aus, und ein
        # ZIP wüsste nie, welcher Stand es ist.
        inhalt = (ROOT / "stand.txt").read_text(encoding="utf-8")
        assert "beschreibung: $Format:%(describe:tags=true,match=v[0-9]*)$" in inhalt
        assert "datum: $Format:%cs$" in inhalt

        zeilen = (ROOT / ".gitattributes").read_text(encoding="utf-8").splitlines()
        assert ["stand.txt", "export-subst"] in [zeile.split() for zeile in zeilen]

    def test_stand_py_laesst_sich_auch_mit_altem_python_lesen(self):
        # Der Starter holt die Datei mit dem Python des Rechners, das auch
        # zu alt sein kann - er muss dann noch sagen können, dass es das ist.
        ast.parse((ROOT / "stand.py").read_text(encoding="utf-8"), feature_version=(3, 7))

    def test_stand_py_braucht_nur_die_standardbibliothek(self):
        baum = ast.parse((ROOT / "stand.py").read_text(encoding="utf-8"))
        oben = {
            name.name.split(".")[0]
            for knoten in baum.body if isinstance(knoten, ast.Import)
            for name in knoten.names
        }
        assert oben <= {"os", "re", "shutil", "subprocess"}


class TestStartuebersicht:
    @pytest.fixture
    def ablauf(self, monkeypatch):
        reihenfolge = []
        monkeypatch.setattr(starter, "version_ermitteln", lambda: "1.5.1 (Stand 27.09.2026)")
        monkeypatch.setattr(starter, "aktualisieren", lambda: reihenfolge.append("pull") or "aktualisiert")
        for schritt in ("umgebung_sicherstellen", "pakete_sicherstellen",
                        "konfiguration_sicherstellen", "datenbank_stand"):
            monkeypatch.setattr(starter, schritt, lambda: "vorhanden")
        monkeypatch.setattr(starter, "starten", lambda browser: 0)
        return reihenfolge

    def test_version_steht_oben(self, ablauf, capsys):
        assert starter.main([]) == 0
        zeilen = capsys.readouterr().out.splitlines()
        assert zeilen[3].startswith("Version ...")
        assert zeilen[3].endswith(" 1.5.1 (Stand 27.09.2026)")
        assert zeilen[4].startswith("Python ")

    def test_nach_dem_update_der_neue_stand(self, ablauf, capsys):
        assert starter.main(["--aktualisieren"]) == 0
        zeilen = capsys.readouterr().out.splitlines()
        namen = [zeile.split(" ")[0] for zeile in zeilen[3:6]]
        assert namen == ["Python", "Aktualisieren", "Version"]
