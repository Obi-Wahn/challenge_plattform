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
                                   paused=True,
                                   paused_at=datetime.now())
        client, _team = logged_in_team(challenge)

        leiste = zeitleiste(client)

        assert "Pausiert" in leiste
        assert 'id="restzeit"' in leiste
        assert "die Uhr steht" in leiste

    def test_die_uhr_steht_waehrend_der_pause_still(self, make_challenge, logged_in_team):
        """Sonst liefe die Uhr im Browser dem Server davon.

        Der Server rechnet ab dem Zeitpunkt der Pause. Zählte der Browser
        weiter, zeigte er nach zehn Minuten Pause zehn Minuten zu wenig, und
        nach dem Fortsetzen spränge die Zeit zurück.
        """
        challenge = make_challenge(start_time=datetime.now() - timedelta(minutes=5),
                                   end_time=datetime.now() + timedelta(hours=1),
                                   paused=True,
                                   paused_at=datetime.now())
        client, _team = logged_in_team(challenge)

        html = seite(client)

        assert "const laeuftDieUhr = false;" in html
        # Der Takt läuft nur, wenn die Uhr laufen darf.
        assert "if (laeuftDieUhr)" in html

    def test_ohne_pause_laeuft_der_takt(self, make_challenge, logged_in_team):
        challenge = make_challenge(start_time=datetime.now() - timedelta(minutes=5),
                                   end_time=datetime.now() + timedelta(hours=1))
        client, _team = logged_in_team(challenge)

        assert "const laeuftDieUhr = true;" in seite(client)

    def test_die_restzeit_der_pause_ist_die_eingefrorene(self, make_challenge,
                                                         logged_in_team):
        """Zehn Minuten Pause dürfen den Teams keine zehn Minuten kosten."""
        challenge = make_challenge(start_time=datetime.now() - timedelta(minutes=20),
                                   end_time=datetime.now() + timedelta(minutes=40),
                                   paused=True,
                                   paused_at=datetime.now() - timedelta(minutes=10))
        client, _team = logged_in_team(challenge)

        # Bei der Pause waren es 50 Minuten, und dabei bleibt es.
        assert 2990 < sekunden_im_skript(client) <= 3000


class TestNeuladenNurWennNichtsUnterwegsIst:
    """Der frühere Auto-Refresh brach laufende Abgaben ab und wurde deshalb
    ausgebaut. Die Standabfrage lädt wieder neu, aber nur hinter einer Prüfung:
    keine abgeschickte Abgabe, keine ausgewählte Datei, keine ungespeicherten
    Namen. Die Uhr selbst lädt nie neu - sie weiß nichts davon, wie der Server
    die Zeit sieht.
    """

    def test_es_gibt_nur_eine_stelle_die_neu_laedt(self, make_challenge, logged_in_team):
        """Eine zweite wäre die, die die Prüfung umgeht."""
        challenge = make_challenge(start_time=datetime.now() - timedelta(minutes=5),
                                   end_time=datetime.now() + timedelta(seconds=30))
        client, _team = logged_in_team(challenge)

        html = re.sub(r"<!--.*?-->", "", seite(client), flags=re.DOTALL)

        assert html.count("location.reload") == 1

    def test_die_uhr_selbst_laedt_nicht_neu(self, make_challenge, logged_in_team):
        """Bei null steht dort nur, dass es so weit ist."""
        challenge = make_challenge(start_time=datetime.now() - timedelta(minutes=5),
                                   end_time=datetime.now() + timedelta(seconds=30))
        client, _team = logged_in_team(challenge)

        html = re.sub(r"<!--.*?-->", "", seite(client), flags=re.DOTALL)
        uhrenskript = html.split("let rest =")[1].split("</script>")[0]

        assert "location.reload" not in uhrenskript
        assert 'id="zeitleiste-neu"' in html

    def test_vor_dem_neuladen_wird_geprueft(self, make_challenge, make_task,
                                            logged_in_team):
        """Die drei Dinge, die ein Neuladen kaputt machen würde."""
        challenge = make_challenge(start_time=datetime.now() - timedelta(minutes=5),
                                   end_time=datetime.now() + timedelta(seconds=30))
        make_task(challenge)
        client, _team = logged_in_team(challenge)

        html = re.sub(r"<!--.*?-->", "", seite(client), flags=re.DOTALL)

        assert "darfNeuLaden()" in html
        assert "abgabeLaeuft" in html
        assert "input[type='file']" in html
        assert "member-names" in html
