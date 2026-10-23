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
from werkzeug.utils import secure_filename

from extensions import db
from models import Submission
from protokoll import stoerung

# Zeichen, die in einem Dateinamen zum Herunterladen stehen bleiben - alles
# andere wird zu "_". So übersteht der Name jedes Betriebssystem, auch mit
# Emoji oder Umlauten im Team- oder Wettbewerbsnamen.
DATEINAMEN_ZEICHEN = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")


def safe_name(text):
    """Text als Teil eines Dateinamens, etwa „Bit & Byte“ als „Bit___Byte“."""
    return "".join(c if c in DATEINAMEN_ZEICHEN else "_" for c in text)


# Wie lang der Name einer abgelegten Abgabe werden darf. Dateisysteme lassen
# meist 255 Zeichen je Namensbestandteil zu; darüber scheitert das Speichern
# mit einem OSError, und die Abgabe endete für das Team in einer Fehlerseite.
# 100 Zeichen sind mehr, als ein Mensch tippt, und lassen Luft für das
# vorangestellte "task_<nummer>_".
MAX_DATEINAME = 100

# So lang ist Task.allowed_extension höchstens (String(10)). Was darüber
# hinausgeht, ist keine Endung mehr, sondern Name.
MAX_ENDUNG = 10


def gekuerzter_dateiname(filename):
    """Kürzt einen zu langen Dateinamen, behält dabei aber die Endung.

    Gekürzt statt abgewiesen: Wie die Datei heißt, ist nebensächlich - es
    zählt, was darin steht -, und ein Team hat pro Aufgabe nur einen
    Versuch. Die Endung bleibt, weil der Download in der Verwaltung sie aus
    dem abgelegten Namen nimmt.

    secure_filename() hat den Namen vorher auf ASCII gebracht, ein Zeichen
    ist hier also auch ein Byte.
    """
    if len(filename) <= MAX_DATEINAME:
        return filename

    stamm, endung = os.path.splitext(filename)
    endung = endung[:MAX_ENDUNG]
    return stamm[:MAX_DATEINAME - len(endung)] + endung


def abgelegter_dateiname(original, endung):
    """Der Name, unter dem eine Abgabe abgelegt wird - immer mit ihrer Endung.

    secure_filename() lässt nur ASCII übrig und nimmt einen Punkt am Anfang
    weg. Aus „Кот.sb3“ oder „🐱.sb3“ wurde so „sb3“, ganz ohne Punkt: Die
    Datei lag ohne Endung da, die Skripte ließen sich nicht anzeigen, und
    der Download kam ohne .sb3. Fehlt die Endung der Aufgabe hinterher,
    kommt sie wieder dran; bleibt vom Namen nichts übrig, heißt die Datei
    „abgabe“.
    """
    name = secure_filename(original or "")
    if endung and not name.lower().endswith(endung.lower()):
        stamm = name if name.lower() != endung.lstrip(".").lower() else ""
        name = (stamm or "abgabe") + endung
    return gekuerzter_dateiname(name or "abgabe")


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

    zum_loeschen_vormerken(session, submission.pfad)


def _melden(pfad, fehler):
    """Hält im Protokoll fest, dass eine Datei liegen geblieben ist.

    Ohne diese Zeile bliebe ein dauerhaftes Problem - eine schreibgeschützte
    Platte, ein Verzeichnis ohne Rechte - unsichtbar: Die Abgaben
    verschwänden aus der Datenbank, die Dateien blieben liegen, und niemand
    erführe davon. Gemeldet, nicht abgebrochen: Eine verwaiste Datei ist
    immer noch besser als eine Löschung, die auf halbem Weg scheitert.
    """
    stoerung("Datei einer gelöschten Abgabe konnte nicht entfernt werden: "
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
