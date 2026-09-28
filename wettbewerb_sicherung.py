"""Einen ganzen Wettbewerb als ZIP sichern und wieder einlesen.

Die ZIP enthält eine ``wettbewerb.json`` und im Ordner ``abgaben/`` die
Dateien, die die Teams hochgeladen haben. In der JSON steht alles, was zum
Wettbewerb gehört: Name, Untertitel, Zeiten, die Aufgaben samt Hinweis und
Schwierigkeit, die Teams und ihre Abgaben mit Punkten und Feedback.

Was bewusst nicht mitkommt:

* Die Passwörter der Teams, auch nicht als Hash, und die Kennzeichen der
  Anmeldung. Eine Sicherung ist eine Datei, die weitergegeben und auf
  USB-Sticks kopiert wird; was sich damit anmelden ließe, gehört nicht
  hinein. Ein eingelesener Wettbewerb ist zum Nachschauen und für Urkunden
  da. Wer ihn fortsetzen will, vergibt auf der Teamseite neue Passwörter.
* Die Namen der Teammitglieder - außer die Lehrkraft wählt ausdrücklich
  „mit Namen“. Sie sind die einzigen Angaben, die eine Schülerin oder einen
  Schüler direkt benennen, und für Rangliste und Punkte braucht es sie nicht.
* Die Einstellungen der Installation (Standardname, Unterschrift). Sie
  gehören nicht zu einem Wettbewerb.

Die Nummern von Teams, Aufgaben und Abgaben in der Datei sind eigene, ab 1
gezählt, nicht die aus der Datenbank. Beim Einlesen vergibt die Datenbank
neue, und die Dateien landen dort, wo eine Abgabe dieses Teams sie auch
abgelegt hätte. Ein Pfad aus der ZIP wird nie als Ziel benutzt.
"""

import json
import os
import tempfile
import zipfile
from datetime import datetime

from werkzeug.utils import secure_filename

from extensions import db
from models import (Challenge, Submission, Task, Team, format_member_names,
                    parse_member_names, MAX_MEMBERS)
from task_rules import clean_task_values

FORMAT_NAME = "coding-wettbewerb-sicherung"
FORMAT_VERSION = 1
JSON_NAME = "wettbewerb.json"
ABGABEN_ORDNER = "abgaben"

# Grenzen für das Einlesen. Die Datei kommt zwar nur von der angemeldeten
# Lehrkraft, aber eine kaputte oder falsche ZIP soll mit einer Meldung
# enden, nicht mit einer vollen Platte.
MAX_JSON_BYTES = 20 * 1024 * 1024
MAX_TEAMS = 500
MAX_TASKS = 200
MAX_TEAMNAME = 100
MAX_TITEL = 200
MAX_UNTERTITEL = 300
MAX_FEEDBACK = 20000
# So groß darf eine einzelne Abgabe sein - dieselbe Grenze wie beim Hochladen.
MAX_DATEI_BYTES = 16 * 1024 * 1024
# Alle Dateien zusammen, ausgepackt.
MAX_GESAMT_BYTES = 2 * 1024 * 1024 * 1024
# So groß darf die hochgeladene ZIP werden. Scratch-Projekte bringen schnell
# ein paar MB mit, bei 30 Teams und fünf Aufgaben kommt einiges zusammen.
MAX_ZIP_BYTES = 1024 * 1024 * 1024


class SicherungFehler(ValueError):
    """Die Datei lässt sich nicht als Sicherung lesen. Die Meldung ist für die Lehrkraft."""


# ------------------------------------------------------------------ Sichern

def _zeit(wert):
    return wert.isoformat(timespec="seconds") if wert else None


