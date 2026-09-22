"""Beim Start ergänzte Datenbank-Änderungen.

Eine Datenbank aus einer älteren Version der Anwendung muss beim Start
weiterbenutzbar werden, ohne dass Teams, Abgaben oder Punkte verloren gehen.
Diese Tests bauen die alten Schemata von Hand nach.
"""

import sqlite3

import pytest

from app import (ensure_added_columns, ensure_pause_timestamp,
                 ensure_team_challenge_binding, ensure_team_uids,
                 run_startup_migrations)


@pytest.fixture
def alte_datenbank(flask_app, database):
    """Ersetzt die Tabellen durch eine ältere Fassung.

    Gibt einen Pfad zur Datei zurück, über den die Tests direkt in die
    Datenbank schauen können.
    """
    from extensions import db

    pfad = flask_app.config["SQLALCHEMY_DATABASE_URI"].replace("sqlite:///", "")

    def _aufbauen(skript):
        db.session.remove()
        # Die gepoolte Verbindung kennt sonst noch das neue Schema.
        db.engine.dispose()

        verbindung = sqlite3.connect(pfad)
        verbindung.executescript(skript)
        verbindung.commit()
        verbindung.close()

        db.engine.dispose()
        return pfad

    return _aufbauen


def lies(pfad, sql):
    verbindung = sqlite3.connect(pfad)
    try:
        return verbindung.execute(sql).fetchall()
    finally:
        verbindung.close()


ALTES_TEAM_SCHEMA = """
DROP TABLE IF EXISTS submissions;
DROP TABLE IF EXISTS teams;
DROP TABLE IF EXISTS tasks;
DROP TABLE IF EXISTS challenges;

CREATE TABLE challenges (
    id INTEGER NOT NULL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    active BOOLEAN,
    paused BOOLEAN,
    start_time DATETIME,
    end_time DATETIME
);
CREATE TABLE teams (
    id INTEGER NOT NULL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    password_hash VARCHAR(200),
    UNIQUE (name)
);
CREATE TABLE tasks (
    id INTEGER NOT NULL PRIMARY KEY,
    challenge_id INTEGER,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    max_points INTEGER,
    allowed_extension VARCHAR(20)
);
CREATE TABLE submissions (
    id INTEGER NOT NULL PRIMARY KEY,
    team_id INTEGER,
    task_id INTEGER,
    filename VARCHAR(300),
    timestamp DATETIME,
    points INTEGER,
    feedback TEXT
);

INSERT INTO challenges (id, title, active, paused) VALUES (1, 'Alter', 0, 0);
INSERT INTO challenges (id, title, active, paused) VALUES (2, 'Aktueller', 1, 0);
INSERT INTO teams (id, name, password_hash) VALUES (1, 'Alpha', 'hash-alpha');
INSERT INTO teams (id, name, password_hash) VALUES (2, 'Beta', 'hash-beta');
INSERT INTO tasks (id, challenge_id, title, max_points, allowed_extension)
    VALUES (1, 2, 'Aufgabe 1', 10, '.sb3');
INSERT INTO submissions (id, team_id, task_id, filename, points)
    VALUES (1, 1, 1, 'x.sb3', 7);
"""


class TestTeamsAnWettbewerbBinden:
    def test_teams_bekommen_den_aktuellen_wettbewerb(self, alte_datenbank):
        pfad = alte_datenbank(ALTES_TEAM_SCHEMA)

        ensure_team_challenge_binding()

        zeilen = lies(pfad, "SELECT id, challenge_id, name, password_hash FROM teams ORDER BY id")
        assert zeilen == [(1, 2, "Alpha", "hash-alpha"), (2, 2, "Beta", "hash-beta")]

    def test_abgaben_bleiben_unveraendert(self, alte_datenbank):
        pfad = alte_datenbank(ALTES_TEAM_SCHEMA)

        ensure_team_challenge_binding()

        assert lies(pfad, "SELECT id, team_id, task_id, points FROM submissions") == [(1, 1, 1, 7)]

    def test_der_name_ist_danach_nur_je_wettbewerb_eindeutig(self, alte_datenbank):
        pfad = alte_datenbank(ALTES_TEAM_SCHEMA)

        ensure_team_challenge_binding()

        verbindung = sqlite3.connect(pfad)
        try:
            verbindung.execute(
                "INSERT INTO teams (challenge_id, name) VALUES (1, 'Alpha')")
            verbindung.commit()

            with pytest.raises(sqlite3.IntegrityError):
                verbindung.execute(
                    "INSERT INTO teams (challenge_id, name) VALUES (2, 'Alpha')")
                verbindung.commit()
        finally:
            verbindung.close()

    def test_zweiter_aufruf_tut_nichts(self, alte_datenbank):
        pfad = alte_datenbank(ALTES_TEAM_SCHEMA)

        ensure_team_challenge_binding()
        vorher = lies(pfad, "SELECT * FROM teams ORDER BY id")
        ensure_team_challenge_binding()

        assert lies(pfad, "SELECT * FROM teams ORDER BY id") == vorher

    def test_ohne_wettbewerb_bleibt_die_zuordnung_offen(self, alte_datenbank):
        pfad = alte_datenbank(ALTES_TEAM_SCHEMA + """
            DELETE FROM submissions;
            DELETE FROM challenges;
        """)

        ensure_team_challenge_binding()

        assert lies(pfad, "SELECT challenge_id FROM teams") == [(None,), (None,)]


