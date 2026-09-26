"""Die Adresse, unter der die Teams den Server erreichen.

Steht hier die falsche Adresse, kommt am Wettbewerbstag niemand auf die
Seite - und gesucht wird der Fehler dann bei der Firewall. Zwei Fälle sind
deshalb festgehalten: der Eintrag von Hand, und das Netz, in dem sich die
Adresse nicht erfragen lässt.
"""

import socket

import pytest

import network
from app import startmeldung
from network import (
    FESTE_ADRESSE,
    PORT_EINTRAG,
    STANDARD_PORT,
    eingetragene_adresse,
    join_url,
    lan_adresse,
    server_port,
)


@pytest.fixture
def ohne_erkennung(monkeypatch):
    """Ein Netz ohne Standardroute: Die Erkennung findet nichts."""
    monkeypatch.setattr(network, "ermittelte_adresse", lambda: None)


@pytest.fixture
def mit_erkennung(monkeypatch):
    monkeypatch.setattr(network, "ermittelte_adresse", lambda: "192.168.1.50")


class TestEingetrageneAdresse:
    def test_der_eintrag_sticht_die_erkennung(self, monkeypatch, mit_erkennung):
        """Wer die Adresse seines Servers kennt, soll sie setzen können."""
        monkeypatch.setenv(FESTE_ADRESSE, "10.0.0.7")

        assert lan_adresse() == "10.0.0.7"

    def test_ohne_eintrag_gilt_die_erkennung(self, monkeypatch, mit_erkennung):
        monkeypatch.delenv(FESTE_ADRESSE, raising=False)

        assert lan_adresse() == "192.168.1.50"

    def test_leerzeichen_ringsum_stoeren_nicht(self, monkeypatch):
        monkeypatch.setenv(FESTE_ADRESSE, "  10.0.0.7  ")

        assert eingetragene_adresse() == "10.0.0.7"

    @pytest.mark.parametrize("wert", ["", "   "])
    def test_ein_leerer_eintrag_zaehlt_nicht(self, monkeypatch, wert):
        monkeypatch.setenv(FESTE_ADRESSE, wert)

        assert eingetragene_adresse() is None

    @pytest.mark.parametrize("wert", ["schulserver", "192.168.1", "192.168.1.300",
                                      "http://192.168.1.50", "192.168.1.50:8000"])
    def test_was_keine_ipv4_adresse_ist_wird_uebergangen(self, monkeypatch, wert):
        """Ein Tippfehler darf nicht stillschweigend in den QR-Code wandern."""
        monkeypatch.setenv(FESTE_ADRESSE, wert)

        assert eingetragene_adresse() is None

    def test_ein_tippfehler_wird_gemeldet(self, monkeypatch, caplog):
        monkeypatch.setenv(FESTE_ADRESSE, "schulserver")

        with caplog.at_level("WARNING"):
            eingetragene_adresse()

        assert FESTE_ADRESSE in caplog.text
        assert "schulserver" in caplog.text


class TestErmittelteAdresse:
    def test_ohne_route_kommt_nichts_zurueck(self, monkeypatch):
        """Ein Netz ohne Gateway: Die Frage lässt sich nicht beantworten.

        Ein zweites öffentliches Ziel hülfe hier nicht - es liefe über
        dieselbe fehlende Route.
        """
        class TaubeSocket:
            def connect(self, ziel):
                raise OSError(101, "Network is unreachable")

            def close(self):
                pass

        monkeypatch.setattr(socket, "socket", lambda *a, **k: TaubeSocket())

        assert network.ermittelte_adresse() is None

    def test_der_socket_wird_auch_im_fehlerfall_geschlossen(self, monkeypatch):
        geschlossen = []

        class TaubeSocket:
            def connect(self, ziel):
                raise OSError(101, "Network is unreachable")

            def close(self):
                geschlossen.append(True)

        monkeypatch.setattr(socket, "socket", lambda *a, **k: TaubeSocket())
        network.ermittelte_adresse()

        assert geschlossen


class TestWennNichtsBekanntIst:
    def test_lan_adresse_gibt_nichts_vor(self, monkeypatch, ohne_erkennung):
        """None heißt: unbekannt. Das soll der Aufrufer sagen können."""
        monkeypatch.delenv(FESTE_ADRESSE, raising=False)

        assert lan_adresse() is None

    def test_get_local_ip_hat_trotzdem_einen_wert(self, monkeypatch, ohne_erkennung):
        monkeypatch.delenv(FESTE_ADRESSE, raising=False)

        assert network.get_local_ip() == "127.0.0.1"

    def test_die_startmeldung_nennt_den_eintrag_statt_einer_falschen_adresse(self):
        meldung = "\n".join(startmeldung(None, 8000, "logs/anwendung.log"))

        assert "127.0.0.1" not in meldung
        assert FESTE_ADRESSE in meldung
        assert "8000" in meldung

    def test_mit_adresse_steht_sie_in_der_startmeldung(self):
        meldung = "\n".join(startmeldung("192.168.1.50", 8000, "logs/anwendung.log"))

        assert "http://192.168.1.50:8000" in meldung
        assert FESTE_ADRESSE not in meldung

    def test_die_startmeldung_nennt_immer_das_protokoll(self):
        for adresse in (None, "192.168.1.50"):
            meldung = "\n".join(startmeldung(adresse, 8000, "logs/anwendung.log"))
            assert "logs/anwendung.log" in meldung


class TestZusammenspielMitDerStartseite:
    def test_der_eintrag_landet_in_der_beitrittsadresse(self, monkeypatch):
        """Der Weg von der .env bis in den QR-Code, in einem Stück."""
        monkeypatch.setenv(FESTE_ADRESSE, "10.0.0.7")

        assert join_url("http://localhost:8000/") == "http://10.0.0.7:8000/"

    def test_eine_echte_adresse_der_anfrage_bleibt_unangetastet(self, monkeypatch):
        """Kommt die Anfrage von einem anderen Gerät, stimmt sie schon."""
        monkeypatch.setenv(FESTE_ADRESSE, "10.0.0.7")

        assert join_url("http://192.168.1.50:8000/") == "http://192.168.1.50:8000/"


class TestPort:
    """Der Port aus der .env - damit ein zweiter Server daneben Platz hat."""

    def test_ohne_eintrag_bleibt_es_bei_8000(self, monkeypatch):
        monkeypatch.delenv(PORT_EINTRAG, raising=False)

        assert STANDARD_PORT == 8000
        assert server_port() == 8000

    def test_der_eintrag_gilt(self, monkeypatch):
        monkeypatch.setenv(PORT_EINTRAG, " 8002 ")

        assert server_port() == 8002

    @pytest.mark.parametrize("wert", ["", "   "])
    def test_ein_leerer_eintrag_zaehlt_nicht(self, monkeypatch, wert):
        monkeypatch.setenv(PORT_EINTRAG, wert)

        assert server_port() == STANDARD_PORT

    @pytest.mark.parametrize("wert", ["800o", "8000.5", "0", "-1", "65536", ":8000"])
    def test_ein_tippfehler_faellt_auf_den_standard_zurueck(self, monkeypatch, caplog, wert):
        """Der Start soll nicht scheitern, der Fehler aber auffallen."""
        monkeypatch.setenv(PORT_EINTRAG, wert)

        assert server_port() == STANDARD_PORT
        assert PORT_EINTRAG in caplog.text

    def test_der_port_steht_in_der_startmeldung(self):
        meldung = "\n".join(startmeldung("192.168.1.50", 8002, "logs/anwendung.log"))

        assert "http://localhost:8002" in meldung
        assert "http://192.168.1.50:8002" in meldung
