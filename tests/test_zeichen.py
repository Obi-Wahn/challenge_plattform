"""Bunte Zeichen bleiben bunt, auch unter Windows.

Manche Zeichen zeigt der Browser ohne Zusatz als Schriftzeichen: einfarbig,
als Umriss in der Textfarbe. Erst der unsichtbare Variantenwähler U+FE0F
dahinter macht sie zum bunten Emoji. Windows hält sich streng daran, aus
🎛 neben „Steuerzentrale" wurde dort ein schwarzer Umriss, den man kaum
erkannte. Nicht jedes System ist so streng, deshalb fällt es beim
Entwickeln leicht nicht auf.
"""

import re
from pathlib import Path

VORLAGEN = Path(__file__).resolve().parent.parent / "templates"

# Alle Einzelzeichen, die erst mit U+FE0F als Emoji gelten (Unicode 16,
# „Emoji" ohne „Emoji_Presentation", Buchstaben-Flaggen ausgenommen).
OHNE_ZUSATZ_EINFARBIG = set(
    "©®‼⁉™ℹ↔↕↖↗↘↙↩↪⌨⏏⏭⏮⏯⏱⏲⏸⏹⏺Ⓜ▪▫▶◀◻◼☀☁☂☃☄☎☑☘☝☠☢☣☦☪☮☯☸☹☺♀♂♟♠♣♥♦♨♻♾"
    "⚒⚔⚕⚖⚗⚙⚛⚜⚠⚧⚰⚱⛈⛏⛑⛓⛩⛰⛱⛴⛷⛸⛹✂✈✉✌✍✏✒✔✖✝✡✳✴❄❇❣❤➡⤴⤵⬅⬆⬇〰〽㊗㊙"
    "🅰🅱🅾🅿🈂🈷🌡🌤🌥🌦🌧🌨🌩🌪🌫🌬🌶🍽🎖🎗🎙🎚🎛🎞🎟🏋🏌🏍🏎🏔🏕🏖🏗🏘🏙🏚🏛🏜"
    "🏝🏞🏟🏳🏵🏷🐿👁📽🕉🕊🕯🕰🕳🕴🕵🕶🕷🕸🕹🖇🖊🖋🖌🖍🖐🖥🖨🖱🖲🖼🗂🗃🗄🗑🗒🗓🗜🗝"
    "🗞🗡🗣🗨🗯🗳🗺🛋🛍🛎🛏🛠🛡🛢🛣🛤🛥🛩🛰🛳"
)

# Diese stehen absichtlich als Umriss da, und zwar überall gleich. Sie
# nehmen die Farbe des Knopfs oder Abzeichens an: ⏸ im gelben „pausiert",
# 🗑 in jedem roten Löschknopf. Bunt zeigt Windows ⏸ und ▶ als blaue
# Kästchen und 🗑 als grauen Eimer.
ABSICHTLICH_EINFARBIG = set("⏸▶✔↩🗑")


def fundstellen(ordner=VORLAGEN):
    """Zeichen, die bunt sein sollen, aber ohne U+FE0F dastehen."""
    gesucht = OHNE_ZUSATZ_EINFARBIG - ABSICHTLICH_EINFARBIG
    return _suche(ordner, "[" + "".join(sorted(gesucht)) + "](?!\ufe0f)")


def bunt_statt_umriss(ordner=VORLAGEN):
    """Zeichen, die Umriss sein sollen, aber U+FE0F tragen."""
    return _suche(ordner, "[" + "".join(sorted(ABSICHTLICH_EINFARBIG)) + "](?=\ufe0f)")


def _suche(ordner, muster):
    """Treffer als „Datei:Zeile Zeichen", damit eine Meldung gleich zeigt, wo."""
    muster = re.compile(muster)
    treffer_liste = []
    for datei in sorted(ordner.rglob("*.html")):
        for nummer, zeile in enumerate(datei.read_text(encoding="utf-8").splitlines(), 1):
            for treffer in muster.finditer(zeile):
                treffer_liste.append(f"{datei.relative_to(ordner)}:{nummer} {treffer.group()}")
    return treffer_liste


class TestBunteZeichen:
    def test_vorlagen_haben_den_zusatz(self):
        assert fundstellen() == []

    def test_umrisse_bleiben_umrisse(self):
        """Alle Löschknöpfe sehen gleich aus, kein einzelner bunter Eimer."""
        assert bunt_statt_umriss() == []

    def test_steuerzentrale(self, admin):
        """Das Zeichen, mit dem es aufgefallen ist."""
        html = admin.get("/admin/", follow_redirects=True).get_data(as_text=True)

        assert "🎛\ufe0f Steuerzentrale" in html

    def test_die_pruefung_greift(self, tmp_path):
        """Beide Suchen finden genau das Zeichen, das falsch dasteht."""
        (tmp_path / "a.html").write_text(
            "🎛 x\n🎛\ufe0f y\n🗑 z\n🗑\ufe0f w\n", encoding="utf-8"
        )

        assert fundstellen(tmp_path) == ["a.html:1 🎛"]
        assert bunt_statt_umriss(tmp_path) == ["a.html:4 🗑"]
