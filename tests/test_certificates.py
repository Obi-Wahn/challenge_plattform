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


def seitenmasse(daten, seite=0):
    """Breite und Höhe der Seite in Millimetern, auf ganze mm gerundet."""
    kasten = pypdf.PdfReader(io.BytesIO(daten)).pages[seite].mediabox
    # PDF rechnet in Punkten: 72 Punkte sind ein Zoll, ein Zoll sind 25,4 mm.
    return (round(float(kasten.width) / 72 * 25.4),
            round(float(kasten.height) / 72 * 25.4))


class TestAusrichtung:
    """Quer- und Hochformat der Urkunden."""

    def test_querformat_ist_die_voreinstellung(self):
        daten = build_certificates_pdf("Site", "Runde 1", [EINTRAG], 3)
        breite, hoehe = seitenmasse(daten)
        assert (breite, hoehe) == (297, 210)

    def test_hochformat_dreht_das_blatt(self):
        daten = build_certificates_pdf("Site", "Runde 1", [EINTRAG], 3,
                                       orientation_key="portrait")
        breite, hoehe = seitenmasse(daten)
        assert (breite, hoehe) == (210, 297)

    def test_unbekannte_ausrichtung_faellt_auf_quer_zurueck(self):
        daten = build_certificates_pdf("Site", "Runde 1", [EINTRAG], 3,
                                       orientation_key="diagonal")
        assert seitenmasse(daten) == (297, 210)

    @pytest.mark.parametrize("ausrichtung", ["landscape", "portrait"])
    def test_inhalt_steht_in_beiden_formaten_vollstaendig_drin(self, ausrichtung):
        daten = build_certificates_pdf("Coding-Wettbewerb", "Runde 1", [EINTRAG], 3,
                                       signature_name="Tobias Händler",
                                       orientation_key=ausrichtung)
        text = pdf_text(daten)
        for erwartet in ["Urkunde", "Die Pixelpiraten", "Runde 1", "1. Platz",
                         "38 Punkte", "Coding-Wettbewerb"]:
            assert erwartet in text, f"{erwartet!r} fehlt im {ausrichtung}"

    @pytest.mark.parametrize("ausrichtung", ["landscape", "portrait"])
    def test_jede_seite_hat_dieselbe_ausrichtung(self, ausrichtung):
        eintraege = [dict(EINTRAG, team_id=i, name=f"Team {i}", rank=i)
                     for i in range(1, 4)]
        daten = build_certificates_pdf("Site", "Runde 1", eintraege, 3,
                                       orientation_key=ausrichtung)
        assert seitenzahl(daten) == 3
        masse = {seitenmasse(daten, s) for s in range(3)}
        assert len(masse) == 1


