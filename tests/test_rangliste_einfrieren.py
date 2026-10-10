"""Die Rangliste vor Schluss einfrieren.

Je Wettbewerb an- und abschaltbar, mit einstellbaren Minuten vor Schluss. Ab
dann zeigt die Rangliste am Beamer nur, was bis dahin abgegeben war. Die
eigenen Punkte eines Teams bleiben auf seiner Seite immer aktuell, den echten
Stand verkündet die Siegerehrung, und erst nach dem Auflösen gibt es die
Urkunden - auf denen steht der Platz.
"""

from datetime import datetime, timedelta

from tests.helpers import csrf_token


def frisch(challenge):
    from extensions import db
    from models import Challenge

    db.session.expire_all()
    return db.session.get(Challenge, challenge.id)


def abgabe(team, task, punkte, vor_minuten):
    """Eine bewertete Abgabe, die vor `vor_minuten` Minuten hochgeladen wurde."""
    from extensions import db
    from models import Submission

    eintrag = Submission(team_id=team.id, task_id=task.id, filename="x.sb3",
                         points=punkte,
                         timestamp=datetime.now() - timedelta(minutes=vor_minuten))
    db.session.add(eintrag)
    db.session.commit()
    return eintrag


def posten(admin, pfad, daten=None):
    daten = dict(daten or {})
    daten["csrf_token"] = csrf_token(admin, "/admin/challenges/new")
    return admin.post(pfad, data=daten, follow_redirects=True)


def gesamt_auf_der_rangliste(client, teamname):
    """Die Gesamtpunkte eines Teams, wie sie am Beamer stehen.

    Nach dem Ende führt /scoreboard zum Podest; die ganze Rangliste gibt es
    dann mit `vollstaendig`, wie über den Link unter dem Podest.
    """
    import re

    html = client.get("/scoreboard?vollstaendig=1").get_data(as_text=True)
    zeile = html.split(teamname, 1)[1].split("</tr>", 1)[0]
    return int(re.findall(r'ranglisten-gesamt[^>]*>\s*(\d+)', zeile)[0])


def laufender_wettbewerb(make_challenge, minuten_bis_ende=10, **kwargs):
    """Läuft seit 80 Minuten, friert 15 Minuten vor Schluss ein."""
    kwargs.setdefault("freeze_enabled", True)
    kwargs.setdefault("freeze_minutes", 15)
    return make_challenge(
        start_time=datetime.now() - timedelta(minutes=80),
        end_time=datetime.now() + timedelta(minutes=minuten_bis_ende),
        **kwargs,
    )


class TestWannEingefrorenIst:
    def test_ausgeschaltet_friert_nichts_ein(self, make_challenge):
        challenge = laufender_wettbewerb(make_challenge, freeze_enabled=False)
        assert challenge.freeze_point is None
        assert not challenge.scoreboard_frozen

    def test_ein_neuer_wettbewerb_friert_nicht_ein(self, make_challenge):
        """Standard ist aus - wer es will, schaltet es je Wettbewerb ein."""
        challenge = make_challenge(end_time=datetime.now() - timedelta(minutes=1))
        assert challenge.freeze_enabled is False
        assert not challenge.scoreboard_frozen

    def test_ab_den_minuten_vor_schluss_ist_eingefroren(self, make_challenge):
        challenge = laufender_wettbewerb(make_challenge, minuten_bis_ende=10)
        assert challenge.scoreboard_frozen

    def test_davor_noch_nicht(self, make_challenge):
        challenge = laufender_wettbewerb(make_challenge, minuten_bis_ende=20)
        assert not challenge.scoreboard_frozen

    def test_die_minuten_sind_einstellbar(self, make_challenge):
        challenge = laufender_wettbewerb(make_challenge, minuten_bis_ende=20,
                                         freeze_minutes=30)
        assert challenge.scoreboard_frozen

    def test_ohne_endzeit_gibt_es_kein_vor_schluss(self, make_challenge):
        challenge = make_challenge(start_time=datetime.now(), freeze_enabled=True)
        assert challenge.freeze_point is None
        assert not challenge.scoreboard_frozen

    def test_nach_dem_ende_bleibt_es_eingefroren_bis_zum_aufloesen(self, make_challenge):
        """Sonst stünde das Ergebnis am Beamer, bevor die Siegerehrung es verkündet."""
        challenge = laufender_wettbewerb(make_challenge, minuten_bis_ende=-5)
        assert challenge.status() == "finished"
        assert challenge.scoreboard_frozen

        challenge.scoreboard_revealed = True
        assert not challenge.scoreboard_frozen


