"""Urkunden: PDF-Inhalt, Unterschrift und der Download durch die Teams."""

import io
from datetime import datetime, timedelta

import pypdf
import pytest

from certificates import build_certificates_pdf, pdf_safe
from tests.helpers import csrf_token


def pdf_text(daten):
    leser = pypdf.PdfReader(io.BytesIO(daten))
    return "\n".join(seite.extract_text() for seite in leser.pages)


def seitenzahl(daten):
    return len(pypdf.PdfReader(io.BytesIO(daten)).pages)


EINTRAG = {"team_id": 1, "name": "Die Pixelpiraten", "total": 38, "solved": 3, "rank": 1}


class TestZeichenSaeuberung:
    """Die eingebaute Schrift kann nur latin-1 - sonst bricht fpdf2 ab."""

    def test_typografische_zeichen_werden_ersetzt(self):
        assert pdf_safe("Runde – „eins“") == 'Runde - "eins"'

    def test_emoji_werden_entfernt(self):
        assert pdf_safe("Team 🚀 Rakete") == "Team Rakete"

    def test_umlaute_bleiben(self):
        assert pdf_safe("Katze läuft im Kreis") == "Katze läuft im Kreis"

    def test_ein_name_nur_aus_emoji_wird_leer(self):
        assert pdf_safe("🚀🎵") == ""


class TestPdfAufbau:
    def test_eine_seite_je_team(self):
        eintraege = [dict(EINTRAG, team_id=i, name=f"Team {i}") for i in range(4)]

        daten = build_certificates_pdf("Wettbewerb", "Titel", eintraege, 4)

        assert seitenzahl(daten) == 4

    def test_urkunde_nennt_team_platz_und_punkte(self):
        daten = build_certificates_pdf("Coding-Wettbewerb", "Scratch-Wettbewerb",
                                       [EINTRAG], 4)

        text = pdf_text(daten)
        assert "Die Pixelpiraten" in text
        assert "1. Platz" in text
        assert "38 Punkte" in text
        assert "3 von 4 Aufgaben" in text

    def test_ohne_platzierung_kein_platz_aufdruck(self):
        eintrag = dict(EINTRAG, rank=0, total=0, solved=0)

        text = pdf_text(build_certificates_pdf("W", "T", [eintrag], 4))

        assert "Platz" not in text

    def test_emoji_im_teamnamen_bricht_nichts(self):
        eintrag = dict(EINTRAG, name="Team 🚀 Rakete")

        text = pdf_text(build_certificates_pdf("W", "T", [eintrag], 4))

        assert "Team" in text

    def test_name_nur_aus_emoji_wird_zu_team(self):
        """Sonst stünde auf der Urkunde gar kein Name."""
        eintrag = dict(EINTRAG, name="🚀")

        assert "Team" in pdf_text(build_certificates_pdf("W", "T", [eintrag], 4))


class TestUnterschrift:
    def test_ohne_namen_steht_unterschrift_dort(self):
        text = pdf_text(build_certificates_pdf("W", "T", [EINTRAG], 4))

        assert "Unterschrift" in text

    @pytest.mark.parametrize("schrift", ["caveat", "dancing", "vibes"])
    def test_handschrift_setzt_den_namen_zweimal(self, schrift):
        """Einmal geschrieben auf der Linie, einmal lesbar darunter."""
        daten = build_certificates_pdf("W", "T", [EINTRAG], 4,
                                       signature_name="Tobias Händler",
                                       signature_font_key=schrift)

        text = pdf_text(daten)
        assert text.count("Tobias Händler") == 2
        assert "Unterschrift" not in text

    def test_druckschrift_setzt_den_namen_einmal(self):
        daten = build_certificates_pdf("W", "T", [EINTRAG], 4,
                                       signature_name="Tobias Händler",
                                       signature_font_key="print")

        assert pdf_text(daten).count("Tobias Händler") == 1

    def test_unbekannte_schrift_faellt_auf_die_standardschrift_zurueck(self):
        daten = build_certificates_pdf("W", "T", [EINTRAG], 4,
                                       signature_name="Tobias Händler",
                                       signature_font_key="gibtsnicht")

        assert pdf_text(daten).count("Tobias Händler") == 2

    def test_eingebettete_schrift_kann_alle_zeichen(self):
        """Anders als die eingebaute Schrift braucht sie keine Säuberung."""
        daten = build_certificates_pdf("W", "T", [EINTRAG], 4,
                                       signature_name="Zoë Groß–Müller",
                                       signature_font_key="caveat")

        assert "Zoë Groß–Müller" in pdf_text(daten)