class TestNachtraeglicheSpalten:
    def test_hinweis_spalten_werden_ergaenzt(self, alte_datenbank):
        pfad = alte_datenbank(ALTES_TEAM_SCHEMA)

        ensure_added_columns()

        spalten = {zeile[1] for zeile in lies(pfad, "PRAGMA table_info(tasks)")}
        assert {"hint", "hint_visible"} <= spalten

    def test_korrektur_spalte_wird_ergaenzt(self, alte_datenbank):
        pfad = alte_datenbank(ALTES_TEAM_SCHEMA)

        ensure_added_columns()

        spalten = {zeile[1] for zeile in lies(pfad, "PRAGMA table_info(submissions)")}
        assert "resubmit_allowed" in spalten

    def test_unterschrift_spalten_werden_ergaenzt_und_vorbelegt(self, alte_datenbank):
        pfad = alte_datenbank("""
            DROP TABLE IF EXISTS settings;
            CREATE TABLE settings (
                id INTEGER NOT NULL PRIMARY KEY,
                site_name VARCHAR(100) NOT NULL,
                tagline VARCHAR(300) NOT NULL
            );
            INSERT INTO settings (id, site_name, tagline)
                VALUES (1, 'Alter Name', 'Alter Untertitel');
        """)

        ensure_added_columns()

        zeilen = lies(pfad, "SELECT site_name, signature_name, signature_font FROM settings")
        assert zeilen == [("Alter Name", "", "caveat")]

    def test_spalte_fuer_den_untertitel_wird_ergaenzt(self, alte_datenbank):
        """Alte Wettbewerbe bekommen ein leeres Feld - also weiter den
        Untertitel aus den Einstellungen, genau wie bisher."""
        pfad = alte_datenbank(ALTES_TEAM_SCHEMA)

        ensure_added_columns()

        spalten = {zeile[1] for zeile in lies(pfad, "PRAGMA table_info(challenges)")}
        assert "tagline" in spalten
        assert lies(pfad, "SELECT tagline FROM challenges") == [("",), ("",)]

    def test_spalte_fuer_den_zeitpunkt_der_pause_wird_ergaenzt(self, alte_datenbank):
        pfad = alte_datenbank(ALTES_TEAM_SCHEMA)

        ensure_added_columns()

        spalten = {zeile[1] for zeile in lies(pfad, "PRAGMA table_info(challenges)")}
        assert "paused_at" in spalten

    def test_eine_laufende_pause_bekommt_einen_zeitpunkt(self, alte_datenbank):
        """Wer beim Update gerade pausiert hat, soll die Uhr angehalten sehen.

        Ohne Zeitpunkt liefe sie trotz Pause weiter, wie in der Fassung davor.
        Der Start des Updates ist der genaueste Zeitpunkt, den es noch gibt.
        """
        pfad = alte_datenbank(ALTES_TEAM_SCHEMA + """
            UPDATE challenges SET paused = 1 WHERE id = 2;
        """)

        ensure_added_columns()
        ensure_pause_timestamp()

        zeilen = lies(pfad, "SELECT id, paused_at FROM challenges ORDER BY id")
        assert zeilen[0][1] is None, "Ein nicht pausierter Wettbewerb bleibt leer"
        assert zeilen[1][1] is not None, "Die laufende Pause braucht einen Zeitpunkt"

    def test_der_zeitpunkt_steht_so_da_wie_alle_anderen(self, alte_datenbank):
        """Derselbe Text, den auch der Weg über die Modelle schreibt.

        Ohne die Typangabe ginge das datetime-Objekt unverändert an sqlite3,
        und dessen eingebauter Adapter ist seit Python 3.12 abgekündigt - er
        meldete sich bei jedem Testlauf mit einer Warnung. Geschrieben wird
        so oder so derselbe Text; hier steht, dass das auch stimmt.
        """
        import re

        pfad = alte_datenbank(ALTES_TEAM_SCHEMA + """
            UPDATE challenges SET paused = 1 WHERE id = 2;
        """)

        ensure_added_columns()
        ensure_pause_timestamp()

        zeitpunkt = lies(pfad, "SELECT paused_at FROM challenges WHERE id = 2")[0][0]
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(\.\d+)?", zeitpunkt), \
            f"So steht der Zeitpunkt nicht in der Datenbank: {zeitpunkt!r}"

    def test_kein_rohes_datum_geht_an_sqlite(self, alte_datenbank):
        """Der abgekündigte Adapter von sqlite3 wird gar nicht erst bemüht."""
        from datetime import datetime

        from sqlalchemy import event

        from extensions import db

        pfad = alte_datenbank(ALTES_TEAM_SCHEMA + """
            UPDATE challenges SET paused = 1 WHERE id = 2;
        """)
        ensure_added_columns()

        rohe = []

        def mitschreiben(conn, cursor, anweisung, parameter, kontext, many):
            werte = parameter.values() if isinstance(parameter, dict) else (parameter or ())
            rohe.extend(w for w in werte if isinstance(w, datetime))

        event.listen(db.engine, "before_cursor_execute", mitschreiben)
        try:
            ensure_pause_timestamp()
        finally:
            event.remove(db.engine, "before_cursor_execute", mitschreiben)

        assert not rohe, f"Ein datetime-Objekt ging unverwandelt weiter: {rohe}"
        assert lies(pfad, "SELECT paused_at FROM challenges WHERE id = 2")[0][0]

    def test_spalten_fuer_die_namen_werden_ergaenzt(self, alte_datenbank):
        pfad = alte_datenbank(ALTES_TEAM_SCHEMA)

        ensure_added_columns()

        spalten = {zeile[1] for zeile in lies(pfad, "PRAGMA table_info(teams)")}
        assert {"member_names", "members_approved"} <= spalten

    def test_spalte_fuer_das_kennzeichen_wird_ergaenzt(self, alte_datenbank):
        pfad = alte_datenbank(ALTES_TEAM_SCHEMA)

        ensure_added_columns()

        spalten = {zeile[1] for zeile in lies(pfad, "PRAGMA table_info(teams)")}
        assert "uid" in spalten

    def test_zweiter_aufruf_tut_nichts(self, alte_datenbank):
        alte_datenbank(ALTES_TEAM_SCHEMA)

        ensure_added_columns()
        ensure_added_columns() # darf nicht an einer doppelten Spalte scheitern

    def test_vorhandene_daten_bleiben_erhalten(self, alte_datenbank):
        pfad = alte_datenbank(ALTES_TEAM_SCHEMA)

        ensure_added_columns()

        assert lies(pfad, "SELECT title, max_points FROM tasks") == [("Aufgabe 1", 10)]


