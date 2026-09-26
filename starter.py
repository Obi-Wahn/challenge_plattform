"""Richtet die Plattform ein, wenn nötig, und startet sie.

Aufgerufen wird das von den drei Startdateien start_windows.bat,
start_macos.command und start_linux.sh. Die tun nichts anderes, als ein
Python zu finden und diese Datei damit auszuführen - die eigentliche Arbeit
steht nur hier, einmal für alle drei Systeme.

    python starter.py                   einrichten, was fehlt, dann starten
    python starter.py --aktualisieren   vorher die neue Fassung holen
    python starter.py --ohne-browser    kein Browserfenster öffnen

Jeder Schritt sieht erst nach, ob er nötig ist. Wer die Startdatei zehnmal
öffnet, bekommt beim zweiten bis zehnten Mal nur den Start - und wenn etwas
fehlt, etwa weil jemand den Ordner .venv gelöscht hat, wird genau das
nachgeholt. Eine vorhandene .env und die Datenbank werden nie angefasst.

Diese Datei läuft mit dem Python des Rechners, nicht mit dem der
Anwendung. Sie braucht deshalb nur die Standardbibliothek, und sie muss sich
auch mit einem zu alten Python noch lesen lassen, damit sie sagen kann, dass
es zu alt ist.
"""

import argparse
import getpass
import hashlib
import os
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
import venv
import webbrowser

# Die älteste Fassung, mit der die Abhängigkeiten laufen (fpdf2 verlangt
# sie). Dieselbe Zahl steht in der README und in der CI.
MINDEST_PYTHON = (3, 10)

BASIS = os.path.dirname(os.path.abspath(__file__))
UMGEBUNG = ".venv"

# Liegt in der virtuellen Umgebung und merkt sich, zu welcher requirements.txt
# die installierten Pakete gehören. Ändert sich die Datei - nach einem
# Update etwa -, wird neu installiert, sonst nicht.
PAKETSTAND = ".starter-pakete"

# Die Platzhalter aus .env.example. Steht einer davon noch in einer .env,
# läuft die Anwendung zwar, aber mit einem Passwort, das im Repository steht.
PLATZHALTER = {"change-this-in-production-random-string", "change-this-password"}

# Wie lange nach dem Start auf den Server gewartet wird, bevor der Browser
# aufgeht. Beim ersten Start legt die Anwendung erst die Datenbank an.
BROWSER_WARTEZEIT = 30


class Abbruch(Exception):
    """Ein Fehler, zu dem es eine verständliche Erklärung gibt.

    Der Text wird so ausgegeben, wie er ist - ohne Traceback, der einer
    Lehrkraft nichts sagt.
    """


def zeile(was, ergebnis):
    """Eine Zeile der Übersicht, mit Punkten bis zum Ergebnis."""
    print(f"{was} ".ljust(24, ".") + f" {ergebnis}")


# --- Python -----------------------------------------------------------------

def python_pruefen(version=None):
    """Die Fassung als Text, oder Abbruch, wenn sie zu alt ist."""
    version = version or sys.version_info
    text = ".".join(str(teil) for teil in version[:3])

    if tuple(version[:2]) < MINDEST_PYTHON:
        noetig = ".".join(str(teil) for teil in MINDEST_PYTHON)
        raise Abbruch(
            f"Gefunden wurde Python {text}, die Plattform braucht {noetig} oder neuer.\n"
            "Ein aktuelles Python gibt es unter https://www.python.org/downloads/\n"
            "Unter Windows beim Installieren \"Add python.exe to PATH\" ankreuzen."
        )

    return text


# --- Virtuelle Umgebung -----------------------------------------------------

def umgebungs_python(basis=BASIS, betriebssystem=None):
    """Der Pfad zum Python in der virtuellen Umgebung."""
    betriebssystem = betriebssystem or os.name
    if betriebssystem == "nt":
        return os.path.join(basis, UMGEBUNG, "Scripts", "python.exe")
    return os.path.join(basis, UMGEBUNG, "bin", "python")