class TestEinstellungen:
    def test_unterschrift_wird_gespeichert_und_getrimmt(self, admin, database):
        from models import Settings

        admin.post("/admin/settings", data={
            "csrf_token": csrf_token(admin, "/admin/settings"),
            "site_name": "W", "tagline": "U",
            "signature_name": "  Tobias Händler  ",
            "signature_font": "vibes",
        })

        settings = Settings.get()
        assert settings.signature_name == "Tobias Händler"
        assert settings.signature_font == "vibes"

    def test_unbekannte_schrift_wird_nicht_gespeichert(self, admin, database):
        from models import Settings

        admin.post("/admin/settings", data={
            "csrf_token": csrf_token(admin, "/admin/settings"),
            "site_name": "W", "tagline": "U",
            "signature_name": "Tobias", "signature_font": "gibtsnicht",
        })

        assert Settings.get().signature_font == "caveat"

    def test_name_laesst_sich_wieder_leeren(self, admin, database):
        from models import Settings

        settings = Settings.get()
        settings.signature_name = "Tobias Händler"
        database.session.commit()

        admin.post("/admin/settings", data={
            "csrf_token": csrf_token(admin, "/admin/settings"),
            "site_name": "W", "tagline": "U",
            "signature_name": "", "signature_font": "caveat",
        })

        assert Settings.get().signature_name == ""


class TestAdminDownload:
    def test_alle_urkunden_als_pdf(self, admin, make_challenge, make_team):
        challenge = make_challenge(title="Scratch-Wettbewerb")
        make_team(challenge, name="Team A")
        make_team(challenge, name="Team B")

        antwort = admin.get("/admin/urkunden.pdf")

        assert antwort.mimetype == "application/pdf"
        assert seitenzahl(antwort.data) == 2

    def test_einzelne_urkunde_als_pdf(self, admin, make_challenge, make_team):
        challenge = make_challenge()
        team = make_team(challenge, name="Die Pixelpiraten")

        antwort = admin.get(f"/admin/urkunden/{team.id}.pdf")

        assert seitenzahl(antwort.data) == 1
        assert "Die Pixelpiraten" in pdf_text(antwort.data)

    def test_ohne_teams_gibt_es_nichts_zu_drucken(self, admin, make_challenge):
        make_challenge()

        antwort = admin.get("/admin/urkunden.pdf", follow_redirects=True)

        assert "keine Teams" in antwort.get_data(as_text=True)

    def test_druckansicht_bindet_die_gewaehlte_schrift_ein(
            self, admin, make_challenge, make_team, database):
        from models import Settings

        challenge = make_challenge()
        make_team(challenge, name="Team A")
        settings = Settings.get()
        settings.signature_name = "Tobias Händler"
        settings.signature_font = "vibes"
        database.session.commit()

        html = admin.get("/admin/urkunden").get_data(as_text=True)

        assert "Tobias Händler" in html
        assert "GreatVibes-Regular.ttf" in html


class TestTeamDownload:
    def test_vor_dem_ende_gibt_es_keine_urkunde(
            self, make_challenge, logged_in_team):
        challenge = make_challenge()
        client, _team = logged_in_team(challenge)

        assert client.get("/urkunde.pdf").status_code == 403

    def test_vor_dem_ende_steht_auch_kein_knopf_da(
            self, make_challenge, logged_in_team):
        challenge = make_challenge()
        client, _team = logged_in_team(challenge)

        assert "Urkunde herunterladen" not in client.get("/challenge").get_data(as_text=True)

    def test_nach_dem_ende_laedt_das_team_seine_urkunde(
            self, make_challenge, logged_in_team, database):
        challenge = make_challenge()
        client, _team = logged_in_team(challenge, name="Die Pixelpiraten")

        challenge.end_time = datetime.now() - timedelta(minutes=1)
        database.session.commit()

        assert "Urkunde herunterladen" in client.get("/challenge").get_data(as_text=True)

        antwort = client.get("/urkunde.pdf")
        assert antwort.mimetype == "application/pdf"
        assert seitenzahl(antwort.data) == 1
        assert "Die Pixelpiraten" in pdf_text(antwort.data)

    def test_jedes_team_bekommt_nur_die_eigene(
            self, flask_app, make_challenge, logged_in_team, database):
        challenge = make_challenge()
        erster, _a = logged_in_team(challenge, name="Team A")
        zweiter, _b = logged_in_team(challenge, name="Team B")

        challenge.end_time = datetime.now() - timedelta(minutes=1)
        database.session.commit()

        text = pdf_text(zweiter.get("/urkunde.pdf").data)
        assert "Team B" in text
        assert "Team A" not in text

    def test_ohne_anmeldung_keine_urkunde(self, client, make_challenge, database):
        challenge = make_challenge()
        challenge.end_time = datetime.now() - timedelta(minutes=1)
        database.session.commit()

        assert client.get("/urkunde.pdf").status_code == 302

    def test_dateiname_uebersteht_einen_emoji_teamnamen(
            self, make_challenge, logged_in_team, database):
        challenge = make_challenge()
        client, _team = logged_in_team(challenge, name="Team 🚀 Rakete")

        challenge.end_time = datetime.now() - timedelta(minutes=1)
        database.session.commit()

        antwort = client.get("/urkunde.pdf")

        assert antwort.status_code == 200
        assert ".pdf" in antwort.headers["Content-Disposition"]
