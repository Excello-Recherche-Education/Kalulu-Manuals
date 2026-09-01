"""Lay the manual out as a PDF.

Deliberately plain: a numbered step, its paragraph, the screenshot underneath.
The old hand-made manuals were a Google Doc of alternating text and pasted
images, and that shape was right -- what was wrong was that a human had to keep
it consistent across languages and re-paste every screenshot when a screen
changed.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from PIL import Image
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    Image as RLImage,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
)

from . import theme
from .model import Manual, Step
from .shots import ShotLibrary


def _styles() -> dict[str, ParagraphStyle]:
    body = ParagraphStyle(
        "body",
        fontName=theme.BODY,
        fontSize=10.5,
        leading=15.5,
        textColor=theme.GREY_DARK,
        alignment=TA_LEFT,
        spaceAfter=0,
    )
    return {
        "body": body,
        "section": ParagraphStyle(
            "section", parent=body, fontName=theme.DISPLAY, fontSize=19, leading=24,
            textColor=theme.NAVY, spaceBefore=0, spaceAfter=3 * mm,
        ),
        "intro": ParagraphStyle(
            "intro", parent=body, fontSize=11, leading=17, textColor=theme.GREY,
            spaceAfter=5 * mm,
        ),
        "steptitle": ParagraphStyle(
            "steptitle", parent=body, fontName=theme.BODY_BOLD, fontSize=12,
            leading=16, textColor=theme.PURPLE, spaceAfter=1.5 * mm,
        ),
        "note": ParagraphStyle(
            "note", parent=body, fontSize=9.5, leading=14, textColor=theme.NAVY,
            leftIndent=4 * mm, rightIndent=4 * mm, spaceBefore=2 * mm, spaceAfter=2 * mm,
        ),
        "cover_title": ParagraphStyle(
            "cover_title", parent=body, fontName=theme.DISPLAY, fontSize=34, leading=40,
            textColor=theme.WHITE,
        ),
        "cover_sub": ParagraphStyle(
            "cover_sub", parent=body, fontSize=14, leading=20, textColor=theme.LAVENDER,
        ),
        "cover_meta": ParagraphStyle(
            "cover_meta", parent=body, fontSize=9.5, leading=14, textColor=theme.LAVENDER,
        ),
        "toc": ParagraphStyle(
            "toc", parent=body, fontName=theme.BODY_BOLD, fontSize=11, leading=20,
            textColor=theme.PURPLE,
        ),
        "toc_step": ParagraphStyle(
            "toc_step", parent=body, fontSize=10, leading=16, textColor=theme.GREY_DARK,
            leftIndent=8 * mm,
        ),
    }


class Rule(Flowable):
    """A hairline the width of the frame."""

    def __init__(self, colour=theme.GREY_LIGHTER, thickness: float = 0.6, space: float = 3 * mm):
        super().__init__()
        self.colour, self.thickness, self.space = colour, thickness, space
        self.width = 0
        self.height = space

    def wrap(self, available_width, _available_height):
        self.width = available_width
        return available_width, self.space

    def draw(self):
        self.canv.setStrokeColor(self.colour)
        self.canv.setLineWidth(self.thickness)
        self.canv.line(0, self.space / 2, self.width, self.space / 2)


class NoteBox(Flowable):
    """A lavender panel behind a paragraph, for the 'optional' asides."""

    def __init__(self, paragraph: Paragraph, padding: float = 3 * mm):
        super().__init__()
        self.paragraph, self.padding = paragraph, padding
        self.width = self.height = 0

    def wrap(self, available_width, _available_height):
        self.width = available_width
        _, inner = self.paragraph.wrap(available_width - 2 * self.padding, 0)
        self.height = inner + 2 * self.padding
        return self.width, self.height

    def draw(self):
        self.canv.setFillColor(theme.LAVENDER)
        self.canv.setStrokeColor(theme.PURPLE)
        self.canv.setLineWidth(0.7)
        self.canv.roundRect(0, 0, self.width, self.height, 2 * mm, stroke=1, fill=1)
        self.paragraph.drawOn(self.canv, self.padding, self.padding)


class Heading(Paragraph):
    """A heading that also becomes a place the reader can jump to.

    Carries the anchor name so `ManualDoc.afterFlowable` can, once the heading
    has actually been laid out and its page is therefore known, register the
    destination, add a sidebar bookmark, and -- for sections -- feed the
    printed table of contents.
    """

    def __init__(self, text: str, style: ParagraphStyle, anchor: str, level: int = 0,
                 in_contents: bool = True):
        super().__init__(text, style)
        self.anchor = anchor
        self.level = level
        self.in_contents = in_contents
        self.plain = text


class ManualDoc(BaseDocTemplate):
    """Two page templates: a full-bleed navy cover, then the body."""

    def __init__(self, path: Path, manual: Manual):
        super().__init__(
            str(path),
            pagesize=theme.PAGE_SIZE,
            leftMargin=theme.MARGIN_LEFT,
            rightMargin=theme.MARGIN_RIGHT,
            topMargin=theme.MARGIN_TOP,
            bottomMargin=theme.MARGIN_BOTTOM,
            title=f"{manual.title} - {manual.subtitle}".strip(" -"),
            author="Excello Recherche & Education",
            subject=f"{manual.audience} / {manual.locale}",
        )
        self.manual = manual
        width = theme.PAGE_SIZE[0] - theme.MARGIN_LEFT - theme.MARGIN_RIGHT
        height = theme.PAGE_SIZE[1] - theme.MARGIN_TOP - theme.MARGIN_BOTTOM
        body_frame = Frame(theme.MARGIN_LEFT, theme.MARGIN_BOTTOM, width, height, id="body")
        cover_frame = Frame(
            theme.MARGIN_LEFT, theme.MARGIN_BOTTOM + 40 * mm, width, height - 40 * mm, id="cover"
        )
        self.addPageTemplates([
            PageTemplate(id="cover", frames=[cover_frame], onPage=self._cover_background),
            PageTemplate(id="body", frames=[body_frame], onPage=self._footer),
        ])

    def afterFlowable(self, flowable) -> None:
        """Record where each heading landed, now that it has a page number."""
        if not isinstance(flowable, Heading):
            return
        self.canv.bookmarkPage(flowable.anchor)
        # The key must be a str. Handed bytes, ReportLab quietly uses the key
        # itself as the visible title, so the sidebar fills with "sec-..."
        # slugs and nothing errors.
        self.canv.addOutlineEntry(
            flowable.plain, flowable.anchor, level=flowable.level, closed=False
        )
        if flowable.in_contents:
            # The fourth element is the anchor: TableOfContents turns the whole
            # entry into a link to it, which is the clickable bit.
            self.notify("TOCEntry", (flowable.level, flowable.plain, self.page, flowable.anchor))

    def _cover_background(self, canvas, _doc) -> None:
        canvas.saveState()
        canvas.setFillColor(theme.NAVY)
        canvas.rect(0, 0, *theme.PAGE_SIZE, stroke=0, fill=1)
        canvas.setFillColor(theme.PURPLE)
        canvas.rect(0, 0, theme.PAGE_SIZE[0], 26 * mm, stroke=0, fill=1)
        canvas.restoreState()

    def _footer(self, canvas, doc) -> None:
        # Ask the reader to open with the bookmark pane showing; the manual is
        # something people dip into rather than read front to back.
        canvas.showOutline()
        canvas.saveState()
        canvas.setFont(theme.BODY, 8)
        canvas.setFillColor(theme.GREY)
        y = theme.MARGIN_BOTTOM - 7 * mm
        canvas.drawString(theme.MARGIN_LEFT, y, self.manual.title)
        canvas.drawRightString(theme.PAGE_SIZE[0] - theme.MARGIN_RIGHT, y, str(doc.page))
        canvas.setStrokeColor(theme.GREY_LIGHTER)
        canvas.setLineWidth(0.5)
        canvas.line(
            theme.MARGIN_LEFT, y + 3.5 * mm,
            theme.PAGE_SIZE[0] - theme.MARGIN_RIGHT, y + 3.5 * mm,
        )
        canvas.restoreState()


def _screenshot(path: Path, max_width: float, max_height: float = 118 * mm) -> RLImage:
    with Image.open(path) as probe:
        w, h = probe.size
    scale = min(max_width / w, max_height / h)
    return RLImage(str(path), width=w * scale, height=h * scale)


def build_pdf(
    manual: Manual,
    out_path: Path,
    shots: ShotLibrary,
    *,
    labels: dict[str, str] | None = None,
) -> Path:
    """Render one manual. Appends any screenshot gaps to ``manual.warnings``."""
    theme.register_fonts()
    styles = _styles()
    labels = labels or {}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc = ManualDoc(out_path, manual)
    width = theme.CONTENT_WIDTH

    story: list = []

    # -- cover ----------------------------------------------------------------
    story.append(Paragraph(manual.title, styles["cover_title"]))
    story.append(Spacer(1, 4 * mm))
    if manual.subtitle:
        story.append(Paragraph(manual.subtitle, styles["cover_sub"]))
    story.append(Spacer(1, 10 * mm))
    meta = [
        f"{labels.get('language', 'Language')}: {manual.locale}",
        f"{labels.get('app_version', 'Kalulu')}: {manual.app_version}" if manual.app_version else "",
        f"{labels.get('generated', 'Generated')}: {date.today().isoformat()}",
    ]
    story.append(Paragraph("<br/>".join(m for m in meta if m), styles["cover_meta"]))
    if not manual.reviewed:
        story.append(Spacer(1, 8 * mm))
        story.append(
            Paragraph(
                labels.get(
                    "unreviewed",
                    "DRAFT - this translation has not been reviewed by a native speaker.",
                ),
                ParagraphStyle("warn", parent=styles["cover_meta"], textColor=theme.WARNING,
                               fontName=theme.BODY_BOLD),
            )
        )

    # -- contents -------------------------------------------------------------
    story.append(NextPageTemplate("body"))
    story.append(PageBreak())
    story.append(Paragraph(labels.get("contents", "Contents"), styles["section"]))
    contents = TableOfContents()
    contents.levelStyles = [styles["toc"], styles["toc_step"]]
    # Dot leaders from the top level down, so every line runs to its page number.
    contents.dotsMinLevel = 0
    story.append(contents)
    story.append(PageBreak())

    # -- sections -------------------------------------------------------------
    for index, section in enumerate(manual.sections, start=1):
        story.append(
            Heading(f"{index}. {section.title}", styles["section"], f"sec-{section.id}")
        )
        if section.intro:
            story.append(Paragraph(section.intro, styles["intro"]))
        for number, step in enumerate(section.steps, start=1):
            story.extend(_step_flowables(step, number, manual, shots, styles, width, section.id))
        if index != len(manual.sections):
            story.append(PageBreak())

    # Two passes: the first discovers which page each heading fell on, the
    # second lays the contents out knowing them. Page numbers can shift between
    # passes -- a longer contents page pushes everything down -- so ReportLab
    # repeats until they stop moving.
    doc.multiBuild(story)
    return out_path


def _step_flowables(
    step: Step,
    number: int,
    manual: Manual,
    shots: ShotLibrary,
    styles: dict[str, ParagraphStyle],
    width: float,
    section_id: str = "",
) -> list:
    """One step, kept on a single page wherever it fits."""
    block: list = []
    if step.title:
        # In the reader's bookmark pane but not in the printed contents: 33
        # steps would bury the nine sections a reader is actually navigating by.
        block.append(
            Heading(f"{number}. {step.title}", styles["steptitle"],
                    f"step-{section_id}-{step.id}", level=1, in_contents=False)
        )
        block.append(Paragraph(step.body, styles["body"]))
    else:
        block.append(Paragraph(f"<b>{number}.</b>&nbsp; {step.body}", styles["body"]))

    if step.shot:
        resolved = shots.resolve(step.shot, manual.locale, step.annotations)
        if resolved.is_placeholder:
            manual.warnings.append(
                f"no screenshot for {step.shot!r} in {manual.locale} - placeholder used"
            )
        elif resolved.used_locale != manual.locale:
            manual.warnings.append(
                f"{step.shot!r}: no {manual.locale} capture, used {resolved.used_locale}"
            )
        cached = shots.render_to_cache(resolved, manual.locale, fingerprint=repr(step.annotations))
        block.append(Spacer(1, 3 * mm))
        block.append(_screenshot(cached, width))

    if step.note:
        block.append(NoteBox(Paragraph(step.note, styles["note"])))

    block.append(Rule(space=6 * mm))
    # KeepTogether stops a caption stranding itself at the foot of a page away
    # from the screenshot it describes.
    return [KeepTogether(block)]