def umgebung_sicherstellen(basis=BASIS, anlegen=None):
    """Legt die virtuelle Umgebung an, wenn es sie nicht gibt.

    Gibt "vorhanden" oder "angelegt" zurück. Ein Ordner .venv ohne Python
    darin - ein abgebrochener früherer Versuch - wird neu angelegt.
    """
    if os.path.isfile(umgebungs_python(basis)):
        return "vorhanden"

    anlegen = anlegen or (lambda pfad: venv.create(pfad, with_pip=True, clear=True))
    ordner = os.path.join(basis, UMGEBUNG)

    try:
        anlegen(ordner)
    except Exception as fehler:
        # Halb angelegt nützt sie nichts und würde beim nächsten Start für
        # vollständig gehalten.
        shutil.rmtree(ordner, ignore_errors=True)
        hinweis = ""
        if sys.platform.startswith("linux"):
            hinweis = (
                "\nAuf Debian und Ubuntu fehlt dafür oft ein Paket:\n"
                "    sudo apt install python3-venv"
            )
        raise Abbruch(
            f"Die virtuelle Umgebung ließ sich nicht anlegen ({fehler}).{hinweis}"
        ) from fehler

    if not os.path.isfile(umgebungs_python(basis)):
        shutil.rmtree(ordner, ignore_errors=True)
        raise Abbruch("Die virtuelle Umgebung wurde angelegt, enthält aber kein Python.")

    return "angelegt"


# --- Pakete -----------------------------------------------------------------

def paketkennung(basis=BASIS):
    """Prüfsumme der requirements.txt."""
    with open(os.path.join(basis, "requirements.txt"), "rb") as datei:
        return hashlib.sha256(datei.read()).hexdigest()


def pakete_sicherstellen(basis=BASIS, ausfuehren=subprocess.run):
    """Installiert die Pakete, wenn sie fehlen oder veraltet sind."""
    stand = os.path.join(basis, UMGEBUNG, PAKETSTAND)
    kennung = paketkennung(basis)

    try:
        with open(stand, encoding="utf-8") as datei:
            if datei.read().strip() == kennung:
                return "aktuell"
    except OSError:
        pass

    print("Pakete werden installiert. Das braucht Internet und dauert")
    print("beim ersten Mal ein bis zwei Minuten ...")
    ergebnis = ausfuehren([
        umgebungs_python(basis), "-m", "pip", "install",
        "--disable-pip-version-check", "-q",
        "-r", os.path.join(basis, "requirements.txt"),
    ], cwd=basis)

    if ergebnis.returncode != 0:
        raise Abbruch(
            "Die Pakete ließen sich nicht installieren. Die Meldung von pip steht oben.\n"
            "Meist fehlt die Internetverbindung - im Schulnetz etwa hinter einem Proxy.\n"
            "Beim nächsten Öffnen der Startdatei wird es erneut versucht."
        )

    # Erst nach Erfolg vermerken: Sonst hielte der nächste Start eine halbe
    # Installation für fertig.
    with open(stand, "w", encoding="utf-8") as datei:
        datei.write(kennung + "\n")

    return "installiert"


# --- Konfiguration ----------------------------------------------------------

def env_lesen(pfad):
    """Die Einträge einer .env, grob gelesen: nur KEY=Wert, Anführungszeichen weg.

    Genau genug für das, was hier gebraucht wird (Port, Platzhalter). Die
    Anwendung selbst liest die Datei mit python-dotenv.
    """
    werte = {}
    try:
        with open(pfad, encoding="utf-8") as datei:
            for eintrag in datei:
                eintrag = eintrag.strip()
                if not eintrag or eintrag.startswith("#") or "=" not in eintrag:
                    continue
                name, wert = eintrag.split("=", 1)
                wert = wert.strip()
                if len(wert) >= 2 and wert[0] == wert[-1] and wert[0] in "'\"":
                    wert = wert[1:-1]
                werte[name.strip()] = wert
    except OSError:
        pass
    return werte


def passwort_erfragen(eingabe=getpass.getpass):
    """Fragt das Admin-Passwort ab, zweimal, bis beide Eingaben passen."""
    print()
    print("Beim ersten Start braucht die Plattform ein Admin-Passwort.")
    print("Damit meldest du dich unter /admin an. Beim Tippen erscheinen keine Zeichen.")

    while True:
        passwort = eingabe("Admin-Passwort: ")
        if not passwort.strip():
            print("Das Passwort darf nicht leer sein.")
            continue
        if "'" in passwort or "${" in passwort or "\n" in passwort:
            # Das Apostroph beendete den Wert in der .env, und ${...} ersetzt
            # python-dotenv durch eine andere Einstellung.
            print("Bitte ohne ' und ohne ${ - beides bringt die .env durcheinander.")
            continue
        if eingabe("Noch einmal: ") != passwort:
            print("Die beiden Eingaben stimmen nicht überein, bitte noch einmal.")
            continue
        print()
        return passwort


