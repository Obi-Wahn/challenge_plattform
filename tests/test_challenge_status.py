"""Der Zustand eines Wettbewerbs: geplant, läuft, pausiert, beendet."""

from datetime import datetime, timedelta

VOR_EINER_STUNDE = timedelta(hours=-1)
IN_EINER_STUNDE = timedelta(hours=1)


def zeit(versatz):
    return datetime.now() + versatz


def test_ohne_zeiten_ist_nichts_geplant(make_challenge):
    challenge = make_challenge()
    assert challenge.status() == "not_scheduled"
    assert challenge.accepts_submissions is True


def test_startzeit_in_der_zukunft_ist_geplant(make_challenge):
    challenge = make_challenge(start_time=zeit(IN_EINER_STUNDE))
    assert challenge.status() == "upcoming"
    assert challenge.state_label == "geplant"


def test_geplanter_wettbewerb_nimmt_bewusst_schon_abgaben_an(make_challenge):
    """Die Startzeit steuert den Countdown, nicht die Abgabe.

    So kann die Lehrkraft vorher testen, ohne sich selbst auszusperren.
    """
    challenge = make_challenge(start_time=zeit(IN_EINER_STUNDE))
    assert challenge.accepts_submissions is True


def test_zwischen_start_und_ende_laeuft_er(make_challenge):
    challenge = make_challenge(start_time=zeit(VOR_EINER_STUNDE),
                               end_time=zeit(IN_EINER_STUNDE))
    assert challenge.status() == "running"
    assert challenge.state_label == "läuft"
    assert challenge.accepts_submissions is True


def test_ohne_endzeit_laeuft_er_weiter(make_challenge):
    challenge = make_challenge(start_time=zeit(VOR_EINER_STUNDE))
    assert challenge.status() == "running"


def test_abgelaufene_endzeit_beendet_ihn(make_challenge):
    challenge = make_challenge(start_time=zeit(timedelta(hours=-2)),
                               end_time=zeit(VOR_EINER_STUNDE))
    assert challenge.status() == "finished"
    assert challenge.accepts_submissions is False


def test_endzeit_ohne_startzeit_beendet_ihn_auch(make_challenge):
    """Darauf setzt der Knopf „Wettbewerb beenden“ auf."""
    challenge = make_challenge(end_time=zeit(VOR_EINER_STUNDE))
    assert challenge.status() == "finished"
    assert challenge.accepts_submissions is False


def test_pause_sperrt_abgaben_ohne_den_status_zu_aendern(make_challenge):
    challenge = make_challenge(start_time=zeit(VOR_EINER_STUNDE), paused=True)
    assert challenge.status() == "running"
    assert challenge.accepts_submissions is False
    assert challenge.state_label == "pausiert"


def test_beendet_sticht_pausiert(make_challenge):
    challenge = make_challenge(end_time=zeit(VOR_EINER_STUNDE), paused=True)
    assert challenge.state_label == "beendet"


def test_sekunden_bis_zum_start(make_challenge):
    challenge = make_challenge(start_time=zeit(timedelta(minutes=10)))
    assert 590 <= challenge.seconds_until_start <= 600


def test_sekunden_werden_nie_negativ(make_challenge):
    challenge = make_challenge(start_time=zeit(VOR_EINER_STUNDE),
                               end_time=zeit(VOR_EINER_STUNDE))
    assert challenge.seconds_until_start == 0
    assert challenge.remaining_seconds == 0


def test_ohne_endzeit_gibt_es_keine_restzeit(make_challenge):
    """0 blendet den Countdown auf der Startseite aus."""
    challenge = make_challenge(start_time=zeit(VOR_EINER_STUNDE))
    assert challenge.remaining_seconds == 0


class TestAktuellerWettbewerb:
    def test_ohne_wettbewerb_gibt_es_keinen(self, database):
        from models import Challenge
        assert Challenge.current() is None

    def test_der_aktivierte_gewinnt(self, make_challenge):
        from models import Challenge
        make_challenge(title="Alt", active=False)
        aktiv = make_challenge(title="Aktiv", active=True)
        make_challenge(title="Neuer, aber nicht aktiv", active=False)
        assert Challenge.current().id == aktiv.id

    def test_ohne_aktivierung_der_neueste(self, make_challenge):
        """Damit eine frische Installation ohne „aktivieren“ funktioniert."""
        from models import Challenge
        make_challenge(title="Erster", active=False)
        neuester = make_challenge(title="Zweiter", active=False)
        assert Challenge.current().id == neuester.id
