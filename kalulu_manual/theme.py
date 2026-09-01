"""Page geometry, palette and fonts.

The palette is transcribed from the app's own design tokens
(`Kalulu-Frontend/sources/ui/design.gd`) so the manual and the product it
documents look like the same thing. The typeface is the app's Mulish, converted
to TrueType because ReportLab cannot embed CFF outlines — see
`tools/otf_to_ttf.py`.
"""
from __future__ import annotations

from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# --- Brand, from Design.PURPLE / Design.NAVY --------------------------------
PURPLE = HexColor("#812a80")
NAVY = HexColor("#2a367d")
GREY_DARK = HexColor("#474747")
GREY = HexColor("#707070")
GREY_LIGHT = HexColor("#cccccc")
GREY_LIGHTER = HexColor("#e0e0e0")
LAVENDER = HexColor("#f2ebf5")
ERROR = HexColor("#ff3334")
WARNING = HexColor("#ffaf17")
WHITE = HexColor("#ffffff")

#: What annotations drawn onto screenshots are stroked in. The old hand-made
#: manuals used a red pen; this keeps that read while staying on-palette.
ANNOTATION = HexColor("#d32f2f")

PAGE_SIZE = A4
MARGIN_LEFT = 22 * mm
MARGIN_RIGHT = 22 * mm
MARGIN_TOP = 20 * mm
MARGIN_BOTTOM = 18 * mm
CONTENT_WIDTH = PAGE_SIZE[0] - MARGIN_LEFT - MARGIN_RIGHT

_FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"

#: Registered font names, or the Helvetica fallbacks when the TTFs are absent.
BODY = "Helvetica"
BODY_BOLD = "Helvetica-Bold"
DISPLAY = "Helvetica-Bold"

_registered = False


def register_fonts() -> bool:
    """Register Mulish if it is vendored. Returns True when it was used.

    Falls back to Helvetica rather than failing: a manual that builds in plain
    Helvetica is far more useful than one that does not build at all, and every
    language the app ships is covered by Latin-1 either way.
    """
    global BODY, BODY_BOLD, DISPLAY, _registered
    if _registered:
        return BODY != "Helvetica"

    faces = {
        "Mulish": _FONT_DIR / "kalulu_mulish_regular.ttf",
        "Mulish-Bold": _FONT_DIR / "kalulu_mulish_bold.ttf",
        "Mulish-Black": _FONT_DIR / "kalulu_mulish_black.ttf",
    }
    _registered = True
    if not all(p.exists() for p in faces.values()):
        return False
    try:
        for name, path in faces.items():
            pdfmetrics.registerFont(TTFont(name, str(path)))
    except Exception:  # noqa: BLE001 - a broken font must not break the build
        return False

    pdfmetrics.registerFontFamily(
        "Mulish", normal="Mulish", bold="Mulish-Bold", italic="Mulish", boldItalic="Mulish-Bold"
    )
    BODY, BODY_BOLD, DISPLAY = "Mulish", "Mulish-Bold", "Mulish-Black"
    return True
