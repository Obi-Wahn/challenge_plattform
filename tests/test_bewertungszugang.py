"""Der Bewertungszugang: ein zweites Passwort, das nur zum Bewerten reicht.

Gewünscht von Tobias am 08.10.2026: Jemand soll beim Bewerten helfen können,
ohne an die Steuerzentrale zu kommen. Die Lehrkraft setzt dafür in den
Einstellungen ein eigenes Passwort; leer heißt, es gibt keinen solchen
Zugang. Angemeldet wird sich auf derselben Seite wie als Admin, das Passwort
entscheidet. Erlaubt sind Abgaben ansehen, herunterladen und bewerten.
Löschen, Freigeben und alles andere bleiben beim Admin.
"""

import io
import os

import pytest

from tests.helpers import ADMIN_PASSWORD, csrf_token

PASSWORT = "bewerten-2026"


def logdatei_inhalt(flask_app):
    pfad = os.path.join(flask_app.config["LOG_DIR"], "anwendung.log")
    if not os.path.exists(pfad):
        return ""
    with open(pfad, encoding="utf-8") as datei:
        return datei.read()


def passwort_setzen(admin, passwort):
    return admin.post("/admin/settings", data={
        "csrf_token": csrf_token(admin, "/admin/settings"),
        "review_password": passwort,
    })


def anmelden(client, passwort):
    return client.post("/admin/login", data={
        "csrf_token": csrf_token(client, "/admin/login"),
        "password": passwort,
    })


@pytest.fixture
def eingerichtet(admin):
    """Der Bewertungszugang mit PASSWORT, eingerichtet vom Admin."""
    passwort_setzen(admin, PASSWORT)
    return admin


@pytest.fixture
def bewerter(flask_app, eingerichtet):
    """Ein Testclient, der mit dem Passwort für die Bewertung angemeldet ist."""
    client = flask_app.test_client()
    antwort = anmelden(client, PASSWORT)
    assert antwort.status_code == 302
    return client


@pytest.fixture
def abgabe(make_challenge, make_task, logged_in_team):
    """Eine Abgabe von Team Blitz im aktiven Wettbewerb."""
    from models import Submission

    challenge = make_challenge()
    task = make_task(challenge, title="Katze bewegen", allowed_extension=".py")
    client, _team = logged_in_team(challenge)
    client.post(f"/submit/{task.id}", data={
        "csrf_token": csrf_token(client, "/"),
        "file": (io.BytesIO(b"print('miau')"), "loesung.py"),
    }, content_type="multipart/form-data")
    return Submission.query.one()


class TestEinrichten:
    def test_ohne_passwort_gibt_es_keinen_zugang(self, flask_app):
        from models import Settings

        assert Settings.get().review_access is False
        assert Settings.get().check_review_password("") is False

    def test_passwort_wird_nur_als_hash_gespeichert(self, eingerichtet):
        from models import Settings

        settings = Settings.get()
        assert settings.review_access
        assert PASSWORT not in settings.review_password_hash
        assert settings.check_review_password(PASSWORT)

    def test_leeres_feld_laesst_das_passwort_stehen(self, eingerichtet):
        from models import Settings

        vorher = Settings.get().review_password_hash
        passwort_setzen(eingerichtet, "")
        assert Settings.get().review_password_hash == vorher

    def test_zu_kurz_wird_nicht_gespeichert(self, admin):
        from models import Settings

        antwort = passwort_setzen(admin, "kurz")
        assert Settings.get().review_access is False

        seite = admin.get(antwort.headers["Location"]).get_data(as_text=True)
        assert "mindestens 6 Zeichen" in seite

    def test_admin_passwort_wird_abgelehnt(self, admin):
        from models import Settings

        antwort = passwort_setzen(admin, ADMIN_PASSWORD)
        seite = admin.get(antwort.headers["Location"]).get_data(as_text=True)
        assert "nicht dasselbe sein wie das Admin-Passwort" in seite
        assert Settings.get().review_access is False

    def test_die_anderen_einstellungen_werden_trotzdem_gespeichert(self, admin):
        from models import Settings

        admin.post("/admin/settings", data={
            "csrf_token": csrf_token(admin, "/admin/settings"),
            "site_name": "Calliope-Cup",
            "review_password": "kurz",
        })
        assert Settings.get().site_name == "Calliope-Cup"
        assert Settings.get().review_access is False

    def test_abschalten(self, eingerichtet):
        from models import Settings

        antwort = eingerichtet.post("/admin/bewertungszugang-abschalten", data={
            "csrf_token": csrf_token(eingerichtet, "/admin/settings"),
        })
        assert antwort.status_code == 302
        assert Settings.get().review_access is False

    def test_einstellungsseite_zeigt_den_stand(self, admin):
        assert "Nicht eingerichtet" in admin.get("/admin/settings").get_data(as_text=True)
        passwort_setzen(admin, PASSWORT)
        seite = admin.get("/admin/settings").get_data(as_text=True)
        assert "Eingerichtet" in seite
        assert "Bewertungszugang abschalten" in seite
        assert PASSWORT not in seite

    def test_kasten_steht_nach_der_unterschrift(self, admin):
        seite = admin.get("/admin/settings").get_data(as_text=True)
        assert seite.index("Unterschrift auf den Urkunden") < seite.index("Bewertungszugang")
        assert seite.index("Bewertungszugang") < seite.index("💾 Speichern")


