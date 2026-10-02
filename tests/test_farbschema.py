"""Hell oder dunkel - der Umschalter in der oberen Leiste.

Die Seite folgt ohne eigene Wahl der Einstellung des Geräts, der Knopf in
der Leiste überschreibt sie. Die Wahl bleibt im Browser: Der Server
bekommt sie nie zu sehen und setzt dafür kein Cookie. Ob die Farben im
Browser stimmen, prüft kein Test hier - nur, dass alles dafür da ist.
"""

import re
from datetime import datetime, timedelta
from pathlib import Path

from tests.test_navigation import leiste

STYLE = Path(__file__).resolve().parent.parent / "static" / "style.css"


def kopf(client, pfad="/"):
    html = client.get(pfad).get_data(as_text=True)
    return html[:html.index("</head>")]


class TestUmschalter:
    def test_steht_in_der_leiste(self, client, make_challenge):
        make_challenge(end_time=datetime.now() + timedelta(hours=1))

        nav = leiste(client)

        assert 'id="farbschema-knopf"' in nav

    def test_ohne_javascript_unsichtbar(self, client, make_challenge):
        """Ohne Skript könnte der Knopf nichts umschalten."""
        make_challenge(end_time=datetime.now() + timedelta(hours=1))

        nav = leiste(client)
        eintrag = re.search(r'<li[^>]*id="farbschema-eintrag"[^>]*>', nav)

        assert eintrag is not None
        assert "hidden" in eintrag.group(0)

    def test_zwischen_seiten_und_team(self, make_challenge, logged_in_team):
        """Teamname und Abmelden bleiben beieinander."""
        challenge = make_challenge(end_time=datetime.now() + timedelta(hours=1))
        client, _team = logged_in_team(challenge)

        nav = leiste(client)

        assert nav.index("Rangliste") < nav.index("farbschema-knopf")
        assert nav.index("farbschema-knopf") < nav.index("👥 Team Blitz")

    def test_auch_auf_den_admin_seiten(self, admin, make_challenge):
        make_challenge(end_time=datetime.now() + timedelta(hours=1))

        assert 'id="farbschema-knopf"' in leiste(admin, "/admin/dashboard")


class TestWahl:
    def test_steht_vor_dem_ersten_zeichnen_fest(self, client):
        """Im Kopf gesetzt, damit die Seite nicht erst dunkel aufblitzt."""
        html = kopf(client)

        assert 'localStorage.getItem("farbschema")' in html
        assert "prefers-color-scheme: light" in html
        assert "data-farbschema" in html

    def test_der_server_merkt_sich_nichts(self, client):
        """Kein Cookie, keine Abfrage: Die Wahl bleibt im Browser."""
        antwort = client.get("/")
        html = antwort.get_data(as_text=True)

        assert "farbschema" not in " ".join(antwort.headers.getlist("Set-Cookie"))
        assert "document.cookie" not in html
        assert "fetch(" not in html[html.index("farbschema-knopf"):]


class TestStil:
    def test_der_helle_modus_hat_eigene_farben(self):
        css = STYLE.read_text(encoding="utf-8")

        for klasse in ("body", ".event-card", ".zeitleiste", ".navbar-dark",
                       ".text-light", ".btn-outline-light", ".table-dark"):
            assert f'[data-farbschema="hell"] {klasse}' in css, klasse

    def test_dunkel_bleibt_ohne_attribut(self):
        """Der dunkle Grund steht ohne Bedingung - ohne Skript bleibt es dunkel."""
        css = STYLE.read_text(encoding="utf-8")
        grundlayout = css[:css.index("/* ====== Sterne")]

        assert "#0b0f1f" in grundlayout
        assert "data-farbschema" not in grundlayout

    def test_lesbar_auf_dunklem_grund(self):
        """Editorleiste und Ranglistenpunkte haben im dunklen Modus eigene
        Farben, und der helle Modus stellt die alten wieder her.

        Ohne eigene Farbe zeichnete die Werkzeugleiste des Markdown-Editors
        schwarz auf der dunklen Karte, die Punkte der Rangliste standen
        dunkelgrün auf dunklem Grund, und der Strich für leere Felder war
        gar nicht zu sehen.
        """
        css = STYLE.read_text(encoding="utf-8")

        for klasse in (".EasyMDEContainer .editor-toolbar button",
                       ".EasyMDEContainer .editor-toolbar i.separator",
                       ".ranglisten-punkte", ".ranglisten-leer"):
            assert f"\n{klasse} {{" in css, klasse
            assert f'[data-farbschema="hell"] {klasse} {{' in css, klasse

    def test_rangliste_nutzt_die_eigenen_klassen(self, client, make_challenge,
                                                 make_task, make_team):
        from extensions import db
        from models import Submission

        challenge = make_challenge(end_time=datetime.now() + timedelta(hours=1))
        erste = make_task(challenge, title="Labyrinth")
        make_task(challenge, title="Ping-Pong")
        team = make_team(challenge, name="Team Blitz")
        db.session.add(Submission(team_id=team.id, task_id=erste.id,
                                  filename="loesung.sb3", points=8))
        db.session.commit()

        html = client.get("/scoreboard").get_data(as_text=True)

        assert 'class="badge ranglisten-punkte"' in html
        assert 'class="ranglisten-leer"' in html
        assert "text-success" not in html[html.index("<table"):]