def sicherung_bauen(challenge, mit_namen):
    """Schreibt die ZIP in eine temporäre Datei und gibt (datei, zahlen) zurück.

    Die Datei liegt nicht im Verzeichnis der Anwendung und verschwindet,
    sobald sie geschlossen ist - nach dem Herunterladen also. zahlen ist ein
    dict mit teams, aufgaben, abgaben und fehlend (Abgaben, deren Datei auf
    der Platte nicht mehr lag).
    """
    tasks = Task.query.filter_by(challenge_id=challenge.id).order_by(Task.id).all()
    teams = Team.query.filter_by(challenge_id=challenge.id).order_by(Team.name).all()

    aufgabe_nr = {task.id: nr for nr, task in enumerate(tasks, start=1)}
    team_nr = {team.id: nr for nr, team in enumerate(teams, start=1)}

    datei = tempfile.TemporaryFile()
    abgaben = []
    fehlend = 0

    with zipfile.ZipFile(datei, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for team in teams:
            for submission in sorted(team.submissions, key=lambda s: s.id):
                if submission.task_id not in aufgabe_nr:
                    continue

                eintrag = {
                    "team": team_nr[team.id],
                    "aufgabe": aufgabe_nr[submission.task_id],
                    "datei": None,
                    "zeit": _zeit(submission.timestamp),
                    "punkte": submission.points,
                    "feedback": submission.feedback or "",
                    "nachreichen_erlaubt": bool(submission.resubmit_allowed),
                }

                pfad = submission.filename
                if pfad and os.path.isfile(pfad):
                    name = os.path.basename(pfad)
                    ziel = f"{ABGABEN_ORDNER}/team_{team_nr[team.id]}/{name}"
                    zf.write(pfad, ziel)
                    eintrag["datei"] = ziel
                else:
                    fehlend += 1

                abgaben.append(eintrag)

        inhalt = {
            "format": FORMAT_NAME,
            "version": FORMAT_VERSION,
            "gesichert_am": _zeit(datetime.now()),
            "mit_namen": bool(mit_namen),
            "wettbewerb": {
                "titel": challenge.title,
                "untertitel": challenge.tagline or "",
                "start": _zeit(challenge.start_time),
                "ende": _zeit(challenge.end_time),
                "pausiert": bool(challenge.paused),
                "pausiert_seit": _zeit(challenge.paused_at),
            },
            "aufgaben": [
                {
                    "nr": aufgabe_nr[task.id],
                    "titel": task.title,
                    "beschreibung": task.description or "",
                    "punkte": task.max_points or 0,
                    "dateiformat": task.allowed_extension,
                    "hinweis": task.hint or "",
                    "hinweis_sichtbar": bool(task.hint_visible),
                    "schwierigkeit": task.difficulty or "",
                }
                for task in tasks
            ],
            "teams": [
                _team_eintrag(team, team_nr[team.id], mit_namen) for team in teams
            ],
            "abgaben": abgaben,
        }
        text = json.dumps(inhalt, ensure_ascii=False, indent=2) + "\n"
        zf.writestr(JSON_NAME, text.encode("utf-8"))

    datei.seek(0)
    return datei, {"teams": len(teams), "aufgaben": len(tasks),
                   "abgaben": len(abgaben), "fehlend": fehlend}


def _team_eintrag(team, nr, mit_namen):
    eintrag = {"nr": nr, "name": team.name}
    if mit_namen:
        eintrag["namen"] = team.member_list
        eintrag["namen_freigegeben"] = bool(team.members_approved)
    return eintrag


# ------------------------------------------------------------------ Einlesen

def _datum(wert):
    if not wert:
        return None
    try:
        return datetime.fromisoformat(str(wert))
    except ValueError:
        return None


def _ganzzahl(wert):
    if wert is None or isinstance(wert, bool):
        return None
    try:
        return int(wert)
    except (TypeError, ValueError):
        return None


def _liste(daten, schluessel):
    wert = daten.get(schluessel, [])
    if not isinstance(wert, list):
        raise SicherungFehler(f"„{schluessel}“ muss eine Liste sein.")
    return [eintrag for eintrag in wert if isinstance(eintrag, dict)]


def _inhalt_lesen(zf):
    """Die wettbewerb.json aus der ZIP, geprüft auf Format und Größe."""
    try:
        info = zf.getinfo(JSON_NAME)
    except KeyError:
        raise SicherungFehler(
            f"In der ZIP fehlt die Datei {JSON_NAME}. Ist das eine Sicherung "
            "eines ganzen Wettbewerbs? Eine Aufgaben-Datei (.json) wird auf der "
            "Aufgaben-Seite eingelesen.")

    if info.file_size > MAX_JSON_BYTES:
        raise SicherungFehler(f"{JSON_NAME} ist unerwartet groß.")

    try:
        daten = json.loads(zf.read(info).decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise SicherungFehler(f"{JSON_NAME} ist keine gültige JSON-Datei.")

    if not isinstance(daten, dict) or daten.get("format") != FORMAT_NAME:
        raise SicherungFehler("Die Datei ist keine Sicherung eines Wettbewerbs.")

    version = _ganzzahl(daten.get("version"))
    if version is None or version > FORMAT_VERSION:
        raise SicherungFehler(
            "Die Sicherung stammt aus einer neueren Fassung der Plattform. "
            "Erst die Plattform aktualisieren, dann einlesen.")

    return daten


def sicherung_einlesen(dateiobjekt, upload_ordner):
    """Legt aus der ZIP einen neuen, inaktiven Wettbewerb an.

    Gibt (challenge, zahlen, hinweise) zurück. Wirft SicherungFehler, wenn
    die Datei nicht passt; dann ist nichts angelegt und keine Datei
    geschrieben.
    """
    try:
        zf = zipfile.ZipFile(dateiobjekt)
    except (zipfile.BadZipFile, OSError):
        raise SicherungFehler("Die Datei ist keine ZIP-Datei.")

    geschrieben = []
    try:
        with zf:
            daten = _inhalt_lesen(zf)
            ergebnis = _anlegen(zf, daten, upload_ordner, geschrieben)
        db.session.commit()
        return ergebnis
    except BaseException:
        db.session.rollback()
        for pfad in geschrieben:
            try:
                os.remove(pfad)
            except OSError:
                pass
        raise


def _anlegen(zf, daten, upload_ordner, geschrieben):
    hinweise = []

    wettbewerb = daten.get("wettbewerb")
    if not isinstance(wettbewerb, dict):
        raise SicherungFehler("In der Sicherung steht kein Wettbewerb.")

    titel = str(wettbewerb.get("titel") or "").strip()[:MAX_TITEL]
    if not titel:
        raise SicherungFehler("Der Wettbewerb in der Sicherung hat keinen Namen.")

    aufgaben = _liste(daten, "aufgaben")
    teams = _liste(daten, "teams")
    abgaben = _liste(daten, "abgaben")

    if len(aufgaben) > MAX_TASKS:
        raise SicherungFehler(f"Die Sicherung enthält mehr als {MAX_TASKS} Aufgaben.")
    if len(teams) > MAX_TEAMS:
        raise SicherungFehler(f"Die Sicherung enthält mehr als {MAX_TEAMS} Teams.")

    # Vor dem ersten Schreiben: Passt alles, was ausgepackt würde, auf die
    # Platte? Die Angaben stehen im Verzeichnis der ZIP.
    gesamt = sum(info.file_size for info in zf.infolist())
    if gesamt > MAX_GESAMT_BYTES:
        raise SicherungFehler("Ausgepackt wäre die Sicherung zu groß.")

    challenge = Challenge(
        title=titel,
        tagline=str(wettbewerb.get("untertitel") or "").strip()[:MAX_UNTERTITEL],
        start_time=_datum(wettbewerb.get("start")),
        end_time=_datum(wettbewerb.get("ende")),
        # Nie aktiv: Ein eingelesener Wettbewerb soll nicht unbemerkt den
        # laufenden ablösen. Aktivieren geht wie bei jedem anderen.
        active=False,
        paused=bool(wettbewerb.get("pausiert")),
        paused_at=_datum(wettbewerb.get("pausiert_seit")),
    )
    if challenge.paused and not challenge.paused_at:
        challenge.paused = False
    db.session.add(challenge)
    db.session.flush()

    task_zu = {}
    for eintrag in aufgaben:
        werte, meldungen, problem = clean_task_values(
            eintrag.get("titel"), eintrag.get("beschreibung"),
            eintrag.get("punkte", 0), eintrag.get("dateiformat"),
            eintrag.get("hinweis"), eintrag.get("schwierigkeit"))
        if problem:
            hinweise.append(f"Aufgabe {eintrag.get('nr')}: übersprungen")
            continue
        hinweise.extend(meldungen)
        task = Task(challenge_id=challenge.id,
                    hint_visible=bool(eintrag.get("hinweis_sichtbar")), **werte)
        db.session.add(task)
        task_zu[_ganzzahl(eintrag.get("nr"))] = task

    team_zu = {}
    vergeben = set()
    for eintrag in teams:
        name = " ".join(str(eintrag.get("name") or "").split())[:MAX_TEAMNAME]
        if not name or name in vergeben:
            hinweise.append(f"Team {eintrag.get('nr')}: ohne Namen oder doppelt, übersprungen")
            continue
        vergeben.add(name)

        team = Team(challenge_id=challenge.id, name=name)
        namen = eintrag.get("namen")
        if isinstance(namen, list):
            liste = parse_member_names("\n".join(str(n) for n in namen))[:MAX_MEMBERS]
            team.member_names = format_member_names(liste) or None
            team.members_approved = bool(eintrag.get("namen_freigegeben")) and bool(liste)
        db.session.add(team)
        team_zu[_ganzzahl(eintrag.get("nr"))] = team

    # Die Nummern braucht der Ablageort der Dateien.
    db.session.flush()

    namen_in_zip = set(zf.namelist())
    belegt = set()
    zahlen = {"teams": len(team_zu), "aufgaben": len(task_zu), "abgaben": 0,
              "ohne_datei": 0}

    for eintrag in abgaben:
        team = team_zu.get(_ganzzahl(eintrag.get("team")))
        task = task_zu.get(_ganzzahl(eintrag.get("aufgabe")))
        if team is None or task is None or (team.id, task.id) in belegt:
            continue
        belegt.add((team.id, task.id))

        pfad = _datei_auspacken(zf, eintrag.get("datei"), namen_in_zip,
                                upload_ordner, team, task, geschrieben)
        if pfad is None:
            zahlen["ohne_datei"] += 1
            # Die Spalte darf nicht leer sein. Ein Pfad, unter dem nichts
            # liegt, verhält sich wie eine Abgabe, deren Datei verloren ging:
            # Punkte und Feedback bleiben, der Download meldet „nicht da“.
            pfad = os.path.join(upload_ordner, str(team.id),
                                f"task_{task.id}_fehlt{task.allowed_extension}")

        punkte = _ganzzahl(eintrag.get("punkte"))
        if punkte is not None:
            punkte = max(0, min(punkte, task.max_points or 0))

        db.session.add(Submission(
            team_id=team.id,
            task_id=task.id,
            filename=pfad,
            timestamp=_datum(eintrag.get("zeit")) or datetime.now(),
            points=punkte,
            feedback=str(eintrag.get("feedback") or "")[:MAX_FEEDBACK] or None,
            resubmit_allowed=bool(eintrag.get("nachreichen_erlaubt")),
        ))
        zahlen["abgaben"] += 1

    return challenge, zahlen, hinweise


def _datei_auspacken(zf, name, namen_in_zip, upload_ordner, team, task, geschrieben):
    """Schreibt eine Abgabe aus der ZIP an ihren Platz und gibt den Pfad zurück.

    Der Name aus der ZIP bestimmt nur, welcher Eintrag gelesen wird. Wohin
    geschrieben wird, steht hier: in den Ordner des Teams, benannt wie beim
    Hochladen. So kann keine Datei aus der Sicherung anderswo landen.
    """
    if not isinstance(name, str) or name not in namen_in_zip:
        return None

    info = zf.getinfo(name)
    if info.is_dir() or info.file_size > MAX_DATEI_BYTES:
        return None

    dateiname = secure_filename(os.path.basename(name))
    # Beim Sichern trägt der Name schon das „task_<alte Nummer>_“ vom
    # Hochladen. Das fällt weg, die neue Nummer kommt davor.
    if dateiname.startswith("task_"):
        dateiname = dateiname.split("_", 2)[-1]
    dateiname = (dateiname or "abgabe")[:100]

    ordner = os.path.join(upload_ordner, str(team.id))
    os.makedirs(ordner, exist_ok=True)
    pfad = os.path.join(ordner, f"task_{task.id}_{dateiname}")

    with zf.open(info) as quelle, open(pfad, "wb") as ziel:
        geschrieben.append(pfad)
        ziel.write(quelle.read(MAX_DATEI_BYTES + 1)[:MAX_DATEI_BYTES])

    return pfad
