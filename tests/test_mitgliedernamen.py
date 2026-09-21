"""Die Namen der Teammitglieder: eintragen, kontrollieren, freigeben.

Der Weg hat zwei Schalter. Erst muss die Lehrkraft die Möglichkeit überhaupt
freigeben, dann tragen die Teams ihre Namen ein, und erst nach der Kontrolle
durch die Lehrkraft stehen sie auf der Urkunde.
"""

import pytest

from certificates import names_line
from models import (MAX_MEMBERS, MAX_MEMBER_NAME_LENGTH, MAX_MEMBER_TEXT_LENGTH,
                    parse_member_names)
from tests.helpers import csrf_token


def eintragen(client, *namen, text=None):
    """Das Team schickt seine Namen ab."""
    return client.post("/team/namen", data={
        "csrf_token": csrf_token(client, "/challenge"),
        "member_names": "\n".join(namen) if text is None else text,
    })


def admin_namen(admin, team, *namen, knopf=None):
    """Die Lehrkraft speichert, gibt frei oder nimmt die Freigabe zurück."""
    felder = {
        "csrf_token": csrf_token(admin, "/admin/teams"),
        "member_names": "\n".join(namen),
    }
    if knopf:
        felder[knopf] = "1"
    return admin.post(f"/admin/team/{team.id}/namen", data=felder)


def moeglichkeit_freigeben(database, an=True):
    from models import Settings

    einstellungen = Settings.get()
    einstellungen.member_names_enabled = an
    database.session.commit()


class TestNamenEinlesen:
    def test_eine_zeile_ist_ein_name(self):
        assert parse_member_names("Anna\nBen\nCarla") == ["Anna", "Ben", "Carla"]

    def test_komma_trennt_genauso(self):
        """Schüler reihen ihre Namen erfahrungsgemäß in einer Zeile auf."""
        assert parse_member_names("Anna, Ben; Carla") == ["Anna", "Ben", "Carla"]

    def test_leere_zeilen_und_doppelte_leerzeichen_fallen_weg(self):
        assert parse_member_names("\n\nAnna   Beispiel \n \n Ben\n") == [
            "Anna Beispiel", "Ben"]

    def test_ein_sehr_langer_name_wird_gekuerzt(self):
        (name,) = parse_member_names("M" * 200)

        assert len(name) == MAX_MEMBER_NAME_LENGTH

    def test_ohne_eingabe_bleibt_die_liste_leer(self):
        assert parse_member_names(None) == []
        assert parse_member_names("   \n  ") == []


class TestAufzaehlung:
    def test_ein_name_steht_allein(self):
        assert names_line(["Anna"]) == "Anna"

    def test_zwei_namen_bekommen_ein_und(self):
        assert names_line(["Anna", "Ben"]) == "Anna und Ben"

    def test_ab_drei_namen_trennt_das_komma(self):
        assert names_line(["Anna", "Ben", "Carla"]) == "Anna, Ben und Carla"

    def test_ohne_namen_bleibt_nichts(self):
        assert names_line([]) == ""
        assert names_line(None) == ""


