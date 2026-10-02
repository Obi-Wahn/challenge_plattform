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
nachgeholt. Die Datenbank wird nie angefasst, eine vorhandene .env nur,
wenn darin noch ein öffentlich bekannter Beispielwert oder ein zu kurzer
Schlüssel steht.

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

# Die älteste Fassung, mit der die Abhängigkeiten laufen (Markdown verlangt
# sie). Dieselbe Zahl steht in app.py, in der README und in der CI.
MINDEST_PYTHON = (3, 11)

BASIS = os.path.dirname(os.path.abspath(__file__))
UMGEBUNG = ".venv"

# Liegt in der virtuellen Umgebung und merkt sich, zu welcher requirements.txt
# die installierten Pakete gehören. Ändert sich die Datei - nach einem
# Update etwa -, wird neu installiert, sonst nicht.
PAKETSTAND = ".starter-pakete"

# Die Beispielwerte aus .env.example und der README. Sie stehen öffentlich im
# Repository, mit einem davon startet die Anwendung nicht (siehe config.py,
# dort steht dieselbe Liste - diese Datei kann config.py nicht laden, weil
# die beim Laden schon nach der .env fragt). Steht einer in der .env,
# ersetzt ihn konfiguration_sicherstellen().
PLATZHALTER = {
    "change-this-in-production-random-string",
    "change-this-password",
    "dein-geheimer-schluessel",
    "dein-sicheres-passwort",
}

# Kürzer darf ein SECRET_KEY nicht sein, sonst lässt er sich durchprobieren.
# Wie MIN_SCHLUESSEL in config.py.
MIN_SCHLUESSEL = 32

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


def umgebungs_version(basis=BASIS):
    """Mit welchem Python die Umgebung gebaut ist, etwa "3.13" - oder None.

    Das steht in .venv/pyvenv.cfg. Die Umgebung bleibt an dieses Python
    gebunden, auch wenn der Starter selbst längst mit einem neueren läuft.
    """
    try:
        with open(os.path.join(basis, UMGEBUNG, "pyvenv.cfg"), encoding="utf-8") as datei:
            for eintrag in datei:
                name, _, wert = eintrag.partition("=")
                if name.strip() in ("version", "version_info"):
                    teile = wert.strip().split(".")
                    if len(teile) >= 2:
                        return f"{teile[0]}.{teile[1]}"
    except OSError:
        pass
    return None


def umgebung_laeuft(basis=BASIS):
    """Startet das Python der Umgebung überhaupt noch?

    Nicht mehr, wenn das Python, mit dem sie gebaut wurde, deinstalliert
    ist - die Datei in .venv gibt es dann trotzdem noch.
    """
    try:
        return subprocess.run(
            [umgebungs_python(basis), "-c", ""],
            capture_output=True, timeout=60,
        ).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def mit_version(stand, basis):
    version = umgebungs_version(basis)
    return f"{stand} (Python {version})" if version else stand


def umgebung_sicherstellen(basis=BASIS, anlegen=None, laeuft=umgebung_laeuft):
    """Legt die virtuelle Umgebung an, wenn es sie nicht gibt oder sie nicht läuft.

    Eine laufende Umgebung bleibt, auch wenn sie mit einem älteren Python
    gebaut ist: Neu anlegen braucht Internet, und am Wettbewerbstag im
    Schulnetz würde sonst eine funktionierende durch eine kaputte ersetzt.
    Die Übersicht nennt die Version, wer wechseln will, löscht .venv.

    Ausgenommen ist eine Umgebung mit einem Python unter MINDEST_PYTHON: In
    ihr lassen sich die Pakete nicht mehr installieren, sie wird also ohnehin
    nicht mehr laufen. Das betrifft etwa eine .venv mit Python 3.10, die vor
    der Anhebung auf 3.11 angelegt wurde.

    Eine, die nicht mehr läuft, ist ohnehin verloren und wird neu angelegt.
    Ebenso ein Ordner .venv ohne Python darin - ein abgebrochener früherer
    Versuch. Die Pakete folgen von selbst: Ihr Vermerk lag in der alten
    Umgebung.
    """
    ordner = os.path.join(basis, UMGEBUNG)
    ergebnis = "angelegt"

    # lexists: Unter Linux und macOS ist das Python in .venv eine
    # Verknüpfung, die nach dem Deinstallieren ins Leere zeigt.
    if os.path.lexists(umgebungs_python(basis)):
        version = umgebungs_version(basis)
        if version and tuple(int(teil) for teil in version.split(".")) < MINDEST_PYTHON:
            ergebnis = f"neu angelegt, die alte hatte Python {version}"
        elif laeuft(basis):
            return mit_version("vorhanden", basis)
        else:
            ergebnis = "neu angelegt, die alte lief nicht mehr"

    anlegen = anlegen or (lambda pfad: venv.create(pfad, with_pip=True, clear=True))

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

    return mit_version(ergebnis, basis)


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


