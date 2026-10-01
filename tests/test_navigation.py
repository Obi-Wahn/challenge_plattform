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



class TestSymbole:
    """Jeder Eintrag trägt ein Zeichen, das Auge findet ihn daran schneller.

    Wo es geht, dasselbe wie über der Seite, zu der er führt: 🔐 steht auch
    über der Team-Anmeldung, 🔓 am Abmelde-Knopf der Steuerzentrale und 👥
    über „Teams verwalten".
    """

    def test_ohne_anmeldung(self, client, make_challenge):
        make_challenge(end_time=datetime.now() + timedelta(hours=1))

        nav = leiste(client)

        assert "🏆 Rangliste" in nav
        assert "🔐 Anmelden" in nav

    def test_mit_anmeldung(self, make_challenge, logged_in_team):
        challenge = make_challenge(end_time=datetime.now() + timedelta(hours=1))
        client, _team = logged_in_team(challenge)

        nav = leiste(client)

        assert "🧩 Wettbewerb" in nav
        assert "👥 Team Blitz" in nav
        assert "🔓 Abmelden" in nav

    def test_anmeldeknoepfe(self, client, make_challenge):
        """Auch der Knopf, der die Anmeldung abschickt, trägt das Schloss."""
        # Ohne aktiven Wettbewerb zeigt die Team-Anmeldung kein Formular.
        make_challenge(end_time=datetime.now() + timedelta(hours=1))

        for pfad in ("/login", "/admin/login"):
            html = client.get(pfad).get_data(as_text=True)
            knopf = html[html.index('<button type="submit"'):]
            knopf = knopf[:knopf.index("</button>")]

            assert "🔐 Anmelden" in knopf, pfad

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


class TestZurueckOben:
    """Der Weg zurück steht auch über der Überschrift, nicht nur ganz unten.

    Auf langen Seiten wie Bewertungen oder Einstellungen musste man sonst
    erst bis ans Ende scrollen. Der untere Link bleibt für den, der schon
    unten ist.
    """

    @staticmethod
    def seiten(cid):
        steuerzentrale = "/admin/dashboard"
        wettbewerb = f"/admin/wettbewerb/{cid}"
        return [
            (f"/admin/wettbewerb/{cid}", steuerzentrale, "← zurück zur Steuerzentrale"),
            ("/admin/challenges/new", steuerzentrale, "← zurück zur Steuerzentrale"),
            ("/admin/submissions", steuerzentrale, "← zurück zur Steuerzentrale"),
            ("/admin/teams", steuerzentrale, "← zurück zur Steuerzentrale"),
            ("/admin/settings", steuerzentrale, "← zurück zur Steuerzentrale"),
            (f"/admin/challenges/{cid}/edit", wettbewerb, "← zurück zum Wettbewerb"),
            (f"/admin/challenges/{cid}/tasks", wettbewerb, "← zurück zum Wettbewerb"),
        ]

    @staticmethod
    def inhalt(admin, pfad):
        """Der Seiteninhalt ohne Leiste und ohne Kommentare."""
        html = admin.get(pfad).get_data(as_text=True)
        html = html[html.index("</nav>"):]
        return re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)

    def test_oben_und_unten(self, admin, make_challenge):
        challenge = make_challenge()

        for pfad, ziel, text in self.seiten(challenge.id):
            html = self.inhalt(admin, pfad)
            links = [m.start() for m in re.finditer(
                rf'<a href="{re.escape(ziel)}"[^>]*>\s*{text}\s*</a>', html)]
            # Die Wettbewerbsseite trägt im Kopf eine Karte statt einer
            # Überschrift - dort zählt, dass der Link vor ihr steht.
            kopf = re.search(r'<h[12]|class="event-card', html).start()

            assert len(links) == 2, pfad
            assert links[0] < kopf, pfad
