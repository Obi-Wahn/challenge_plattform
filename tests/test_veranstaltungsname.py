"""Der Name eines Wettbewerbs ist sein Titel, und er gilt dort, wo er gemeint ist.

Die Einstellungen halten nur die Standardwerte: Sie gelten, solange kein
Wettbewerb mit eigenem Namen läuft. Läuft einer, steht überall sein Name -
auf der Startseite, der Rangliste, der Teamseite, den Urkunden und auch im
Browsertitel, in der Leiste oben und in der Fußzeile. Den Untertitel darf ein
Wettbewerb überschreiben; lässt er ihn leer, gilt der aus den Einstellungen.
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
    """Die globalen Werte, auf die ohne Wettbewerb zurückgefallen wird."""
    from models import Settings

    settings = Settings.get()
    settings.site_name = "Coding-Wettbewerb"
    settings.tagline = "Ein Wettbewerb für Code, Ideen und Kreativität."
    database.session.commit()
    return settings


class TestAuflösung:
    def test_der_titel_ist_der_name(self, einstellungen, make_challenge):
        from models import event_branding

        challenge = make_challenge(title="Scratch-Wettbewerb")

        assert event_branding(challenge)["name"] == "Scratch-Wettbewerb"

    def test_ohne_eigenen_untertitel_gilt_der_aus_den_einstellungen(self, einstellungen,
                                                                    make_challenge):
        from models import event_branding

        marke = event_branding(make_challenge(title="Scratch-Wettbewerb"))

        assert marke["tagline"] == "Ein Wettbewerb für Code, Ideen und Kreativität."

    def test_eigener_untertitel_gewinnt(self, einstellungen, make_challenge):
        from models import event_branding

        challenge = make_challenge(title="Scratch-Wettbewerb",
                                   tagline="Klasse 6b programmiert Spiele")

        assert event_branding(challenge)["tagline"] == "Klasse 6b programmiert Spiele"

    def test_ohne_wettbewerb_gelten_die_einstellungen(self, einstellungen):
        """Auf einer frischen Installation gibt es noch keinen Wettbewerb."""
        from models import event_branding

        marke = event_branding(None)

        assert marke["name"] == "Coding-Wettbewerb"
        assert marke["tagline"] == "Ein Wettbewerb für Code, Ideen und Kreativität."


class TestSeiten:
    def test_startseite_zeigt_den_namen_des_wettbewerbs(self, einstellungen, client,
                                                        make_challenge):
        make_challenge(title="Scratch-Wettbewerb",
                       tagline="Klasse 6b programmiert Spiele")

        seite = client.get("/").get_data(as_text=True)

        assert "Scratch-Wettbewerb" in seite
        assert "Klasse 6b programmiert Spiele" in seite

    def test_rangliste_zeigt_den_namen_des_wettbewerbs(self, einstellungen, client,
                                                       make_challenge):
        """Die Rangliste ist die Beamerseite, seit es die Countdown-Seite nicht mehr gibt."""
        make_challenge(title="Calliope-Wettbewerb")

        assert "Calliope-Wettbewerb" in client.get("/scoreboard").get_data(as_text=True)

    def test_leiste_oben_zeigt_den_namen_des_wettbewerbs(self, einstellungen, client,
                                                        make_challenge):
        """Auch auf einer Seite, die zu keinem Wettbewerb gehört: Es läuft ja einer."""
        make_challenge(title="Scratch-Wettbewerb")

        seite = client.get("/login").get_data(as_text=True)

        assert 'class="navbar-brand"' in seite
        assert "Scratch-Wettbewerb" in seite
        assert "Coding-Wettbewerb" not in seite

    def test_browsertitel_und_fusszeile_zeigen_den_wettbewerb(self, einstellungen, client,
                                                              make_challenge):
        make_challenge(title="Scratch-Wettbewerb")

        seite = client.get("/login").get_data(as_text=True)

        assert "<title>Scratch-Wettbewerb</title>" in seite
        assert "&copy; Scratch-Wettbewerb" in seite

    def test_leiste_oben_bleibt_beim_aktiven_wettbewerb(self, einstellungen, admin,
                                                        make_challenge):
        """Eine Seite über einen älteren Wettbewerb ändert die Leiste nicht."""
        alt = make_challenge(title="Calliope-Wettbewerb", active=False)
        make_challenge(title="Scratch-Wettbewerb")

        seite = admin.get(f"/admin/urkunden?wettbewerb={alt.id}").get_data(as_text=True)

        assert "Calliope-Wettbewerb" in seite
        assert ">🚀 Scratch-Wettbewerb</a>" in seite

    def test_ohne_wettbewerb_steht_der_standardname_in_der_leiste(self, einstellungen,
                                                                  client):
        """Zum Beispiel auf einer frischen Installation."""
        seite = client.get("/login").get_data(as_text=True)

        assert "Coding-Wettbewerb" in seite

    def test_ohne_wettbewerb_steht_der_name_aus_den_einstellungen_da(self, einstellungen,
                                                                     client):
        seite = client.get("/").get_data(as_text=True)

        assert "Coding-Wettbewerb" in seite
        assert "Ein Wettbewerb für Code, Ideen und Kreativität." in seite


class TestUrkunde:
    def test_urkunde_traegt_den_namen_des_wettbewerbs(self, einstellungen, make_challenge,
                                                      make_team):
        from certificates import build_certificates_for, certificate_entry

        challenge = make_challenge(title="Scratch-Wettbewerb")
        team = make_team(challenge, name="Die Pixelpiraten")

        text = pdf_text(build_certificates_for(challenge, [certificate_entry(team, [])], 0))

        assert "Scratch-Wettbewerb" in text
        assert "Coding-Wettbewerb" not in text

    def test_der_name_steht_nur_einmal_auf_dem_blatt(self, einstellungen, make_challenge,
                                                     make_team):
        """Kopfzeile und Teilnahme-Zeile nannten ihn vorher beide."""
        from certificates import build_certificates_for, certificate_entry

        challenge = make_challenge(title="Scratch-Wettbewerb")
        team = make_team(challenge, name="Die Pixelpiraten")

        text = pdf_text(build_certificates_for(challenge, [certificate_entry(team, [])], 0))

        assert text.count("Scratch-Wettbewerb") == 1
        assert "für die Teilnahme am Wettbewerb" in text

    def test_ohne_wettbewerb_steht_der_name_aus_den_einstellungen_drauf(self,
                                                                        einstellungen):
        from certificates import build_certificates_for

        eintrag = {"team_id": 1, "name": "Die Pixelpiraten",
                   "total": 0, "solved": 0, "rank": 0}

        assert "Coding-Wettbewerb" in pdf_text(build_certificates_for(None, [eintrag], 0))


class TestLangerName:
    """Ein Wettbewerbsname wird länger als "Coding-Wettbewerb".

    Er darf deshalb auf zwei Zeilen umbrechen, statt unter die Größe des
    Fließtextes zu schrumpfen - dieselbe Regel wie beim Teamnamen. Geprüft
    wird am fertigen PDF, in beiden Ausrichtungen.
    """

    LANG = "Calliope-mini-Wettbewerb der Klassen 5 und 6 am Gymnasium Musterstadt"

    def urkunde(self, name, ausrichtung):
        from certificates import build_certificates_pdf

        eintrag = {"team_id": 1, "name": "Die Pixelpiraten",
                   "total": 38, "solved": 3, "rank": 1}
        return pdf_zeilen(build_certificates_pdf(name, [eintrag], 4,
                                                 orientation_key=ausrichtung))

    @pytest.mark.parametrize("ausrichtung", ["landscape", "portrait"])
    def test_langer_name_wird_nicht_kleiner_als_der_fliesstext(self, ausrichtung):
        zeilen = self.urkunde(self.LANG, ausrichtung)
        fliesstext = next(g for g, t in zeilen if t == "verliehen an das Team")

        kopf = [g for g, t in zeilen if t and t in self.LANG]

        assert kopf, "Der Name des Wettbewerbs steht nicht auf der Urkunde"
        assert min(kopf) >= fliesstext

    def test_im_hochformat_bricht_er_um_statt_zu_schrumpfen(self):
        zeilen = self.urkunde(self.LANG, "portrait")
        volle_groesse = self.urkunde("Coding-Wettbewerb", "portrait")[0][0]

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
        alt = make_challenge(title="Scratch-Wettbewerb", active=False)
        make_team(alt, name="Die Pixelpiraten")

        neu = make_challenge(title="Calliope-Wettbewerb", active=True)
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

        team = Team.query.filter_by(name="Die Pixelpiraten").one()

        antwort = admin.get(f"/admin/urkunden/{team.id}.pdf")

        assert antwort.status_code == 200
        assert "Scratch-Wettbewerb" in pdf_text(antwort.data)

    def test_unbekannter_wettbewerb_gibt_404(self, admin, zwei_wettbewerbe):
        assert admin.get("/admin/urkunden?wettbewerb=9999").status_code == 404

    def test_wettbewerb_ohne_zahl_wird_ignoriert(self, admin, zwei_wettbewerbe):
        """Eine krumme Adresse soll die Seite nicht mit 500 beenden."""
        antwort = admin.get("/admin/urkunden?wettbewerb=abc")

        assert antwort.status_code == 200
        assert "Die Bitjaeger" in antwort.get_data(as_text=True)


class TestFormular:
    def test_neuer_wettbewerb_speichert_den_untertitel(self, einstellungen, admin, database):
        from models import Challenge

        admin.post("/admin/challenges/new", data={
            "csrf_token": csrf_token(admin, "/admin/challenges/new"),
            "title": "Scratch-Wettbewerb",
            "tagline": "Klasse 6b programmiert Spiele",
        })

        challenge = Challenge.query.filter_by(title="Scratch-Wettbewerb").one()
        assert challenge.tagline == "Klasse 6b programmiert Spiele"

    def test_neuer_wettbewerb_ohne_untertitel_bleibt_leer(self, einstellungen, admin,
                                                          database):
        from models import Challenge

        admin.post("/admin/challenges/new", data={
            "csrf_token": csrf_token(admin, "/admin/challenges/new"),
            "title": "Scratch-Wettbewerb",
        })

        assert Challenge.query.filter_by(title="Scratch-Wettbewerb").one().tagline == ""

    def test_bearbeiten_speichert_den_untertitel(self, einstellungen, admin, database,
                                                 make_challenge):
        challenge = make_challenge(title="Scratch-Wettbewerb")
        pfad = f"/admin/challenges/{challenge.id}/edit"

        admin.post(pfad, data={
            "csrf_token": csrf_token(admin, pfad),
            "title": "Scratch-Wettbewerb",
            "tagline": "Klasse 6b programmiert Spiele",
        })

        database.session.refresh(challenge)
        assert challenge.tagline == "Klasse 6b programmiert Spiele"

    def test_leeres_feld_nimmt_den_eigenen_untertitel_wieder_weg(self, einstellungen, admin,
                                                                 database, make_challenge):
        """Anders als der Name darf er geleert werden - leer heißt "wie eingestellt"."""
        challenge = make_challenge(title="Scratch-Wettbewerb", tagline="Eigener Text")
        pfad = f"/admin/challenges/{challenge.id}/edit"

        admin.post(pfad, data={
            "csrf_token": csrf_token(admin, pfad),
            "title": "Scratch-Wettbewerb",
            "tagline": "",
        })

        database.session.refresh(challenge)
        assert challenge.tagline == ""

        from models import event_branding
        assert event_branding(challenge)["tagline"] == \
            "Ein Wettbewerb für Code, Ideen und Kreativität."

    def test_zu_langer_untertitel_wird_gekuerzt(self, einstellungen, admin, database,
                                                make_challenge):
        """Die Spalte fasst 300 Zeichen; mehr soll die Datenbank nicht sehen."""
        challenge = make_challenge(title="Scratch-Wettbewerb")
        pfad = f"/admin/challenges/{challenge.id}/edit"

        admin.post(pfad, data={
            "csrf_token": csrf_token(admin, pfad),
            "title": "Scratch-Wettbewerb",
            "tagline": "U" * 400,
        })

        database.session.refresh(challenge)
        assert len(challenge.tagline) == 300
