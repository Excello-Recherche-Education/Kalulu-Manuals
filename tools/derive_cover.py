"""Derive a cover for a language the designer did not draw, from the French one.

The covers in `assets/covers/` are the designer's own artwork, one two-page PDF
per language: the front, then the back. Only French, Spanish and Portuguese were
drawn. For any other language this keeps every drawn element of the French
pair -- the logo, the star, the partner logos, the diamond rules, the navy box
behind the web address -- removes the French words, and sets the translated
ones in their place, in the same typeface, size, colour and baseline.

    python tools/derive_cover.py it        # writes assets/covers/it.pdf

The result is committed like the drawn ones, so building a manual never runs
this. Re-run it when the French cover changes; add a language to `COVERS_TEXT`.

Two approximations, both invisible at reading size: the designer used Mulish
Light for the footer and Mulish Medium for the address, and only Regular, Bold
and Black are vendored, so those two are set in Regular.

The partner logo "Agir pour l'Education" is drawn artwork, localised by the
designer for Spanish and Portuguese. A derived cover keeps the French one:
it is the organisation's name, and a translation of it is not ours to invent.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import ContentStream
from reportlab.lib.colors import CMYKColor
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kalulu_manual import theme  # noqa: E402

COVERS = ROOT / "assets" / "covers"

#: The designer's navy, as the cover PDF specifies it (CMYK, not the app's RGB).
INK = CMYKColor(1, 0.945, 0.18, 0.055)
PAPER = CMYKColor(0, 0, 0, 0)

#: Measured from the French cover's text operators, in the cover's own points:
#: (size, first baseline, the vertical axis the block is centred on). None of
#: the axes is the page's own centre -- the designer centred each block by eye
#: against the artwork -- so each is matched rather than recomputed.
FRONT = (20.7132, 128.29, 216.86)
BACK = (12, 475.3145, 213.6)
FOOTER = (9, 89.7988, 208.05)
#: The navy box behind the address spans x 175.47..237.06.
ADDRESS_CENTRE = 206.26
LEADING = 1.2  # every text block on both pages is set at 120 %

# Each line is a list of (text, bold) runs, broken where the designer broke the
# French: a centred block reads as designed only when its lines are chosen.
COVERS_TEXT = {
    "it": {
        "front": ["Guida all’uso", "dell’applicazione Kalulu"],
        "back": [
            [("Agir pour l’Éducation beneficia del sostegno della", False)],
            [("Fondation du Collège de France", True), (" e dei suoi mecenati", False)],
            [("LVMH", True), (", la ", False), ("Fondation Engie", True), (", la ", False),
             ("Fondation Covéa", True), (" e", False)],
            [("Stellantis", True), (".", False)],
            [("Kalulu beneficia inoltre del sostegno della Fondation", False)],
            [("Jean-François de Clermont-Tonnerre.", False)],
        ],
        "footer": "Trovate tutto il nostro materiale didattico su",
    },
}

#: Written in white on the navy box the French back already draws.
ADDRESS = "excellolab.org"


def _without_text(page, reader) -> None:
    """Drop every text-showing operator, and keep everything else.

    Only Tj / TJ / ' / " go: the text object and its state operators stay, since
    the French front sets its fill colour inside the text object and the star
    drawn after it relies on that colour still being current.
    """
    content = ContentStream(page.get_contents(), reader)
    content.operations = [
        (operands, op) for operands, op in content.operations
        if op not in (b"Tj", b"TJ", b"'", b'"')
    ]
    page.replace_contents(content)


def _centred_line(canvas: Canvas, runs, size: float, y: float, centre: float) -> None:
    fonts = [theme.BODY_BOLD if bold else theme.BODY for _text, bold in runs]
    widths = [stringWidth(text, font, size) for (text, _bold), font in zip(runs, fonts)]
    x = centre - sum(widths) / 2
    for (text, _bold), font, width in zip(runs, fonts, widths):
        canvas.setFont(font, size)
        canvas.drawString(x, y, text)
        x += width


def _overlay(size: tuple[float, float], draw):
    buffer = io.BytesIO()
    canvas = Canvas(buffer, pagesize=size)
    draw(canvas)
    canvas.showPage()
    canvas.save()
    buffer.seek(0)
    return PdfReader(buffer).pages[0]


def derive(locale: str) -> Path:
    if not theme.register_fonts():
        raise SystemExit("Mulish is not in assets/fonts; a cover set in Helvetica is not one")
    text = COVERS_TEXT[locale]
    reader = PdfReader(COVERS / "fr.pdf")
    writer = PdfWriter()
    writer.append(reader)
    front, back = writer.pages
    size = (float(front.mediabox.width), float(front.mediabox.height))

    def block(canvas: Canvas, lines, metrics) -> None:
        size, baseline, centre = metrics
        for index, runs in enumerate(lines):
            _centred_line(canvas, runs, size, baseline - index * size * LEADING, centre)

    def draw_front(canvas: Canvas) -> None:
        canvas.setFillColor(INK)
        block(canvas, [[(line, True)] for line in text["front"]], FRONT)

    def draw_back(canvas: Canvas) -> None:
        canvas.setFillColor(INK)
        block(canvas, text["back"], BACK)
        block(canvas, [[(text["footer"], False)]], FOOTER)
        canvas.setFillColor(PAPER)
        size, baseline, _centre = FOOTER
        # Into the box the French back already draws, which does not move.
        _centred_line(canvas, [(ADDRESS, False)], size, baseline - size * LEADING,
                      ADDRESS_CENTRE)

    for page, draw in ((front, draw_front), (back, draw_back)):
        _without_text(page, writer)
        page.merge_page(_overlay(size, draw))

    writer.add_metadata({
        "/Title": f"Kalulu guide covers - {locale}",
        "/Author": "Excello Recherche & Education",
    })
    out = COVERS / f"{locale}.pdf"
    with out.open("wb") as handle:
        writer.write(handle)
    return out


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in COVERS_TEXT:
        raise SystemExit(f"usage: derive_cover.py {{{'|'.join(COVERS_TEXT)}}}")
    print(derive(sys.argv[1]).relative_to(ROOT))