class TestFreigabeDerMoeglichkeit:
    """Solange die Lehrkraft nichts freigegeben hat, gibt es das Feld nicht."""

    def test_ohne_freigabe_steht_kein_feld_auf_der_team_seite(self, make_challenge,
                                                              logged_in_team):
        challenge = make_challenge()
        client, _ = logged_in_team(challenge)

        assert "member_names" not in client.get("/challenge").get_data(as_text=True)

    def test_ohne_freigabe_wird_nichts_angenommen(self, make_challenge, logged_in_team,
                                                  database):
        challenge = make_challenge()
        client, team = logged_in_team(challenge)

        # Das Formular gibt es auf der Seite gar nicht, das Token kommt
        # deshalb von woanders her - abgeschickt wird von Hand.
        antwort = client.post("/team/namen", data={
            "csrf_token": csrf_token(client, "/login"),
            "member_names": "Anna",
        })

        assert antwort.status_code == 403
        assert team.member_names in (None, "")

    def test_nach_der_freigabe_steht_das_feld_da(self, make_challenge, logged_in_team,
                                                 database):
        challenge = make_challenge()
        moeglichkeit_freigeben(database)
        client, _ = logged_in_team(challenge)

        seite = client.get("/challenge").get_data(as_text=True)
        assert "member_names" in seite
        assert "Urkunde" in seite

    def test_die_lehrkraft_schaltet_sie_in_den_einstellungen_ein(self, admin, database):
        from models import Settings

        admin.post("/admin/settings", data={
            "csrf_token": csrf_token(admin, "/admin/settings"),
            "site_name": "Coding-Wettbewerb",
            "tagline": "Untertitel",
            "member_names_enabled": "1",
        })

        assert Settings.get().member_names_enabled is True

    def test_ohne_haekchen_ist_sie_wieder_aus(self, admin, database):
        from models import Settings

        moeglichkeit_freigeben(database)

        admin.post("/admin/settings", data={
            "csrf_token": csrf_token(admin, "/admin/settings"),
            "site_name": "Coding-Wettbewerb",
            "tagline": "Untertitel",
        })

        assert Settings.get().member_names_enabled is False


class TestTeamTraegtEin:
    @pytest.fixture(autouse=True)
    def _moeglichkeit(self, database):
        moeglichkeit_freigeben(database)

    def test_namen_werden_gespeichert_aber_noch_nicht_freigegeben(self, make_challenge,
                                                                  logged_in_team):
        challenge = make_challenge()
        client, team = logged_in_team(challenge)

        eintragen(client, "Anna Beispiel", "Ben Muster")

        assert team.member_list == ["Anna Beispiel", "Ben Muster"]
        assert team.members_approved is False
        assert team.certificate_names == []

    def test_das_team_sieht_seine_namen_wieder(self, make_challenge, logged_in_team):
        challenge = make_challenge()
        client, _ = logged_in_team(challenge)

        eintragen(client, "Anna Beispiel")

        assert "Anna Beispiel" in client.get("/challenge").get_data(as_text=True)

    def test_eine_aenderung_nach_der_freigabe_hebt_sie_auf(self, make_challenge,
                                                           logged_in_team, database):
        """Sonst könnte nach der Kontrolle etwas anderes auf die Urkunde rutschen."""
        challenge = make_challenge()
        client, team = logged_in_team(challenge)

        eintragen(client, "Anna Beispiel")
        team.members_approved = True
        database.session.commit()

        eintragen(client, "Anna Beispiel", "Ein Schummler")

        assert team.members_approved is False

    def test_dieselben_namen_noch_einmal_lassen_die_freigabe_stehen(self, make_challenge,
                                                                    logged_in_team,
                                                                    database):
        """Wer nur auf „speichern“ drückt, soll nicht zurück in die Warteschlange."""
        challenge = make_challenge()
        client, team = logged_in_team(challenge)

        eintragen(client, "Anna Beispiel")
        team.members_approved = True
        database.session.commit()

        eintragen(client, "Anna Beispiel")

        assert team.members_approved is True

    def test_mehr_namen_als_erlaubt_werden_gekappt(self, make_challenge, logged_in_team):
        challenge = make_challenge()
        client, team = logged_in_team(challenge)

        eintragen(client, *[f"Kind {i}" for i in range(MAX_MEMBERS + 5)])

        assert len(team.member_list) == MAX_MEMBERS

    def test_eine_zu_lange_liste_wird_gar_nicht_gespeichert(self, make_challenge,
                                                            logged_in_team):
        """Hinten abschneiden hieße, jemanden von der Urkunde zu streichen."""
        challenge = make_challenge()
        client, team = logged_in_team(challenge)

        eintragen(client, "Anna Beispiel")
        antwort = eintragen(client, *["M" * MAX_MEMBER_NAME_LENGTH] * MAX_MEMBERS,
                            )
        seite = antwort.headers["Location"]

        assert "/challenge" in seite
        assert team.member_list == ["Anna Beispiel"], "die alte Liste muss stehen bleiben"

    def test_leeres_feld_loescht_die_namen(self, make_challenge, logged_in_team):
        challenge = make_challenge()
        client, team = logged_in_team(challenge)

        eintragen(client, "Anna Beispiel")
        eintragen(client, text="")

        assert team.member_list == []

    def test_wer_nicht_angemeldet_ist_traegt_nichts_ein(self, client, make_challenge):
        make_challenge()

        antwort = client.post("/team/namen", data={"member_names": "Anna"})

        assert antwort.status_code in (302, 400)

    def test_ein_team_schreibt_nur_in_die_eigene_liste(self, make_challenge,
                                                       logged_in_team, make_team):
        challenge = make_challenge()
        client, _ = logged_in_team(challenge, name="Team Blitz")
        fremd = make_team(challenge, name="Team Fremd", password="anders")

        eintragen(client, "Anna Beispiel")

        assert fremd.member_list == []


