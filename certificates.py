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


class CertificatePDF(FPDF):
    def __init__(self, *args, signature_name="", signature_font_key=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.signature_name = " ".join(str(signature_name or "").split())

        font = signature_font(signature_font_key)
        self.signature_font_size = font["size"]
        self.signature_font_family = None
        if self.signature_name and font["file"]:
            path = os.path.join(FONT_DIR, font["file"])
            if os.path.exists(path):
                self.signature_font_family = font["css"]
                self.add_font(self.signature_font_family, "", path)

    def certificate(self, site_name, challenge_title, entry, task_count, date_text):
        self.add_page()

        # Decorative double border
        self.set_draw_color(90, 90, 120)
        self.set_line_width(1.2)
        self.rect(10, 10, self.w - 20, self.h - 20)
        self.set_line_width(0.3)
        self.rect(14, 14, self.w - 28, self.h - 28)

        self.set_y(38)
        self.set_font("Helvetica", "", 16)
        self.set_text_color(90, 90, 120)
        self.cell(0, 8, pdf_safe(site_name), align="C", new_x="LMARGIN", new_y="NEXT")

        self.ln(4)
        self.set_font("Helvetica", "B", 40)
        self.set_text_color(30, 30, 60)
        self.cell(0, 18, "Urkunde", align="C", new_x="LMARGIN", new_y="NEXT")

        self.ln(6)
        self.set_font("Helvetica", "", 14)
        self.set_text_color(60, 60, 80)
        self.cell(0, 8, "verliehen an das Team", align="C", new_x="LMARGIN", new_y="NEXT")

        self.ln(2)
        self.set_font("Helvetica", "B", 30)
        self.set_text_color(20, 20, 40)
        # Falls back when a name consists only of characters the font cannot
        # show, so the certificate never carries a blank name.
        self.cell(0, 16, pdf_safe(entry["name"]) or "Team", align="C",
                  new_x="LMARGIN", new_y="NEXT")

        self.ln(4)
        self.set_font("Helvetica", "", 14)
        self.set_text_color(60, 60, 80)
        if challenge_title:
            self.cell(
                0, 8, pdf_safe(f"für die Teilnahme am Wettbewerb \"{challenge_title}\""),
                align="C", new_x="LMARGIN", new_y="NEXT"
            )
        else:
            self.cell(0, 8, "für die Teilnahme am Wettbewerb", align="C",
                      new_x="LMARGIN", new_y="NEXT")

        place_label = PLACE_LABELS.get(entry["rank"])
        if place_label:
            self.ln(6)
            self.set_font("Helvetica", "B", 22)
            self.set_text_color(150, 110, 20)
            self.cell(0, 12, pdf_safe(place_label), align="C", new_x="LMARGIN", new_y="NEXT")

        self.ln(4)
        self.set_font("Helvetica", "", 14)
        self.set_text_color(60, 60, 80)
        points = entry["total"]
        summary = f"{points} " + ("Punkt" if points == 1 else "Punkte")
        if task_count:
            solved = entry["solved"]
            summary += f" - {solved} von {task_count} Aufgaben bearbeitet"
        self.cell(0, 8, pdf_safe(summary), align="C", new_x="LMARGIN", new_y="NEXT")

        # Signature block at the bottom
        self.set_y(-52)
        self.set_font("Helvetica", "", 12)
        self.set_text_color(90, 90, 110)
        self.cell(0, 6, pdf_safe(date_text), align="C", new_x="LMARGIN", new_y="NEXT")

        # The signature sits on the line, so it is drawn before the line is.
        signature_y = self.get_y()
        if self.signature_name:
            self.set_text_color(40, 40, 70)
            if self.signature_font_family:
                # An embedded TrueType font handles the full name as it is -
                # no need to strip characters the way the built-in font needs.
                self.set_font(self.signature_font_family, "", self.signature_font_size)
                self.cell(0, 10, self.signature_name, align="C", new_x="LMARGIN", new_y="NEXT")
            else:
                self.set_font("Helvetica", "", self.signature_font_size)
                self.cell(0, 10, pdf_safe(self.signature_name), align="C",
                          new_x="LMARGIN", new_y="NEXT")
            line_y = signature_y + 11
        else:
            line_y = signature_y + 2

        line_width = 80
        line_x = (self.w - line_width) / 2
        self.set_draw_color(140, 140, 160)
        self.set_line_width(0.3)
        self.line(line_x, line_y, line_x + line_width, line_y)

        self.set_y(line_y + 2)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(130, 130, 150)
        if not self.signature_name:
            caption = "Unterschrift"
        elif self.signature_font_family:
            # A flourished script can be hard to read, so the name is repeated
            # in plain type under the line.
            caption = pdf_safe(self.signature_name)
        else:
            caption = ""
        if caption:
            self.cell(0, 5, caption, align="C", new_x="LMARGIN", new_y="NEXT")


def build_certificates_pdf(site_name, challenge_title, entries, task_count, date_text=None,
                           signature_name="", signature_font_key=None):
    """Builds one PDF holding a certificate page per entry."""
    if date_text is None:
        date_text = datetime.now().strftime("%d.%m.%Y")

    pdf = CertificatePDF(
        orientation="L", unit="mm", format="A4",
        signature_name=signature_name,
        signature_font_key=signature_font_key
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
        signature_font_key=settings.signature_font
    )
