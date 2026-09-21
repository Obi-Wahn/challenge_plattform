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
# "start_y" ist die Höhe, auf der der Text beginnt: Der Unterschriftsblock
# sitzt in beiden Fällen unten am Blattrand, und dazwischen soll der Text
# weder kleben noch verloren wirken.
CERTIFICATE_ORIENTATIONS = {
    "landscape": {
        "label": "Querformat (quer liegendes Blatt)",
        "kurz": "Querformat",
        "fpdf": "L",
        "css": "landscape",
        "start_y": 38,
        "scale": 1.0,
        "signature_offset": 52,
        # A4 quer, 210 mm hoch, minus 1 cm Seitenrand oben und unten.
        "inner_height_mm": 186,
    },
    "portrait": {
        "label": "Hochformat (normal stehendes Blatt)",
        "kurz": "Hochformat",
        "fpdf": "P",
        "css": "portrait",
        "start_y": 55,
        # Ein A4-Hochblatt ist 87 mm hoeher als ein quer liegendes. Mit den
        # Groessen des Querformats stuende der Text als kleiner Block in der
        # Mitte und der Rest bliebe leer. Deshalb wird im Hochformat alles
        # groesser gesetzt - Schrift, Zeilenhoehen und Abstaende gleichermassen,
        # damit die Anordnung dieselbe bleibt.
        "scale": 1.35,
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

# Luft zwischen Text und innerem Zierrahmen, in Millimetern.
INNER_PADDING = 6


class CertificatePDF(FPDF):
    def __init__(self, *args, signature_name="", signature_font_key=None,
                 start_y=None, scale=1.0, signature_offset=52, **kwargs):
        super().__init__(*args, **kwargs)
        self.signature_name = " ".join(str(signature_name or "").split())

        # Wo der Text beginnt. Im Hochformat ist das Blatt höher, der Text
        # müsste sonst oben kleben und der Rest der Seite bliebe leer.
        self.start_y = start_y if start_y is not None else 38

        # Alles auf der Urkunde wird mit diesem Faktor gesetzt: Schriftgrößen,
        # Zeilenhöhen und Abstände. So bleibt die Anordnung dieselbe, und ein
        # höheres Blatt wird nicht mit Leerraum gefüllt, sondern mit Schrift.
        self.scale = scale
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

    def fitted_size(self, text, family, style, size):
        """Verkleinert die Schrift, bis der Text in den Zierrahmen passt.

        Im Hochformat ist das Blatt 87 mm schmaler als im Querformat. Ein
        langer Teamname oder Wettbewerbstitel liefe sonst in den Rahmen
        hinein, statt kleiner gesetzt zu werden.
        """
        verfuegbar = self.text_width()
        while size > 8:
            self.set_font(family, style, size)
            if self.get_string_width(text) <= verfuegbar:
                break
            size -= 1
        self.set_font(family, style, size)
        return size

    def centered_line(self, text, family, style, size, height, color):
        """Eine mittige Zeile innerhalb des Zierrahmens, notfalls kleiner gesetzt."""
        self.set_text_color(*color)
        self.fitted_size(text, family, style, size)

        breite = self.text_width()
        self.set_x((self.w - breite) / 2)
        self.cell(breite, height, text, align="C", new_x="LMARGIN", new_y="NEXT")

    def certificate(self, site_name, challenge_title, entry, task_count, date_text):
        self.add_page()

        # Decorative double border
        self.set_draw_color(90, 90, 120)
        self.set_line_width(1.2)
        self.rect(10, 10, self.w - 20, self.h - 20)
        self.set_line_width(0.3)
        self.rect(14, 14, self.w - 28, self.h - 28)

        self.set_y(self.start_y)
        self.centered_line(pdf_safe(site_name), "Helvetica", "",
                           self.mass(16), self.mass(8), (90, 90, 120))

        self.ln(self.mass(4))
        self.centered_line("Urkunde", "Helvetica", "B",
                           self.mass(40), self.mass(18), (30, 30, 60))

        self.ln(self.mass(6))
        self.centered_line("verliehen an das Team", "Helvetica", "",
                           self.mass(14), self.mass(8), (60, 60, 80))

        self.ln(self.mass(2))
        # Falls back when a name consists only of characters the font cannot
        # show, so the certificate never carries a blank name.
        self.centered_line(pdf_safe(entry["name"]) or "Team", "Helvetica", "B",
                           self.mass(30), self.mass(16), (20, 20, 40))

        self.ln(self.mass(4))
        if challenge_title:
            zeile = pdf_safe(f"für die Teilnahme am Wettbewerb \"{challenge_title}\"")
        else:
            zeile = "für die Teilnahme am Wettbewerb"
        self.centered_line(zeile, "Helvetica", "",
                           self.mass(14), self.mass(8), (60, 60, 80))

        place_label = PLACE_LABELS.get(entry["rank"])
        if place_label:
            self.ln(self.mass(6))
            self.centered_line(pdf_safe(place_label), "Helvetica", "B",
                               self.mass(22), self.mass(12), (150, 110, 20))

        self.ln(self.mass(4))
        points = entry["total"]
        summary = f"{points} " + ("Punkt" if points == 1 else "Punkte")
        if task_count:
            solved = entry["solved"]
            summary += f" - {solved} von {task_count} Aufgaben bearbeitet"
        self.centered_line(pdf_safe(summary), "Helvetica", "",
                           self.mass(14), self.mass(8), (60, 60, 80))

        # Signature block at the bottom
        self.set_y(-self.signature_offset)
        self.centered_line(pdf_safe(date_text), "Helvetica", "",
                           self.mass(12), self.mass(6), (90, 90, 110))

        # The signature sits on the line, so it is drawn before the line is.
        signature_y = self.get_y()
        if self.signature_name:
            self.set_text_color(40, 40, 70)
            if self.signature_font_family:
                # An embedded TrueType font handles the full name as it is -
                # no need to strip characters the way the built-in font needs.
                self.centered_line(self.signature_name, self.signature_font_family, "",
                                   self.mass(self.signature_font_size),
                                   self.mass(10), (40, 40, 70))
            else:
                self.centered_line(pdf_safe(self.signature_name), "Helvetica", "",
                                   self.mass(self.signature_font_size),
                                   self.mass(10), (40, 40, 70))
            line_y = signature_y + self.mass(11)
        else:
            line_y = signature_y + self.mass(2)

        # Die Linie bleibt innerhalb des Zierrahmens - im Hochformat ist das
        # Blatt schmaler als die 80 mm, die im Querformat gut aussehen.
        line_width = min(self.mass(80), self.w - 60)
        line_x = (self.w - line_width) / 2
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
        start_y=orientation["start_y"],
        scale=orientation.get("scale", 1.0),
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
    return {"team_id": team.id, "name": team.name, "total": 0, "solved": 0, "rank": 0}


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