class TestAnmelden:
    def test_fuehrt_auf_die_bewertungsseite(self, flask_app, eingerichtet):
        client = flask_app.test_client()
        antwort = anmelden(client, PASSWORT)
        assert antwort.headers["Location"].endswith("/admin/submissions")

    def test_admin_passwort_fuehrt_weiter_in_die_steuerzentrale(self, flask_app, eingerichtet):
        client = flask_app.test_client()
        antwort = anmelden(client, ADMIN_PASSWORD)
        assert antwort.headers["Location"].endswith("/admin/dashboard")

    def test_ohne_eingerichteten_zugang_hilft_kein_passwort(self, client):
        antwort = anmelden(client, PASSWORT)
        assert antwort.status_code == 200
        assert "Falsches Passwort" in antwort.get_data(as_text=True)

    def test_anmeldeseite_nennt_beide_passwoerter_nur_wenn_eingerichtet(
            self, client, admin):
        hinweis = "Admin-Passwort oder Passwort für die Bewertung"
        assert hinweis not in client.get("/admin/login").get_data(as_text=True)
        passwort_setzen(admin, PASSWORT)
        assert hinweis in client.get("/admin/login").get_data(as_text=True)

    def test_feld_heisst_nur_passwort(self, client, admin):
        # Die Seite gilt für beide Zugänge - „Admin-Passwort“ im Feld passte
        # nicht dazu, auch ohne eingerichteten Bewertungszugang nicht.
        for _ in range(2):
            html = client.get("/admin/login").get_data(as_text=True)
            assert 'placeholder="Passwort"' in html
            assert 'placeholder="Admin-Passwort"' not in html
            passwort_setzen(admin, PASSWORT)

    def test_falsches_passwort_steht_im_protokoll(self, flask_app, eingerichtet):
        vorher = len(logdatei_inhalt(flask_app))
        client = flask_app.test_client()
        anmelden(client, "geraten")
        zeile = logdatei_inhalt(flask_app)[vorher:]
        assert "Anmeldung fehlgeschlagen" in zeile
        assert "geraten" not in zeile

    def test_in_der_sitzung_steht_nicht_der_hash(self, bewerter):
        from models import Settings

        with bewerter.session_transaction() as sitzung:
            kennzeichen = sitzung.get("bewertung")
            assert not sitzung.get("is_admin")
        assert kennzeichen
        assert kennzeichen not in Settings.get().review_password_hash

    def test_abmelden(self, bewerter):
        bewerter.get("/admin/logout")
        antwort = bewerter.get("/admin/submissions")
        assert "/admin/login" in antwort.headers["Location"]


class TestWasErlaubtIst:
    def test_bewertungsseite(self, bewerter, abgabe):
        seite = bewerter.get("/admin/submissions")
        assert seite.status_code == 200
        html = seite.get_data(as_text=True)
        assert "Katze bewegen" in html
        assert "Angemeldet zum Bewerten" in html

    def test_bewerten(self, bewerter, abgabe):
        from extensions import db

        bewerter.post("/admin/submissions", data={
            "csrf_token": csrf_token(bewerter, "/admin/submissions"),
            "submission_id": abgabe.id,
            "points": "7",
            "feedback": "Schön gelöst",
        })
        db.session.refresh(abgabe)
        assert abgabe.points == 7
        assert abgabe.feedback == "Schön gelöst"

    def test_bewertung_zuruecksetzen(self, bewerter, abgabe):
        from extensions import db

        abgabe.points = 5
        db.session.commit()
        bewerter.post("/admin/submissions", data={
            "csrf_token": csrf_token(bewerter, "/admin/submissions"),
            "submission_id": abgabe.id,
            "soft_reset": "1",
        })
        db.session.refresh(abgabe)
        assert abgabe.points is None

    def test_code_ansehen(self, bewerter, abgabe):
        antwort = bewerter.get(f"/admin/submissions/{abgabe.id}/code")
        assert "miau" in antwort.get_json()["code"]

    def test_skripte_anzeigen(self, bewerter, abgabe):
        antwort = bewerter.get(f"/admin/submissions/{abgabe.id}/skripte")
        assert antwort.status_code == 200

    def test_herunterladen(self, bewerter, abgabe):
        antwort = bewerter.get(f"/admin/download/{abgabe.id}")
        assert antwort.status_code == 200
        assert b"miau" in antwort.data


