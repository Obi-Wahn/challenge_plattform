"""Die Dauer in Minuten und die Pause, die die Uhr wirklich anhält.

Für eine Schulstunde ist die Dauer die natürliche Eingabe: Man weiß, dass man
45 Minuten hat, nicht, dass um 10:23 Uhr Schluss ist. Gespeichert wird
trotzdem weiterhin allein die Endzeit - die Dauer rechnet sie nur aus.

Und eine Pause, die die Endzeit stehen lässt, verschenkt den Teams genau die
Zeit, die sie dauert. Deshalb merkt sich der Wettbewerb, wann pausiert wurde,
rechnet solange ab diesem Zeitpunkt und schiebt die Endzeit beim Fortsetzen
nach hinten.
"""

import re
from datetime import datetime, timedelta

from tests.helpers import csrf_token


def anmelden_und_posten(admin, pfad, daten):
    daten = dict(daten)
    daten["csrf_token"] = csrf_token(admin, "/admin/challenges/new")
    return admin.post(pfad, data=daten, follow_redirects=True)


def frisch(challenge):
    """Den Wettbewerb neu aus der Datenbank holen."""
    from extensions import db
    from models import Challenge

    db.session.expire_all()
    return db.session.get(Challenge, challenge.id)


class TestPauseHaeltDieUhrAn:
    def test_die_restzeit_steht_waehrend_der_pause_still(self, make_challenge):
        """Der Kern der Sache: Das Ende rückt in der Pause nicht näher."""
        challenge = make_challenge(
            start_time=datetime.now() - timedelta(minutes=10),
            end_time=datetime.now() + timedelta(minutes=30),
            paused=True,
            paused_at=datetime.now() - timedelta(minutes=5),
        )

        # Pausiert wurde vor fünf Minuten, damals waren es 35 Minuten.
        assert 2090 <= challenge.remaining_seconds <= 2100

    def test_ohne_pause_laeuft_die_uhr_wie_bisher(self, make_challenge):
        challenge = make_challenge(
            start_time=datetime.now() - timedelta(minutes=10),
            end_time=datetime.now() + timedelta(minutes=30),
        )
        assert 1790 <= challenge.remaining_seconds <= 1800

    def test_eine_endzeit_in_der_pause_beendet_den_wettbewerb_nicht(self, make_challenge):
        """Sonst wäre eine Pause über die Endzeit hinaus das Ende.

        Genau das passierte früher: Die Endzeit blieb stehen, verstrich
        während der Pause, und der Wettbewerb galt als beendet.
        """
        challenge = make_challenge(
            start_time=datetime.now() - timedelta(hours=2),
            end_time=datetime.now() - timedelta(minutes=10),
            paused=True,
            paused_at=datetime.now() - timedelta(minutes=30),
        )

        assert challenge.status() == "running"
        assert challenge.state_label == "pausiert"
        assert challenge.accepts_submissions is False

    def test_eine_pause_ohne_zeitpunkt_verhaelt_sich_wie_frueher(self, make_challenge):
        """Bestand aus der Zeit vor der Spalte darf nicht kippen."""
        challenge = make_challenge(
            start_time=datetime.now() - timedelta(hours=2),
            end_time=datetime.now() - timedelta(minutes=10),
            paused=True,
        )

        assert challenge.paused_at is None
        assert challenge.status() == "finished"


