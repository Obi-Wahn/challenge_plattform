"""Beim Start ergänzte Datenbank-Änderungen.

Eine Datenbank aus einer älteren Version der Anwendung muss beim Start
weiterbenutzbar werden, ohne dass Teams, Abgaben oder Punkte verloren gehen.
Diese Tests bauen die alten Schemata von Hand nach.
"""

import sqlite3

import pytest

from app import ensure_added_columns, ensure_team_challenge_binding


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

    def test_zweiter_aufruf_tut_nichts(self, alte_datenbank):
        alte_datenbank(ALTES_TEAM_SCHEMA)

        ensure_added_columns()
        ensure_added_columns() # darf nicht an einer doppelten Spalte scheitern

    def test_vorhandene_daten_bleiben_erhalten(self, alte_datenbank):
        pfad = alte_datenbank(ALTES_TEAM_SCHEMA)

        ensure_added_columns()

        assert lies(pfad, "SELECT title, max_points FROM tasks") == [("Aufgabe 1", 10)]


def test_startmigrationen_laufen_auch_auf_einer_leeren_datenbank(database):
    """Auf einer frischen Installation darf nichts schiefgehen."""
    ensure_added_columns()
    ensure_team_challenge_binding()


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