def env_inhalt(vorlage, schluessel, passwort):
    """Die neue .env: die Vorlage, mit echtem Schlüssel und Passwort.

    Das Passwort steht in einfachen Anführungszeichen. python-dotenv nimmt
    es dann wörtlich - ein $, # oder \\ darin bleibt, was es ist. Nur ' und
    ${ gingen schief, die lehnt passwort_erfragen() ab.
    """
    zeilen = []
    for eintrag in vorlage.splitlines():
        if eintrag.startswith("SECRET_KEY="):
            eintrag = f"SECRET_KEY={schluessel}"
        elif eintrag.startswith("ADMIN_PASSWORD="):
            eintrag = f"ADMIN_PASSWORD='{passwort}'"
        zeilen.append(eintrag)
    return "\n".join(zeilen) + "\n"


def konfiguration_sicherstellen(basis=BASIS, passwort_holen=passwort_erfragen):
    """Legt die .env an, wenn es keine gibt. Eine vorhandene bleibt, wie sie ist."""
    ziel = os.path.join(basis, ".env")

    if os.path.exists(ziel):
        werte = env_lesen(ziel)
        if werte.get("ADMIN_PASSWORD") in PLATZHALTER or werte.get("SECRET_KEY") in PLATZHALTER:
            return "vorhanden, aber mit Platzhalter aus .env.example - bitte ändern"
        return "vorhanden"

    with open(os.path.join(basis, ".env.example"), encoding="utf-8") as datei:
        vorlage = datei.read()

    inhalt = env_inhalt(vorlage, secrets.token_hex(32), passwort_holen())

    # "x": nur neu anlegen. Ist in der Zwischenzeit doch eine .env
    # entstanden, wird sie nicht überschrieben.
    with open(ziel, "x", encoding="utf-8") as datei:
        datei.write(inhalt)

    if os.name != "nt":
        # Das Passwort steht im Klartext darin.
        os.chmod(ziel, 0o600)

    return "angelegt"


def datenbank_stand(basis=BASIS):
    """Nur zur Anzeige: Anlegen und Ergänzen macht die Anwendung beim Start."""
    if os.path.exists(os.path.join(basis, "data", "challenge.db")):
        return "vorhanden"
    return "wird beim Start angelegt"


# --- Aktualisieren ----------------------------------------------------------

ZIP_ANLEITUNG = """\
Diese Installation stammt aus einer ZIP-Datei, nicht aus git. Aktualisieren
geht dann von Hand:

  1. Die Plattform beenden.
  2. Die neue ZIP-Datei von der Release-Seite herunterladen:
     https://github.com/Obi-Wahn/challenge_plattform/releases
  3. Sie in einen NEUEN Ordner entpacken.
  4. Aus dem alten Ordner hinüberkopieren:
       data/      die Datenbank
       uploads/   die Abgaben der Teams
       .env       Passwort und Einstellungen (Datei beginnt mit Punkt,
                  ist also oft versteckt)
  5. Die Startdatei im neuen Ordner öffnen.

Die Datenbank passt die Plattform beim Start selbst an und legt vorher eine
Sicherung an. Den alten Ordner erst löschen, wenn alles läuft."""


