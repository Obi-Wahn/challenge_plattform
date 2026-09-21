"""Generation of the printable certificates (Urkunden) as PDF."""

import os
from datetime import datetime

from fpdf import FPDF

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "vendor", "fonts")

# Fonts the admin can pick for the signature under a certificate. All three
# handwriting faces are SIL Open Font License and ship with the repo, so this
# works on a machine without internet. "file" is what fpdf2 embeds, "css" the
# family name the print view uses, "size" the point size that makes the face
# sit nicely on the signature line (they differ a lot in visual size).
SIGNATURE_FONTS = {
    "caveat": {
        "label": "Caveat - locker geschrieben",
        "file": "Caveat-Regular.ttf",
        "css": "Caveat",
        "size": 26,
    },
    "dancing": {
        "label": "Dancing Script - schwungvoll",
        "file": "DancingScript-Regular.ttf",
        "css": "Dancing Script",
        "size": 22,
    },
    "vibes": {
        "label": "Great Vibes - verschnörkelt",
        "file": "GreatVibes-Regular.ttf",
        "css": "Great Vibes",
        "size": 24,
    },
    "print": {
        "label": "Druckschrift (keine Handschrift)",
        "file": None,
        "css": None,
        "size": 14,
    },
}

DEFAULT_SIGNATURE_FONT = "caveat"

# Ausrichtung der Urkunden. Querformat ist die bisherige und weiterhin die
# voreingestellte Fassung; Hochformat gibt es, weil sich so ein Stapel besser
# abheften lässt und manche Drucker damit weniger Zicken machen.
#
# Wo der Text steht, rechnet die Urkunde selbst aus: Sie misst, wie hoch der
# Block wird, und verteilt den Rest auf die Abstände. "gap_stretch" ist die
# Grenze, bis zu der die Abstände dabei aufgehen dürfen.
CERTIFICATE_ORIENTATIONS = {
    "landscape": {
        "label": "Querformat (quer liegendes Blatt)",
        "kurz": "Querformat",
        "fpdf": "L",
        "css": "landscape",
        "scale": 1.0,
        # Das Querformat ist die gewachsene Fassung und füllt sein Blatt schon
        # gut aus - die Abstände bleiben hier so, wie sie gesetzt sind.
        "gap_stretch": 1.0,
        "signature_offset": 52,
        # A4 quer, 210 mm hoch, minus 1 cm Seitenrand oben und unten.
        "inner_height_mm": 186,
    },
    "portrait": {
        "label": "Hochformat (normal stehendes Blatt)",
        "kurz": "Hochformat",
        "fpdf": "P",
        "css": "portrait",
        # Ein A4-Hochblatt ist 87 mm hoeher als ein quer liegendes. Mit den
        # Groessen des Querformats stuende der Text als kleiner Block in der
        # Mitte und der Rest bliebe leer. Deshalb wird im Hochformat alles
        # groesser gesetzt - Schrift, Zeilenhoehen und Abstaende gleichermassen,
        # damit die Anordnung dieselbe bleibt.
        "scale": 1.35,
        # Das Blatt ist hoeher, als die groessere Schrift allein fuellt. Ohne
        # gedehnte Abstaende blieb ueber dem Unterschriftsblock ein leeres
        # Band von rund 4 cm stehen.
        "gap_stretch": 2.0,
        "signature_offset": 62,
        # A4 hoch, 297 mm, minus 1 cm Seitenrand oben und unten.
        "inner_height_mm": 277,
    },
}

DEFAULT_ORIENTATION = "landscape"


def certificate_orientation(key):
    """Die Ausrichtung zu einem gespeicherten Wert, sonst die Voreinstellung."""
    return CERTIFICATE_ORIENTATIONS.get(key) or CERTIFICATE_ORIENTATIONS[DEFAULT_ORIENTATION]


def signature_font(key):
    """The font definition for a stored key, falling back to the default."""
    return SIGNATURE_FONTS.get(key) or SIGNATURE_FONTS[DEFAULT_SIGNATURE_FONT]

# The PDF uses the built-in Helvetica font, which covers latin-1 - enough for
# German text, but not for typographic punctuation or the emoji students like
# to put in their team names. Unsupported characters would otherwise make
# fpdf2 raise, so they are mapped to a plain equivalent or dropped.
_REPLACEMENTS = {
    "–": "-", "—": "-", "‐": "-", "‑": "-",
    "„": '"', "“": '"', "”": '"', "«": '"', "»": '"',
    "‚": "'", "‘": "'", "’": "'",
    "…": "...", "•": "-", "→": "->", " ": " ",
}


def pdf_safe(text):
    text = str(text or "")
    for source, target in _REPLACEMENTS.items():
        text = text.replace(source, target)
    # Anything still outside latin-1 (emoji, other scripts) is dropped.
    cleaned = text.encode("latin-1", errors="ignore").decode("latin-1")
    return " ".join(cleaned.split())


