"""One-off: convert the app's CFF-flavoured Mulish OTFs to TrueType.

ReportLab can only embed TrueType outlines, and Kalulu-Frontend ships Mulish as
`OTTO` (CFF). Run this once when the frontend's fonts change; the resulting TTFs
are committed, so building the manuals needs neither fontTools nor cu2qu.

    python tools/otf_to_ttf.py <frontend-assets-fonts-dir> assets/fonts
"""
import sys
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.pens.ttGlyphPen import TTGlyphPen
from cu2qu.pens import Cu2QuPen

MAX_ERR = 1.0


def convert(src: Path, dst: Path) -> None:
    font = TTFont(str(src))
    glyph_set = font.getGlyphSet()
    glyf_glyphs = {}
    for name in font.getGlyphOrder():
        pen = TTGlyphPen(glyph_set)
        glyph_set[name].draw(Cu2QuPen(pen, MAX_ERR, reverse_direction=True))
        glyf_glyphs[name] = pen.glyph()

    from fontTools.ttLib.tables._g_l_y_f import table__g_l_y_f
    glyf = table__g_l_y_f()
    glyf.glyphOrder = font.getGlyphOrder()
    glyf.glyphs = glyf_glyphs
    font["glyf"] = glyf

    from fontTools.ttLib.tables._l_o_c_a import table__l_o_c_a
    font["loca"] = table__l_o_c_a()

    font["maxp"].tableVersion = 0x00010000
    font["maxp"].maxZones = 1
    font["maxp"].maxTwilightPoints = 0
    font["maxp"].maxStorage = 0
    font["maxp"].maxFunctionDefs = 0
    font["maxp"].maxInstructionDefs = 0
    font["maxp"].maxStackElements = 0
    font["maxp"].maxSizeOfInstructions = 0
    font["maxp"].maxComponentElements = max(
        (len(g.components) for g in glyf_glyphs.values() if g.isComposite()), default=0
    )
    font["head"].glyphDataFormat = 0
    font["head"].indexToLocFormat = 0

    for drop in ("CFF ", "VORG"):
        if drop in font:
            del font[drop]

    font.sfntVersion = "\000\001\000\000"
    font.save(str(dst))
    print(f"  {src.name} -> {dst.name}")


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    src_dir, dst_dir = Path(sys.argv[1]), Path(sys.argv[2])
    dst_dir.mkdir(parents=True, exist_ok=True)
    found = sorted(src_dir.glob("*.otf"))
    if not found:
        print(f"no .otf in {src_dir}", file=sys.stderr)
        return 1
    for otf in found:
        convert(otf, dst_dir / (otf.stem + ".ttf"))
    license_file = src_dir / "OFL.txt"
    if license_file.exists():
        (dst_dir / "OFL.txt").write_bytes(license_file.read_bytes())
        print("  OFL.txt copied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