def aktualisieren(basis=BASIS, ausfuehren=subprocess.run):
    """Holt die neue Fassung mit git, wenn es eine git-Installation ist.

    Nur ein Vorspulen (--ff-only), und nur ohne eigene Änderungen an Dateien
    des Repositorys: Dann kann nichts überschrieben werden. .env, data/ und
    uploads/ sind ohnehin nicht im Repository und bleiben unberührt.
    """
    if not os.path.isdir(os.path.join(basis, ".git")):
        raise Abbruch(ZIP_ANLEITUNG)

    if shutil.which("git") is None:
        raise Abbruch("Das ist eine git-Installation, aber git ist nicht installiert.")

    geaendert = ausfuehren(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=basis, capture_output=True, text=True,
    )
    if geaendert.returncode != 0:
        raise Abbruch(f"git status ist gescheitert:\n{geaendert.stderr.strip()}")
    if geaendert.stdout.strip():
        raise Abbruch(
            "In diesem Ordner sind Dateien der Plattform verändert worden:\n"
            f"{geaendert.stdout.rstrip()}\n"
            "Damit nichts davon verloren geht, wird nicht aktualisiert.\n"
            "Die Änderungen erst sichern oder mit git verwerfen."
        )

    ergebnis = ausfuehren(["git", "pull", "--ff-only"], cwd=basis)
    if ergebnis.returncode != 0:
        raise Abbruch("git pull ist gescheitert, die Meldung steht oben. Es wurde nichts verändert.")

    return "aktualisiert"


# --- Start ------------------------------------------------------------------

def port_ermitteln(basis=BASIS):
    """Der Port aus der .env, nach denselben Regeln wie die Anwendung."""
    sys.path.insert(0, basis)
    from network import PORT_EINTRAG, server_port

    alt = os.environ.get(PORT_EINTRAG)
    wert = env_lesen(os.path.join(basis, ".env")).get(PORT_EINTRAG)
    try:
        if alt is None and wert is not None:
            os.environ[PORT_EINTRAG] = wert
        return server_port()
    finally:
        if alt is None:
            os.environ.pop(PORT_EINTRAG, None)


def port_belegt(port):
    """Nimmt auf diesem Rechner schon etwas Verbindungen auf dem Port an?"""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def browser_oeffnen_wenn_bereit(port, server, warten=BROWSER_WARTEZEIT):
    """Öffnet den Browser, sobald der Server antwortet - im Hintergrund."""
    def warte_und_oeffne():
        ende = time.monotonic() + warten
        while time.monotonic() < ende and server.poll() is None:
            if port_belegt(port):
                try:
                    webbrowser.open(f"http://localhost:{port}")
                except Exception:
                    # Kein Browser, etwa auf einem Server ohne Oberfläche -
                    # die Adresse steht ohnehin im Fenster.
                    pass
                return
            time.sleep(0.5)

    threading.Thread(target=warte_und_oeffne, daemon=True).start()


def starten(basis=BASIS, browser=True):
    port = port_ermitteln(basis)

    if port_belegt(port):
        raise Abbruch(
            f"Port {port} ist auf diesem Rechner schon belegt.\n"
            "Läuft die Plattform vielleicht schon in einem anderen Fenster? Dann dort\n"
            f"weiterarbeiten: http://localhost:{port}\n"
            "Belegt ihn etwas anderes, lässt sich der Port mit PORT=8002 in der .env ändern."
        )

    print()
    print("Starte die Plattform ...")
    print()

    server = subprocess.Popen([umgebungs_python(basis), "app.py"], cwd=basis)
    if browser:
        browser_oeffnen_wenn_bereit(port, server)

    try:
        code = server.wait()
    except KeyboardInterrupt:
        # STRG+C erreicht den Server im selben Fenster ebenfalls.
        code = server.wait()
        print("\nPlattform beendet.")
        return 0

    if code != 0:
        raise Abbruch("Die Plattform hat sich mit einem Fehler beendet. Die Meldung steht oben.")
    return 0


def main(argumente=None):
    parser = argparse.ArgumentParser(description="Richtet die Plattform ein und startet sie.")
    parser.add_argument("--aktualisieren", action="store_true",
                        help="vorher die neue Fassung mit git holen")
    parser.add_argument("--ohne-browser", action="store_true",
                        help="kein Browserfenster öffnen")
    optionen = parser.parse_args(argumente)

    print("Coding-Wettbewerb-Plattform")
    print("===========================")
    print()

    try:
        zeile("Python", python_pruefen())
        if optionen.aktualisieren:
            zeile("Aktualisieren", aktualisieren())
        zeile("Virtuelle Umgebung", umgebung_sicherstellen())
        zeile("Pakete", pakete_sicherstellen())
        zeile("Konfiguration", konfiguration_sicherstellen())
        zeile("Datenbank", datenbank_stand())
        return starten(browser=not optionen.ohne_browser)
    except Abbruch as fehler:
        print()
        print(fehler)
        return 1
    except KeyboardInterrupt:
        print("\nAbgebrochen.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
