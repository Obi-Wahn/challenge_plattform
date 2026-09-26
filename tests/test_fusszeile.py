"""Die Fußzeile - der Name der Anwendung und die beiden leisen Links.

Der Link auf das Repository steht neben der Admin-Anmeldung, nicht an der
Zeile mit dem Namen: die soll ruhig bleiben. Im Schul-LAN ist oft kein
Internet, der Link darf also nirgends im Weg stehen.
"""

import re

REPO = "https://github.com/Obi-Wahn/challenge_plattform"


def fusszeile(client, pfad="/"):
    html = client.get(pfad).get_data(as_text=True)
    anfang = html.index("<footer")
    fuss = html[anfang:html.index("</footer>", anfang)]
    return re.sub(r"<!--.*?-->", "", fuss, flags=re.DOTALL)


class TestQuellcodeLink:
    def test_die_fusszeile_verlinkt_das_repository(self, client):
        fuss = fusszeile(client)

        assert "Quellcode auf GitHub" in fuss
        assert REPO in fuss

    def test_der_link_oeffnet_einen_neuen_tab_ohne_opener(self, client):
        fuss = fusszeile(client)

        assert 'target="_blank"' in fuss
        assert 'rel="noopener"' in fuss

    def test_er_steht_hinter_der_admin_anmeldung(self, client):
        fuss = fusszeile(client)

        assert fuss.index("Admin-Anmeldung") < fuss.index("Quellcode auf GitHub")

    def test_die_zeile_mit_dem_namen_bleibt_ohne_link(self, client):
        fuss = fusszeile(client)
        erste_zeile = fuss[:fuss.index("<br>")]

        assert "<a" not in erste_zeile
