"""Generation of the printable certificates (Urkunden) as PDF."""

from datetime import datetime

from fpdf import FPDF

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

        self.ln(2)
        line_width = 80
        line_x = (self.w - line_width) / 2
        line_y = self.get_y()
        self.set_draw_color(140, 140, 160)
        self.set_line_width(0.3)
        self.line(line_x, line_y, line_x + line_width, line_y)

        self.set_y(line_y + 2)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(130, 130, 150)
        self.cell(0, 5, "Unterschrift", align="C", new_x="LMARGIN", new_y="NEXT")


def build_certificates_pdf(site_name, challenge_title, entries, task_count, date_text=None):
    """Builds one PDF holding a certificate page per entry."""
    if date_text is None:
        date_text = datetime.now().strftime("%d.%m.%Y")

    pdf = CertificatePDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(False)
    pdf.set_title(pdf_safe(f"Urkunden - {site_name}"))

    for entry in entries:
        pdf.certificate(site_name, challenge_title, entry, task_count, date_text)

    return bytes(pdf.output())