class TestWasBeimAdminBleibt:
    def test_keine_knoepfe_zum_loeschen_und_freigeben(self, bewerter, abgabe):
        from extensions import db

        abgabe.task.challenge.self_correction = False
        db.session.commit()
        html = bewerter.get("/admin/submissions").get_data(as_text=True)
        assert "Abgabe vollständig löschen" not in html
        assert "Erneut abgeben erlauben" not in html
        assert "zurück zur Steuerzentrale" not in html

    def test_admin_sieht_die_knoepfe_weiter(self, admin, abgabe):
        html = admin.get("/admin/submissions").get_data(as_text=True)
        assert "Abgabe vollständig löschen" in html
        assert "zurück zur Steuerzentrale" in html
        assert "Angemeldet zum Bewerten" not in html

    def test_loeschen_von_hand_wird_abgewiesen(self, bewerter, abgabe):
        from models import Submission

        antwort = bewerter.post(f"/admin/reset/{abgabe.id}", data={
            "csrf_token": csrf_token(bewerter, "/admin/submissions"),
        })
        assert antwort.status_code == 403
        assert Submission.query.count() == 1

    def test_freigeben_von_hand_wird_abgewiesen(self, bewerter, abgabe):
        from extensions import db

        antwort = bewerter.post(f"/admin/submissions/{abgabe.id}/allow_resubmit", data={
            "csrf_token": csrf_token(bewerter, "/admin/submissions"),
        })
        assert antwort.status_code == 403
        db.session.refresh(abgabe)
        assert not abgabe.resubmit_allowed

    def test_eigenes_passwort_aendern_geht_nicht(self, bewerter):
        from models import Settings

        vorher = Settings.get().review_password_hash
        antwort = bewerter.post("/admin/settings", data={
            "csrf_token": csrf_token(bewerter, "/admin/login"),
            "review_password": "selbst-gewaehlt",
        })
        assert antwort.status_code == 403
        assert Settings.get().review_password_hash == vorher

    @pytest.mark.parametrize("adresse", [
        "/admin/", "/admin/dashboard", "/admin/settings", "/admin/teams",
        "/admin/urkunden", "/admin/urkunden.pdf",
    ])
    def test_andere_seiten_fuehren_zur_bewertung(self, bewerter, adresse):
        antwort = bewerter.get(adresse)
        assert antwort.status_code == 302
        assert antwort.headers["Location"].endswith("/admin/submissions")

    def test_eingefrorene_siegerehrung_bleibt_verdeckt(self, bewerter, make_challenge):
        from datetime import datetime, timedelta

        make_challenge(start_time=datetime.now() - timedelta(minutes=40),
                       end_time=datetime.now() + timedelta(minutes=5),
                       freeze_enabled=True, freeze_minutes=10)
        html = bewerter.get("/siegerehrung").get_data(as_text=True)
        assert "eingefroren" in html.lower()


class TestPasswortWechsel:
    def test_neues_passwort_meldet_ab(self, bewerter, eingerichtet):
        passwort_setzen(eingerichtet, "ganz-neues-passwort")
        antwort = bewerter.get("/admin/submissions")
        assert "/admin/login" in antwort.headers["Location"]
        with bewerter.session_transaction() as sitzung:
            assert "bewertung" not in sitzung

    def test_dasselbe_passwort_noch_einmal_meldet_auch_ab(self, bewerter, eingerichtet):
        passwort_setzen(eingerichtet, PASSWORT)
        antwort = bewerter.get("/admin/submissions")
        assert antwort.status_code == 302

    def test_abschalten_meldet_ab(self, bewerter, eingerichtet):
        eingerichtet.post("/admin/bewertungszugang-abschalten", data={
            "csrf_token": csrf_token(eingerichtet, "/admin/settings"),
        })
        antwort = bewerter.get("/admin/submissions")
        assert "/admin/login" in antwort.headers["Location"]

    def test_altes_passwort_gilt_nicht_mehr(self, flask_app, eingerichtet):
        passwort_setzen(eingerichtet, "ganz-neues-passwort")
        antwort = anmelden(flask_app.test_client(), PASSWORT)
        assert antwort.status_code == 200


class TestProtokoll:
    def test_einrichten_aendern_abschalten(self, flask_app, admin):
        vorher = len(logdatei_inhalt(flask_app))
        passwort_setzen(admin, PASSWORT)
        passwort_setzen(admin, "ganz-neues-passwort")
        admin.post("/admin/bewertungszugang-abschalten", data={
            "csrf_token": csrf_token(admin, "/admin/settings"),
        })
        neu = logdatei_inhalt(flask_app)[vorher:]
        assert "Bewertungszugang eingerichtet" in neu
        assert "Passwort für die Bewertung geändert" in neu
        assert "Bewertungszugang abgeschaltet" in neu
        assert PASSWORT not in neu
        assert "ganz-neues-passwort" not in neu

    def test_bewerten_bleibt_still(self, flask_app, bewerter, abgabe):
        vorher = len(logdatei_inhalt(flask_app))
        bewerter.post("/admin/submissions", data={
            "csrf_token": csrf_token(bewerter, "/admin/submissions"),
            "submission_id": abgabe.id,
            "points": "3",
        })
        assert logdatei_inhalt(flask_app)[vorher:] == ""