class TestRangliste:
    def test_zaehlt_nur_abgaben_bis_zum_einfrieren(self, client, make_challenge,
                                                    make_task, make_team):
        challenge = laufender_wettbewerb(make_challenge, minuten_bis_ende=10)
        task = make_task(challenge, max_points=10)
        andere = make_task(challenge, title="Zweite", max_points=10)
        team = make_team(challenge, name="Team Frost")
        abgabe(team, task, 7, vor_minuten=30)     # vor dem Einfrieren
        abgabe(team, andere, 9, vor_minuten=2)    # danach

        assert gesamt_auf_der_rangliste(client, "Team Frost") == 7

    def test_spaet_bewertet_zaehlt_trotzdem(self, client, make_challenge,
                                             make_task, make_team):
        """Wer vor dem Einfrieren abgab, verliert nichts, weil die Lehrkraft
        erst danach zum Bewerten kam."""
        from extensions import db

        challenge = laufender_wettbewerb(make_challenge, minuten_bis_ende=10)
        task = make_task(challenge)
        team = make_team(challenge, name="Team Frost")
        eintrag = abgabe(team, task, None, vor_minuten=30)

        eintrag.points = 8   # jetzt bewertet, also nach dem Einfrieren
        db.session.commit()

        assert gesamt_auf_der_rangliste(client, "Team Frost") == 8

    def test_zeigt_den_hinweis(self, client, make_challenge):
        laufender_wettbewerb(make_challenge, minuten_bis_ende=10)
        html = client.get("/scoreboard").get_data(as_text=True)
        assert "❄️ Eingefroren seit" in html

    def test_ausgeschaltet_zaehlt_alles(self, client, make_challenge, make_task, make_team):
        challenge = laufender_wettbewerb(make_challenge, freeze_enabled=False)
        task = make_task(challenge)
        team = make_team(challenge, name="Team Frost")
        abgabe(team, task, 9, vor_minuten=2)

        assert gesamt_auf_der_rangliste(client, "Team Frost") == 9
        assert "Eingefroren" not in client.get("/scoreboard").get_data(as_text=True)

    def test_auch_die_lehrkraft_sieht_am_beamer_den_eingefrorenen_stand(
            self, admin, make_challenge, make_task, make_team):
        """Der Beamer hängt meist am Rechner der Lehrkraft."""
        challenge = laufender_wettbewerb(make_challenge, minuten_bis_ende=10)
        task = make_task(challenge)
        team = make_team(challenge, name="Team Frost")
        abgabe(team, task, 9, vor_minuten=2)

        assert gesamt_auf_der_rangliste(admin, "Team Frost") == 0

    def test_aufgeloest_zeigt_sie_den_echten_stand(self, admin, client, make_challenge,
                                                     make_task, make_team):
        challenge = laufender_wettbewerb(make_challenge, minuten_bis_ende=-5)
        task = make_task(challenge)
        team = make_team(challenge, name="Team Frost")
        abgabe(team, task, 9, vor_minuten=7)

        assert gesamt_auf_der_rangliste(client, "Team Frost") == 0
        posten(admin, f"/admin/challenges/{challenge.id}/rangliste-aufloesen")
        assert gesamt_auf_der_rangliste(client, "Team Frost") == 9


