"""Hält den Leitfaden an der Anwendung fest.

Ein Handbuch, das Adressen und Dateien nennt, die es nicht mehr gibt, ist
schlimmer als keines: Es schickt einen am Wettbewerbstag in die Irre. Diese
Tests prüfen deshalb die überprüfbaren Angaben - nicht den Rat selbst.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEITFADEN = ROOT / "docs" / "ADMIN_GUIDE.md"


def text():
    return LEITFADEN.read_text(encoding="utf-8")


def genannte_adressen():
    """Alle `/...`-Angaben aus dem Leitfaden, die Seiten der Anwendung sind."""
    # Nur was in Code-Anführung steht, ist als Adresse gemeint.
    roh = re.findall(r"`(/[^`\s]*)`", text())
    # Verzeichnisangaben wie `data/` sind keine Adressen; die beginnen nicht mit /.
    return sorted(set(roh))


class TestAngaben:
    def test_leitfaden_existiert_und_ist_nicht_leer(self):
        assert LEITFADEN.exists()
        assert len(text()) > 1000

    def test_jede_genannte_adresse_ist_eine_echte_seite(self, flask_app):
        from werkzeug.routing import RequestRedirect

        karte = flask_app.url_map.bind("localhost")

        unbekannt = []
        for adresse in genannte_adressen():
            try:
                karte.match(adresse, method="GET")
            except RequestRedirect:
                # /admin leitet auf /admin/ weiter - erreichbar ist es trotzdem,
                # und genau so tippt man es ein.
                pass
            except Exception:
                unbekannt.append(adresse)

        assert not unbekannt, f"Adressen ohne passende Seite: {unbekannt}"

    def test_er_nennt_ueberhaupt_adressen(self):
        # Sonst würde der Test darüber stillschweigend nichts prüfen.
        assert len(genannte_adressen()) >= 5

    def test_genannte_dateien_und_ordner_gibt_es(self):
        erwartet = ["beispiele", "data", "requirements.txt",
                    "requirements-dev.txt", "werkzeuge/vendor_aktualisieren.py"]
        inhalt = text()
        for eintrag in erwartet:
            assert eintrag in inhalt, f"{eintrag} wird im Leitfaden nicht erwähnt"
            assert (ROOT / eintrag).exists(), f"{eintrag} gibt es im Projekt nicht"

    def test_protokolldatei_heisst_wie_im_code(self, flask_app):
        import os

        from app import configure_logging  # noqa: F401  (nur zur Absicherung importiert)

        name = os.path.basename(
            next(h.baseFilename for h in flask_app.logger.handlers
                 if getattr(h, "baseFilename", None))
        )
        assert name in text(), f"Der Leitfaden nennt die Logdatei nicht {name}"

    def test_readme_verweist_auf_den_leitfaden(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        assert "ADMIN_GUIDE.md" in readme
