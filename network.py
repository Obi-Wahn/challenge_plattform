"""Die Adresse, unter der die Anwendung im Schulnetz erreichbar ist."""

import ipaddress
import logging
import os
import socket
from urllib.parse import urlsplit, urlunsplit

# Adressen, die nur auf dem Rechner selbst gelten. Wer die abtippt oder
# scannt, landet auf dem eigenen Gerät statt auf dem Server.
NUR_LOKAL = {"localhost", "127.0.0.1", "::1", "0.0.0.0", "[::1]", "[::]"}

# Eintrag in der .env, mit dem sich die Netzwerkadresse von Hand setzen
# lässt. Er sticht die Erkennung: Wer die Adresse seines Servers kennt,
# soll sie eintragen können, statt sich auf das Raten zu verlassen.
FESTE_ADRESSE = "LAN_ADRESSE"

# Wohin gefragt wird, um die eigene Adresse zu erfahren. Gesendet wird
# nichts - der Socket wird nur verbunden, um vom Betriebssystem zu hören,
# welche Adresse es dafür nähme.
SUCHZIEL = ("8.8.8.8", 80)

_log = logging.getLogger(__name__)


def eingetragene_adresse():
    """Die von Hand in der .env gesetzte Adresse, falls es eine gibt.

    Nur eine IPv4-Adresse wird genommen. Ein Rechnername stünde sonst im
    QR-Code, und die Handys der Schülerinnen und Schüler müssten ihn
    auflösen können - im Schul-WLAN keine sichere Annahme.
    """
    wert = (os.environ.get(FESTE_ADRESSE) or "").strip()
    if not wert:
        return None

    try:
        ipaddress.IPv4Address(wert)
    except ValueError:
        # Ein Tippfehler darf nicht stillschweigend in den QR-Code wandern.
        _log.warning(
            "%s=%r ist keine IPv4-Adresse und wird übergangen.", FESTE_ADRESSE, wert
        )
        return None

    return wert


def ermittelte_adresse():
    """Die Adresse, mit der dieser Rechner ins Netzwerk geht - oder None.

    Das Betriebssystem beantwortet die Frage aus seiner Routing-Tabelle.
    Gibt es keine Standardroute - ein Switch ohne Gateway, wie er in einem
    abgeschotteten Schulnetz vorkommt -, lässt sie sich so nicht
    beantworten. Ein zweites öffentliches Ziel hülfe dagegen nicht: Es
    liefe über dieselbe fehlende Route. Für diesen Fall gibt es
    FESTE_ADRESSE.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(SUCHZIEL)
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


def lan_adresse():
    """Die Adresse für die anderen Geräte im Netz - oder None.

    None heißt: Sie ist nicht bekannt. Der Aufrufer soll das sagen können,
    statt eine Adresse zu nennen, die niemandem nützt.
    """
    return eingetragene_adresse() or ermittelte_adresse()


def get_local_ip():
    """Wie lan_adresse(), aber mit 127.0.0.1 statt None.

    Für die Stellen, die in jedem Fall eine Adresse einsetzen müssen.
    """
    return lan_adresse() or "127.0.0.1"


def join_url(host_url):
    """Die Adresse, die auf der Startseite steht und im QR-Code steckt.

    host_url ist die Adresse, über die *diese* Anfrage kam. Ruft die Lehrkraft
    die Seite auf dem Server selbst auf und beamt sie, stünde dort
    http://localhost:8000 - für die Geräte der Schülerinnen und Schüler
    wertlos. In dem Fall wird die Netzwerkadresse des Rechners eingesetzt.
    """
    teile = urlsplit(host_url)

    if (teile.hostname or "").lower() not in NUR_LOKAL:
        return host_url

    adresse = get_local_ip()
    if teile.port:
        adresse = f"{adresse}:{teile.port}"

    return urlunsplit((teile.scheme, adresse, teile.path or "/", "", ""))
