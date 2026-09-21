"""Name und Untertitel der Veranstaltung, wenn ein Wettbewerb eigene führt.

Die Einstellungen bleiben die Voreinstellung für die ganze Anwendung; ein
einzelner Wettbewerb darf beides überschreiben. Was er leer lässt, kommt
weiter aus den Einstellungen.
"""

import io

import pypdf
import pytest

from tests.helpers import csrf_token


def pdf_text(daten):
    leser = pypdf.PdfReader(io.BytesIO(daten))
    return "\n".join(seite.extract_text() for seite in leser.pages)


def pdf_zeilen(daten):
    """Die Zeilen der ersten Seite als (Schriftgröße, Text), von oben nach unten."""
    seite = pypdf.PdfReader(io.BytesIO(daten)).pages[0]
    gefunden = []

    def besucher(text, cm, tm, font_dict, font_size):
        if text.strip():
            gefunden.append((round(font_size, 1), text.strip()))

    seite.extract_text(visitor_text=besucher)
    return gefunden


@pytest.fixture
def einstellungen(database):
    """Die globalen Werte, auf die ohne eigenen Namen zurückgefallen wird."""
    from models import Settings

    settings = Settings.get()
    settings.site_name = "Coding-Wettbewerb"
    settings.tagline = "Ein Wettbewerb für Code, Ideen und Kreativität."
    database.session.commit()
    return settings


class TestAuflösung:
    def test_ohne_eigenen_namen_gelten_die_einstellungen(self, einstellungen, make_challenge):
        from models import event_branding

        marke = event_branding(make_challenge())

        assert marke["name"] == "Coding-Wettbewerb"
        assert marke["tagline"] == "Ein Wettbewerb für Code, Ideen und Kreativität."

    def test_eigener_name_gewinnt(self, einstellungen, make_challenge):
        from models import event_branding

        challenge = make_challenge(event_name="Scratch-Wettbewerb",
                                   event_tagline="Klasse 6b programmiert Spiele")

        marke = event_branding(challenge)

        assert marke["name"] == "Scratch-Wettbewerb"
        assert marke["tagline"] == "Klasse 6b programmiert Spiele"

    def test_nur_der_name_gesetzt_laesst_den_untertitel_stehen(self, einstellungen,
                                                               make_challenge):
        """Beide Felder sind einzeln zu haben, nicht nur im Paket."""
        from models import event_branding

        marke = event_branding(make_challenge(event_name="Calliope-Wettbewerb"))

        assert marke["name"] == "Calliope-Wettbewerb"
        assert marke["tagline"] == "Ein Wettbewerb für Code, Ideen und Kreativität."

    def test_ohne_wettbewerb_gelten_die_einstellungen(self, einstellungen):
        from models import event_branding

        assert event_branding(None)["name"] == "Coding-Wettbewerb"


class TestSeiten:
    def test_startseite_zeigt_den_namen_des_wettbewerbs(self, einstellungen, client,
                                                        make_challenge):
        make_challenge(event_name="Scratch-Wettbewerb",
                       event_tagline="Klasse 6b programmiert Spiele")

        seite = client.get("/").get_data(as_text=True)

        assert "Scratch-Wettbewerb" in seite
        assert "Klasse 6b programmiert Spiele" in seite

    def test_countdown_seite_zeigt_den_namen_des_wettbewerbs(self, einstellungen, client,
                                                             make_challenge):
        make_challenge(event_name="Calliope-Wettbewerb")

        seite = client.get("/start").get_data(as_text=True)

        assert "Calliope-Wettbewerb" in seite

    def test_navigationsleiste_behaelt_den_namen_der_anwendung(self, einstellungen, client,
                                                               make_challenge):
        """Sonst hieße auch die Anmeldeseite plötzlich nach einem Wettbewerb."""
        make_challenge(event_name="Scratch-Wettbewerb")

        seite = client.get("/login").get_data(as_text=True)

        assert 'class="navbar-brand"' in seite
        assert "Coding-Wettbewerb" in seite

    def test_ohne_eigenen_namen_steht_ueberall_der_alte(self, einstellungen, client,
                                                        make_challenge):
        make_challenge()

        seite = client.get("/").get_data(as_text=True)

        assert "Coding-Wettbewerb" in seite
        assert "Ein Wettbewerb für Code, Ideen und Kreativität." in seite