class TestLehrkraftKontrolliert:
    @pytest.fixture(autouse=True)
    def _moeglichkeit(self, database):
        moeglichkeit_freigeben(database)

    def test_freigeben_setzt_die_namen_auf_die_urkunde(self, admin, make_challenge,
                                                       make_team):
        challenge = make_challenge()
        team = make_team(challenge, name="Die Pixelpiraten")

        admin_namen(admin, team, "Anna Beispiel", "Ben Muster", knopf="freigeben")

        assert team.members_approved is True
        assert team.certificate_names == ["Anna Beispiel", "Ben Muster"]

    def test_speichern_allein_gibt_nichts_frei(self, admin, make_challenge, make_team):
        challenge = make_challenge()
        team = make_team(challenge)

        admin_namen(admin, team, "Anna Beispiel")

        assert team.member_list == ["Anna Beispiel"]
        assert team.members_approved is False

    def test_die_lehrkraft_darf_einen_tippfehler_berichtigen(self, admin, make_challenge,
                                                             make_team):
        challenge = make_challenge()
        team = make_team(challenge)

        admin_namen(admin, team, "Ana Beispil", knopf="freigeben")
        admin_namen(admin, team, "Anna Beispiel", knopf="freigeben")

        assert team.certificate_names == ["Anna Beispiel"]

    def test_freigabe_zuruecknehmen_holt_die_namen_von_der_urkunde(self, admin,
                                                                   make_challenge,
                                                                   make_team):
        challenge = make_challenge()
        team = make_team(challenge)

        admin_namen(admin, team, "Anna Beispiel", knopf="freigeben")
        admin_namen(admin, team, "Anna Beispiel", knopf="sperren")

        assert team.members_approved is False
        assert team.member_list == ["Anna Beispiel"], "die Namen bleiben trotzdem stehen"

    def test_ohne_namen_gibt_es_nichts_freizugeben(self, admin, make_challenge,
                                                   make_team):
        challenge = make_challenge()
        team = make_team(challenge)

        admin_namen(admin, team, knopf="freigeben")

        assert team.members_approved is False

    def test_eine_zu_lange_liste_aendert_auch_hier_nichts(self, admin, make_challenge,
                                                          make_team):
        challenge = make_challenge()
        team = make_team(challenge)

        admin_namen(admin, team, "Anna Beispiel", knopf="freigeben")
        admin_namen(admin, team, *["M" * MAX_MEMBER_NAME_LENGTH] * MAX_MEMBERS,
                    knopf="freigeben")

        assert team.member_list == ["Anna Beispiel"]
        assert team.members_approved is True

    def test_ohne_anmeldung_geht_das_nicht(self, client, make_challenge, make_team):
        challenge = make_challenge()
        team = make_team(challenge)

        antwort = client.post(f"/admin/team/{team.id}/namen",
                              data={"member_names": "Fremder"})

        assert antwort.status_code in (302, 400)
        assert team.member_list == []

    def test_die_teamverwaltung_zeigt_was_auf_kontrolle_wartet(self, admin,
                                                               make_challenge,
                                                               make_team, database):
        challenge = make_challenge()
        team = make_team(challenge)
        team.member_names = "Anna Beispiel"
        database.session.commit()

        seite = admin.get("/admin/teams").get_data(as_text=True)

        assert "wartet auf deine Kontrolle" in seite


