"""Nach dem Ende führt die Rangliste zum Siegerpodest.

Die Rangliste hängt den ganzen Wettbewerb über am Beamer und lädt sich alle
30 Sekunden neu. Ist der Wettbewerb vorbei, geht es dabei zur Siegerehrung -
und genauso bei jedem neuen Aufruf. Die ganze Rangliste gibt es danach mit
`vollstaendig`, über den Link unter dem Podest.
"""

from datetime import datetime, timedelta


def abgabe(team, task, punkte):
    from extensions import db
    from models import Submission

    db.session.add(Submission(team_id=team.id, task_id=task.id, filename="x.sb3",
                              points=punkte,
                              timestamp=datetime.now() - timedelta(minutes=30)))
    db.session.commit()


def beendet(make_challenge, **kwargs):
    return make_challenge(start_time=datetime.now() - timedelta(minutes=60),
                          end_time=datetime.now() - timedelta(minutes=1), **kwargs)


def laufend(make_challenge, **kwargs):
    return make_challenge(start_time=datetime.now() - timedelta(minutes=5),
                          end_time=datetime.now() + timedelta(minutes=40), **kwargs)


def mit_punkten(challenge, make_task, make_team):
    task = make_task(challenge)
    abgabe(make_team(challenge, name="Füchse"), task, 8)
    abgabe(make_team(challenge, name="Eulen"), task, 5)
    return challenge


def wechselt(client, pfad="/scoreboard"):
    antwort = client.get(pfad)
    if antwort.status_code == 302:
        assert antwort.headers["Location"].endswith("/siegerehrung")
        return True
    assert antwort.status_code == 200
    return False


class TestWannDieRanglisteWechselt:
    def test_nach_dem_ende_zum_podest(self, client, make_challenge, make_task, make_team):
        """Auch wenn die Rangliste erst nach dem Ende geöffnet wird."""
        mit_punkten(beendet(make_challenge), make_task, make_team)
        assert wechselt(client)

    def test_die_offene_rangliste_laedt_sich_neu(self, client, make_challenge):
        """Das Neuladen alle 30 Sekunden bringt den Beamer zum Podest."""
        laufend(make_challenge)
        html = client.get("/scoreboard").get_data(as_text=True)
        assert "location.reload()" in html

    def test_nicht_solange_der_wettbewerb_laeuft(self, client, make_challenge,
                                                 make_task, make_team):
        mit_punkten(laufend(make_challenge), make_task, make_team)
        assert not wechselt(client)

    def test_nicht_in_der_pause(self, client, make_challenge, make_task, make_team):
        challenge = laufend(make_challenge, paused=True, paused_at=datetime.now())
        mit_punkten(challenge, make_task, make_team)
        assert not wechselt(client)

    def test_ohne_punkte_bleibt_die_rangliste(self, client, make_challenge, make_team):
        """Ein leeres Podest wäre nichts zum Verkünden - es geht mit dem
        ersten bewerteten Punkt weiter."""
        challenge = beendet(make_challenge)
        make_team(challenge, name="Füchse")
        antwort = client.get("/scoreboard")
        assert antwort.status_code == 200
        assert "location.reload()" in antwort.get_data(as_text=True)

    def test_vollstaendig_bleibt_die_rangliste(self, client, make_challenge,
                                               make_task, make_team):
        mit_punkten(beendet(make_challenge), make_task, make_team)
        antwort = client.get("/scoreboard?vollstaendig=1")
        assert antwort.status_code == 200
        assert "Füchse" in antwort.get_data(as_text=True)

    def test_ohne_aktiven_wettbewerb_keine_umleitung(self, client):
        assert client.get("/scoreboard").status_code == 200


class TestEingefroren:
    def eingefroren(self, make_challenge, make_task, make_team):
        challenge = beendet(make_challenge, freeze_enabled=True, freeze_minutes=15)
        mit_punkten(challenge, make_task, make_team)
        assert challenge.scoreboard_frozen
        return challenge

    def test_am_geraet_ohne_anmeldung_bleibt_die_rangliste(self, client, make_challenge,
                                                          make_task, make_team):
        """Das Podest verriete dort sonst den Stand, den die Siegerehrung
        verkünden soll - und zeigte ohnehin nur den Hinweis aufs Einfrieren."""
        self.eingefroren(make_challenge, make_task, make_team)
        assert not wechselt(client)

    def test_bei_der_angemeldeten_lehrkraft_zum_podest(self, admin, make_challenge,
                                                       make_task, make_team):
        self.eingefroren(make_challenge, make_task, make_team)
        assert wechselt(admin)

    def test_nach_dem_aufloesen_ueberall(self, client, make_challenge, make_task, make_team):
        from extensions import db

        challenge = self.eingefroren(make_challenge, make_task, make_team)
        challenge.scoreboard_revealed = True
        db.session.commit()
        assert wechselt(client)


class TestVonDerSiegerehrungZurRangliste:
    def test_der_link_unter_dem_podest_fuehrt_zur_ganzen_rangliste(
            self, client, make_challenge, make_task, make_team):
        """Ohne `vollstaendig` schickte die Rangliste gleich zurück zum Podest."""
        mit_punkten(beendet(make_challenge), make_task, make_team)
        html = client.get("/siegerehrung").get_data(as_text=True)
        assert 'href="/scoreboard?vollstaendig=1"' in html
        assert not wechselt(client, "/scoreboard?vollstaendig=1")

    def test_nach_dem_aufloesen_zur_ganzen_rangliste(self, admin, make_challenge,
                                                    make_task, make_team):
        from tests.helpers import csrf_token

        challenge = beendet(make_challenge, freeze_enabled=True, freeze_minutes=15)
        mit_punkten(challenge, make_task, make_team)
        html = admin.get("/siegerehrung").get_data(as_text=True)
        assert 'name="next" value="/scoreboard?vollstaendig=1"' in html

        antwort = admin.post(f"/admin/challenges/{challenge.id}/rangliste-aufloesen", data={
            "csrf_token": csrf_token(admin, "/admin/challenges/new"),
            "next": "/scoreboard?vollstaendig=1",
        })
        assert antwort.headers["Location"].endswith("/scoreboard?vollstaendig=1")


class TestDieSiegerehrungHoltSichDenStand:
    def test_neu_laden_bis_zum_ersten_platz(self, client, make_challenge,
                                            make_task, make_team):
        """Nach dem Ende wird oft noch bewertet - bis zum ersten verkündeten
        Platz holt sich die Seite den neuesten Stand."""
        mit_punkten(beendet(make_challenge), make_task, make_team)
        html = client.get("/siegerehrung").get_data(as_text=True)
        assert 'document.querySelector(".podest-spalte.verkuendet")' in html
        assert "location.reload()" in html

    def test_auch_ohne_podest(self, client, make_challenge):
        beendet(make_challenge)
        html = client.get("/siegerehrung").get_data(as_text=True)
        assert "Noch keine bewerteten Abgaben" in html
        assert "location.reload()" in html