class TestUrkunde:
    def test_urkunde_traegt_den_namen_des_wettbewerbs(self, einstellungen, make_challenge,
                                                      make_team):
        from certificates import build_certificates_for, certificate_entry

        challenge = make_challenge(event_name="Scratch-Wettbewerb", title="Runde 1")
        team = make_team(challenge, name="Die Pixelpiraten")

        daten = build_certificates_for(challenge, [certificate_entry(team, [])], 0)

        text = pdf_text(daten)
        assert "Scratch-Wettbewerb" in text
        assert "Coding-Wettbewerb" not in text

    def test_ohne_eigenen_namen_steht_der_aus_den_einstellungen_drauf(self, einstellungen,
                                                                      make_challenge,
                                                                      make_team):
        from certificates import build_certificates_for, certificate_entry

        challenge = make_challenge(title="Runde 1")
        team = make_team(challenge, name="Die Pixelpiraten")

        daten = build_certificates_for(challenge, [certificate_entry(team, [])], 0)

        assert "Coding-Wettbewerb" in pdf_text(daten)

    def test_veranstaltung_und_titel_stehen_beide_drauf(self, einstellungen, make_challenge,
                                                        make_team):
        """Der Veranstaltungsname oben, die Runde in der Zeile darunter."""
        from certificates import build_certificates_for, certificate_entry

        challenge = make_challenge(event_name="Scratch-Wettbewerb", title="Runde 1")
        team = make_team(challenge, name="Die Pixelpiraten")

        text = pdf_text(build_certificates_for(challenge, [certificate_entry(team, [])], 0))

        assert "Scratch-Wettbewerb" in text
        assert "Runde 1" in text


class TestLangerVeranstaltungsname:
    """Ein eigener Name pro Wettbewerb wird länger als "Coding-Wettbewerb".

    Er darf deshalb auf zwei Zeilen umbrechen, statt unter die Größe des
    Fließtextes zu schrumpfen - dieselbe Regel wie beim Teamnamen. Geprüft
    wird am fertigen PDF, in beiden Ausrichtungen.
    """

    LANG = "Calliope-mini-Wettbewerb der Klassen 5 und 6 am Gymnasium Musterstadt"

    def urkunde(self, name, ausrichtung):
        from certificates import build_certificates_pdf

        eintrag = {"team_id": 1, "name": "Die Pixelpiraten",
                   "total": 38, "solved": 3, "rank": 1}
        return pdf_zeilen(build_certificates_pdf(name, "Runde 1", [eintrag], 4,
                                                 orientation_key=ausrichtung))

    @pytest.mark.parametrize("ausrichtung", ["landscape", "portrait"])
    def test_langer_name_wird_nicht_kleiner_als_der_fließtext(self, ausrichtung):
        zeilen = self.urkunde(self.LANG, ausrichtung)
        fließtext = next(g for g, t in zeilen if t == "verliehen an das Team")

        kopf = [g for g, t in zeilen if t in self.LANG or self.LANG.startswith(t)]

        assert kopf, "Der Veranstaltungsname steht nicht auf der Urkunde"
        assert min(kopf) >= fließtext

    def test_im_hochformat_bricht_er_um_statt_zu_schrumpfen(self):
        zeilen = self.urkunde(self.LANG, "portrait")

        kurz = self.urkunde("Coding-Wettbewerb", "portrait")
        volle_groesse = kurz[0][0]

        # Zwei Zeilen, beide in voller Größe - vorher war es eine bei 13,6 pt.
        assert zeilen[0][0] == volle_groesse
        assert zeilen[1][0] == volle_groesse
        assert zeilen[0][1] + " " + zeilen[1][1] == self.LANG

    @pytest.mark.parametrize("ausrichtung", ["landscape", "portrait"])
    def test_ein_kurzer_name_bleibt_einzeilig(self, ausrichtung):
        """Der Umbruch darf die gewachsene Urkunde nicht anfassen."""
        zeilen = self.urkunde("Coding-Wettbewerb", ausrichtung)

        assert zeilen[0][1] == "Coding-Wettbewerb"
        assert zeilen[1][1] == "Urkunde"


