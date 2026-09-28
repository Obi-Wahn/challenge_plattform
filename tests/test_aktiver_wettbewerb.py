"""Welcher Wettbewerb gilt, wird ausdrücklich gewählt.

Bis v1.9.0 sprang ohne aktivierten Wettbewerb der neueste ein. Nach dem
Löschen des aktiven wurde so still irgendein alter zum aktuellen, und eine
eingelesene Sicherung stand ohne Aktivieren auf der Startseite - obwohl sie
„nie aktiv“ werden sollte. Jetzt gilt ohne Aktivierung keiner; nur ein neu
angelegter Wettbewerb wird von selbst aktiv, wenn gerade keiner es ist.
"""

import io
import json
import zipfile

from tests.helpers import csrf_token


def anlegen(admin, titel):
    return admin.post("/admin/challenges/new", data={
        "csrf_token": csrf_token(admin, "/admin/challenges/new"),
        "title": titel,
    }, follow_redirects=True)


def loeschen(admin, challenge):
    return admin.post(f"/admin/challenges/{challenge.id}/delete", data={
        "csrf_token": csrf_token(admin, f"/admin/wettbewerb/{challenge.id}"),
    }, follow_redirects=True)


def sicherung(titel="Aus der Sicherung"):
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w") as zf:
        zf.writestr("wettbewerb.json", json.dumps({
            "format": "coding-wettbewerb-sicherung", "version": 1,
            "wettbewerb": {"titel": titel},
            "aufgaben": [], "teams": [], "abgaben": []}))
    return puffer.getvalue()


def einlesen(admin, inhalt):
    return admin.post("/admin/challenges/einlesen", data={
        "csrf_token": csrf_token(admin, "/admin/challenges/new"),
        "file": (io.BytesIO(inhalt), "Sicherung.zip"),
    }, content_type="multipart/form-data", follow_redirects=True)


class TestNeuerWettbewerb:
    def test_der_erste_wird_von_selbst_aktiv(self, admin, database):
        from models import Challenge

        seite = anlegen(admin, "Scratch-Tag").get_data(as_text=True)

        assert Challenge.current().title == "Scratch-Tag"
        assert "der aktive Wettbewerb" in seite

    def test_ein_weiterer_loest_den_aktiven_nicht_ab(self, admin, make_challenge):
        from models import Challenge
        aktiv = make_challenge(title="Läuft gerade")

        anlegen(admin, "Nächste Woche")

        assert Challenge.current().id == aktiv.id

    def test_ohne_aktiven_wird_der_neue_aktiv(self, admin, make_challenge):
        from models import Challenge
        make_challenge(title="Alt", active=False)

        anlegen(admin, "Neu")

        assert Challenge.current().title == "Neu"


class TestLoeschenDesAktiven:
    def test_kein_anderer_rueckt_still_nach(self, admin, make_challenge):
        from models import Challenge
        make_challenge(title="Alt und beendet", active=False)
        aktiv = make_challenge(title="Aktiv")

        loeschen(admin, aktiv)

        assert Challenge.current() is None

    def test_die_steuerzentrale_fragt_nach(self, admin, make_challenge):
        make_challenge(title="Alt und beendet", active=False)
        aktiv = make_challenge(title="Aktiv")

        seite = loeschen(admin, aktiv).get_data(as_text=True)

        assert "Kein Wettbewerb ist aktiv" in seite
        assert "Alt und beendet" in seite
        assert "Aktivieren" in seite

    def test_auch_ein_beendeter_laesst_sich_dann_aktivieren(self, admin, make_challenge):
        from datetime import datetime, timedelta
        vorbei = datetime.now() - timedelta(days=1)
        make_challenge(title="Beendet", active=False, end_time=vorbei)
        aktiv = make_challenge(title="Aktiv")

        seite = loeschen(admin, aktiv).get_data(as_text=True)

        # Sonst gäbe es für einen beendeten nur den Umweg über seine Seite.
        beendet_teil = seite[seite.index("Beendet (1)"):]
        assert "challenge/" in beendet_teil and "/activate" in beendet_teil

    def test_die_startseite_nimmt_niemanden_an(self, client, admin, make_challenge):
        make_challenge(title="Alt", active=False)
        aktiv = make_challenge(title="Aktiv")
        loeschen(admin, aktiv)

        # Das Formular steht dann nicht mehr auf der Seite - hier ein von
        # Hand abgeschicktes, das Token kommt von der Anmeldeseite.
        antwort = client.post("/", data={
            "csrf_token": csrf_token(client, "/login"),
            "team": "Nachzügler", "password": "geheim",
        })

        from models import Team
        assert "Gerade ist kein Wettbewerb aktiv" in antwort.get_data(as_text=True)
        assert Team.query.count() == 0

    def test_ohne_andere_bleibt_es_bei_der_kurzen_meldung(self, admin, make_challenge):
        aktiv = make_challenge(title="Einziger")

        seite = loeschen(admin, aktiv).get_data(as_text=True)

        assert "Noch kein Wettbewerb angelegt" in seite
        assert "Kein Wettbewerb ist aktiv" not in seite