class TestKennzeichenDerTeams:
    """Teams von vorher bekommen beim Start ihr Kennzeichen."""

    def test_jedes_alte_team_bekommt_einen_eigenen_wert(self, alte_datenbank):
        pfad = alte_datenbank(ALTES_TEAM_SCHEMA)

        ensure_added_columns()
        ensure_team_uids()

        werte = [zeile[0] for zeile in lies(pfad, "SELECT uid FROM teams ORDER BY id")]
        assert all(werte), "Ohne Kennzeichen käme kein Team mehr auf seine Seite"
        assert len(set(werte)) == len(werte), "Ein gemeinsamer Wert wäre kein Kennzeichen"

    def test_zweiter_aufruf_laesst_die_werte_stehen(self, alte_datenbank):
        """Sonst flöge bei jedem Neustart jedes Team aus seiner Sitzung."""
        pfad = alte_datenbank(ALTES_TEAM_SCHEMA)

        ensure_added_columns()
        ensure_team_uids()
        vorher = lies(pfad, "SELECT id, uid FROM teams ORDER BY id")
        ensure_team_uids()

        assert lies(pfad, "SELECT id, uid FROM teams ORDER BY id") == vorher


def test_startmigrationen_laufen_auch_auf_einer_leeren_datenbank(database):
    """Auf einer frischen Installation darf nichts schiefgehen."""
    run_startup_migrations()