ERSTER_START = "Beim ersten Start braucht die Plattform ein Admin-Passwort."
BEISPIEL_PASSWORT = ("In der .env steht als Admin-Passwort noch der Beispielwert, und der "
                     "steht öffentlich im Repository. Bitte ein eigenes vergeben.")


def passwort_erfragen(eingabe=getpass.getpass, anlass=ERSTER_START):
    """Fragt das Admin-Passwort ab, zweimal, bis beide Eingaben passen."""
    print()
    print(anlass)
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


def env_setzen(inhalt, neue_werte):
    """Der Inhalt einer .env mit neuen Werten für die genannten Einträge.

    Nur deren Zeilen werden ersetzt, alle anderen bleiben samt Kommentaren
    stehen. Steht ein Eintrag mehrfach darin, werden alle ersetzt - sonst
    gälte der letzte, alte. Fehlt einer, kommt er ans Ende. Die Werte kommen
    so in die Datei, wie sie übergeben werden, Anführungszeichen also mit.
    """
    zeilen = []
    gesetzt = set()
    for eintrag in inhalt.splitlines():
        name = eintrag.split("=", 1)[0].strip()
        if "=" in eintrag and name in neue_werte:
            eintrag = f"{name}={neue_werte[name]}"
            gesetzt.add(name)
        zeilen.append(eintrag)
    zeilen += [f"{name}={wert}" for name, wert in neue_werte.items() if name not in gesetzt]
    return "\n".join(zeilen) + "\n"


def passwort_eintrag(passwort):
    """Das Passwort, wie es in die .env kommt.

    In einfachen Anführungszeichen nimmt python-dotenv es wörtlich - ein $,
    # oder \\ darin bleibt, was es ist. Nur ' und ${ gingen schief, die lehnt
    passwort_erfragen() ab.
    """
    return f"'{passwort}'"


def env_inhalt(vorlage, schluessel, passwort):
    """Die neue .env: die Vorlage, mit echtem Schlüssel und Passwort."""
    return env_setzen(vorlage, {"SECRET_KEY": schluessel,
                                "ADMIN_PASSWORD": passwort_eintrag(passwort)})


def schwacher_schluessel(wert):
    """Ob ein SECRET_KEY ersetzt werden muss: Beispielwert oder zu kurz."""
    return wert in PLATZHALTER or len(wert or "") < MIN_SCHLUESSEL


def _nur_fuer_besitzer(ziel):
    if os.name != "nt":
        # Das Passwort steht im Klartext darin.
        os.chmod(ziel, 0o600)