class TestLangeTexteImHochformat:
    """Im Hochformat ist das Blatt 87 mm schmaler - Text muss trotzdem passen."""

    @pytest.mark.parametrize("ausrichtung", ["landscape", "portrait"])
    def test_langer_teamname_laeuft_nicht_ueber_den_rand(self, ausrichtung):
        from certificates import CertificatePDF, certificate_orientation

        name = "Die unglaublich langen Pixelpiraten aus der 8b"
        eintrag = dict(EINTRAG, name=name)
        ausricht = certificate_orientation(ausrichtung)

        pdf = CertificatePDF(orientation=ausricht["fpdf"], unit="mm", format="A4",
                             scale=ausricht["scale"])
        pdf.set_auto_page_break(False)
        pdf.certificate("Site", "Runde 1", eintrag, 3, "01.01.2026")

        # Der Seitenrand ist nicht die Grenze: Der Zierrahmen liegt weiter
        # innen, und genau dort lief der Name vorher hinein.
        groesse = pdf.fitted_size(name, "Helvetica", "B", 30)
        assert pdf.get_string_width(name) <= pdf.text_width()
        assert pdf.text_width() < pdf.w - pdf.l_margin - pdf.r_margin, \
            "die Grenze muss enger sein als der Seitenrand"
        if ausrichtung == "portrait":
            assert groesse < 30, "im Hochformat muss verkleinert werden"

    @pytest.mark.parametrize("ausrichtung", ["landscape", "portrait"])
    def test_kein_text_beruehrt_den_zierrahmen(self, ausrichtung):
        """Der Zierrahmen liegt bei 14 mm - Text muss davor haltmachen.

        Gegen die Seitenränder zu prüfen reichte nicht: Der Name passte
        zwischen die Ränder und lief trotzdem in den Rahmen hinein. Weil
        alle Zeilen mittig stehen, genügt der linke Rand: Was links im
        Rahmen bleibt, bleibt auch rechts drin.
        """
        daten = build_certificates_pdf(
            "Coding-Wettbewerb der Realschule",
            "Der große Scratch- und Calliope-Wettbewerb der Jahrgangsstufe 8",
            [dict(EINTRAG, name="Die unglaublich langen Pixelpiraten aus der 8b")],
            4,
            signature_name="Tobias Henze",
            orientation_key=ausrichtung,
        )

        rahmen = 14 * 72 / 25.4  # 14 mm in PDF-Punkten
        gefunden = []

        def besucher(text, cm, tm, schrift, groesse):
            if text.strip():
                gefunden.append((text.strip(), tm[4]))

        pypdf.PdfReader(io.BytesIO(daten)).pages[0].extract_text(
            visitor_text=besucher)

        assert gefunden, "es wurde überhaupt kein Text gefunden"
        for text, x in gefunden:
            assert x >= rahmen, f"{text!r} beginnt im Rahmen (x={x:.1f}, Rahmen={rahmen:.1f})"

    def test_langer_wettbewerbstitel_passt_ebenfalls(self):
        titel = "Der große Scratch- und Calliope-Wettbewerb der Jahrgangsstufe 8"
        daten = build_certificates_pdf("Site", titel, [EINTRAG], 3,
                                       orientation_key="portrait")
        # Vollständig lesbar heißt: der Titel steht ungekürzt im PDF.
        assert titel in pdf_text(daten)

    def test_kurzer_name_wird_nicht_verkleinert(self):
        from certificates import CertificatePDF

        pdf = CertificatePDF(orientation="P", unit="mm", format="A4")
        pdf.add_page()
        assert pdf.fitted_size("Team A", "Helvetica", "B", 30) == 30


def textzeilen(daten, seite=0):
    """Die Zeilen einer Seite mit Position und Schriftgröße.

    x und y sind Millimeter, y von der Blattoberkante aus gemessen.
    """
    hoehe = float(pypdf.PdfReader(io.BytesIO(daten)).pages[seite].mediabox.height)
    gefunden = []

    def besucher(text, cm, tm, schrift, groesse):
        if text.strip():
            gefunden.append({
                "text": text.strip(),
                "x": tm[4] / 72 * 25.4,
                "y": (hoehe - tm[5]) / 72 * 25.4,
                "groesse": groesse,
            })

    pypdf.PdfReader(io.BytesIO(daten)).pages[seite].extract_text(
        visitor_text=besucher)
    return gefunden


def zeile_mit(zeilen, text):
    for zeile in zeilen:
        if text in zeile["text"]:
            return zeile
    raise AssertionError(f"{text!r} steht nicht auf der Urkunde")