PLACE_LABELS = {1: "1. Platz", 2: "2. Platz", 3: "3. Platz"}


def names_line(namen):
    """Die Namen der Teammitglieder als ein Satz: „Anna, Ben und Carla“.

    Auf einer Urkunde liest sich eine Aufzählung besser als eine Liste
    untereinander - und sie braucht weniger Platz, was bei acht Namen zählt.
    """
    namen = [" ".join(str(name).split()) for name in (namen or [])]
    namen = [name for name in namen if name]

    if not namen:
        return ""
    if len(namen) == 1:
        return namen[0]
    return ", ".join(namen[:-1]) + " und " + namen[-1]

# Luft zwischen Text und innerem Zierrahmen, in Millimetern.
INNER_PADDING = 6


class CertificatePDF(FPDF):
    def __init__(self, *args, signature_name="", signature_font_key=None,
                 scale=1.0, gap_stretch=1.0, signature_offset=52, **kwargs):
        super().__init__(*args, **kwargs)
        self.signature_name = " ".join(str(signature_name or "").split())

        # Alles auf der Urkunde wird mit diesem Faktor gesetzt: Schriftgrößen,
        # Zeilenhöhen und Abstände. So bleibt die Anordnung dieselbe, und ein
        # höheres Blatt wird nicht mit Leerraum gefüllt, sondern mit Schrift.
        self.scale = scale

        # Wie weit die Abstände zwischen den Zeilen aufgehen dürfen, wenn auf
        # dem Blatt Platz übrig ist.
        self.gap_stretch = gap_stretch
        self.signature_offset = signature_offset

        font = signature_font(signature_font_key)
        self.signature_font_size = font["size"]
        self.signature_font_family = None
        if self.signature_name and font["file"]:
            path = os.path.join(FONT_DIR, font["file"])
            if os.path.exists(path):
                self.signature_font_family = font["css"]
                self.add_font(self.signature_font_family, "", path)

    def mass(self, wert):
        """Ein Maß in der Größe dieser Ausrichtung."""
        return wert * self.scale

    def text_width(self):
        """Die Breite, die dem Text zur Verfügung steht.

        Nicht der Seitenrand ist die Grenze, sondern der innere Zierrahmen
        bei 14 mm - plus etwas Luft, damit der Text ihn nicht berührt.
        """
        return self.w - 2 * (14 + INNER_PADDING)

    def fitted_size(self, text, family, style, size, max_width=None):
        """Verkleinert die Schrift, bis der Text in den Zierrahmen passt.

        Im Hochformat ist das Blatt 87 mm schmaler als im Querformat. Ein
        langer Teamname oder Wettbewerbstitel liefe sonst in den Rahmen
        hinein, statt kleiner gesetzt zu werden.

        "max_width" ist für Zeilen da, die enger stehen müssen als der
        Zierrahmen - die Unterschrift etwa gehört über ihre Linie.
        """
        verfuegbar = self.text_width() if max_width is None else max_width
        while size > 8:
            self.set_font(family, style, size)
            if self.get_string_width(text) <= verfuegbar:
                break
            size -= 1
        self.set_font(family, style, size)
        return size

    def fitted_lines(self, text, family, style, size, max_lines, min_size=0):
        """Bricht den Text um und verkleinert ihn erst, wenn das nicht reicht.

        Ein langer Teamname wurde vorher nur verkleinert, bis er in eine
        einzige Zeile passte. Im Hochformat landete er dadurch unter der
        Größe des Fließtexts darunter - ausgerechnet der Name, um den es auf
        der Urkunde geht, war die kleinste Zeile.

        Eine Zeile bleibt die schönere Lösung, solange die Schrift dabei
        nicht unter "min_size" rutscht. Erst darunter sind zwei Zeilen das
        kleinere Übel.
        """
        einzeilig = self.fitted_size(text, family, style, size)
        if max_lines <= 1 or einzeilig >= min_size:
            return [text], einzeilig

        breite = self.text_width()
        while True:
            self.set_font(family, style, size)
            zeilen = self.multi_cell(breite, dry_run=True, output="LINES", text=text)
            if len(zeilen) <= max_lines or size <= 8:
                return list(zeilen), size
            size -= 1

    def centered_line(self, text, family, style, size, height, color, max_width=None):
        """Eine mittige Zeile innerhalb des Zierrahmens, notfalls kleiner gesetzt."""
        self.set_text_color(*color)
        self.fitted_size(text, family, style, size, max_width)
        self.centered_text(text, height)

    def centered_text(self, text, height):
        """Setzt eine Zeile mittig, in der bereits gewählten Schrift."""
        breite = self.text_width()
        self.set_x((self.w - breite) / 2)
        self.cell(breite, height, text, align="C", new_x="LMARGIN", new_y="NEXT")

    def certificate_blocks(self, site_name, challenge_title, entry, task_count):
        """Die Zeilen der Urkunde von oben nach unten, noch ohne Position.

        "abstand" ist die Luft über einer Zeile, "zeilen" die Zahl der Zeilen,
        auf die sie notfalls umbrechen darf.
        """
        if challenge_title:
            teilnahme = pdf_safe(f"für die Teilnahme am Wettbewerb \"{challenge_title}\"")
        else:
            teilnahme = "für die Teilnahme am Wettbewerb"

        points = entry["total"]
        summary = f"{points} " + ("Punkt" if points == 1 else "Punkte")
        if task_count:
            summary += f" - {entry['solved']} von {task_count} Aufgaben bearbeitet"

        bloecke = [
            {"text": pdf_safe(site_name), "style": "", "size": 16, "hoehe": 8,
             "farbe": (90, 90, 120), "abstand": 0},
            {"text": "Urkunde", "style": "B", "size": 40, "hoehe": 18,
             "farbe": (30, 30, 60), "abstand": 4},
            {"text": "verliehen an das Team", "style": "", "size": 14, "hoehe": 8,
             "farbe": (60, 60, 80), "abstand": 6},
            # "Team" fällt ein, wenn der Name nur aus Zeichen besteht, die die
            # Schrift nicht zeigen kann - leer bleibt die Zeile nie. Auf zwei
            # Zeilen darf er, sobald er einzeilig kleiner würde als die
            # Zeilen um ihn herum.
            {"text": pdf_safe(entry["name"]) or "Team", "style": "B", "size": 30,
             "hoehe": 16, "farbe": (20, 20, 40), "abstand": 2,
             "zeilen": 2, "mindestens": 16},
        ]

        # Die Namen der Teammitglieder stehen direkt unter dem Teamnamen -
        # sie gehören zu ihm. In der Größe des Fließtexts: kleiner als der
        # Teamname, aber nicht kleiner als die Zeilen darunter. Reicht eine
        # Zeile nicht, bricht die Aufzählung um, statt zu schrumpfen; vier
        # Zeilen sind die Grenze. Hat ein Team keine freigegebenen Namen,
        # fehlt die Zeile ganz und die Urkunde sieht aus wie bisher.
        namen = names_line(entry.get("members"))
        if namen:
            bloecke.append(
                {"text": pdf_safe(namen), "style": "", "size": 14, "hoehe": 8,
                 "farbe": (70, 70, 95), "abstand": 1,
                 "zeilen": 4, "mindestens": 12})

        bloecke.append(
            {"text": teilnahme, "style": "", "size": 14, "hoehe": 8,
             "farbe": (60, 60, 80), "abstand": 4})

        place_label = PLACE_LABELS.get(entry["rank"])
        if place_label:
            bloecke.append(
                {"text": pdf_safe(place_label), "style": "B", "size": 22, "hoehe": 12,
                 "farbe": (150, 110, 20), "abstand": 6})

        bloecke.append(
            {"text": pdf_safe(summary), "style": "", "size": 14, "hoehe": 8,
             "farbe": (60, 60, 80), "abstand": 4})
        return bloecke

    def layout_blocks(self, bloecke):
        """Misst die Zeilen aus und verteilt den übrigen Platz auf die Abstände.

        Zwischen Zierrahmen und Unterschriftsblock ist mehr Platz, als die
        Zeilen brauchen. Vorher stand dieser Rest als ein leeres Band über
        der Unterschrift; jetzt geht er in die Abstände, bis zu der Grenze,
        die die Ausrichtung vorgibt.
        """
        for block in bloecke:
            gewuenscht = self.mass(block["size"])
            zeilen, gesetzt = self.fitted_lines(
                block["text"], "Helvetica", block["style"], gewuenscht,
                block.get("zeilen", 1), self.mass(block.get("mindestens", 0)))
            block["zeilen_text"] = zeilen
            block["gesetzt"] = gesetzt
            # Die Zeilenhöhe folgt der Schrift, die wirklich gesetzt wurde.
            # Sonst schwebte ein verkleinerter Name in einer viel zu hohen Zeile.
            block["zeilenhoehe"] = self.mass(block["hoehe"]) * gesetzt / gewuenscht

        text_hoehe = sum(b["zeilenhoehe"] * len(b["zeilen_text"]) for b in bloecke)
        abstaende = sum(self.mass(b["abstand"]) for b in bloecke)

        oben = 14 + INNER_PADDING
        platz = (self.h - self.signature_offset) - oben

        uebrig = platz - text_hoehe - abstaende
        faktor = 1.0
        if uebrig > 0 and abstaende > 0:
            faktor = min(self.gap_stretch, 1 + uebrig / abstaende)
        for block in bloecke:
            block["luft"] = self.mass(block["abstand"]) * faktor

        hoehe = text_hoehe + abstaende * faktor
        return oben + max(0, (platz - hoehe) / 2)

    def certificate(self, site_name, challenge_title, entry, task_count, date_text):
        self.add_page()

        # Decorative double border
        self.set_draw_color(90, 90, 120)
        self.set_line_width(1.2)
        self.rect(10, 10, self.w - 20, self.h - 20)
        self.set_line_width(0.3)
        self.rect(14, 14, self.w - 28, self.h - 28)

        bloecke = self.certificate_blocks(site_name, challenge_title, entry, task_count)
        self.set_y(self.layout_blocks(bloecke))

        for block in bloecke:
            if block["luft"]:
                self.ln(block["luft"])
            self.set_text_color(*block["farbe"])
            self.set_font("Helvetica", block["style"], block["gesetzt"])
            for zeile in block["zeilen_text"]:
                self.centered_text(zeile, block["zeilenhoehe"])

        # Signature block at the bottom
        self.set_y(-self.signature_offset)
        self.centered_line(pdf_safe(date_text), "Helvetica", "",
                           self.mass(12), self.mass(6), (90, 90, 110))

        # Die Linie bleibt innerhalb des Zierrahmens - im Hochformat ist das
        # Blatt schmaler als die 80 mm, die im Querformat gut aussehen.
        line_width = min(self.mass(80), self.w - 60)
        line_x = (self.w - line_width) / 2

        # The signature sits on the line, so it is drawn before the line is.
        signature_y = self.get_y()
        if self.signature_name:
            self.set_text_color(40, 40, 70)
            # Ein langer Name wurde vorher nur auf die Breite des Zierrahmens
            # verkleinert und stand dadurch weit über beide Enden seiner
            # eigenen Linie hinaus. Die Linie ist die Grenze, nicht der Rahmen.
            if self.signature_font_family:
                # An embedded TrueType font handles the full name as it is -
                # no need to strip characters the way the built-in font needs.
                self.centered_line(self.signature_name, self.signature_font_family, "",
                                   self.mass(self.signature_font_size),
                                   self.mass(10), (40, 40, 70), line_width)
            else:
                self.centered_line(pdf_safe(self.signature_name), "Helvetica", "",
                                   self.mass(self.signature_font_size),
                                   self.mass(10), (40, 40, 70), line_width)
            line_y = signature_y + self.mass(11)
        else:
            line_y = signature_y + self.mass(2)

        self.set_draw_color(140, 140, 160)
        self.set_line_width(0.3)
        self.line(line_x, line_y, line_x + line_width, line_y)

        self.set_y(line_y + self.mass(2))
        if not self.signature_name:
            caption = "Unterschrift"
        elif self.signature_font_family:
            # A flourished script can be hard to read, so the name is repeated
            # in plain type under the line.
            caption = pdf_safe(self.signature_name)
        else:
            caption = ""
        if caption:
            self.centered_line(caption, "Helvetica", "",
                               self.mass(10), self.mass(5), (130, 130, 150))


