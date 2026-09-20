"""Hilfsmittel, die mehrere Testdateien brauchen.

Bewusst nicht in conftest.py: Die lädt pytest selbst, und ein zusätzliches
"from tests.conftest import ..." würde sie ein zweites Mal als eigenes Modul
laden - mit eigenem temporärem Verzeichnis und doppelt gesetzten
Umgebungsvariablen.
"""

import os
import re
import tempfile

# Muss gesetzt sein, bevor config.py geladen wird: Die Datei verlangt diese
# Werte beim Import. load_dotenv() überschreibt vorhandene Variablen nicht,
# eine .env der Entwicklerin kann also nicht dazwischenfunken.
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ADMIN_PASSWORD", "test-admin")

ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]

# Eigene Datenbank in einem temporären Verzeichnis: data/challenge.db wird
# von den Tests nie angefasst.
TMP_DIR = tempfile.mkdtemp(prefix="challenge-tests-")
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(TMP_DIR, "test.db")


def csrf_token(client, path):
    """Holt ein CSRF-Token von einer Seite, die ein Formular enthält.

    Ohne Token weist Flask-WTF jedes POST mit 400 ab - dann testet man nicht
    die Anwendung, sondern den Schutzmechanismus.

    Das g.csrf_token muss vorher weg: Flask-WTF merkt sich das Token im
    App-Kontext, und die Tests halten einen offen. Sonst bekäme ein zweiter
    Testclient im selben Test kein eigenes Session-Cookie. Im echten Betrieb
    gibt es diesen Fall nicht - dort lebt der Kontext nur für eine Anfrage.
    """
    from flask import g

    g.pop("csrf_token", None)
    html = client.get(path).get_data(as_text=True)
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match, f"Auf {path} steht kein CSRF-Token - falsche Seite gewählt?"
    return match.group(1)