class TestTeamnameBleibtLesbar:
    """Der Name ist die Hauptzeile - er darf nicht der kleinste Text sein."""

    LANG = "Die unglaublich schnellen Schildkroeten aus Klasse 8b"

    @pytest.mark.parametrize("ausrichtung", ["landscape", "portrait"])
    def test_langer_name_bleibt_groesser_als_der_fliesstext(self, ausrichtung):
        """Vorher schrumpfte er im Hochformat unter die Zeile darunter."""
        daten = build_certificates_pdf(
            "Robotik-Wettbewerb der Gesamtschule Musterstadt", "Sumo-Roboter 2026",
            [dict(EINTRAG, name=self.LANG)], 8, orientation_key=ausrichtung)

        zeilen = textzeilen(daten)
        name = zeile_mit(zeilen, "Die unglaublich")
        fliesstext = zeile_mit(zeilen, "für die Teilnahme")

        assert name["groesse"] > fliesstext["groesse"], (
            f"der Teamname ({name['groesse']:.1f}pt) ist kleiner gesetzt als "
            f"der Fliesstext ({fliesstext['groesse']:.1f}pt)")

    def test_im_hochformat_darf_der_name_umbrechen(self):
        daten = build_certificates_pdf("Site", "Runde 1",
                                       [dict(EINTRAG, name=self.LANG)], 3,
                                       orientation_key="portrait")

        teile = [z["text"] for z in textzeilen(daten) if "Schildkroeten" in z["text"]
                 or "Die unglaublich" in z["text"]]
        assert len(teile) == 2, f"erwartet wurden zwei Zeilen, gefunden: {teile}"
        assert " ".join(teile) == self.LANG

    def test_im_querformat_bleibt_er_einzeilig(self):
        """Dort reicht die Breite - ein Umbruch waere nur unruhig."""
        daten = build_certificates_pdf("Site", "Runde 1",
                                       [dict(EINTRAG, name=self.LANG)], 3,
                                       orientation_key="landscape")

        assert zeile_mit(textzeilen(daten), "Schildkroeten")["text"] == self.LANG

    def test_ein_name_bricht_nicht_auf_mehr_als_zwei_zeilen(self):
        name = ("Arbeitsgemeinschaft Robotik und Technik der Gesamtschule "
                "Musterstadt Nord und Umgebung")
        daten = build_certificates_pdf("Site", "Runde 1",
                                       [dict(EINTRAG, name=name)], 3,
                                       orientation_key="portrait")

        gesucht = name.split()[0]
        zeilen = textzeilen(daten)
        start = [i for i, z in enumerate(zeilen) if gesucht in z["text"]][0]
        # Zwischen Name und "für die Teilnahme" darf hoechstens eine weitere
        # Zeile stehen.
        bis = [i for i, z in enumerate(zeilen) if "für die Teilnahme" in z["text"]][0]
        assert bis - start <= 2


class TestUnterschriftBleibtAufDerLinie:
    """Die Linie ist die Grenze, nicht der Zierrahmen."""

    NAME = "Dr. Tobias Mustermann-Schildkroetenhausen"

    @pytest.mark.parametrize("ausrichtung", ["landscape", "portrait"])
    def test_langer_name_laeuft_nicht_ueber_die_linie(self, ausrichtung):
        from certificates import certificate_orientation

        ausricht = certificate_orientation(ausrichtung)
        daten = build_certificates_pdf("Site", "Runde 1", [EINTRAG], 3,
                                       signature_name=self.NAME,
                                       signature_font_key="caveat",
                                       orientation_key=ausrichtung)

        breite_mm, _ = seitenmasse(daten)
        linie = min(80 * ausricht["scale"], breite_mm - 60)

        # Alle Zeilen stehen mittig, also genügt der linke Rand: Was links
        # innerhalb der Linie beginnt, endet rechts auch dort.
        for zeile in textzeilen(daten):
            if self.NAME.split()[-1] in zeile["text"]:
                text_breite = breite_mm - 2 * zeile["x"]
                assert text_breite <= linie + 0.5, (
                    f"die Unterschrift ist {text_breite:.1f} mm breit, "
                    f"die Linie nur {linie:.1f} mm")


