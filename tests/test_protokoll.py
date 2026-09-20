"""Prüft die Protokolldatei.

Sie ist dafür da, dass eine Störung am Wettbewerbstag nachvollziehbar
bleibt, auch wenn niemand das Terminalfenster im Blick hatte.
"""

import logging
import os

from app import LOG_HANDLER_NAME, configure_logging


def logdatei(flask_app):
    return os.path.join(flask_app.config["LOG_DIR"], "anwendung.log")


def inhalt(flask_app):
    pfad = logdatei(flask_app)
    if not os.path.exists(pfad):
        return ""
    with open(pfad, encoding="utf-8") as datei:
        return datei.read()


class TestEinrichtung:
    def test_datei_wird_angelegt(self, flask_app):
        flask_app.logger.info("Prüfzeile")
        assert os.path.exists(logdatei(flask_app))

    def test_schreibt_nicht_in_die_laufende_installation(self, flask_app):
        # Wäre LOG_DIR nicht umgebogen, liefe dieser Test in logs/ des Repos.
        assert flask_app.config["LOG_DIR"].startswith(os.path.dirname(
            flask_app.config["UPLOAD_FOLDER"]))

    def test_zweiter_aufruf_haengt_keinen_zweiten_handler_an(self, flask_app):
        vorher = [h for h in flask_app.logger.handlers if h.name == LOG_HANDLER_NAME]
        configure_logging(flask_app)
        nachher = [h for h in flask_app.logger.handlers if h.name == LOG_HANDLER_NAME]
        assert len(vorher) == len(nachher) == 1

    def test_datei_rotiert_statt_unbegrenzt_zu_wachsen(self, flask_app):
        handler = next(h for h in flask_app.logger.handlers if h.name == LOG_HANDLER_NAME)
        assert handler.maxBytes > 0
        assert handler.backupCount > 0

    def test_waitress_meldungen_landen_in_derselben_datei(self, flask_app):
        handler = next(h for h in flask_app.logger.handlers if h.name == LOG_HANDLER_NAME)
        assert handler in logging.getLogger("waitress").handlers


class TestInhalt:
    def test_meldung_steht_mit_zeitstempel_in_der_datei(self, flask_app):
        flask_app.logger.warning("Testmeldung 12345")
        text = inhalt(flask_app)
        assert "Testmeldung 12345" in text
        # Ohne Zeitstempel ist im Nachhinein nicht zuzuordnen, wann es war.
        zeile = [z for z in text.splitlines() if "Testmeldung 12345" in z][-1]
        assert zeile[:4].isdigit(), f"kein Datum am Zeilenanfang: {zeile!r}"
        assert "WARNING" in zeile

    def test_unbehandelter_fehler_wird_protokolliert(self, flask_app, monkeypatch,
                                                      make_challenge):
        """Der eigentliche Zweck: Ein Absturz einer Seite hinterlässt eine Spur.

        Geprüft an einer echten Seite - die Rangliste wird von innen heraus
        zum Scheitern gebracht, statt eine Testroute anzulegen.
        """
        make_challenge(active=True)

        def kaputt(challenge):
            raise RuntimeError("Absicht: kaputte Rangliste")

        monkeypatch.setattr("blueprints.public.get_standings", kaputt)

        # Flask reicht Ausnahmen im Testmodus sonst durch, statt sie zu
        # protokollieren - im echten Betrieb ist es andersherum.
        monkeypatch.setitem(flask_app.config, "PROPAGATE_EXCEPTIONS", False)

        antwort = flask_app.test_client().get("/scoreboard")
        assert antwort.status_code == 500

        text = inhalt(flask_app)
        assert "Absicht: kaputte Rangliste" in text
        assert "Traceback" in text, "ohne Traceback ist die Spur wertlos"
        assert "/scoreboard" in text, "ohne die Adresse ist unklar, wo es knallte"

    def test_normale_seiten_erzeugen_keine_fehlermeldung(self, flask_app):
        vorher = inhalt(flask_app)
        flask_app.test_client().get("/")
        neu = inhalt(flask_app)[len(vorher):]
        assert "ERROR" not in neu