class TestPauseUndFortsetzenImAdmin:
    def test_pause_merkt_sich_den_zeitpunkt(self, admin, make_challenge):
        challenge = make_challenge(start_time=datetime.now() - timedelta(minutes=5),
                                   end_time=datetime.now() + timedelta(minutes=40))

        anmelden_und_posten(admin, f"/admin/challenges/{challenge.id}/pause", {})

        challenge = frisch(challenge)
        assert challenge.paused is True
        assert challenge.paused_at is not None

    def test_fortsetzen_schiebt_die_endzeit_um_die_pause_nach_hinten(
            self, admin, make_challenge):
        ende = datetime.now() + timedelta(minutes=25)
        challenge = make_challenge(
            start_time=datetime.now() - timedelta(minutes=20),
            end_time=ende,
            paused=True,
            paused_at=datetime.now() - timedelta(minutes=10),
        )

        anmelden_und_posten(admin, f"/admin/challenges/{challenge.id}/resume", {})

        challenge = frisch(challenge)
        assert challenge.paused is False
        assert challenge.paused_at is None
        # Zehn Minuten Pause, also zehn Minuten später Schluss.
        verschiebung = (challenge.end_time - ende).total_seconds()
        assert 595 <= verschiebung <= 605

    def test_die_restzeit_ist_nach_dem_fortsetzen_dieselbe_wie_vorher(
            self, admin, make_challenge):
        """Darauf kommt es den Teams an: Es geht keine Arbeitszeit verloren."""
        challenge = make_challenge(
            start_time=datetime.now() - timedelta(minutes=20),
            end_time=datetime.now() + timedelta(minutes=25),
            paused=True,
            paused_at=datetime.now() - timedelta(minutes=10),
        )
        vorher = challenge.remaining_seconds

        anmelden_und_posten(admin, f"/admin/challenges/{challenge.id}/resume", {})

        assert abs(frisch(challenge).remaining_seconds - vorher) <= 5

    def test_ohne_endzeit_gibt_es_nichts_zu_verschieben(self, admin, make_challenge):
        challenge = make_challenge(
            start_time=datetime.now() - timedelta(minutes=20),
            paused=True,
            paused_at=datetime.now() - timedelta(minutes=10),
        )

        anmelden_und_posten(admin, f"/admin/challenges/{challenge.id}/resume", {})

        challenge = frisch(challenge)
        assert challenge.end_time is None
        assert challenge.paused is False

    def test_beenden_hebt_die_pause_auf(self, admin, make_challenge):
        """Sonst bestimmte der Zeitpunkt der Pause weiter die Rechnung.

        Der Wettbewerb liefe trotz gesetzter Endzeit weiter - beendet sticht
        pausiert.
        """
        challenge = make_challenge(
            start_time=datetime.now() - timedelta(minutes=20),
            end_time=datetime.now() + timedelta(minutes=25),
            paused=True,
            paused_at=datetime.now() - timedelta(minutes=10),
        )

        anmelden_und_posten(admin, f"/admin/challenges/{challenge.id}/finish", {})

        challenge = frisch(challenge)
        assert challenge.paused is False
        assert challenge.paused_at is None
        assert challenge.status() == "finished"

    def test_wieder_oeffnen_raeumt_den_zeitpunkt_mit_weg(self, admin, make_challenge):
        challenge = make_challenge(
            start_time=datetime.now() - timedelta(hours=2),
            end_time=datetime.now() - timedelta(minutes=5),
            paused=True,
            paused_at=datetime.now() - timedelta(minutes=30),
        )

        anmelden_und_posten(admin, f"/admin/challenges/{challenge.id}/reopen", {})

        challenge = frisch(challenge)
        assert challenge.paused_at is None
        assert challenge.end_time is None


class TestDauerImFormular:
    def test_die_dauer_rechnet_die_endzeit_aus(self, admin, make_challenge):
        start = datetime.now().replace(second=0, microsecond=0) + timedelta(hours=1)
        challenge = make_challenge(start_time=start)

        anmelden_und_posten(admin, f"/admin/challenges/{challenge.id}/edit", {
            "title": challenge.title,
            "tagline": "",
            "start_time": start.strftime("%Y-%m-%dT%H:%M"),
            "end_time": "",
            "duration_minutes": "45",
        })

        challenge = frisch(challenge)
        assert challenge.end_time == start + timedelta(minutes=45)
        assert challenge.duration_minutes == 45

    def test_ohne_startzeit_zaehlt_die_dauer_ab_jetzt(self, admin, make_challenge):
        challenge = make_challenge()

        anmelden_und_posten(admin, f"/admin/challenges/{challenge.id}/edit", {
            "title": challenge.title,
            "tagline": "",
            "start_time": "",
            "end_time": "",
            "duration_minutes": "30",
        })

        challenge = frisch(challenge)
        assert challenge.status() == "running"
        assert 1750 <= challenge.remaining_seconds <= 1800

    def test_die_dauer_sticht_eine_eingetragene_endzeit(self, admin, make_challenge):
        """Wer eine Dauer einträgt, meint sie auch."""
        start = datetime.now().replace(second=0, microsecond=0)
        challenge = make_challenge()

        anmelden_und_posten(admin, f"/admin/challenges/{challenge.id}/edit", {
            "title": challenge.title,
            "tagline": "",
            "start_time": start.strftime("%Y-%m-%dT%H:%M"),
            "end_time": (start + timedelta(hours=5)).strftime("%Y-%m-%dT%H:%M"),
            "duration_minutes": "20",
        })

        assert frisch(challenge).end_time == start + timedelta(minutes=20)

    def test_ein_leeres_dauerfeld_laesst_die_endzeit_in_ruhe(self, admin, make_challenge):
        start = datetime.now().replace(second=0, microsecond=0)
        ende = start + timedelta(hours=3)
        challenge = make_challenge()

        anmelden_und_posten(admin, f"/admin/challenges/{challenge.id}/edit", {
            "title": challenge.title,
            "tagline": "",
            "start_time": start.strftime("%Y-%m-%dT%H:%M"),
            "end_time": ende.strftime("%Y-%m-%dT%H:%M"),
            "duration_minutes": "",
        })

        assert frisch(challenge).end_time == ende

    def test_unsinn_im_dauerfeld_aendert_nichts(self, admin, make_challenge):
        start = datetime.now().replace(second=0, microsecond=0)
        ende = start + timedelta(hours=3)
        challenge = make_challenge(start_time=start, end_time=ende)

        for wert in ["dreißig", "0", "-5", "100000"]:
            antwort = anmelden_und_posten(
                admin, f"/admin/challenges/{challenge.id}/edit", {
                    "title": challenge.title,
                    "tagline": "",
                    "start_time": start.strftime("%Y-%m-%dT%H:%M"),
                    "end_time": ende.strftime("%Y-%m-%dT%H:%M"),
                    "duration_minutes": wert,
                })

            assert "Dauer" in antwort.get_data(as_text=True), f"Keine Meldung zu {wert!r}"
            assert frisch(challenge).end_time == ende, f"{wert!r} hat die Endzeit verstellt"

    def test_das_feld_bleibt_leer_und_nennt_die_eingestellte_dauer(
            self, admin, make_challenge):
        """Vorbefüllt wäre es eine Falle: Es würde die Endzeit überschreiben."""
        start = datetime.now().replace(second=0, microsecond=0)
        challenge = make_challenge(start_time=start, end_time=start + timedelta(minutes=45))

        html = admin.get(f"/admin/challenges/{challenge.id}/edit").get_data(as_text=True)
        feld = re.search(r'<input[^>]*name="duration_minutes"[^>]*>', html).group(0)

        assert 'value=' not in feld
        assert "45 Minuten" in html