class TestEigenePunkte:
    def test_die_teamseite_zeigt_immer_den_aktuellen_stand(
            self, make_challenge, make_task, logged_in_team):
        """Eingefroren wird nur der Vergleich, nicht was ein Team selbst geschafft hat."""
        challenge = laufender_wettbewerb(make_challenge, minuten_bis_ende=10)
        task = make_task(challenge, title="Katze", max_points=10)
        client, team = logged_in_team(challenge)
        abgabe(team, task, 9, vor_minuten=2)

        html = client.get("/challenge").get_data(as_text=True)
        assert "Abgegeben (9 Punkte)" in html


class TestSiegerehrung:
    def eingefroren_beendet(self, make_challenge, make_task, make_team):
        challenge = laufender_wettbewerb(make_challenge, minuten_bis_ende=-5)
        task = make_task(challenge)
        spaet = make_team(challenge, name="Team Endspurt")
        abgabe(spaet, task, 10, vor_minuten=7)
        return challenge

    def test_die_lehrkraft_sieht_den_echten_stand(self, admin, make_challenge,
                                                  make_task, make_team):
        self.eingefroren_beendet(make_challenge, make_task, make_team)
        html = admin.get("/siegerehrung").get_data(as_text=True)
        assert "Team Endspurt" in html
        assert "Rangliste auflösen" in html

    def test_andere_bekommen_das_podium_nicht_vorab(self, client, make_challenge,
                                                    make_task, make_team):
        """Auch nicht im Quelltext - die Plätze stehen dort sonst nur verborgen."""
        self.eingefroren_beendet(make_challenge, make_task, make_team)
        html = client.get("/siegerehrung").get_data(as_text=True)
        assert "Team Endspurt" not in html
        assert "Die Rangliste ist eingefroren" in html

    def test_nach_dem_aufloesen_sehen_es_alle(self, admin, client, make_challenge,
                                              make_task, make_team):
        challenge = self.eingefroren_beendet(make_challenge, make_task, make_team)
        posten(admin, f"/admin/challenges/{challenge.id}/rangliste-aufloesen")
        html = client.get("/siegerehrung").get_data(as_text=True)
        assert "Team Endspurt" in html
        assert "Rangliste auflösen" not in html


class TestUrkundeDerTeams:
    def test_gibt_es_erst_nach_dem_aufloesen(self, admin, make_challenge, logged_in_team):
        """Auf der Urkunde steht der Platz - den verkündet die Siegerehrung."""
        challenge = laufender_wettbewerb(make_challenge, minuten_bis_ende=-5)
        client, _team = logged_in_team(challenge)

        assert client.get("/urkunde.pdf").status_code == 403
        html = client.get("/challenge").get_data(as_text=True)
        assert "/urkunde.pdf" not in html
        assert "Eure Urkunde gibt es nach der Siegerehrung" in html

        posten(admin, f"/admin/challenges/{challenge.id}/rangliste-aufloesen")
        assert client.get("/urkunde.pdf").status_code == 200
        assert "/urkunde.pdf" in client.get("/challenge").get_data(as_text=True)

    def test_ohne_einfrieren_gleich_nach_dem_ende(self, make_challenge, logged_in_team):
        challenge = laufender_wettbewerb(make_challenge, minuten_bis_ende=-5,
                                         freeze_enabled=False)
        client, _team = logged_in_team(challenge)
        assert client.get("/urkunde.pdf").status_code == 200

    def test_die_offene_teamseite_merkt_das_aufloesen(self, admin, make_challenge,
                                                      logged_in_team):
        """Der Urkunden-Knopf erscheint ohne Neuladen von Hand."""
        challenge = laufender_wettbewerb(make_challenge, minuten_bis_ende=-5)
        client, _team = logged_in_team(challenge)
        vorher = client.get("/challenge/stand").get_json()["stand"]

        posten(admin, f"/admin/challenges/{challenge.id}/rangliste-aufloesen")
        assert client.get("/challenge/stand").get_json()["stand"] != vorher


