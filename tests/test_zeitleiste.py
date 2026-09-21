"""Die Zeitleiste auf der Wettbewerbsseite.

Sie zeigt den Stand und die Restzeit dort, wo die Teams ohnehin stehen: bei
ihren Aufgaben. Vorher stand die Zeit nur auf der Countdown-Seite, die für
den Beamer gedacht ist.
"""

import re
from datetime import datetime, timedelta


def seite(client, pfad="/challenge"):
    return client.get(pfad).get_data(as_text=True)


def zeitleiste(client, pfad="/challenge"):
    """Nur die Zeitleiste, ohne den Rest der Seite und ohne Kommentare.

    Beides darf nicht mitzählen. Der Seiteninhalt nicht: Wörter wie „beendet"
    stehen auch unter jedem Abgabeknopf. Und die Kommentare nicht: In ihnen
    stehen dieselben Wörter, zu sehen bekommt sie aber niemand.
    """
    html = re.sub(r"<!--.*?-->", "", seite(client, pfad), flags=re.DOTALL)
    anfang = html.index('<div class="zeitleiste')

    tiefe = 0
    for treffer in re.finditer(r"<div\b|</div>", html[anfang:]):
        tiefe += 1 if treffer.group().startswith("<div") else -1
        if tiefe == 0:
            return html[anfang:anfang + treffer.end()]

    raise AssertionError("Die Zeitleiste wird nicht geschlossen")


def sekunden_im_skript(client, pfad="/challenge"):
    """Die Sekunden, mit denen der Browser zu zählen beginnt."""
    treffer = re.search(r"let rest = (\d+);", seite(client, pfad))
    return int(treffer.group(1)) if treffer else None


class TestWaehrendDesWettbewerbs:
    def test_stand_und_uhr_stehen_in_der_leiste(self, make_challenge, logged_in_team):
        challenge = make_challenge(start_time=datetime.now() - timedelta(minutes=5),
                                   end_time=datetime.now() + timedelta(hours=1))
        client, _team = logged_in_team(challenge)

        leiste = zeitleiste(client)

        assert "Läuft" in leiste
        assert 'id="restzeit"' in leiste
        assert "verbleibend" in leiste

    def test_die_restzeit_kommt_vom_server(self, make_challenge, logged_in_team):
        """Eine falsch gestellte Uhr auf dem Handy darf die Zeit nicht verschieben."""
        challenge = make_challenge(start_time=datetime.now() - timedelta(minutes=5),
                                   end_time=datetime.now() + timedelta(hours=1))
        client, _team = logged_in_team(challenge)

        assert 3500 < sekunden_im_skript(client) <= 3600

    def test_ohne_endzeit_zeigt_sie_keine_uhr(self, make_challenge, logged_in_team):
        """Ohne Endzeit gibt es nichts herunterzuzählen."""
        challenge = make_challenge(start_time=datetime.now() - timedelta(minutes=5))
        client, _team = logged_in_team(challenge)

        leiste = zeitleiste(client)

        assert "Läuft" in leiste
        assert 'id="restzeit"' not in leiste
        assert "Abgaben sind möglich" in leiste
        assert sekunden_im_skript(client) is None


class TestVorDemStart:
    def test_sie_zaehlt_bis_zum_beginn(self, make_challenge, logged_in_team):
        challenge = make_challenge(start_time=datetime.now() + timedelta(minutes=10),
                                   end_time=datetime.now() + timedelta(hours=2))
        client, _team = logged_in_team(challenge)

        leiste = zeitleiste(client)

        assert "Startet in" in leiste
        assert 'id="restzeit"' in leiste
        assert 500 < sekunden_im_skript(client) <= 600


class TestNachDemEnde:
    def test_beendet_mit_der_urkunde_daneben(self, make_challenge, logged_in_team):
        challenge = make_challenge(start_time=datetime.now() - timedelta(hours=2),
                                   end_time=datetime.now() - timedelta(minutes=1))
        client, _team = logged_in_team(challenge)

        leiste = zeitleiste(client)

        assert "Beendet" in leiste
        assert "/urkunde.pdf" in leiste
        assert 'id="restzeit"' not in leiste


class TestPause:
    def test_die_pause_steht_in_der_leiste(self, make_challenge, logged_in_team):
        challenge = make_challenge(start_time=datetime.now() - timedelta(minutes=5),
                                   end_time=datetime.now() + timedelta(hours=1),
                                   paused=True)
        client, _team = logged_in_team(challenge)

        leiste = zeitleiste(client)

        assert "Pausiert" in leiste
        # Die Uhr läuft weiter: Das Ende rückt auch während einer Pause näher.
        assert 'id="restzeit"' in leiste


class TestKeinAutomatischesNeuladen:
    def test_die_seite_laedt_sich_nicht_selbst_neu(self, make_challenge, logged_in_team):
        """Ein Neuladen würde eine laufende Abgabe abbrechen.

        Genau deshalb wurde der Auto-Refresh auf dieser Seite schon einmal
        wieder ausgebaut. Bei null erscheint stattdessen ein Link zum
        Neuladen, den das Team selbst antippt.
        """
        challenge = make_challenge(start_time=datetime.now() - timedelta(minutes=5),
                                   end_time=datetime.now() + timedelta(seconds=30))
        client, _team = logged_in_team(challenge)

        # Ohne die Kommentare: In einem davon steht der Auto-Refresh, der
        # genau deswegen schon einmal stillgelegt wurde.
        html = re.sub(r"<!--.*?-->", "", seite(client), flags=re.DOTALL)

        assert "location.reload" not in html
        assert 'id="zeitleiste-neu"' in html