class TestMeldungen:
    def test_die_meldung_nennt_das_datum_wenn_das_ende_morgen_liegt(
            self, admin, make_challenge):
        """Sonst liest sich ein Ende am nächsten Tag wie eines am selben."""
        start = datetime.now().replace(hour=23, minute=30, second=0, microsecond=0)
        challenge = make_challenge()

        antwort = anmelden_und_posten(admin, f"/admin/challenges/{challenge.id}/edit", {
            "title": challenge.title,
            "tagline": "",
            "start_time": start.strftime("%Y-%m-%dT%H:%M"),
            "end_time": "",
            "duration_minutes": "90",
        })

        morgen = (start + timedelta(minutes=90)).strftime("%d.%m., %H:%M")
        assert morgen in antwort.get_data(as_text=True)

    def test_am_selben_tag_steht_nur_die_uhrzeit(self, admin, make_challenge):
        start = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
        challenge = make_challenge()

        antwort = anmelden_und_posten(admin, f"/admin/challenges/{challenge.id}/edit", {
            "title": challenge.title,
            "tagline": "",
            "start_time": start.strftime("%Y-%m-%dT%H:%M"),
            "end_time": "",
            "duration_minutes": "45",
        })

        text = antwort.get_data(as_text=True)
        assert "bis 09:45 Uhr" in text
        assert "09.45" not in text


class TestJetztStarten:
    def test_ein_klick_setzt_start_und_ende(self, admin, make_challenge):
        challenge = make_challenge()

        anmelden_und_posten(admin, f"/admin/challenges/{challenge.id}/jetzt-starten",
                            {"duration_minutes": "45"})

        challenge = frisch(challenge)
        assert challenge.status() == "running"
        assert challenge.duration_minutes == 45
        assert 2650 <= challenge.remaining_seconds <= 2700

    def test_der_start_hebt_eine_pause_auf(self, admin, make_challenge):
        challenge = make_challenge(
            start_time=datetime.now() - timedelta(days=7),
            paused=True,
            paused_at=datetime.now() - timedelta(days=7),
        )

        anmelden_und_posten(admin, f"/admin/challenges/{challenge.id}/jetzt-starten",
                            {"duration_minutes": "20"})

        challenge = frisch(challenge)
        assert challenge.paused is False
        assert challenge.paused_at is None
        assert challenge.accepts_submissions is True

    def test_ohne_dauer_passiert_nichts(self, admin, make_challenge):
        challenge = make_challenge()

        antwort = anmelden_und_posten(
            admin, f"/admin/challenges/{challenge.id}/jetzt-starten",
            {"duration_minutes": ""})

        assert "Dauer" in antwort.get_data(as_text=True)
        assert frisch(challenge).start_time is None

    def test_der_knopf_steht_auf_der_detailseite(self, admin, make_challenge):
        challenge = make_challenge()

        html = admin.get(f"/admin/wettbewerb/{challenge.id}").get_data(as_text=True)

        assert f"/admin/challenges/{challenge.id}/jetzt-starten" in html
        assert "Jetzt starten für" in html

    def test_beim_beendeten_wettbewerb_fehlt_er(self, admin, make_challenge):
        """Dort gehört „Wieder öffnen“ hin, nicht ein neuer Start."""
        challenge = make_challenge(end_time=datetime.now() - timedelta(minutes=5))

        html = admin.get(f"/admin/wettbewerb/{challenge.id}").get_data(as_text=True)

        assert "jetzt-starten" not in html
        assert "Wieder öffnen" in html