class TestEinstellen:
    def formular(self, challenge, **mehr):
        daten = {
            "title": challenge.title,
            "tagline": "",
            "start_time": challenge.start_time.strftime("%Y-%m-%dT%H:%M"),
            "end_time": challenge.end_time.strftime("%Y-%m-%dT%H:%M"),
        }
        daten.update(mehr)
        return daten

    def test_einschalten_mit_minuten(self, admin, make_challenge):
        challenge = laufender_wettbewerb(make_challenge, freeze_enabled=False)
        posten(admin, f"/admin/challenges/{challenge.id}/edit",
               self.formular(challenge, freeze_enabled="on", freeze_minutes="20"))

        challenge = frisch(challenge)
        assert challenge.freeze_enabled is True
        assert challenge.freeze_minutes == 20

    def test_ausschalten(self, admin, make_challenge):
        challenge = laufender_wettbewerb(make_challenge)
        posten(admin, f"/admin/challenges/{challenge.id}/edit", self.formular(challenge))
        assert frisch(challenge).freeze_enabled is False

    def test_unsinnige_minuten_werden_abgewiesen(self, admin, make_challenge):
        challenge = laufender_wettbewerb(make_challenge, freeze_enabled=False)
        antwort = posten(admin, f"/admin/challenges/{challenge.id}/edit",
                         self.formular(challenge, title="Neu", freeze_enabled="on",
                                       freeze_minutes="0"))

        assert "größer als null" in antwort.get_data(as_text=True)
        challenge = frisch(challenge)
        assert challenge.freeze_enabled is False
        assert challenge.title != "Neu", "nichts darf halb gespeichert sein"

    def test_das_formular_zeigt_die_einstellung(self, admin, make_challenge):
        challenge = laufender_wettbewerb(make_challenge, freeze_minutes=25)
        html = admin.get(f"/admin/challenges/{challenge.id}/edit").get_data(as_text=True)
        assert 'name="freeze_enabled"' in html
        assert 'value="25"' in html

    def test_ein_neuer_name_friert_eine_aufgeloeste_rangliste_nicht_wieder_ein(
            self, admin, make_challenge):
        challenge = laufender_wettbewerb(make_challenge, minuten_bis_ende=-5,
                                         scoreboard_revealed=True)
        posten(admin, f"/admin/challenges/{challenge.id}/edit",
               self.formular(challenge, title="Umbenannt", freeze_enabled="on",
                             freeze_minutes="15"))
        assert frisch(challenge).scoreboard_revealed is True

    def test_neue_zeiten_fangen_von_vorn_an(self, admin, make_challenge):
        challenge = laufender_wettbewerb(make_challenge, minuten_bis_ende=-5,
                                         scoreboard_revealed=True)
        posten(admin, f"/admin/challenges/{challenge.id}/jetzt-starten",
               {"duration_minutes": "45"})
        challenge = frisch(challenge)
        assert challenge.scoreboard_revealed is False
        assert challenge.frozen_since is None

    def test_die_wettbewerbsseite_nennt_den_zeitpunkt(self, admin, make_challenge):
        challenge = laufender_wettbewerb(make_challenge, minuten_bis_ende=30)
        html = admin.get(f"/admin/wettbewerb/{challenge.id}").get_data(as_text=True)
        assert "Die Rangliste friert um" in html

        challenge = laufender_wettbewerb(make_challenge, title="Zweiter", minuten_bis_ende=5,
                                         active=False)
        html = admin.get(f"/admin/wettbewerb/{challenge.id}").get_data(as_text=True)
        assert "eingefroren" in html
        assert "Rangliste auflösen" in html


