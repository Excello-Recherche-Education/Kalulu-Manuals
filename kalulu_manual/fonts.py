"""Kalulu's Mulish, as TrueType, from the Kalulu-Fonts submodule.

No font is kept in this repository: `kalulu-fonts/` is the Kalulu-Fonts
repository, which every Kalulu repository that uses a font mounts. Its Mulish
is CFF-flavoured OpenType (`OTTO`), and ReportLab can only embed TrueType
outlines, so each weight is converted once into `build/fonts/` and reused.

The converted file is named after a hash of its source, so a font changed in
Kalulu-Fonts is converted again the next time it is asked for, and a stale
conversion can never be picked up.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "kalulu-fonts" / "mulish"
CACHE = ROOT / "build" / "fonts"

#: Cubic-to-quadratic tolerance, in font units.
MAX_ERR = 1.0


def mulish(weight: str) -> Path | None:
    """The TrueType file of a Mulish weight ("regular", "bold" or "black").

    None when `kalulu-fonts/` is not checked out (`git submodule update
    --init`), so callers can fall back rather than fail.
    """
    source = SOURCE / f"kalulu_mulish_{weight}.otf"
    if not source.is_file():
        return None
    digest = hashlib.sha256(source.read_bytes()).hexdigest()[:12]
    target = CACHE / f"kalulu_mulish_{weight}-{digest}.ttf"
    if not target.is_file():
        CACHE.mkdir(parents=True, exist_ok=True)
        partial = target.with_name(f"{target.name}.{os.getpid()}.partial")
        _to_truetype(source, partial)
        partial.replace(target)
    return target


def _to_truetype(source: Path, target: Path) -> None:
    """Rewrite a CFF OpenType font's outlines as TrueType quadratics."""
    from fontTools.pens.cu2quPen import Cu2QuPen
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    from fontTools.ttLib import TTFont
    from fontTools.ttLib.tables._g_l_y_f import table__g_l_y_f
    from fontTools.ttLib.tables._l_o_c_a import table__l_o_c_a

    # The source's timestamps are kept, so the same source always gives the
    # same bytes.
    font = TTFont(str(source), recalcTimestamp=False)
    glyph_set = font.getGlyphSet()
    glyphs = {}
    for name in font.getGlyphOrder():
        pen = TTGlyphPen(glyph_set)
        glyph_set[name].draw(Cu2QuPen(pen, MAX_ERR, reverse_direction=True))
        glyphs[name] = pen.glyph()

    glyf = table__g_l_y_f()
    glyf.glyphOrder = font.getGlyphOrder()
    glyf.glyphs = glyphs
    font["glyf"] = glyf
    font["loca"] = table__l_o_c_a()

    maxp = font["maxp"]
    maxp.tableVersion = 0x00010000
    maxp.maxZones = 1
    maxp.maxTwilightPoints = 0
    maxp.maxStorage = 0
    maxp.maxFunctionDefs = 0
    maxp.maxInstructionDefs = 0
    maxp.maxStackElements = 0
    maxp.maxSizeOfInstructions = 0
    maxp.maxComponentElements = max(
        (len(glyph.components) for glyph in glyphs.values() if glyph.isComposite()), default=0
    )
    font["head"].glyphDataFormat = 0
    font["head"].indexToLocFormat = 0
    for table in ("CFF ", "VORG"):
        if table in font:
            del font[table]
    font.sfntVersion = "\000\001\000\000"
    font.save(str(target))
