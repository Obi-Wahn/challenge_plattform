"""Export and import of task sets, so a good set can be reused next time.

The file is plain JSON: readable, editable in any text editor and easy to pass
on to a colleague. Only what describes a task travels with it - not the
submissions, not the points teams scored, and not whether a hint was already
revealed during an event.
"""

import json
from datetime import datetime

from models import DEFAULT_TASK_FORMAT
from task_rules import KEIN_TITEL, PUNKTE_KEINE_ZAHL, clean_task_values

FORMAT_NAME = "coding-wettbewerb-aufgaben"
FORMAT_VERSION = 1

# Wie viele Aufgaben eine Datei höchstens mitbringen darf. Was für eine
# einzelne Aufgabe gilt - Titel, Punkte, Dateiformat - steht in task_rules.
MAX_TASKS = 200


def export_tasks(challenge, tasks):
    """The dictionary that gets written to the export file."""
    return {
        "format": FORMAT_NAME,
        "version": FORMAT_VERSION,
        "exportiert_am": datetime.now().strftime("%d.%m.%Y"),
        "wettbewerb": challenge.title if challenge else "",
        "aufgaben": [
            {
                "titel": task.title,
                "beschreibung": task.description or "",
                "punkte": task.max_points or 0,
                "dateiformat": task.allowed_extension or DEFAULT_TASK_FORMAT,
                "hinweis": task.hint or "",
            }
            for task in tasks
        ],
    }


def export_bytes(challenge, tasks):
    """The export file as bytes, with umlauts left readable."""
    text = json.dumps(export_tasks(challenge, tasks), ensure_ascii=False, indent=2)
    return (text + "\n").encode("utf-8")


class ImportError_(ValueError):
    """Raised when a file cannot be read as a task set at all."""


def parse_tasks(raw):
    """Reads an export file.

    Returns (tasks, skipped) where tasks is a list of dictionaries ready to be
    turned into Task rows, and skipped lists readable reasons for the entries
    that were left out. Raises ImportError_ when the file as a whole is
    unusable, with a message meant for the admin.
    """
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ImportError_("Die Datei ist keine Textdatei. Erwartet wird eine .json-Datei.")

    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise ImportError_(f"Die Datei ist keine gültige JSON-Datei (Zeile {error.lineno}).")

    # A bare list of tasks is accepted too, so a hand-written file works.
    if isinstance(data, list):
        entries = data
    elif isinstance(data, dict):
        entries = data.get("aufgaben")
        if entries is None:
            entries = data.get("tasks")
        if entries is None:
            raise ImportError_("In der Datei steht keine Liste „aufgaben“.")
    else:
        raise ImportError_("Die Datei enthält keine Aufgaben.")

    if not isinstance(entries, list):
        raise ImportError_("„aufgaben“ muss eine Liste sein.")

    if len(entries) > MAX_TASKS:
        raise ImportError_(f"Die Datei enthält mehr als {MAX_TASKS} Aufgaben.")

    tasks = []
    skipped = []

    for number, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            skipped.append(f"Eintrag {number}: kein Aufgaben-Eintrag")
            continue

        # Dieselben Regeln, die auch für das Formular gelten.
        werte, hinweise, problem = clean_task_values(
            entry.get("titel") or entry.get("title"),
            entry.get("beschreibung") or entry.get("description"),
            entry.get("punkte", entry.get("max_points", 0)),
            entry.get("dateiformat") or entry.get("allowed_extension"),
            entry.get("hinweis") or entry.get("hint"),
        )

        if problem == KEIN_TITEL:
            skipped.append(f"Eintrag {number}: ohne Titel")
            continue
        if problem == PUNKTE_KEINE_ZAHL:
            titel = str(entry.get("titel") or entry.get("title") or "")[:40]
            skipped.append(f"„{titel}“: Punktzahl ist keine Zahl")
            continue

        skipped.extend(hinweise)
        tasks.append(werte)

    if not tasks:
        raise ImportError_("In der Datei steht keine verwendbare Aufgabe." +
                           (" " + " · ".join(skipped[:3]) if skipped else ""))

    return tasks, skipped
