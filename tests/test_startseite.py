"""Die erste Seite, die Schülerinnen und Schüler sehen.

Sie muss beides anbieten: den QR-Code fürs Handy und die Adresse zum
Abtippen am PC. Und sie darf nicht die Adresse des Servers selbst zeigen -
sonst landen alle auf ihrem eigenen Gerät.
"""

import pytest

from network import NUR_LOKAL, abtipp_adresse, join_url


class TestBeitrittsAdresse:
    def test_eine_echte_netzwerkadresse_bleibt_stehen(self):
        assert join_url("http://192.168.1.50:8000/") == "http://192.168.1.50:8000/"

    def test_ein_name_bleibt_ebenfalls_stehen(self):
        assert join_url("http://schulserver:8000/") == "http://schulserver:8000/"

    @pytest.mark.parametrize("nur_lokal", ["localhost", "127.0.0.1", "0.0.0.0"])
    def test_lokale_adressen_werden_ersetzt(self, nur_lokal):
        """Sonst steht beim Beamen vom Server aus 'localhost' auf der Wand."""
        ergebnis = join_url(f"http://{nur_lokal}:8000/")

        assert nur_lokal not in ergebnis or ergebnis == "http://127.0.0.1:8000/"
        assert ergebnis.startswith("http://")
        assert ergebnis.endswith(":8000/")

    def test_der_port_bleibt_erhalten(self, monkeypatch):
        import network

        monkeypatch.setattr(network, "get_local_ip", lambda: "192.168.1.50")

        assert network.join_url("http://localhost:8000/") == "http://192.168.1.50:8000/"

    def test_ohne_port_geht_es_auch(self, monkeypatch):
        import network

        monkeypatch.setattr(network, "get_local_ip", lambda: "192.168.1.50")

        assert network.join_url("http://localhost/") == "http://192.168.1.50/"

    def test_die_liste_der_lokalen_adressen_ist_klein_geschrieben(self):
        assert all(a == a.lower() for a in NUR_LOKAL)


class TestAbtippAdresse:
    """Über dem QR-Code steht die Adresse ohne http:// und Schrägstrich.

    Beides ergänzt der Browser, und ohne die acht Zeichen passt die Adresse
    in doppelter Größe auf dieselbe Zeile.
    """

    def test_http_und_schraegstrich_fallen_weg(self):
        assert abtipp_adresse("http://10.100.4.17:8000/") == "10.100.4.17:8000"

    def test_ohne_port_bleibt_die_ip(self):
        assert abtipp_adresse("http://192.168.1.50/") == "192.168.1.50"

    def test_https_bleibt_vollstaendig(self):
        """Ohne Vorsilbe versuchte der Browser womöglich http."""
        assert abtipp_adresse("https://schule.example:8443/") == \
            "https://schule.example:8443/"

    def test_ein_unterordner_bleibt_stehen(self):
        """Läuft die Anwendung hinter einem Pfad, gehört er zur Adresse."""
        assert abtipp_adresse("http://10.0.0.7/wettbewerb/") == "10.0.0.7/wettbewerb/"


class TestSeitenaufbau:
    def test_reihenfolge_gruss_adresse_qr_anmeldung(self, client, make_challenge):
        """Von oben nach unten, wie im Unterricht gebraucht."""
        make_challenge(greeting="Los geht's!")
        html = client.get("/").get_data(as_text=True)

        willkommen = html.index("Los geht")
        adresse = html.index("Adresse eintippen")
        qr = html.index("data:image/png;base64")
        anmeldung = html.index('name="team"')

        assert willkommen < adresse < qr < anmeldung

    def test_die_adresse_steht_zum_abtippen_da(self, client, make_challenge):
        make_challenge()
        html = client.get("/").get_data(as_text=True)

        import re
        treffer = re.search(r'style="--zeichen: (\d+)">([^<]+)</p>', html)
        assert treffer, "Adresse steht nicht auf der Seite"

        # Nach der Zeichenzahl richtet style.css die Schriftgröße aus
        assert int(treffer.group(1)) == len(treffer.group(2))

    def test_der_qr_code_ist_da(self, client, make_challenge):
        make_challenge()

        assert "data:image/png;base64" in client.get("/").get_data(as_text=True)

    def test_qr_code_und_angezeigte_adresse_gehoeren_zusammen(
            self, flask_app, make_challenge, monkeypatch):
        """Beide müssen dieselbe Adresse meinen.

        Der QR-Code trägt sie vollständig, angezeigt wird sie ohne http://
        und Schrägstrich - siehe TestAbtippAdresse.
        """
        import io

        import qrcode

        make_challenge()
        html = flask_app.test_client().get("/").get_data(as_text=True)

        import re
        treffer = re.search(r'class="beitritt-adresse[^"]*"[^>]*>([^<]+)<', html)
        assert treffer, "Adresse steht nicht auf der Seite"
        angezeigt = treffer.group(1).strip()
        assert "://" not in angezeigt

        # Denselben Code noch einmal erzeugen und die Bilder vergleichen
        puffer = io.BytesIO()
        qrcode.make(f"http://{angezeigt}/").save(puffer, format="PNG")
        import base64
        erwartet = base64.b64encode(puffer.getvalue()).decode("ascii")

        assert erwartet in html, "QR-Code zeigt eine andere Adresse als der Text"

    def test_auch_bei_einer_fehlermeldung_bleibt_alles_stehen(
            self, client, make_challenge, token):
        """Wer sich vertippt, soll die Adresse nicht verlieren."""
        make_challenge()

        antwort = client.post("/", data={
            "csrf_token": token(client, "/"),
            "team": "", "password": "",
        })
        html = antwort.get_data(as_text=True)

        assert "Bitte Teamname und Passwort angeben" in html
        assert "beitritt-adresse" in html
        assert "data:image/png;base64" in html

    def test_ohne_wettbewerb_steht_die_adresse_auch_da(self, client, database):
        html = client.get("/").get_data(as_text=True)

        assert "beitritt-adresse" in html