class TestAusrichtungEinstellen:
    def test_auswahl_wird_gespeichert(self, admin, database):
        from models import Settings

        admin.post("/admin/settings", data={
            "csrf_token": csrf_token(admin, "/admin/settings"),
            "site_name": "W", "tagline": "U",
            "signature_name": "", "signature_font": "caveat",
            "certificate_orientation": "portrait",
        })

        assert Settings.get().certificate_orientation == "portrait"

    def test_unbekannte_auswahl_wird_nicht_gespeichert(self, admin, database):
        from models import Settings

        admin.post("/admin/settings", data={
            "csrf_token": csrf_token(admin, "/admin/settings"),
            "site_name": "W", "tagline": "U",
            "signature_name": "", "signature_font": "caveat",
            "certificate_orientation": "diagonal",
        })

        assert Settings.get().certificate_orientation == "landscape"

    def test_einstellungsseite_zeigt_beide_formate_zur_wahl(self, admin, database):
        html = admin.get("/admin/settings").get_data(as_text=True)
        assert 'value="landscape"' in html
        assert 'value="portrait"' in html

    def test_download_folgt_der_einstellung(self, admin, make_challenge, make_team,
                                            database):
        from models import Settings

        challenge = make_challenge()
        make_team(challenge, name="Team A")
        Settings.get().certificate_orientation = "portrait"
        database.session.commit()

        antwort = admin.get("/admin/urkunden.pdf")
        assert seitenmasse(antwort.data) == (210, 297)

    def test_druckansicht_folgt_der_einstellung(self, admin, make_challenge, make_team,
                                                database):
        from models import Settings

        challenge = make_challenge()
        make_team(challenge, name="Team A")
        Settings.get().certificate_orientation = "portrait"
        database.session.commit()

        html = admin.get("/admin/urkunden").get_data(as_text=True)
        assert "size: A4 portrait" in html
        assert "277mm" in html
        # Der Hinweis über den Urkunden darf nicht das Gegenteil raten.
        assert "im Druckdialog Hochformat wählen" in html
        assert "Querformat" not in html

    def test_druckansicht_bleibt_ohne_einstellung_quer(self, admin, make_challenge,
                                                       make_team, database):
        challenge = make_challenge()
        make_team(challenge, name="Team A")

        html = admin.get("/admin/urkunden").get_data(as_text=True)
        assert "size: A4 landscape" in html
        assert "186mm" in html
        assert "im Druckdialog Querformat wählen" in html

    def test_team_bekommt_seine_urkunde_im_gewaehlten_format(
            self, make_challenge, logged_in_team, database):
        from models import Settings

        challenge = make_challenge(
            end_time=datetime.now() - timedelta(minutes=5),
            start_time=datetime.now() - timedelta(hours=2),
        )
        client, _team = logged_in_team(challenge)
        Settings.get().certificate_orientation = "portrait"
        database.session.commit()

        antwort = client.get("/urkunde.pdf")
        assert antwort.status_code == 200
        assert seitenmasse(antwort.data) == (210, 297)