def vorhandene_env_pruefen(ziel, passwort_holen, umgebung=os.environ):
    """Ersetzt in einer vorhandenen .env, was öffentlich bekannt oder zu schwach ist.

    Mit einem bekannten oder kurzen SECRET_KEY kann sich jeder ein Cookie als
    Lehrkraft bauen (siehe config.py). Den Schlüssel muss niemand kennen, er
    wird deshalb ohne Rückfrage neu gewürfelt - die Teams melden sich danach
    einmal neu an. Das Admin-Passwort dagegen muss die Lehrkraft kennen: Steht
    dort noch der Beispielwert, wird nach einem neuen gefragt.

    Was in der Umgebung des Rechners gesetzt ist, gilt vor der .env und
    bleibt unberührt. Alles andere in der Datei auch.
    """
    werte = env_lesen(ziel)
    neu = {}

    if "SECRET_KEY" not in umgebung and schwacher_schluessel(werte.get("SECRET_KEY")):
        neu["SECRET_KEY"] = secrets.token_hex(32)

    passwort = werte.get("ADMIN_PASSWORD")
    if "ADMIN_PASSWORD" not in umgebung and (not passwort or passwort in PLATZHALTER):
        neu["ADMIN_PASSWORD"] = passwort_eintrag(passwort_holen())

    if not neu:
        return "vorhanden"

    # utf-8-sig: Eine mit dem Windows-Editor gespeicherte .env beginnt mit
    # einem unsichtbaren Zeichen, und die erste Zeile hieße sonst anders.
    with open(ziel, encoding="utf-8-sig") as datei:
        inhalt = datei.read()
    with open(ziel, "w", encoding="utf-8") as datei:
        datei.write(env_setzen(inhalt, neu))
    _nur_fuer_besitzer(ziel)

    teile = []
    if "SECRET_KEY" in neu:
        teile.append("neuer Schlüssel (Teams melden sich einmal neu an)")
    if "ADMIN_PASSWORD" in neu:
        teile.append("neues Admin-Passwort")
    return "vorhanden, " + " und ".join(teile)


def _beispiel_passwort_erfragen():
    return passwort_erfragen(anlass=BEISPIEL_PASSWORT)


def konfiguration_sicherstellen(basis=BASIS, passwort_holen=None):
    """Legt die .env an, wenn es keine gibt.

    Eine vorhandene bleibt, wie sie ist - bis auf Beispielwerte und einen zu
    kurzen Schlüssel, siehe vorhandene_env_pruefen().
    """
    ziel = os.path.join(basis, ".env")

    if os.path.exists(ziel):
        return vorhandene_env_pruefen(ziel, passwort_holen or _beispiel_passwort_erfragen)

    with open(os.path.join(basis, ".env.example"), encoding="utf-8") as datei:
        vorlage = datei.read()

    inhalt = env_inhalt(vorlage, secrets.token_hex(32), (passwort_holen or passwort_erfragen)())

    # "x": nur neu anlegen. Ist in der Zwischenzeit doch eine .env
    # entstanden, wird sie nicht überschrieben.
    with open(ziel, "x", encoding="utf-8") as datei:
        datei.write(inhalt)
    _nur_fuer_besitzer(ziel)

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

    def stand():
        # Die Meldung von git selbst ("Already up to date.") ist je nach
        # Spracheinstellung eine andere, der Commit nicht.
        kopf = ausfuehren(["git", "rev-parse", "HEAD"], cwd=basis, capture_output=True, text=True)
        return kopf.stdout.strip() if kopf.returncode == 0 else None

    vorher = stand()
    ergebnis = ausfuehren(["git", "pull", "--ff-only"], cwd=basis)
    if ergebnis.returncode != 0:
        raise Abbruch("git pull ist gescheitert, die Meldung steht oben. Es wurde nichts verändert.")

    if vorher is not None and stand() == vorher:
        return "schon aktuell"
    return "aktualisiert"


# --- Version ----------------------------------------------------------------

def version_ermitteln(basis=BASIS):
    """Welcher Stand hier liegt, etwa "1.5.1 (Stand 27.09.2026)".

    stand.py ist wie network.py nur Standardbibliothek und wird erst hier
    geholt, damit starter.py oben nichts Eigenes importiert.
    """
    sys.path.insert(0, basis)
    import stand

    return stand.ermitteln(basis)


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
        # Oben, damit man als Erstes sieht, welcher Stand läuft - nach einem
        # Update erst danach, sonst stünde dort noch der alte.
        if not optionen.aktualisieren:
            zeile("Version", version_ermitteln())
        zeile("Python", python_pruefen())
        if optionen.aktualisieren:
            zeile("Aktualisieren", aktualisieren())
            zeile("Version", version_ermitteln())
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
