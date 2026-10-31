"""Das Zeichen im Browser-Tab und vor dem Namen in der Leiste.

Es muss im Schul-LAN ohne Internet erscheinen, liegt also selbst in static/
und verweist auf nichts außerhalb.
"""

import re
from pathlib import Path

STATIC = Path(__file__).resolve().parent.parent / "static"


def kopf(client, pfad="/login"):
    html = client.get(pfad).get_data(as_text=True)
    return html[:html.index("</head>")]


class TestDateien:
    def test_alle_drei_liegen_in_static(self):
        for name in ("favicon.svg", "favicon.ico", "apple-touch-icon.png"):
            assert (STATIC / name).stat().st_size > 0, name

    def test_svg_holt_nichts_von_aussen(self):
        """Keine Schrift, kein Bild, kein Verweis - nur die eigene Adresse."""
        svg = (STATIC / "favicon.svg").read_text(encoding="utf-8")
        adressen = re.findall(r"https?://[^\s\"']+", svg)
        assert adressen == ["http://www.w3.org/2000/svg"]
        assert "href" not in svg
        assert "<text" not in svg

    def test_ico_ist_eine_ico(self):
        assert (STATIC / "favicon.ico").read_bytes()[:4] == b"\x00\x00\x01\x00"

    def test_png_fuer_den_startbildschirm(self):
        daten = (STATIC / "apple-touch-icon.png").read_bytes()
        assert daten[:8] == b"\x89PNG\r\n\x1a\n"
        breite = int.from_bytes(daten[16:20], "big")
        hoehe = int.from_bytes(daten[20:24], "big")
        assert (breite, hoehe) == (180, 180)


class TestEinbindung:
    def test_kopf_nennt_alle_drei(self, client):
        html = kopf(client)
        assert 'rel="icon" href="/static/favicon.ico"' in html
        assert 'rel="icon" href="/static/favicon.svg" type="image/svg+xml"' in html
        assert 'rel="apple-touch-icon" href="/static/apple-touch-icon.png"' in html

    def test_leiste_zeigt_das_zeichen_statt_der_rakete(self, client):
        html = client.get("/login").get_data(as_text=True)
        anfang = html.index('class="navbar-brand"')
        marke = html[anfang:html.index("</a>", anfang)]
        assert 'src="/static/favicon.svg"' in marke
        # Rein schmückend: Der Name steht gleich daneben.
        assert 'alt=""' in marke
        assert "🚀" not in marke


class TestAbruf:
    def test_favicon_ico_ohne_404(self, client):
        """Browser fragen /favicon.ico auch ohne Verweis ab."""
        antwort = client.get("/favicon.ico")
        assert antwort.status_code == 200
        assert antwort.mimetype == "image/vnd.microsoft.icon"
        assert antwort.data == (STATIC / "favicon.ico").read_bytes()
        antwort.close()

    def test_svg_wird_als_svg_ausgeliefert(self, client):
        antwort = client.get("/static/favicon.svg")
        assert antwort.status_code == 200
        assert antwort.mimetype == "image/svg+xml"
        antwort.close()