class TestHochformatFuelltDasBlatt:
    """Ein A4-Hochblatt ist 87 mm höher - das soll Schrift füllen, nicht Leerraum.

    Mit den Größen des Querformats stand der Text als kleiner Block in der
    Mitte. Im Hochformat wird deshalb alles größer gesetzt: Schrift,
    Zeilenhöhen und Abstände gleichermaßen, damit die Anordnung dieselbe
    bleibt.
    """

    def textbereich(self, daten):
        """Von der obersten bis zur untersten Textzeile, in Millimetern."""
        seite = pypdf.PdfReader(io.BytesIO(daten)).pages[0]
        hoehen = []

        def besucher(text, cm, tm, schrift, groesse):
            if text.strip():
                hoehen.append(tm[5])

        seite.extract_text(visitor_text=besucher)
        assert hoehen, "kein Text gefunden"
        return (min(hoehen) / 72 * 25.4, max(hoehen) / 72 * 25.4)

    def schriftgroessen(self, daten):
        seite = pypdf.PdfReader(io.BytesIO(daten)).pages[0]
        groessen = []

        def besucher(text, cm, tm, schrift, groesse):
            if text.strip():
                # tm[0] ist die waagerechte Skalierung der Textmatrix.
                groessen.append(round(groesse * tm[0], 1))

        seite.extract_text(visitor_text=besucher)
        return groessen

    def urkunde(self, ausrichtung):
        return build_certificates_pdf(
            "Coding-Wettbewerb", "Scratch!",
            [{"team_id": 1, "name": "Test1", "total": 10, "solved": 1, "rank": 1}],
            4, date_text="21.09.2026", signature_name="Tobias Henze",
            orientation_key=ausrichtung)

    def test_hochformat_setzt_groesser_als_querformat(self):
        quer = max(self.schriftgroessen(self.urkunde("landscape")))
        hoch = max(self.schriftgroessen(self.urkunde("portrait")))

        assert hoch > quer, "im Hochformat muss größer gesetzt werden"

    def test_der_text_nutzt_mehr_als_die_haelfte_der_hoehe(self):
        """Sonst steht er wieder als Block in der Mitte."""
        oben, unten = self.textbereich(self.urkunde("portrait"))
        # In PDF-Koordinaten wächst y nach oben, deshalb ist "unten" der
        # größere Wert.
        genutzt = unten - oben
        innen = 297 - 2 * 14   # Blatt minus Zierrahmen

        assert genutzt > innen / 2, \
            f"der Text nutzt nur {genutzt:.0f} von {innen} mm"

    def zeilen_von_oben(self, daten):
        """Die Höhe jeder Textzeile, von der Blattoberkante aus in Millimetern."""
        seite = pypdf.PdfReader(io.BytesIO(daten)).pages[0]
        hoehen = []

        def besucher(text, cm, tm, schrift, groesse):
            if text.strip():
                hoehen.append(297 - tm[5] / 72 * 25.4)

        seite.extract_text(visitor_text=besucher)
        return sorted(hoehen)

    def test_der_hauptblock_steht_mittig_ueber_der_unterschrift(self):
        """Nicht die äußersten Zeilen zählen, sondern der Textblock.

        Der Unterschriftsblock sitzt absichtlich unten am Blatt. Gemessen
        werden muss deshalb der Abstand vom Rahmen zum Hauptblock und der
        vom Hauptblock zum Unterschriftsblock - dazwischen soll es
        ausgewogen aussehen.
        """
        from certificates import certificate_orientation

        hoch = certificate_orientation("portrait")
        beginn_unterschrift = 297 - hoch["signature_offset"]

        hauptblock = [y for y in self.zeilen_von_oben(self.urkunde("portrait"))
                      if y < beginn_unterschrift]
        assert hauptblock, "kein Text über dem Unterschriftsblock"

        luft_oben = min(hauptblock) - 14
        luft_unten = beginn_unterschrift - max(hauptblock)

        assert abs(luft_oben - luft_unten) < 15, \
            f"oben {luft_oben:.0f} mm, unten {luft_unten:.0f} mm - schief"

    def test_ueber_der_unterschrift_bleibt_kein_leeres_band(self):
        """Der Rest der Höhe geht in die Abstände, nicht in ein leeres Band.

        Der Textblock stand zwar mittig, füllte das Hochblatt aber nicht:
        zwischen der letzten Zeile und dem Unterschriftsblock klaffte ein
        leeres Band von gut 4 cm.
        """
        from certificates import certificate_orientation

        beginn_unterschrift = 297 - certificate_orientation("portrait")["signature_offset"]
        hauptblock = [y for y in self.zeilen_von_oben(self.urkunde("portrait"))
                      if y < beginn_unterschrift]

        band = beginn_unterschrift - max(hauptblock)
        assert band < 30, f"über der Unterschrift stehen {band:.0f} mm leer"

    def test_der_text_bleibt_im_zierrahmen(self):
        oben, unten = self.textbereich(self.urkunde("portrait"))

        assert oben > 14, f"der Text beginnt bei {oben:.0f} mm, im Rahmen"
        assert unten < 297 - 14, f"der Text endet bei {unten:.0f} mm, im Rahmen"

    def test_querformat_bleibt_unveraendert(self):
        """Die Größen des Querformats dürfen sich nicht mitverschieben."""
        from certificates import CERTIFICATE_ORIENTATIONS

        assert CERTIFICATE_ORIENTATIONS["landscape"]["scale"] == 1.0
        assert CERTIFICATE_ORIENTATIONS["landscape"]["signature_offset"] == 52
        # Die Überschrift steht im Querformat weiterhin in 40 Punkt.
        assert 40 in [round(g) for g in self.schriftgroessen(self.urkunde("landscape"))]


