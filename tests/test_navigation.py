"""Die obere Leiste - das Einzige, was auf jeder Seite gleich bleibt.

Ein Eintrag hängt am Stand des Wettbewerbs: die Urkunde, sobald er beendet
ist. Sie führt auf eine Seite, die es vorher schon gab, zu der aber kein
einziger Link zeigte. Die Restzeit steht auf der Wettbewerbsseite selbst,
siehe test_zeitleiste.py.
"""

import re
from datetime import datetime, timedelta


def leiste(client, pfad="/scoreboard"):
    """Nur die Navigationsleiste einer Seite, ohne Kommentare.

    Zweierlei darf hier nicht mitzählen. Der Seiteninhalt nicht: Die
    Wettbewerbsseite verlinkt die Urkunde auch selbst, ein Treffer im ganzen
    HTML sagt also nichts darüber, ob der Eintrag in der Leiste steht. Und
    die Kommentare nicht: In ihnen stehen dieselben Wörter wie in den
    Einträgen, zu sehen bekommt sie aber niemand.
    """
    html = client.get(pfad).get_data(as_text=True)
    anfang = html.index("<nav")
    nav = html[anfang:html.index("</nav>", anfang)]
    return re.sub(r"<!--.*?-->", "", nav, flags=re.DOTALL)


class TestOhneAnmeldung:
    def test_nur_rangliste_und_anmelden(self, client, make_challenge):
        make_challenge(end_time=datetime.now() + timedelta(hours=1))

        nav = leiste(client)

        assert "Rangliste" in nav
        assert "Anmelden" in nav
        assert "Countdown" not in nav
        assert "Urkunde" not in nav


class TestKeinCountdown:
    """Die Restzeit steht auf der Wettbewerbsseite, nicht hinter einem Link.

    Ein Eintrag in der Leiste würde die Teams von genau der Seite wegführen,
    auf der die Zeit jetzt ohnehin steht.
    """

    def test_waehrend_des_wettbewerbs_keiner(self, make_challenge, logged_in_team):
        challenge = make_challenge(start_time=datetime.now() - timedelta(minutes=5),
                                   end_time=datetime.now() + timedelta(hours=1))
        client, _team = logged_in_team(challenge)

        nav = leiste(client)

        assert "Countdown" not in nav
        assert "/start" not in nav

    def test_vor_dem_start_auch_nicht(self, make_challenge, logged_in_team):
        challenge = make_challenge(start_time=datetime.now() + timedelta(hours=1))
        client, _team = logged_in_team(challenge)

        assert "Countdown" not in leiste(client)


class TestUrkunde:
    def test_nach_dem_ende_steht_sie_in_der_leiste(self, make_challenge, logged_in_team):
        challenge = make_challenge(start_time=datetime.now() - timedelta(hours=2),
                                   end_time=datetime.now() - timedelta(minutes=1))
        client, _team = logged_in_team(challenge)

        nav = leiste(client)

        assert "Urkunde" in nav
        assert "/urkunde.pdf" in nav
        assert "Countdown" not in nav

    def test_der_link_gibt_wirklich_ein_pdf_her(self, make_challenge, logged_in_team):
        """Was in der Leiste steht, muss auch funktionieren."""
        challenge = make_challenge(start_time=datetime.now() - timedelta(hours=2),
                                   end_time=datetime.now() - timedelta(minutes=1))
        client, _team = logged_in_team(challenge)

        antwort = client.get("/urkunde.pdf")

        assert antwort.status_code == 200
        assert antwort.mimetype == "application/pdf"


class TestReihenfolge:
    def test_wettbewerb_steht_vor_der_rangliste(self, make_challenge, logged_in_team):
        """Die Seite, auf der Teams arbeiten, kommt zuerst."""
        challenge = make_challenge(end_time=datetime.now() + timedelta(hours=1))
        client, _team = logged_in_team(challenge)

        nav = leiste(client)

        assert nav.index("Wettbewerb") < nav.index("Rangliste")

    def test_abmelden_steht_ganz_hinten(self, make_challenge, logged_in_team):
        challenge = make_challenge(end_time=datetime.now() + timedelta(hours=1))
        client, _team = logged_in_team(challenge)

        nav = leiste(client)

        assert nav.index("Rangliste") < nav.index("Abmelden")
        assert nav.index("Team Blitz") < nav.index("Abmelden")


class TestKlappmenue:
    def test_der_abmelde_knopf_ist_im_stapel_nicht_eingerueckt(self, make_challenge,
                                                               logged_in_team):
        """Unter 992 px stapeln sich die Einträge untereinander.

        Ein Einzug nur am Abmelde-Knopf sähe dort aus wie ein Versehen, auf
        dem Desktop braucht er ihn aber als Abstand zum Teamnamen.
        """
        challenge = make_challenge(end_time=datetime.now() + timedelta(hours=1))
        client, _team = logged_in_team(challenge)

        nav = leiste(client)

        assert "ms-lg-2" in nav
        assert 'class="nav-link btn btn-outline-light btn-sm ms-2"' not in nav