class TestEingeleseneSicherung:
    def test_wird_auch_ohne_aktiven_nicht_aktuell(self, admin, database):
        from models import Challenge

        einlesen(admin, sicherung())

        assert Challenge.query.one().active is False
        assert Challenge.current() is None

    def test_neben_einem_aktiven_bleibt_der_aktive(self, admin, make_challenge):
        from models import Challenge
        aktiv = make_challenge(title="Aktiv")

        einlesen(admin, sicherung())

        assert Challenge.current().id == aktiv.id


class TestJetztStartenOhneAktivierung:
    def test_die_meldung_sagt_dass_ihn_niemand_sieht(self, admin, make_challenge):
        make_challenge(title="Aktiv")
        anderer = make_challenge(title="Vorbereitet", active=False)

        seite = admin.post(f"/admin/challenges/{anderer.id}/jetzt-starten", data={
            "csrf_token": csrf_token(admin, f"/admin/wettbewerb/{anderer.id}"),
            "duration_minutes": "45",
        }, follow_redirects=True).get_data(as_text=True)

        assert "nicht der aktive Wettbewerb" in seite

    def test_beim_aktiven_bleibt_die_gewohnte_meldung(self, admin, make_challenge):
        aktiv = make_challenge(title="Aktiv")

        seite = admin.post(f"/admin/challenges/{aktiv.id}/jetzt-starten", data={
            "csrf_token": csrf_token(admin, f"/admin/wettbewerb/{aktiv.id}"),
            "duration_minutes": "45",
        }, follow_redirects=True).get_data(as_text=True)

        assert "Die Teams sehen die neue Zeit" in seite
        assert "nicht der aktive Wettbewerb" not in seite


class TestUpdateVonFrueher:
    """Ein Bestand, in dem nie jemand „Aktivieren“ gedrückt hat.

    Dort galt bisher der neueste. Nach dem Update soll derselbe weiter
    gelten - ausdrücklich aktiv, statt dass die Startseite leer wird.
    """

    def test_der_bisher_angezeigte_wird_aktiv(self, make_challenge):
        from app import ensure_active_challenge
        from extensions import db
        from models import Challenge
        make_challenge(title="Erster", active=False)
        zweiter = make_challenge(title="Zweiter", active=False)

        ensure_active_challenge()
        db.session.expire_all()

        assert Challenge.current().id == zweiter.id

    def test_ein_aktiver_bleibt_unberuehrt(self, make_challenge):
        from app import ensure_active_challenge
        from extensions import db
        from models import Challenge
        aktiv = make_challenge(title="Aktiv")
        make_challenge(title="Neuer", active=False)

        ensure_active_challenge()
        db.session.expire_all()

        assert Challenge.current().id == aktiv.id
        assert Challenge.query.filter_by(active=True).count() == 1

    def test_ohne_wettbewerb_passiert_nichts(self, database):
        from app import ensure_active_challenge
        ensure_active_challenge()


class TestStartseiteOhneAktiven:
    def test_statt_des_formulars_steht_warum(self, client, make_challenge):
        make_challenge(title="Alt", active=False)

        seite = client.get("/").get_data(as_text=True)

        assert "Gerade ist kein Wettbewerb aktiv" in seite
        assert 'name="password"' not in seite

    def test_frische_installation_zeigt_das_formular_weiter(self, client, database):
        seite = client.get("/").get_data(as_text=True)

        assert 'name="password"' in seite
