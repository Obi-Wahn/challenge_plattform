"""Die erste Seite, die Schülerinnen und Schüler sehen.

Sie muss beides anbieten: den QR-Code fürs Handy und die Adresse zum
Abtippen am PC. Und sie darf nicht die Adresse des Servers selbst zeigen -
sonst landen alle auf ihrem eigenen Gerät.
"""

import pytest

from network import NUR_LOKAL, join_url


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


class TestSeitenaufbau:
    def test_reihenfolge_willkommen_qr_adresse_anmeldung(self, client, make_challenge):
        """Von oben nach unten, wie im Unterricht gebraucht."""
        make_challenge()
        html = client.get("/").get_data(as_text=True)

        willkommen = html.index("Willkommen!")
        qr = html.index("data:image/png;base64")
        adresse = html.index("Adresse eintippen")
        anmeldung = html.index('name="team"')

        assert willkommen < qr < adresse < anmeldung

    def test_die_adresse_steht_zum_abtippen_da(self, client, make_challenge):
        make_challenge()
        html = client.get("/").get_data(as_text=True)

        assert "beitritt-adresse" in html
        assert "http://" in html

    def test_der_qr_code_ist_da(self, client, make_challenge):
        make_challenge()

        assert "data:image/png;base64" in client.get("/").get_data(as_text=True)

    def test_qr_code_und_angezeigte_adresse_gehoeren_zusammen(
            self, flask_app, make_challenge, monkeypatch):
        """Beide müssen dieselbe Adresse meinen."""
        import io

        import qrcode

        make_challenge()
        html = flask_app.test_client().get("/").get_data(as_text=True)

        import re
        treffer = re.search(r'class="beitritt-adresse[^"]*">([^<]+)<', html)
        assert treffer, "Adresse steht nicht auf der Seite"
        angezeigt = treffer.group(1).strip()

        # Denselben Code noch einmal erzeugen und die Bilder vergleichen
        puffer = io.BytesIO()
        qrcode.make(angezeigt).save(puffer, format="PNG")
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
