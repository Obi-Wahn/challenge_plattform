"""Rangliste und Podium.

Bei Gleichstand rücken die folgenden Teams nach (1, 2, 2, 3) statt einen
Platz zu überspringen - so bleibt kein Platz auf dem Podium leer.
"""

import pytest

from scoring import get_podium, get_standings


@pytest.fixture
def wettbewerb_mit_punkten(make_challenge, make_task, make_team, database):
    """Baut einen Wettbewerb und trägt Punkte ein.

    punkte_je_team: {Teamname: [Punkte für Aufgabe 1, Aufgabe 2, ...]},
    None bedeutet „nicht abgegeben“.
    """
    from models import Submission

    def _bauen(punkte_je_team, aufgaben=2):
        challenge = make_challenge()
        tasks = [make_task(challenge, title=f"Aufgabe {i + 1}") for i in range(aufgaben)]

        for name, punkte in punkte_je_team.items():
            team = make_team(challenge, name=name)
            for task, wert in zip(tasks, punkte):
                if wert is None:
                    continue
                database.session.add(Submission(
                    team_id=team.id, task_id=task.id, filename="x.sb3", points=wert))
        database.session.commit()
        return challenge

    return _bauen


def raenge(standings):
    return [(eintrag["name"], eintrag["rank"], eintrag["total"]) for eintrag in standings]


def test_teams_ohne_abgabe_stehen_mit_null_punkten_drin(wettbewerb_mit_punkten):
    challenge = wettbewerb_mit_punkten({"Fleißig": [10, 10], "Zaghaft": [None, None]})

    _tasks, standings = get_standings(challenge)

    assert raenge(standings) == [("Fleißig", 1, 20), ("Zaghaft", 2, 0)]


def test_sortierung_nach_punkten(wettbewerb_mit_punkten):
    challenge = wettbewerb_mit_punkten({
        "Mitte": [5, 5], "Beste": [10, 10], "Letzte": [1, 0]})

    _tasks, standings = get_standings(challenge)

    assert [e["name"] for e in standings] == ["Beste", "Mitte", "Letzte"]


def test_gleichstand_teilt_sich_den_platz_und_die_naechsten_ruecken_nach(
        wettbewerb_mit_punkten):
    challenge = wettbewerb_mit_punkten({
        "Erste": [10, 10],
        "Zweite A": [5, 5],
        "Zweite B": [5, 5],
        "Dritte": [1, 1],
    })

    _tasks, standings = get_standings(challenge)

    assert raenge(standings) == [
        ("Erste", 1, 20),
        ("Zweite A", 2, 10),
        ("Zweite B", 2, 10),
        ("Dritte", 3, 2),
    ]


def test_bei_gleichstand_entscheidet_der_name_ueber_die_reihenfolge(
        wettbewerb_mit_punkten):
    """Nicht die Reihenfolge des Anlegens - die wäre willkürlich."""
    challenge = wettbewerb_mit_punkten({"Zebra": [5, 5], "Ameise": [5, 5]})

    _tasks, standings = get_standings(challenge)

    assert [e["name"] for e in standings] == ["Ameise", "Zebra"]


def test_geloeste_aufgaben_werden_gezaehlt(wettbewerb_mit_punkten):
    challenge = wettbewerb_mit_punkten({"Team": [10, None]})

    _tasks, standings = get_standings(challenge)

    assert standings[0]["solved"] == 1


def test_eine_abgabe_mit_null_punkten_zaehlt_als_bearbeitet(wettbewerb_mit_punkten):
    challenge = wettbewerb_mit_punkten({"Team": [0, None]})

    _tasks, standings = get_standings(challenge)

    assert standings[0]["solved"] == 1
    assert standings[0]["total"] == 0


def test_nur_teams_des_eigenen_wettbewerbs(
        make_challenge, make_task, make_team, database):
    aktuell = make_challenge(title="Aktuell", active=True)
    make_task(aktuell)
    make_team(aktuell, name="Gehört dazu")

    fremd = make_challenge(title="Fremd", active=False)
    make_team(fremd, name="Gehört nicht dazu")

    _tasks, standings = get_standings(aktuell)

    assert [e["name"] for e in standings] == ["Gehört dazu"]


class TestPodium:
    def test_die_ersten_drei(self, wettbewerb_mit_punkten):
        challenge = wettbewerb_mit_punkten({
            "Gold": [10, 10], "Silber": [8, 8], "Bronze": [5, 5], "Vierte": [1, 1]})

        _tasks, standings = get_standings(challenge)
        podium = get_podium(standings)

        assert [stufe["place"] for stufe in podium] == [1, 2, 3]
        assert [stufe["teams"][0]["name"] for stufe in podium] == ["Gold", "Silber", "Bronze"]

    def test_gleichstand_teilt_sich_eine_stufe(self, wettbewerb_mit_punkten):
        challenge = wettbewerb_mit_punkten({
            "Gold": [10, 10], "Silber A": [8, 8], "Silber B": [8, 8], "Bronze": [5, 5]})

        _tasks, standings = get_standings(challenge)
        podium = get_podium(standings)

        assert [len(stufe["teams"]) for stufe in podium] == [1, 2, 1]
        assert podium[2]["teams"][0]["name"] == "Bronze"

    def test_teams_ohne_punkte_kommen_nicht_aufs_podium(self, wettbewerb_mit_punkten):
        challenge = wettbewerb_mit_punkten({
            "Mit Punkten": [10, 10], "Ohne A": [None, None], "Ohne B": [0, None]})

        _tasks, standings = get_standings(challenge)
        podium = get_podium(standings)

        assert len(podium) == 1
        assert podium[0]["teams"][0]["name"] == "Mit Punkten"

    def test_ohne_punkte_bleibt_das_podium_leer(self, wettbewerb_mit_punkten):
        challenge = wettbewerb_mit_punkten({"Team": [None, None]})

        _tasks, standings = get_standings(challenge)

        assert get_podium(standings) == []


class TestOeffentlicheSeiten:
    def test_rangliste_zeigt_die_teams(self, client, wettbewerb_mit_punkten):
        wettbewerb_mit_punkten({"Die Pixelpiraten": [10, 10]})

        html = client.get("/scoreboard").get_data(as_text=True)

        assert "Die Pixelpiraten" in html

    def test_siegerehrung_zeigt_das_podium(self, client, wettbewerb_mit_punkten):
        wettbewerb_mit_punkten({"Die Pixelpiraten": [10, 10]})

        html = client.get("/siegerehrung").get_data(as_text=True)

        assert "Die Pixelpiraten" in html

    def test_seiten_funktionieren_auch_ohne_wettbewerb(self, client, database):
        for pfad in ["/", "/login", "/scoreboard", "/siegerehrung"]:
            assert client.get(pfad).status_code == 200, pfad

    def test_die_alte_countdown_adresse_fuehrt_zur_rangliste(self, client, database):
        """Die Seite gibt es nicht mehr, ein altes Lesezeichen soll trotzdem tragen."""
        antwort = client.get("/start")

        assert antwort.status_code == 302
        assert antwort.headers["Location"].endswith("/scoreboard")