class TestUrkundenFuerAeltereWettbewerbe:
    """Wer bei der Siegerehrung gefehlt hat, soll seine Urkunde später bekommen."""

    @pytest.fixture
    def zwei_wettbewerbe(self, einstellungen, database, make_challenge, make_team):
        alt = make_challenge(title="Runde 1", active=False,
                             event_name="Scratch-Wettbewerb")
        make_team(alt, name="Die Pixelpiraten")

        neu = make_challenge(title="Runde 2", active=True,
                             event_name="Calliope-Wettbewerb")
        make_team(neu, name="Die Bitjaeger")

        return alt, neu

    def test_druckansicht_zeigt_den_gewaehlten_wettbewerb(self, admin, zwei_wettbewerbe):
        alt, _ = zwei_wettbewerbe

        seite = admin.get(f"/admin/urkunden?wettbewerb={alt.id}").get_data(as_text=True)

        assert "Die Pixelpiraten" in seite
        assert "Die Bitjaeger" not in seite
        assert "Scratch-Wettbewerb" in seite

    def test_druckansicht_ohne_angabe_zeigt_weiter_den_aktiven(self, admin, zwei_wettbewerbe):
        seite = admin.get("/admin/urkunden").get_data(as_text=True)

        assert "Die Bitjaeger" in seite
        assert "Die Pixelpiraten" not in seite

    def test_pdf_des_aelteren_wettbewerbs_traegt_dessen_namen(self, admin, zwei_wettbewerbe):
        alt, _ = zwei_wettbewerbe

        antwort = admin.get(f"/admin/urkunden.pdf?wettbewerb={alt.id}")

        assert antwort.status_code == 200
        text = pdf_text(antwort.data)
        assert "Scratch-Wettbewerb" in text
        assert "Calliope-Wettbewerb" not in text
        assert "Die Pixelpiraten" in text

    def test_einzelne_urkunde_folgt_dem_wettbewerb_des_teams(self, admin, zwei_wettbewerbe,
                                                             database):
        """Früher nahm sie immer den aktiven - mit falschem Namen und ohne Punkte."""
        from models import Team

        alt, _ = zwei_wettbewerbe
        team = Team.query.filter_by(name="Die Pixelpiraten").one()

        antwort = admin.get(f"/admin/urkunden/{team.id}.pdf")

        assert antwort.status_code == 200
        text = pdf_text(antwort.data)
        assert "Scratch-Wettbewerb" in text
        assert "Runde 1" in text

    def test_unbekannter_wettbewerb_gibt_404(self, admin, zwei_wettbewerbe):
        assert admin.get("/admin/urkunden?wettbewerb=9999").status_code == 404

    def test_wettbewerb_ohne_zahl_wird_ignoriert(self, admin, zwei_wettbewerbe):
        """Eine krumme Adresse soll die Seite nicht mit 500 beenden."""
        antwort = admin.get("/admin/urkunden?wettbewerb=abc")

        assert antwort.status_code == 200
        assert "Die Bitjaeger" in antwort.get_data(as_text=True)


class TestFormular:
    def test_neuer_wettbewerb_speichert_den_namen(self, einstellungen, admin, database):
        from models import Challenge

        admin.post("/admin/challenges/new", data={
            "csrf_token": csrf_token(admin, "/admin/challenges/new"),
            "title": "Runde 1",
            "event_name": "Scratch-Wettbewerb",
            "event_tagline": "Klasse 6b programmiert Spiele",
        })

        challenge = Challenge.query.filter_by(title="Runde 1").one()
        assert challenge.event_name == "Scratch-Wettbewerb"
        assert challenge.event_tagline == "Klasse 6b programmiert Spiele"

    def test_neuer_wettbewerb_ohne_angabe_bleibt_leer(self, einstellungen, admin, database):
        from models import Challenge

        admin.post("/admin/challenges/new", data={
            "csrf_token": csrf_token(admin, "/admin/challenges/new"),
            "title": "Runde 1",
        })

        challenge = Challenge.query.filter_by(title="Runde 1").one()
        assert challenge.event_name == ""
        assert challenge.event_tagline == ""

    def test_bearbeiten_speichert_den_namen(self, einstellungen, admin, database,
                                            make_challenge):
        challenge = make_challenge(title="Runde 1")
        pfad = f"/admin/challenges/{challenge.id}/edit"

        admin.post(pfad, data={
            "csrf_token": csrf_token(admin, pfad),
            "title": "Runde 1",
            "event_name": "Scratch-Wettbewerb",
            "event_tagline": "Klasse 6b programmiert Spiele",
        })

        database.session.refresh(challenge)
        assert challenge.event_name == "Scratch-Wettbewerb"

    def test_leeres_feld_nimmt_den_eigenen_namen_wieder_weg(self, einstellungen, admin,
                                                            database, make_challenge):
        """Anders als der Titel darf er geleert werden - leer heißt "wie eingestellt"."""
        challenge = make_challenge(title="Runde 1", event_name="Scratch-Wettbewerb")
        pfad = f"/admin/challenges/{challenge.id}/edit"

        admin.post(pfad, data={
            "csrf_token": csrf_token(admin, pfad),
            "title": "Runde 1",
            "event_name": "",
            "event_tagline": "",
        })

        database.session.refresh(challenge)
        assert challenge.event_name == ""

        from models import event_branding
        assert event_branding(challenge)["name"] == "Coding-Wettbewerb"

    def test_zu_langer_name_wird_gekuerzt_statt_abgelehnt(self, einstellungen, admin,
                                                          database, make_challenge):
        """Die Spalte fasst 100 Zeichen; mehr soll die Datenbank nicht sehen."""
        challenge = make_challenge(title="Runde 1")
        pfad = f"/admin/challenges/{challenge.id}/edit"

        admin.post(pfad, data={
            "csrf_token": csrf_token(admin, pfad),
            "title": "Runde 1",
            "event_name": "N" * 200,
        })

        database.session.refresh(challenge)
        assert len(challenge.event_name) == 100


def test_anmeldung_ohne_wettbewerb_funktioniert(einstellungen, client):
    """Auf einer frischen Installation gibt es noch keinen Wettbewerb."""
    assert client.get("/").status_code == 200
    assert "Coding-Wettbewerb" in client.get("/").get_data(as_text=True)