class TestAufDerUrkunde:
    @pytest.fixture(autouse=True)
    def _moeglichkeit(self, database):
        moeglichkeit_freigeben(database)

    def urkunde_des_teams(self, client):
        import io

        import pypdf

        antwort = client.get("/urkunde.pdf")
        assert antwort.status_code == 200
        leser = pypdf.PdfReader(io.BytesIO(antwort.data))
        return "\n".join(seite.extract_text() for seite in leser.pages)

    def beendet(self, challenge, database):
        from datetime import datetime, timedelta

        challenge.end_time = datetime.now() - timedelta(minutes=1)
        database.session.commit()

    def test_freigegebene_namen_stehen_im_pdf(self, make_challenge, logged_in_team,
                                              database):
        challenge = make_challenge()
        client, team = logged_in_team(challenge)

        eintragen(client, "Anna Beispiel", "Ben Muster")
        team.members_approved = True
        self.beendet(challenge, database)

        assert "Anna Beispiel und Ben Muster" in self.urkunde_des_teams(client)

    def test_ohne_freigabe_steht_kein_name_im_pdf(self, make_challenge, logged_in_team,
                                                  database):
        challenge = make_challenge()
        client, _ = logged_in_team(challenge)

        eintragen(client, "Anna Beispiel")
        self.beendet(challenge, database)

        assert "Anna Beispiel" not in self.urkunde_des_teams(client)

    def test_die_druckansicht_zeigt_dieselben_namen(self, admin, make_challenge,
                                                    make_team, database):
        challenge = make_challenge()
        team = make_team(challenge, name="Die Pixelpiraten")
        team.member_names = "Anna Beispiel\nBen Muster"
        team.members_approved = True
        database.session.commit()

        seite = admin.get("/admin/urkunden").get_data(as_text=True)

        assert "Anna Beispiel und Ben Muster" in seite

    def test_die_druckansicht_schweigt_ohne_freigabe(self, admin, make_challenge,
                                                     make_team, database):
        challenge = make_challenge()
        team = make_team(challenge)
        team.member_names = "Anna Beispiel"
        database.session.commit()

        assert "Anna Beispiel" not in admin.get("/admin/urkunden").get_data(as_text=True)

    def test_die_gesamt_pdf_der_lehrkraft_traegt_die_namen(self, admin, make_challenge,
                                                           make_team, database):
        import io

        import pypdf

        challenge = make_challenge()
        team = make_team(challenge)
        team.member_names = "Anna Beispiel"
        team.members_approved = True
        database.session.commit()

        antwort = admin.get("/admin/urkunden.pdf")
        text = "\n".join(s.extract_text()
                         for s in pypdf.PdfReader(io.BytesIO(antwort.data)).pages)

        assert "Anna Beispiel" in text


def test_die_grenze_passt_zu_zwoelf_ueblichen_namen():
    """Die Längengrenze darf einem echten Team nicht im Weg stehen."""
    namen = ["Anna-Lena Schmidt", "Benjamin Müller", "Charlotte Weber",
             "David Fischer", "Emilia Schneider", "Finn-Luca Wagner",
             "Greta Hoffmann", "Hannes Bauer", "Isabella Richter",
             "Jonas Klein", "Katharina Wolf", "Leonard Schröder"]

    assert len(namen) == MAX_MEMBERS
    assert len(names_line(namen)) <= MAX_MEMBER_TEXT_LENGTH
