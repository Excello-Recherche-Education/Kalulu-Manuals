"""Build "Kalulu Installation Help.pdf" - one guide covering both desktop platforms.

There used to be two separate documents handed out on their own: a Word file for
Windows and a PDF for macOS. A person downloading a build does not know which
one they need until they have opened it, so this merges them into a single PDF
that opens on a contents page and sends the reader to their platform.

The text is transcribed from those two originals. Two deliberate departures,
both marked in the source below:

  * the macOS download step also names the .zip, because that is what the
    GitHub release actually ships - the original only described the .dmg;
  * the app bundle is written "Kalulu.app", which is its real name.

Unlike the per-language manuals, this one is not generated from the app and
does not change per release, so the built PDF is committed next to this script
rather than left in the gitignored build/ directory: the release pipeline
attaches it to every GitHub release and has to find it in a fresh clone.

    python tools/build_installation_help.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from reportlab.lib.enums import TA_LEFT  # noqa: E402
from reportlab.lib.styles import ParagraphStyle  # noqa: E402
from reportlab.lib.units import mm  # noqa: E402
from reportlab.platypus import (  # noqa: E402
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents  # noqa: E402

from kalulu_manual import theme  # noqa: E402

OUT = ROOT / "installation-help" / "Kalulu Installation Help.pdf"
TITLE = "Kalulu - Installation Help"

# Mulish carries no emoji and no arrows: U+26A0, U+2705, U+25B8, U+2192 and the
# non-breaking hyphen U+2011 are all absent, and ReportLab would draw nothing at
# all for them. The originals leaned on them, so their meaning is carried by
# layout and colour here instead - a callout box rather than a warning sign -
# and the one that has a real equivalent, the separator, becomes U+203A.
CHEVRON = "›"


# --- content -----------------------------------------------------------------
# ("heading", text) | ("para", text) | ("steps", [text, ...])
# ("bullets", [...]) | ("code", [line, ...]) | ("callout", (title, text))
# ("note", text)

WINDOWS = [
    ("steps", [
        "<b>Download and place the files.</b> Take the two files "
        "<font face='Courier'>Kalulu.exe</font> and "
        "<font face='Courier'>libgdsqlite.windows.template_release.x86_64.dll</font> "
        "and put them together in the same folder on your computer.",
        "<b>Run the program.</b> Double-click on "
        "<font face='Courier'>Kalulu.exe</font>.",
        "<b>If you get a security warning.</b> If a message appears saying the "
        "program is unrecognized or has been blocked, look for an option such as "
        "<b>&#8220;Run anyway&#8221;</b> or <b>&#8220;Allow execution&#8221;</b>, "
        "and click it to continue.",
    ]),
    ("callout", ("Done!", "The game should now launch and work correctly.")),
]

MACOS = [
    ("callout", ("Important", (
        "Run Kalulu only if you fully trust its source. Messages like "
        "&#8220;The application is damaged&#8221; or &#8220;Apple cannot check it "
        "for malicious software&#8221; often mean the app is unsigned or marked as "
        "quarantined (not necessarily corrupted)."
    ))),
    ("heading2", "Download and install"),
    # Departure from the original, which only described the .dmg: the GitHub
    # release ships a .zip, so a reader following the old text looks for a file
    # they never downloaded.
    ("steps", [
        "Locate the file you downloaded, usually in <b>Downloads</b>: "
        "<font face='Courier'>Kalulu-macOS-&lt;version&gt;.zip</font> from the "
        "releases page, or <font face='Courier'>Kalulu.dmg</font>.",
        "Open it. A zip unpacks to <font face='Courier'>Kalulu.app</font>; a .dmg "
        "opens a <i>Kalulu</i> volume in the Finder.",
        "Drag <font face='Courier'>Kalulu.app</font> into <b>Applications</b>.",
        "If you opened a .dmg, eject the <i>Kalulu</i> volume from the Finder "
        "(the eject icon).",
    ]),
    ("note", "Terminal equivalent of the copy:"),
    ("code", ['cp -R "/Volumes/Kalulu/Kalulu.app" "/Applications/Kalulu.app"']),

    ("heading2", f"Method 1 {CHEVRON} Right-click, Open (recommended)"),
    ("steps", [
        "Open <b>/Applications</b>.",
        f"Right-click (or Ctrl-click) <font face='Courier'>Kalulu.app</font> "
        f"{CHEVRON} <b>Open</b>.",
        "In the &#8220;<i>from an unidentified developer</i>&#8221; dialog, click "
        "<b>Open</b>.",
    ]),
    ("note", "macOS creates a Gatekeeper exception: from the second launch, a "
             "normal double-click will work."),

    ("heading2", f"Method 2 {CHEVRON} System Settings, Privacy &amp; Security"),
    ("steps", [
        "First try a double-click on <font face='Courier'>Kalulu.app</font> - let "
        "it be blocked, then close the alert.",
        f"Go to the Apple menu {CHEVRON} <b>System Settings</b> {CHEVRON} "
        f"<b>Privacy &amp; Security</b> (older versions: <b>System Preferences</b> "
        f"{CHEVRON} <b>Security &amp; Privacy</b>).",
        "Scroll to find &#8220;<i>Kalulu.app was blocked&#8230;</i>&#8221;.",
        "Click <b>Open Anyway</b>, then confirm <b>Open</b>.",
    ]),

    ("heading2", f"Method 3 {CHEVRON} Terminal, for the &#8220;is damaged&#8221; message"),
    ("para", "That message is often caused by the quarantine attribute. Remove it "
             "using Terminal (<b>Applications</b> " + CHEVRON + " <b>Utilities</b> "
             + CHEVRON + " <b>Terminal</b>):"),
    ("code", ['xattr -dr com.apple.quarantine "/Applications/Kalulu.app"']),
    ("note", "Then relaunch Kalulu.app, ideally combined with Method 1 "
             "(right-click, Open)."),

    ("heading2", "Advanced: temporarily disable Gatekeeper (not recommended)"),
    ("para", "Use only if everything above fails."),
    ("code", [
        "# Disable Gatekeeper",
        "sudo spctl --master-disable",
        "# Open the app once",
        'open "/Applications/Kalulu.app"',
        "# Re-enable Gatekeeper",
        "sudo spctl --master-enable",
    ]),

    ("heading2", "Quick troubleshooting"),
    ("bullets", [
        "Nothing happens on double-click: use Method 1 (right-click, Open).",
        "Still shows &#8220;damaged&#8221;: run the <font face='Courier'>xattr</font> "
        "command above, then try Method 1 again.",
        "App still inside the .dmg: make sure you actually copied "
        "<font face='Courier'>Kalulu.app</font> to <b>/Applications</b>, then "
        "ejected the .dmg.",
        "Paths with spaces: keep the quotes in commands, e.g. "
        "<font face='Courier'>&quot;/Applications/Kalulu app.app&quot;</font>.",
        "No <b>Open Anyway</b> button: attempt one launch just before, then return "
        "to Privacy &amp; Security.",
        "After the first successful launch, future launches work by double-click.",
    ]),

    ("heading2", "When in doubt"),
    ("para", "If you don&#8217;t recognize the app or its origin, don&#8217;t open "
             "it and contact the publisher for a signed / notarized build."),
]

SECTIONS = [
    ("Windows", "Windows 10 and Windows 11", WINDOWS),
    ("macOS", "macOS 10.13 and later", MACOS),
]


# --- styles ------------------------------------------------------------------

def styles() -> dict[str, ParagraphStyle]:
    theme.register_fonts()
    body = ParagraphStyle(
        "body", fontName=theme.BODY, fontSize=10.5, leading=15,
        textColor=theme.GREY_DARK, alignment=TA_LEFT, spaceAfter=5,
    )
    return {
        "title": ParagraphStyle(
            "title", parent=body, fontName=theme.DISPLAY, fontSize=26, leading=31,
            textColor=theme.PURPLE, spaceAfter=4,
        ),
        "subtitle": ParagraphStyle(
            "subtitle", parent=body, fontSize=11.5, leading=16,
            textColor=theme.GREY, spaceAfter=14,
        ),
        "h1": ParagraphStyle(
            "h1", parent=body, fontName=theme.DISPLAY, fontSize=19, leading=24,
            textColor=theme.PURPLE, spaceBefore=0, spaceAfter=2,
        ),
        "h1sub": ParagraphStyle(
            "h1sub", parent=body, fontSize=10, leading=14, textColor=theme.GREY,
            spaceAfter=12,
        ),
        "h2": ParagraphStyle(
            "h2", parent=body, fontName=theme.BODY_BOLD, fontSize=12.5, leading=17,
            textColor=theme.NAVY, spaceBefore=13, spaceAfter=5, keepWithNext=1,
        ),
        "body": body,
        "note": ParagraphStyle(
            "note", parent=body, fontSize=9.8, leading=14, textColor=theme.GREY,
            leftIndent=4,
        ),
        "step": ParagraphStyle("step", parent=body, leading=15),
        "num": ParagraphStyle(
            "num", parent=body, fontName=theme.BODY_BOLD, textColor=theme.PURPLE,
            alignment=2,
        ),
        "code": ParagraphStyle(
            "code", fontName="Courier", fontSize=8.8, leading=12.5,
            textColor=theme.NAVY,
        ),
        "callout_t": ParagraphStyle(
            "callout_t", fontName=theme.BODY_BOLD, fontSize=10.5, leading=15,
            textColor=theme.PURPLE, spaceAfter=2,
        ),
        "callout_b": ParagraphStyle(
            "callout_b", fontName=theme.BODY, fontSize=10, leading=14.5,
            textColor=theme.GREY_DARK,
        ),
        "toc": ParagraphStyle(
            "toc", fontName=theme.BODY_BOLD, fontSize=13, leading=24,
            textColor=theme.NAVY,
        ),
    }


def _boxed(rows, bg, bar) -> Table:
    """A left-barred, tinted block - used for callouts and code."""
    t = Table([[""] + [rows]], colWidths=[3 * mm, theme.CONTENT_WIDTH - 3 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), bar),
        ("BACKGROUND", (1, 0), (1, -1), bg),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (0, -1), 0),
        ("RIGHTPADDING", (0, 0), (0, -1), 0),
        ("LEFTPADDING", (1, 0), (1, -1), 8),
        ("RIGHTPADDING", (1, 0), (1, -1), 8),
        ("TOPPADDING", (1, 0), (1, -1), 7),
        ("BOTTOMPADDING", (1, 0), (1, -1), 7),
    ]))
    return t


def blocks_to_flowables(blocks, st) -> list:
    out = []
    for kind, payload in blocks:
        if kind == "heading2":
            out.append(Paragraph(payload, st["h2"]))
        elif kind == "para":
            out.append(Paragraph(payload, st["body"]))
        elif kind == "note":
            out.append(Spacer(1, 1))
            out.append(Paragraph(payload, st["note"]))
        elif kind == "steps":
            rows = [[Paragraph(f"{i}.", st["num"]), Paragraph(text, st["step"])]
                    for i, text in enumerate(payload, 1)]
            t = Table(rows, colWidths=[8 * mm, theme.CONTENT_WIDTH - 8 * mm])
            t.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (0, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            out.append(t)
        elif kind == "bullets":
            for text in payload:
                rows = [[Paragraph("&bull;", st["num"]), Paragraph(text, st["step"])]]
                t = Table(rows, colWidths=[6 * mm, theme.CONTENT_WIDTH - 6 * mm])
                t.setStyle(TableStyle([
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 1),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]))
                out.append(t)
        elif kind == "code":
            lines = [Paragraph(l.replace("&", "&amp;").replace("<", "&lt;"), st["code"])
                     for l in payload]
            out.append(Spacer(1, 3))
            out.append(_boxed(lines, theme.LAVENDER, theme.NAVY))
            out.append(Spacer(1, 5))
        elif kind == "callout":
            title, text = payload
            inner = [Paragraph(title, st["callout_t"]), Paragraph(text, st["callout_b"])]
            out.append(Spacer(1, 4))
            out.append(_boxed(inner, theme.LAVENDER, theme.PURPLE))
            out.append(Spacer(1, 6))
    return out


class HelpDoc(BaseDocTemplate):
    """Two-pass build so the contents page carries real page numbers."""

    def __init__(self, path, st):
        super().__init__(
            str(path), pagesize=theme.PAGE_SIZE,
            leftMargin=theme.MARGIN_LEFT, rightMargin=theme.MARGIN_RIGHT,
            topMargin=theme.MARGIN_TOP, bottomMargin=theme.MARGIN_BOTTOM,
            title=TITLE, author="Excello Recherche & Education",
            subject="Installing and launching Kalulu on Windows and macOS",
        )
        self.st = st
        frame = Frame(self.leftMargin, self.bottomMargin,
                      self.width, self.height, id="body")
        self.addPageTemplates([PageTemplate(id="page", frames=[frame],
                                            onPage=self._decorate)])

    def _decorate(self, canv, doc):
        canv.saveState()
        canv.setFont(theme.BODY, 8)
        canv.setFillColor(theme.GREY)
        canv.drawString(theme.MARGIN_LEFT, 11 * mm, TITLE)
        canv.drawRightString(theme.PAGE_SIZE[0] - theme.MARGIN_RIGHT, 11 * mm,
                             str(canv.getPageNumber()))
        canv.setStrokeColor(theme.GREY_LIGHTER)
        canv.setLineWidth(0.5)
        canv.line(theme.MARGIN_LEFT, 14 * mm,
                  theme.PAGE_SIZE[0] - theme.MARGIN_RIGHT, 14 * mm)
        canv.restoreState()

    def afterFlowable(self, flowable):
        if getattr(flowable, "_toc_key", None):
            text = flowable.getPlainText()
            key = flowable._toc_key
            self.canv.bookmarkPage(key)
            self.notify("TOCEntry", (0, text, self.page, key))
            self.canv.addOutlineEntry(text, key, level=0, closed=False)


def build() -> Path:
    st = styles()
    story: list = [
        Paragraph(TITLE, st["title"]),
        Paragraph(
            "Installing and launching Kalulu on a desktop computer. "
            "Read only the section for the machine you are using.",
            st["subtitle"],
        ),
    ]

    toc = TableOfContents()
    toc.levelStyles = [st["toc"]]
    story += [Paragraph("Contents", st["h2"]), toc]

    for i, (name, sub, blocks) in enumerate(SECTIONS):
        if i:
            story.append(PageBreak())
        else:
            story.append(Spacer(1, 10))
        head = Paragraph(name, st["h1"])
        head._toc_key = f"sec-{name.lower()}"
        story.append(KeepTogether([head, Paragraph(sub, st["h1sub"])]))
        story += blocks_to_flowables(blocks, st)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    HelpDoc(OUT, st).multiBuild(story)
    return OUT


if __name__ == "__main__":
    p = build()
    print(f"wrote {p}  ({p.stat().st_size / 1024:.0f} KB)")
