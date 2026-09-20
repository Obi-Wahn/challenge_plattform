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

from sqlalchemy import event
from sqlalchemy.orm import object_session

from extensions import db
from models import Submission

# Schlüssel, unter dem die Pfade bis zum Abschluss der Transaktion warten.
VORGEMERKT = "abgaben_dateien_zum_loeschen"


@event.listens_for(Submission, "after_delete")
def _datei_vormerken(mapper, connection, submission):
    """Merkt sich den Pfad, solange das Objekt noch da ist."""
    if not submission.filename:
        return

    session = object_session(submission)
    if session is None:
        return

    session.info.setdefault(VORGEMERKT, []).append(submission.filename)


@event.listens_for(db.session, "after_commit")
def _dateien_loeschen(session):
    for pfad in session.info.pop(VORGEMERKT, []):
        try:
            os.remove(pfad)
        except OSError:
            # Schon weg oder nie angekommen: Das Löschen der Abgabe darf
            # daran nicht scheitern.
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
