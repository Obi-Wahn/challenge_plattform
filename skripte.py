"""Die Skripte einer Abgabe als Blöcke, für Bewertungsseite und Teamseite.

Gelesen wird von scratch_skripte (.sb3) und snap_skripte (.xml); hier steht
nur, welche Endung zu welchem Leser gehört und was bei einer Datei gilt, die
es nicht mehr gibt. Wer eine Abgabe sehen darf, prüft die jeweilige Route.
"""

import os
import re

from flask import jsonify

import scratch_skripte
import snap_skripte

# Welche Abgaben sich als Blöcke anzeigen lassen, und wer sie liest. Hinter
# .xml kann auch ein Programm aus Open Roberta stecken; das merkt erst
# snap_skripte beim Lesen und sagt es dann.
BLOCK_LESER = {
    ".sb3": scratch_skripte.skripte_der_abgabe,
    ".xml": snap_skripte.skripte_der_abgabe,
}

# Die Hinweise der Leser raten der Lehrkraft, die Datei herunterzuladen. Ein
# Team kann das nicht - es hat die Datei ja selbst -, also fällt der Rat auf
# der Teamseite weg.
_DOWNLOAD_RAT = re.compile(r"\s+-\s+zum Ansehen herunterladen.*$")


def als_bloecke(dateiname):
    """Ob sich eine Abgabe dieses Namens als Blöcke anzeigen lässt."""
    return os.path.splitext(dateiname)[1].lower() in BLOCK_LESER


def skripte_antwort(submission, fuer_team=False):
    """Die Skripte einer Abgabe als JSON-Antwort mit Figuren und Hinweis.

    Als JSON und nicht als Seite: So kann der Browser den Inhalt einer
    fremden Datei unter keinen Umständen als HTML auffassen. Die Bilder
    zeichnet erst der Browser mit scratchblocks.
    """
    leser = BLOCK_LESER.get(os.path.splitext(submission.filename)[1].lower())
    if leser is None:
        figuren, hinweis = [], ("Nur Projekte aus Scratch 3 (.sb3) und Snap! (.xml) "
                                "lassen sich so anzeigen.")
    elif not os.path.isfile(submission.pfad):
        figuren, hinweis = [], "Die Datei liegt nicht mehr an ihrem Platz."
    else:
        figuren, hinweis = leser(submission.pfad)

    if fuer_team and hinweis:
        hinweis = _DOWNLOAD_RAT.sub(".", hinweis)

    antwort = jsonify({"figuren": figuren, "hinweis": hinweis})
    # Der Browser soll den Inhalt auch dann nicht als HTML auffassen, wenn er
    # zu raten versucht, was er da bekommt.
    antwort.headers["X-Content-Type-Options"] = "nosniff"
    return antwort
