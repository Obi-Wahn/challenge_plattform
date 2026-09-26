"""Wichtige Ereignisse für die Protokolldatei logs/anwendung.log.

Geloggt wird, was etwas anlegt, ändert oder wegnimmt - und was schiefgeht.
Der gewöhnliche Betrieb bleibt still: kein Seitenaufruf, keine An- und
Abmeldung eines Teams, keine eingegangene Abgabe, keine einzelne Bewertung.
Sonst wäre die Datei nach einer Schulstunde nicht mehr zu lesen, und genau
dann soll sie gebraucht werden können.

Dass die Zeilen hier durch zwei Funktionen laufen statt einzeln über
``current_app.logger``, hat einen Grund: So steht die Form einer Zeile an
einer Stelle, und es ist im Nachhinein zu sehen, welche Ereignisse die
Anwendung überhaupt festhält - ein Blick auf die Aufrufe von ``ereignis``
genügt.
"""

from flask import current_app, has_app_context, request


def ereignis(vorlage, *werte):
    """Hält ein Ereignis des gewöhnlichen Betriebs fest (INFO).

    Die Werte werden nicht selbst eingesetzt, sondern der Protokollierung
    überlassen: Scheitert das Einsetzen - ein Name mit einem Prozentzeichen
    zum Beispiel -, bleibt das eine Meldung im Protokoll und bringt nicht die
    Seite zu Fall, auf der das Ereignis passierte.
    """
    if has_app_context():
        current_app.logger.info(vorlage, *werte)


def stoerung(vorlage, *werte):
    """Hält etwas fest, das jemand ansehen sollte (WARNING)."""
    if has_app_context():
        current_app.logger.warning(vorlage, *werte)


def absender():
    """Die Adresse des Geräts, von dem die Anfrage kam - oder „unbekannt“."""
    try:
        return request.remote_addr or "unbekannt"
    except RuntimeError: # außerhalb einer Anfrage
        return "unbekannt"
