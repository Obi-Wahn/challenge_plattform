"""Aufräumen nach dem Wettbewerb.

Nach einem Wettbewerb liegen Daten der Schülerinnen und Schüler an drei
Stellen: in der Datenbank (Teams, Namen, Passwörter, Abgaben), in der
Protokolldatei (Teamnamen, IP-Adressen) und in den Sicherungskopien, die der
Start vor einem Umbau der Datenbank anlegt (alles). Hier steht, wie jede
davon wieder verschwindet - ohne dass jemand im Dateisystem suchen muss.

Wer etwas aufheben will, sichert den Wettbewerb vorher als ZIP.
"""

import glob
import os

from flask import current_app

from extensions import db

# Der Name des Handlers, der in logs/anwendung.log schreibt (siehe
# configure_logging in app.py).
LOG_HANDLER_NAME = "protokolldatei"
PROTOKOLLDATEI = "anwendung.log"


def wettbewerb_aufraeumen(challenge):
    """Löscht Teams und Abgaben eines Wettbewerbs, gibt (teams, abgaben) zurück.

    Mit den Teams gehen ihre Namen für die Urkunde, ihre Passwörter und über
    die Kaskade ihre Abgaben samt Punkten und Feedback - und die Dateien
    dazu, dafür sorgt uploads.py. Wettbewerb, Einstellungen und Aufgaben
    bleiben: Beim nächsten Mal ist alles vorbereitet, nur ohne Kinder.

    Eine stehende Durchsage fällt mit weg, sie kann Namen enthalten. Und
    ein eingefrorener Stand beginnt von vorn - es gibt nichts mehr, was er
    verbergen könnte.
    """
    teams = list(challenge.teams)
    abgaben = sum(len(team.submissions) for team in teams)
    for team in teams:
        db.session.delete(team)
    challenge.clear_announcement()
    challenge.reset_freeze()
    db.session.commit()
    return len(teams), abgaben


def _datenbankdatei():
    uri = current_app.config["SQLALCHEMY_DATABASE_URI"]
    if not uri.startswith("sqlite:///"):
        return None
    return uri[len("sqlite:///"):]


def sicherungskopien():
    """Die Kopien, die der Start vor einem Umbau der Datenbank angelegt hat.

    Als Liste von (Dateiname, Größe in Bytes), älteste zuerst. Sie heißen wie
    die Datenbank mit „-vor-…“ dahinter, siehe backup_before_migration in
    app.py - nur solche Dateien werden hier je angefasst.
    """
    pfad = _datenbankdatei()
    if not pfad:
        return []
    stamm = os.path.splitext(os.path.basename(pfad))[0]
    muster = os.path.join(os.path.dirname(pfad) or ".", f"{glob.escape(stamm)}-vor-*.db")
    return [(os.path.basename(p), os.path.getsize(p)) for p in sorted(glob.glob(muster))]


def sicherungskopien_loeschen():
    """Löscht die Sicherungskopien, gibt (gelöscht, nicht gelöscht) zurück."""
    pfad = _datenbankdatei()
    geloescht, fehler = 0, 0
    for name, _groesse in sicherungskopien():
        try:
            os.remove(os.path.join(os.path.dirname(pfad) or ".", name))
            geloescht += 1
        except OSError:
            fehler += 1
    return geloescht, fehler


def protokolldateien():
    """Die Protokolldatei und ihre älteren Stände, als (Dateiname, Größe)."""
    log_dir = current_app.config["LOG_DIR"]
    namen = sorted(glob.glob(os.path.join(glob.escape(log_dir), PROTOKOLLDATEI + "*")))
    return [(os.path.basename(p), os.path.getsize(p)) for p in namen]


def protokoll_leeren():
    """Leert die Protokolldatei und löscht ihre älteren Stände.

    Die laufende Datei hält der Server offen. Sie wird darum über ihren
    Handler geleert statt gelöscht - so schreibt er danach einfach am Anfang
    weiter, auch unter Windows, wo eine offene Datei nicht zu löschen ist.

    Gibt zurück, wie viele ältere Stände sich nicht löschen ließen.
    """
    log_dir = current_app.config["LOG_DIR"]
    aktuell = os.path.join(log_dir, PROTOKOLLDATEI)

    handler = next((h for h in current_app.logger.handlers
                    if h.name == LOG_HANDLER_NAME), None)
    if handler is not None and getattr(handler, "stream", None):
        handler.acquire()
        try:
            handler.flush()
            handler.stream.seek(0)
            handler.stream.truncate()
        finally:
            handler.release()
    elif os.path.exists(aktuell):
        open(aktuell, "w", encoding="utf-8").close()

    fehler = 0
    for name, _groesse in protokolldateien():
        if name != PROTOKOLLDATEI:
            try:
                os.remove(os.path.join(log_dir, name))
            except OSError:
                fehler += 1
    return fehler


def groesse_text(anzahl_bytes):
    """„1,2 MB“ oder „340 KB“ - für die Anzeige, nicht zum Rechnen."""
    if anzahl_bytes >= 1024 * 1024:
        return f"{anzahl_bytes / (1024 * 1024):.1f} MB".replace(".", ",")
    return f"{max(1, round(anzahl_bytes / 1024))} KB"