def test_der_umbau_der_teams_verliert_die_spalten_der_namen_nicht(alte_datenbank):
    """Die Reihenfolge der Migrationen zählt.

    Der Umbau schreibt die teams-Tabelle neu und kennt dabei nur die Spalten
    von damals. Liefe er nach dem Ergänzen, fielen die Namen wieder heraus -
    und ein Schul-Rechner mit einer alten Datenbank stünde ohne sie da.
    """
    pfad = alte_datenbank(ALTES_TEAM_SCHEMA)

    run_startup_migrations()

    spalten = {zeile[1] for zeile in lies(pfad, "PRAGMA table_info(teams)")}
    assert {"challenge_id", "member_names", "members_approved", "uid"} <= spalten
    assert lies(pfad, "SELECT name FROM teams ORDER BY id") == [("Alpha",), ("Beta",)]


class TestSicherungVorDerAenderung:
    """Vor einem Umbau der Struktur entsteht eine Kopie der Datenbank."""

    @pytest.fixture(autouse=True)
    def _ohne_vorherige_sicherung(self):
        """Der Merker gilt je Start - im Test je Test."""
        import app as anwendung

        anwendung._backup_path = None
        yield
        anwendung._backup_path = None

    def sicherungen(self, pfad):
        import glob
        import os

        ordner = os.path.dirname(pfad)
        return sorted(glob.glob(os.path.join(ordner, "*-vor-*.db")))

    def test_umbau_der_teams_legt_eine_kopie_an(self, alte_datenbank):
        pfad = alte_datenbank(ALTES_TEAM_SCHEMA)
        assert self.sicherungen(pfad) == []

        ensure_team_challenge_binding()

        kopien = self.sicherungen(pfad)
        assert len(kopien) == 1
        assert "-vor-teams-" in kopien[0]

    def test_die_kopie_enthaelt_den_stand_von_vorher(self, alte_datenbank):
        """Der eigentliche Zweck: an den Zustand vor dem Umbau herankommen."""
        pfad = alte_datenbank(ALTES_TEAM_SCHEMA)

        ensure_team_challenge_binding()

        kopie = self.sicherungen(pfad)[0]
        schema = lies(kopie, "SELECT sql FROM sqlite_master WHERE name='teams'")[0][0]
        assert "_challenge_team_uc" not in schema, "Kopie zeigt schon das neue Schema"
        assert lies(kopie, "SELECT name FROM teams ORDER BY id") == [("Alpha",), ("Beta",)]

    def test_ergaenzte_spalten_legen_eine_kopie_an(self, alte_datenbank):
        pfad = alte_datenbank(ALTES_TEAM_SCHEMA)

        ensure_added_columns()

        kopien = self.sicherungen(pfad)
        assert len(kopien) == 1, kopien
        assert "-vor-spalten-" in kopien[0]

    def test_ohne_aenderung_entsteht_keine_kopie(self, alte_datenbank):
        """Sonst läge nach zwanzig Starts zwanzigmal dasselbe im Ordner."""
        pfad = alte_datenbank(ALTES_TEAM_SCHEMA)

        ensure_added_columns()
        ensure_team_challenge_binding()
        vorher = self.sicherungen(pfad)

        import app as anwendung
        anwendung._backup_path = None
        ensure_added_columns()
        ensure_team_challenge_binding()

        assert self.sicherungen(pfad) == vorher

    def test_ein_start_legt_hoechstens_eine_kopie_an(self, alte_datenbank):
        """Sie entsteht vor der ersten Änderung und deckt damit beide ab."""
        pfad = alte_datenbank(ALTES_TEAM_SCHEMA)

        ensure_added_columns()
        ensure_team_challenge_binding()

        assert len(self.sicherungen(pfad)) == 1

    def test_auf_einer_frischen_installation_wird_nichts_gesichert(self, database):
        import app as anwendung

        ensure_added_columns()
        ensure_team_challenge_binding()

        assert anwendung._backup_path is None

    def test_scheitert_die_sicherung_wird_nicht_umgebaut(self, alte_datenbank, monkeypatch):
        """Lieber gar nicht starten als ungesichert umbauen."""
        import app as anwendung

        pfad = alte_datenbank(ALTES_TEAM_SCHEMA)

        def geht_schief(*args, **kwargs):
            raise OSError("kein Platz auf dem Gerät")

        monkeypatch.setattr(anwendung.sqlite3, "connect", geht_schief)

        with pytest.raises(RuntimeError) as fehler:
            ensure_team_challenge_binding()

        assert "nicht gesichert werden" in str(fehler.value)

        # Der Patch muss weg, bevor wir selbst in die Datenbank schauen.
        monkeypatch.undo()

        # Die Tabelle steht noch im alten Zustand.
        schema = lies(pfad, "SELECT sql FROM sqlite_master WHERE name='teams'")[0][0]
        assert "_challenge_team_uc" not in schema
