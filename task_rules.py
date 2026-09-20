"""Was für eine Aufgabe gilt - einmal, für alle Wege.

Eine Aufgabe entsteht auf drei Wegen: über das Formular, beim Bearbeiten und
beim Einlesen einer Datei. Die Regeln dafür standen bisher nur im Einleseweg;
das Formular übernahm, was ankam. Ein von Hand abgeschicktes Formular konnte
so eine Aufgabe mit -50 Punkten anlegen (damit gibt jede Bewertung 0 Punkte,
ohne dass es auffällt) oder ein Dateiformat eintragen, das gar nicht
vorgesehen ist. Eine Punktzahl wie "abc" beendete die Anfrage mit einem
Serverfehler.

Die Regeln stehen deshalb hier, und alle drei Wege benutzen sie.
"""

from models import TASK_FORMATS, DEFAULT_TASK_FORMAT

MAX_TITLE = 200
MAX_POINTS = 1000
# Großzügig, aber nicht unbegrenzt: Die Beschreibung soll eine Aufgabe
# erklären, keine Datenbank füllen.
MAX_DESCRIPTION = 20000
MAX_HINT = 2000


# Gründe, aus denen keine Aufgabe entsteht. Die Meldung dazu formuliert der
# Aufrufer: Im Formular steht die Lehrkraft davor, beim Einlesen einer Datei
# gehört die Nummer des Eintrags dazu.
KEIN_TITEL = "kein_titel"
PUNKTE_KEINE_ZAHL = "punkte_keine_zahl"


def clean_task_values(title, description, points, extension, hint):
    """Prüft die Werte einer Aufgabe.

    Gibt (werte, hinweise, problem) zurück:

    * werte    - die geprüften Werte, oder None
    * hinweise - was zurechtgerückt wurde; zum Anzeigen, nicht zum Abbrechen
    * problem  - der Grund, wenn keine Aufgabe daraus wird, sonst None

    Ein fehlender Titel und eine Punktzahl, die keine Zahl ist, sind Probleme:
    Da lässt sich nichts sinnvoll erraten. Alles andere wird zurechtgerückt
    und gemeldet.
    """
    hinweise = []

    title = str(title or "").strip()
    if not title:
        return None, hinweise, KEIN_TITEL

    if len(title) > MAX_TITLE:
        title = title[:MAX_TITLE]
        hinweise.append(f"Titel auf {MAX_TITLE} Zeichen gekürzt")

    try:
        points = int(points)
    except (TypeError, ValueError):
        return None, hinweise, PUNKTE_KEINE_ZAHL

    if points < 0:
        hinweise.append(f"„{title[:40]}“: Punktzahl war negativ, 0 eingetragen")
        points = 0
    elif points > MAX_POINTS:
        hinweise.append(f"„{title[:40]}“: Punktzahl auf {MAX_POINTS} begrenzt")
        points = MAX_POINTS

    extension = str(extension or "").strip()
    if extension not in TASK_FORMATS:
        # Ein unbekanntes Format könnte kein Team hochladen, deshalb die
        # Voreinstellung - aber mit Ansage statt stillschweigend.
        if extension:
            hinweise.append(
                f"„{title[:40]}“: Dateiformat {extension} ist unbekannt, "
                f"{DEFAULT_TASK_FORMAT} eingetragen"
            )
        extension = DEFAULT_TASK_FORMAT

    description = str(description or "")
    if len(description) > MAX_DESCRIPTION:
        description = description[:MAX_DESCRIPTION]
        hinweise.append(f"„{title[:40]}“: Beschreibung gekürzt")

    hint = str(hint or "").strip()
    if len(hint) > MAX_HINT:
        hint = hint[:MAX_HINT]
        hinweise.append(f"„{title[:40]}“: Hinweis gekürzt")

    werte = {
        "title": title,
        "description": description or None,
        "max_points": points,
        "allowed_extension": extension,
        "hint": hint or None,
    }
    return werte, hinweise, None
