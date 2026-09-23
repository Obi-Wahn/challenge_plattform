"""Hochgeladene Dateien verschwinden zusammen mit ihrer Abgabe.

Eine Abgabe kann auf vier Wegen verschwinden: die Abgabe selbst wird
gelöscht, oder ihr Team, ihre Aufgabe oder der ganze Wettbewerb - die
letzten drei über die Kaskade der Datenbank. In allen vier Fällen soll die
Datei mitgehen. Dafür sorgt ein Haken an der Datenbank statt vier einzelner
Aufräumzeilen in den Routen: Der greift auch bei einem Löschweg, den es
heute noch nicht gibt.

Gelöscht wird erst nach dem Abschluss der Transaktion. Bricht sie ab,
bleibt die Datei liegen - andersherum wäre der Verlust nicht mehr
rückholbar.
"""

import os

from flask import current_app, has_app_context
from sqlalchemy import event
from sqlalchemy.orm import object_session

from extensions import db
from models import Submission

# Schlüssel, unter dem die Pfade bis zum Abschluss der Transaktion warten.
VORGEMERKT = "abgaben_dateien_zum_loeschen"


def zum_loeschen_vormerken(session, pfad):
    """Löscht die Datei, sobald die laufende Änderung abgeschlossen ist.

    Gedacht für die Korrekturabgabe: Dort wird eine vorhandene Abgabe auf
    eine neue Datei umgestellt, und die alte soll erst dann verschwinden,
    wenn die Umstellung auch wirklich gespeichert ist.
    """
    if pfad:
        session.info.setdefault(VORGEMERKT, []).append(pfad)


@event.listens_for(Submission, "after_delete")
def _datei_vormerken(mapper, connection, submission):
    """Merkt sich den Pfad, solange das Objekt noch da ist."""
    session = object_session(submission)
    if session is None:
        return

    zum_loeschen_vormerken(session, submission.filename)


def _melden(pfad, fehler):
    """Hält im Protokoll fest, dass eine Datei liegen geblieben ist.

    Ohne diese Zeile bliebe ein dauerhaftes Problem - eine schreibgeschützte
    Platte, ein Verzeichnis ohne Rechte - unsichtbar: Die Abgaben
    verschwänden aus der Datenbank, die Dateien blieben liegen, und niemand
    erführe davon. Gemeldet, nicht abgebrochen: Eine verwaiste Datei ist
    immer noch besser als eine Löschung, die auf halbem Weg scheitert.
    """
    if has_app_context():
        current_app.logger.warning(
            "Datei einer gelöschten Abgabe konnte nicht entfernt werden: "
            "%s (%s)", pfad, fehler)


@event.listens_for(db.session, "after_commit")
def _dateien_loeschen(session):
    for pfad in session.info.pop(VORGEMERKT, []):
        try:
            os.remove(pfad)
        except FileNotFoundError:
            # Schon weg oder nie angekommen. Das ist der gewöhnliche Fall
            # einer von Hand aufgeräumten Ablage und keine Meldung wert.
            continue
        except OSError as fehler:
            # Alles andere - fehlende Rechte, Platte nur lesbar - ist eine
            # Störung, die jemand sehen sollte.
            _melden(pfad, fehler)
            continue

        # Das Verzeichnis des Teams mitnehmen, sobald es leer ist.
        ordner = os.path.dirname(pfad)
        try:
            os.rmdir(ordner)
        except OSError:
            pass


@event.listens_for(db.session, "after_rollback")
def _vormerkung_verwerfen(session):
    """Nichts wurde gelöscht, also bleibt auch keine Datei zu löschen."""
    session.info.pop(VORGEMERKT, None)