def build_certificates_pdf(site_name, challenge_title, entries, task_count, date_text=None,
                           signature_name="", signature_font_key=None,
                           orientation_key=None):
    """Builds one PDF holding a certificate page per entry."""
    if date_text is None:
        date_text = datetime.now().strftime("%d.%m.%Y")

    orientation = certificate_orientation(orientation_key)

    pdf = CertificatePDF(
        orientation=orientation["fpdf"], unit="mm", format="A4",
        signature_name=signature_name,
        signature_font_key=signature_font_key,
        scale=orientation.get("scale", 1.0),
        gap_stretch=orientation.get("gap_stretch", 1.0),
        signature_offset=orientation.get("signature_offset", 52)
    )
    pdf.set_auto_page_break(False)
    pdf.set_title(pdf_safe(f"Urkunden - {site_name}"))

    for entry in entries:
        pdf.certificate(site_name, challenge_title, entry, task_count, date_text)

    return bytes(pdf.output())


def certificate_entry(team, standings):
    """The standings row of a team, or an empty one if it has no result yet."""
    for entry in standings:
        if entry["team_id"] == team.id:
            return entry
    return {"team_id": team.id, "name": team.name, "members": team.certificate_names,
            "total": 0, "solved": 0, "rank": 0}


def build_certificates_for(challenge, entries, task_count):
    """Certificates for a competition, using the configured signature."""
    from models import Settings

    settings = Settings.get()
    return build_certificates_pdf(
        settings.site_name,
        challenge.title if challenge else "",
        entries,
        task_count,
        signature_name=settings.signature_name,
        signature_font_key=settings.signature_font,
        orientation_key=settings.certificate_orientation
    )