class TestPauseUndEnde:
    def test_eine_pause_vor_dem_einfrieren_verschiebt_es(self, admin, make_challenge):
        """Die Teams haben länger Zeit, also friert es auch später ein."""
        challenge = laufender_wettbewerb(
            make_challenge, minuten_bis_ende=30, paused=True,
            paused_at=datetime.now() - timedelta(minutes=10))
        vorher = challenge.freeze_point

        posten(admin, f"/admin/challenges/{challenge.id}/resume")
        challenge = frisch(challenge)
        assert challenge.frozen_since is None
        assert challenge.freeze_point - vorher >= timedelta(minutes=9)

    def test_eine_pause_nach_dem_einfrieren_laesst_den_zeitpunkt_stehen(
            self, admin, make_challenge, make_task, make_team, client):
        """Sonst tauchten Abgaben kurz vor der Pause wieder am Beamer auf."""
        challenge = laufender_wettbewerb(
            make_challenge, minuten_bis_ende=3, paused=True,
            paused_at=datetime.now() - timedelta(minutes=10))
        task = make_task(challenge)
        team = make_team(challenge, name="Team Frost")
        # Eingefroren war ab 15 Minuten vor dem Ende, also vor zwölf Minuten,
        # pausiert seit zehn - diese Abgabe kam dazwischen.
        abgabe(team, task, 5, vor_minuten=11)
        vorher = challenge.freeze_point
        assert gesamt_auf_der_rangliste(client, "Team Frost") == 0

        posten(admin, f"/admin/challenges/{challenge.id}/resume")
        challenge = frisch(challenge)
        assert challenge.freeze_point == vorher
        assert gesamt_auf_der_rangliste(client, "Team Frost") == 0

    def test_vorzeitig_beendet_verschwindet_nichts_vom_beamer(
            self, admin, make_challenge, make_task, make_team, client):
        """Beenden setzt das Ende auf jetzt. Rückte das Einfrieren mit, fielen
        die Abgaben der letzten Minuten nachträglich wieder heraus."""
        challenge = laufender_wettbewerb(make_challenge, minuten_bis_ende=60)
        task = make_task(challenge)
        team = make_team(challenge, name="Team Frost")
        abgabe(team, task, 6, vor_minuten=3)
        assert gesamt_auf_der_rangliste(client, "Team Frost") == 6

        posten(admin, f"/admin/challenges/{challenge.id}/finish")
        challenge = frisch(challenge)
        assert challenge.scoreboard_frozen, "die Siegerehrung bleibt der Moment"
        assert gesamt_auf_der_rangliste(client, "Team Frost") == 6

    def test_beenden_nach_dem_einfrieren_behaelt_den_zeitpunkt(self, admin, make_challenge):
        challenge = laufender_wettbewerb(make_challenge, minuten_bis_ende=10)
        vorher = challenge.freeze_point
        posten(admin, f"/admin/challenges/{challenge.id}/finish")
        assert frisch(challenge).freeze_point == vorher

    def test_wieder_oeffnen_taut_auf(self, admin, make_challenge):
        challenge = laufender_wettbewerb(make_challenge, minuten_bis_ende=-5,
                                         frozen_since=datetime.now() - timedelta(minutes=20))
        posten(admin, f"/admin/challenges/{challenge.id}/reopen")
        challenge = frisch(challenge)
        assert challenge.frozen_since is None
        assert not challenge.scoreboard_frozen


class TestSicherung:
    def test_die_einstellung_kommt_mit(self, flask_app, make_challenge):
        from wettbewerb_sicherung import sicherung_bauen, sicherung_einlesen

        challenge = laufender_wettbewerb(make_challenge, freeze_minutes=25)
        datei, _zahlen = sicherung_bauen(challenge, mit_namen=False)
        with datei:
            datei.seek(0)
            neu, _zahlen, _hinweise = sicherung_einlesen(
                datei, flask_app.config["UPLOAD_FOLDER"])

        assert neu.freeze_enabled is True
        assert neu.freeze_minutes == 25
