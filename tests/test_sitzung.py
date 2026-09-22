"""Was aus der Anmeldung eines Teams wird, wenn sein Wettbewerb verschwindet.

Ein Wettbewerb zu löschen nimmt seine Teams mit. Im Browser lebt das Cookie
aber weiter, und die obere Leiste zeigte deshalb weiter Teamnamen und
„Abmelden“ an. Schlimmer noch: SQLite vergibt die Nummer eines gelöschten
Teams wieder, die alte Sitzung passte also auf ein fremdes Team im nächsten
Wettbewerb.
"""

import io
from datetime import datetime, timedelta

from tests.helpers import csrf_token


def wettbewerb_loeschen(admin, challenge):
    antwort = admin.post(f"/admin/challenges/{challenge.id}/delete", data={
        "csrf_token": csrf_token(admin, f"/admin/wettbewerb/{challenge.id}"),
    })
    assert antwort.status_code == 302, "Der Wettbewerb wurde nicht gelöscht"


class TestGeloeschterWettbewerb:
    """Der Admin löscht den Wettbewerb, das Team hat seine Seite offen."""

    def test_leiste_zeigt_das_team_nicht_mehr_an(
            self, make_challenge, logged_in_team, admin):
        challenge = make_challenge(title="Scratch")
        team_client, _team = logged_in_team(challenge, name="Team Blitz")

        wettbewerb_loeschen(admin, challenge)

        leiste = team_client.get("/").get_data(as_text=True)
        assert "Team Blitz" not in leiste
        assert "Abmelden" not in leiste
        assert "Anmelden" in leiste

    def test_die_sitzung_wird_geraeumt(self, make_challenge, logged_in_team, admin):
        challenge = make_challenge(title="Scratch")
        team_client, _team = logged_in_team(challenge)

        wettbewerb_loeschen(admin, challenge)
        team_client.get("/")

        with team_client.session_transaction() as sitzung:
            assert "team_id" not in sitzung
            assert "team_name" not in sitzung

    def test_die_wettbewerbsseite_schickt_auf_die_startseite(
            self, make_challenge, logged_in_team, admin):
        challenge = make_challenge(title="Scratch")
        team_client, _team = logged_in_team(challenge)

        wettbewerb_loeschen(admin, challenge)

        antwort = team_client.get("/challenge")
        assert antwort.status_code == 302
        assert antwort.headers["Location"].endswith("/")

    def test_ohne_admin_im_selben_browser(self, flask_app, make_challenge,
                                          logged_in_team, admin):
        """Es liegt nicht daran, dass jemand zugleich als Admin angemeldet ist.

        Der Admin löscht aus seinem eigenen Testclient heraus, das Team hat
        einen zweiten - getrennte Cookies, dasselbe Ergebnis.
        """
        challenge = make_challenge(title="Scratch")
        team_client, _team = logged_in_team(challenge, name="Team Blitz")

        wettbewerb_loeschen(admin, challenge)

        with team_client.session_transaction() as sitzung:
            assert "is_admin" not in sitzung
        assert "Team Blitz" not in team_client.get("/").get_data(as_text=True)


class TestWiederverwendeteTeamnummer:
    """Die alte Sitzung darf nicht auf ein neues Team mit derselben Nummer passen."""

    def test_alte_sitzung_wird_kein_fremdes_team(
            self, make_challenge, logged_in_team, admin, make_team):
        challenge = make_challenge(title="Scratch")
        team_client, altes_team = logged_in_team(challenge, name="Team Blitz")

        wettbewerb_loeschen(admin, challenge)

        neu = make_challenge(title="Calliope")
        fremdes_team = make_team(neu, name="Die Anderen", password="anders")
        assert fremdes_team.id == altes_team.id, \
            "Ohne wiederverwendete Nummer prüft der Test nichts"

        antwort = team_client.get("/challenge")

        assert antwort.status_code == 302
        assert "Die Anderen" not in team_client.get("/").get_data(as_text=True)

    def test_keine_abgabe_unter_fremdem_namen(
            self, make_challenge, logged_in_team, admin, make_team, make_task):
        from models import Submission

        challenge = make_challenge(title="Scratch")
        team_client, _altes_team = logged_in_team(challenge)

        wettbewerb_loeschen(admin, challenge)

        jetzt = datetime.now()
        neu = make_challenge(title="Calliope",
                             start_time=jetzt - timedelta(minutes=1),
                             end_time=jetzt + timedelta(minutes=45))
        make_team(neu, name="Die Anderen", password="anders")
        aufgabe = make_task(neu, title="Aufgabe 1")

        antwort = team_client.post(f"/submit/{aufgabe.id}", data={
            "csrf_token": csrf_token(team_client, "/"),
            "file": (io.BytesIO(b"projekt"), "loesung.sb3"),
        }, content_type="multipart/form-data")

        # Die alte Anmeldung gilt nicht mehr: Es geht zur Startseite, und
        # abgegeben wird unter keinem Namen etwas.
        assert antwort.status_code == 302
        assert antwort.headers["Location"] == "/"
        assert Submission.query.count() == 0


def test_anmeldung_merkt_sich_das_kennzeichen(client, make_challenge):
    """Ohne das Kennzeichen in der Sitzung ließe sich nichts davon prüfen."""
    from models import Team

    make_challenge()

    client.post("/", data={
        "csrf_token": csrf_token(client, "/"),
        "team": "Die Pixelpiraten",
        "password": "geheim",
    })

    team = Team.query.filter_by(name="Die Pixelpiraten").one()
    assert team.uid, "Ein neues Team bekommt ein Kennzeichen"
    with client.session_transaction() as sitzung:
        assert sitzung["team_uid"] == team.uid


def test_jedes_team_hat_ein_eigenes_kennzeichen(make_challenge, make_team):
    challenge = make_challenge()
    eines = make_team(challenge, name="Eins")
    anderes = make_team(challenge, name="Zwei")

    assert eines.uid != anderes.uid


def test_abmelden_raeumt_auch_das_kennzeichen(client, make_challenge):
    make_challenge()
    client.post("/", data={
        "csrf_token": csrf_token(client, "/"),
        "team": "Die Pixelpiraten",
        "password": "geheim",
    })

    client.get("/logout")

    with client.session_transaction() as sitzung:
        assert "team_uid" not in sitzung


def test_sitzung_ohne_kennzeichen_gilt_nicht_mehr(
        flask_app, make_challenge, make_team):
    """Ein Cookie aus der Zeit vor dieser Änderung kennt kein Kennzeichen.

    Es durchzulassen hieße, genau die Lücke offen zu lassen, um die es geht -
    also melden sich diese Teams einmal neu an.
    """
    challenge = make_challenge()
    team = make_team(challenge, name="Team Blitz", password="geheim")

    client = flask_app.test_client()
    with client.session_transaction() as sitzung:
        sitzung["team_id"] = team.id
        sitzung["team_name"] = team.name

    assert client.get("/challenge").status_code == 302