class TestNamenDerTeammitglieder:
    """Die Namen der Schüler unter dem Teamnamen."""

    MIT_NAMEN = dict(EINTRAG, members=["Anna Beispiel", "Ben Muster", "Carla Test"])

    def zeilen(self, daten):
        """Jede Zeile als (Text, Höhe von unten, gesetzte Schriftgröße)."""
        gefunden = []

        def besucher(text, cm, tm, schrift, groesse):
            if text.strip():
                gefunden.append((text.strip(), round(tm[5], 2), round(groesse * tm[3], 2)))

        for seite in pypdf.PdfReader(io.BytesIO(daten)).pages:
            seite.extract_text(visitor_text=besucher)
        return gefunden

    def urkunde(self, eintrag, ausrichtung="landscape"):
        return build_certificates_pdf(
            "Coding-Wettbewerb", "Scratch-Cup", [eintrag], 4,
            date_text="21.09.2026", signature_name="Tobias Händler",
            orientation_key=ausrichtung)

    @pytest.mark.parametrize("ausrichtung", ["landscape", "portrait"])
    def test_die_namen_stehen_unter_dem_teamnamen(self, ausrichtung):
        zeilen = self.zeilen(self.urkunde(self.MIT_NAMEN, ausrichtung))
        texte = [text for text, _, _ in zeilen]

        assert "Anna Beispiel, Ben Muster und Carla Test" in texte
        assert texte.index("Die Pixelpiraten") + 1 == texte.index(
            "Anna Beispiel, Ben Muster und Carla Test")

    @pytest.mark.parametrize("ausrichtung", ["landscape", "portrait"])
    def test_die_namen_stehen_kleiner_als_der_teamname(self, ausrichtung):
        """Der Teamname bleibt die größte Zeile - es ist seine Urkunde."""
        zeilen = self.zeilen(self.urkunde(self.MIT_NAMEN, ausrichtung))
        groessen = {text: groesse for text, _, groesse in zeilen}

        assert (groessen["Anna Beispiel, Ben Muster und Carla Test"]
                < groessen["Die Pixelpiraten"])

    @pytest.mark.parametrize("ausrichtung", ["landscape", "portrait"])
    def test_die_namen_stehen_nicht_kleiner_als_der_fliesstext(self, ausrichtung):
        """Wessen Urkunde das ist, soll nicht das Kleingedruckte sein."""
        zeilen = self.zeilen(self.urkunde(self.MIT_NAMEN, ausrichtung))
        groessen = {text: groesse for text, _, groesse in zeilen}

        fliesstext = groessen['für die Teilnahme am Wettbewerb "Scratch-Cup"']
        assert groessen["Anna Beispiel, Ben Muster und Carla Test"] >= fliesstext

    def test_ohne_namen_steht_keine_zusaetzliche_zeile_da(self):
        zeilen = self.zeilen(self.urkunde(EINTRAG))
        texte = [text for text, _, _ in zeilen]

        assert texte.index("Die Pixelpiraten") + 1 == texte.index(
            'für die Teilnahme am Wettbewerb "Scratch-Cup"')

    # Das Layout ohne Namen, wie es vor dieser Änderung war: Höhe über dem
    # unteren Blattrand und gesetzte Schriftgröße je Zeile. Das Querformat ist
    # die eingefrorene Referenz und darf sich durch nichts verschieben.
    REFERENZ = {
        "landscape": [
            (474.26, 16.0), (418.87, 40.0), (372.81, 14.0), (328.33, 30.0),
            (287.77, 14.0), (240.02, 22.0), (202.73, 14.0),
            (135.3, 12.0), (108.42, 26.0), (83.46, 10.0),
        ],
        "portrait": [
            (707.43, 21.6), (617.34, 54.0), (532.2, 18.9), (464.5, 40.5),
            (394.44, 18.9), (307.01, 29.7), (241.37, 18.9),
            (159.41, 16.2), (123.12, 35.1), (89.42, 13.5),
        ],
    }

    @pytest.mark.parametrize("ausrichtung", ["landscape", "portrait"])
    def test_ohne_namen_steht_alles_wie_vorher(self, ausrichtung):
        """Ein Team ohne freigegebene Namen bekommt genau die alte Urkunde."""
        gemessen = [(y, groesse)
                    for _, y, groesse in self.zeilen(self.urkunde(EINTRAG, ausrichtung))]

        assert gemessen == self.REFERENZ[ausrichtung]

    @pytest.mark.parametrize("ausrichtung", ["landscape", "portrait"])
    def test_die_laengste_erlaubte_liste_laeuft_nicht_in_die_unterschrift(self,
                                                                          ausrichtung):
        """Viele lange Namen sind der Normalfall, nicht der Sonderfall."""
        from certificates import names_line
        from models import MAX_MEMBERS, MAX_MEMBER_TEXT_LENGTH

        namen = ["Anna-Lena Schmidt-Hohenzollern"] * MAX_MEMBERS
        while len(names_line(namen)) > MAX_MEMBER_TEXT_LENGTH:
            namen.pop()

        zeilen = self.zeilen(self.urkunde(dict(EINTRAG, members=namen), ausrichtung))
        # Die letzten drei Zeilen sind Datum und Unterschrift, ganz unten am Blatt.
        text_unten = min(y for _, y, _ in zeilen[:-3])
        block_oben = max(y for _, y, _ in zeilen[-3:])
        luft = (text_unten - block_oben) / 72 * 25.4

        assert luft > 7, f"nur {luft:.1f} mm über dem Unterschriftsblock"
