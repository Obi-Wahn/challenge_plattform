"""Die Module liegen in plattform/, alles andere findet weiter den Projektordner.

Seit die Module nicht mehr direkt im Projektordner liegen, zeigt __file__ in
ihnen eine Ebene zu tief. Ginge das bei der Datenbank schief, fände die
Anwendung die vorhandene data/challenge.db nicht und legte still eine leere
an - darauf achten diese Tests.
"""

import ast
import os
import subprocess
import sys
from pathlib import Path

from plattform import certificates
from plattform.config import Config

ROOT = Path(__file__).resolve().parent.parent

# Was die Anwendung ohne Angaben in der .env wählt, abgefragt in einem
# eigenen Python: In diesem hier haben die Tests DATABASE_URL und LOG_DIR
# schon auf ein temporäres Verzeichnis gesetzt.
ABFRAGE = (
    "from plattform.config import Config\n"
    "print(Config.SQLALCHEMY_DATABASE_URI)\n"
    "print(Config.UPLOAD_FOLDER)\n"
    "print(Config.LOG_DIR)\n"
)


def importe(pfad):
    baum = ast.parse(pfad.read_text(encoding="utf-8"))
    namen = set()
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.Import):
            namen |= {alias.name.split(".")[0] for alias in knoten.names}
        elif isinstance(knoten, ast.ImportFrom):
            namen.add((knoten.module or "").split(".")[0])
    return namen


class TestPfade:
    def test_basis_ist_der_projektordner(self):
        assert Path(Config.BASE_DIR) == ROOT

    def test_ohne_angaben_liegt_alles_im_projektordner(self, tmp_path):
        umgebung = {
            name: wert for name, wert in os.environ.items()
            if name not in ("DATABASE_URL", "LOG_DIR")
        }
        umgebung["PYTHONPATH"] = str(ROOT)
        # Aus einem anderen Ordner gestartet: Es darf nicht davon abhängen,
        # wo man gerade steht.
        ausgabe = subprocess.run(
            [sys.executable, "-c", ABFRAGE], cwd=tmp_path, env=umgebung,
            capture_output=True, text=True, check=True,
        ).stdout.splitlines()

        assert ausgabe == [
            "sqlite:///" + str(ROOT / "data" / "challenge.db"),
            str(ROOT / "uploads"),
            str(ROOT / "logs"),
        ]

    def test_die_schriften_fuer_die_unterschrift_werden_gefunden(self):
        assert Path(certificates.FONT_DIR) == ROOT / "static" / "vendor" / "fonts"
        for schrift in certificates.SIGNATURE_FONTS.values():
            if schrift["file"]:
                assert (Path(certificates.FONT_DIR) / schrift["file"]).is_file()


class TestStarterLaedtNetwork:
    """starter.py holt plattform.network mit dem Python des Rechners."""

    def test_plattform_init_importiert_nichts(self):
        # Sonst zöge "from plattform.network import ..." alles Weitere nach,
        # bevor Flask und die übrigen Pakete installiert sind.
        assert importe(ROOT / "plattform" / "__init__.py") == set()

    def test_network_braucht_nur_die_standardbibliothek(self):
        assert importe(ROOT / "plattform" / "network.py") <= set(sys.stdlib_module_names)


class TestOrdnung:
    def test_oben_liegen_nur_die_startdateien_als_python(self):
        # Neue Module gehören nach plattform/, damit die Startdateien oben
        # leicht zu finden bleiben. Gefragt wird git, damit eigene Notizen
        # oder Versuche im Ordner nicht stören.
        dateien = subprocess.run(
            ["git", "ls-files", "*.py"], cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout.split()
        assert sorted(name for name in dateien if "/" not in name) == [
            "app.py", "stand.py", "starter.py",
        ]
