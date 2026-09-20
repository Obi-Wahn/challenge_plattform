"""Die Adresse, unter der die Anwendung im Schulnetz erreichbar ist."""

import socket
from urllib.parse import urlsplit, urlunsplit

# Adressen, die nur auf dem Rechner selbst gelten. Wer die abtippt oder
# scannt, landet auf dem eigenen Gerät statt auf dem Server.
NUR_LOKAL = {"localhost", "127.0.0.1", "::1", "0.0.0.0", "[::1]", "[::]"}


def get_local_ip():
    """Die IP, mit der dieser Rechner ins Netzwerk geht.

    Es wird nichts gesendet - der Socket wird nur verbunden, um vom
    Betriebssystem zu erfahren, welche Adresse es dafür nehmen würde.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


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
