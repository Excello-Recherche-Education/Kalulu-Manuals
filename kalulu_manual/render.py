"""Lay the manual out as a PDF.

Deliberately plain: a numbered step, its paragraph, the screenshot underneath.
The old hand-made manuals were a Google Doc of alternating text and pasted
images, and that shape was right -- what was wrong was that a human had to keep
it consistent across languages and re-paste every screenshot when a screen
changed.

One document serves every audience. Teachers and parents used to get a manual
each, which asked a reader to decide which of two files was theirs before
reading a word of either -- and the two were about thirty-odd identical steps
apart from four. So the restricted steps stay in place and are marked instead,
two ways:

* a chip above the step title, "Teacher only" / "Parent only", tinted per
  audience so a reader skims by colour;
* a callout at each point the flow actually forks, naming which numbered steps
  each audience follows and where everyone rejoins. It is computed from the
  structure, so re-ordering a flow cannot leave it pointing at the wrong step
  numbers -- the same reason annotations anchor to nodes and not to pixels.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from PIL import Image
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
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
from .model import Manual, Section, Step
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
        "fork": ParagraphStyle(
            "fork", parent=body, fontSize=10, leading=15, textColor=theme.NAVY,
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
    """A tinted panel behind a paragraph, for the asides and the forks."""

    def __init__(self, paragraph: Paragraph, padding: float = 3 * mm,
                 fill=theme.LAVENDER, stroke=theme.PURPLE):
        super().__init__()
        self.paragraph, self.padding = paragraph, padding
        self.fill, self.stroke = fill, stroke
        self.width = self.height = 0

    def wrap(self, available_width, _available_height):
        self.width = available_width
        _, inner = self.paragraph.wrap(available_width - 2 * self.padding, 0)
        self.height = inner + 2 * self.padding
        return self.width, self.height

    def draw(self):
        self.canv.setFillColor(self.fill)
        self.canv.setStrokeColor(self.stroke)
        self.canv.setLineWidth(0.7)
        self.canv.roundRect(0, 0, self.width, self.height, 2 * mm, stroke=1, fill=1)
        self.paragraph.drawOn(self.canv, self.padding, self.padding)


class Badge(Flowable):
    """A chip naming the audience a step is restricted to.

    Its own flowable rather than coloured text inside the heading, because
    this is the one mark a reader has to be able to spot without reading: a
    parent flicking through the account chapter needs to see at a glance that
    three steps are not theirs.
    """

    def __init__(self, text: str, fill, ink, size: float = 7.5,
                 pad_x: float = 2.4 * mm, pad_y: float = 1.1 * mm):
        super().__init__()
        self.text, self.fill, self.ink, self.size = text, fill, ink, size
        self.pad_x, self.pad_y = pad_x, pad_y
        self.width = pdfmetrics.stringWidth(text, theme.BODY_BOLD, size) + 2 * pad_x
        self.height = size + 2 * pad_y

    def wrap(self, _available_width, _available_height):
        return self.width, self.height

    def draw(self):
        canvas = self.canv
        canvas.setFillColor(self.fill)
        canvas.setStrokeColor(self.ink)
        canvas.setLineWidth(0.6)
        canvas.roundRect(0, 0, self.width, self.height, self.height / 2, stroke=1, fill=1)
        canvas.setFillColor(self.ink)
        canvas.setFont(theme.BODY_BOLD, self.size)
        # A fraction of the size rather than a measured ascent: the chip holds
        # one short line and looking centred is the whole requirement.
        canvas.drawString(self.pad_x, self.pad_y + 0.24 * self.size, self.text)


class Heading(Paragraph):
    """A heading that also becomes a place the reader can jump to.

    Carries the anchor name so `ManualDoc.afterFlowable` can, once the heading
    has actually been laid out and its page is therefore known, register the
    destination, add a sidebar bookmark, and -- for sections -- feed the
    printed table of contents.
    """

    def __init__(self, text: str, style: ParagraphStyle, anchor: str, level: int = 0,
                 in_contents: bool = True, outline: str | None = None):
        super().__init__(text, style)
        self.anchor = anchor
        self.level = level
        self.in_contents = in_contents
        #: What the reader's sidebar shows. Differs from the printed heading
        #: only for a restricted step, where the bookmark carries the audience
        #: too -- the chip is drawn, and a drawing does not reach the sidebar.
        self.plain = outline or text


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
            subject=f"{', '.join(manual.audiences)} / {manual.locale}".lstrip(" /"),
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


# -- audiences ---------------------------------------------------------------


def _hex(colour) -> str:
    """'#812a80' from a ReportLab colour, for inline <font color="...">."""
    return "#" + colour.hexval()[2:]


def _fill_audience(template: str, name: str, wrap=lambda word: word) -> str:
    """Substitute an audience name into a label.

    ``{^audience}`` capitalises it and ``{audience}`` does not, the same caret
    convention the prose glossary uses -- because the same name opens a fork
    line ("Docente: pasos 4 a 6") and sits inside a chip ("Solo docente"), and
    three of the four languages want different case in the two places. The
    names are therefore stored lowercase, as the common nouns they are.

    ``wrap`` decorates the word once its case is settled, for the colour markup
    the fork lines put around it.
    """
    capital = name[:1].upper() + name[1:]
    return (template.replace("{^audience}", wrap(capital))
                    .replace("{audience}", wrap(name)))


class Audiences:
    """The per-locale wording and tint of every audience in the manual."""

    def __init__(self, manual: Manual, labels: dict[str, str]):
        self.order = list(manual.audiences)
        self.labels = labels
        self.tint = {
            name: theme.AUDIENCE_TINTS[index % len(theme.AUDIENCE_TINTS)]
            for index, name in enumerate(self.order)
        }

    def name(self, audience: str) -> str:
        return str(self.labels.get(f"audience_{audience}") or audience)

    def only(self, audiences: tuple[str, ...]) -> str:
        """'Teacher only' — the chip's text."""
        template = str(self.labels.get("audience_only") or "{^audience} only")
        listed = ", ".join(self.name(a) for a in self.order if a in audiences)
        return _fill_audience(template, listed)

    def badge(self, audiences: tuple[str, ...]) -> Badge:
        first = next((a for a in self.order if a in audiences), audiences[0])
        fill, ink = self.tint.get(first, theme.AUDIENCE_TINTS[0])
        return Badge(self.only(audiences), fill, ink)

    def steps_phrase(self, numbers: list[int]) -> str:
        """'step 7', 'steps 4 to 6', or a plain list when they are not a run."""
        if len(numbers) == 1:
            return str(self.labels.get("step_one") or "step {n}").replace("{n}", str(numbers[0]))
        contiguous = numbers == list(range(numbers[0], numbers[-1] + 1))
        if contiguous:
            return (str(self.labels.get("step_range") or "steps {a} to {b}")
                    .replace("{a}", str(numbers[0])).replace("{b}", str(numbers[-1])))
        return (str(self.labels.get("step_list") or "steps {list}")
                .replace("{list}", ", ".join(str(n) for n in numbers)))

    def fork_markup(self, runs: dict[str, list[int]], rejoin: int | None) -> str:
        """The callout's paragraph: who follows which steps, and where next."""
        lines = [f"<b>{self.labels.get('fork_intro') or 'This depends on your account:'}</b>"]
        template = str(self.labels.get("fork_line") or "{^audience}: {steps}")
        for audience in self.order:
            numbers = runs.get(audience)
            if not numbers:
                continue
            _, ink = self.tint.get(audience, theme.AUDIENCE_TINTS[0])
            coloured = _fill_audience(
                template, self.name(audience),
                lambda word, ink=ink: f'<font color="{_hex(ink)}"><b>{word}</b></font>',
            )
            lines.append(coloured.replace("{steps}", self.steps_phrase(numbers)))
        if rejoin is not None:
            lines.append(
                str(self.labels.get("fork_rejoin") or "Everyone continues at {steps}.")
                .replace("{steps}", self.steps_phrase([rejoin]))
            )
        return "<br/>".join(lines)


def _fork_callouts(section: Section, audiences: Audiences) -> dict[int, str]:
    """Markup to insert before the step at each 1-based number that opens a fork.

    A fork is a run of consecutive restricted steps that more than one audience
    appears in -- the account chapter asks a teacher three questions and a
    parent one, then both carry on together. A run only one audience appears in
    is not a fork and gets no callout: its chip already says everything, and a
    box repeating it would be noise.
    """
    callouts: dict[int, str] = {}
    steps = section.steps
    index = 0
    while index < len(steps):
        if steps[index].is_shared:
            index += 1
            continue
        end = index
        while end < len(steps) and not steps[end].is_shared:
            end += 1
        runs: dict[str, list[int]] = {}
        for offset in range(index, end):
            for audience in steps[offset].audiences:
                runs.setdefault(audience, []).append(offset + 1)
        if len(runs) > 1:
            rejoin = end + 1 if end < len(steps) else None
            callouts[index + 1] = audiences.fork_markup(runs, rejoin)
        index = end
    return callouts


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
    audiences = Audiences(manual, labels)
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
        if not section.is_shared:
            story.append(audiences.badge(section.audiences))
            story.append(Spacer(1, 1.5 * mm))
        story.append(
            Heading(
                f"{index}. {section.title}", styles["section"], f"sec-{section.id}",
                outline=None if section.is_shared
                else f"{index}. {section.title} ({audiences.only(section.audiences)})",
            )
        )
        if section.intro:
            story.append(Paragraph(section.intro, styles["intro"]))
        callouts = _fork_callouts(section, audiences)
        for number, step in enumerate(section.steps, start=1):
            if number in callouts:
                story.append(
                    KeepTogether([
                        NoteBox(Paragraph(callouts[number], styles["fork"]),
                                fill=theme.CALLOUT, stroke=theme.NAVY),
                        Spacer(1, 4 * mm),
                    ])
                )
            story.extend(
                _step_flowables(step, number, manual, shots, styles, width, section.id, audiences)
            )
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
    audiences: Audiences | None = None,
) -> list:
    """One step, kept on a single page wherever it fits."""
    block: list = []
    restricted = bool(step.audiences) and audiences is not None
    if restricted:
        block.append(audiences.badge(step.audiences))
        block.append(Spacer(1, 1.2 * mm))
    if step.title:
        # In the reader's bookmark pane but not in the printed contents: 33
        # steps would bury the nine sections a reader is actually navigating by.
        block.append(
            Heading(
                f"{number}. {step.title}", styles["steptitle"],
                f"step-{section_id}-{step.id}", level=1, in_contents=False,
                outline=f"{number}. {step.title} ({audiences.only(step.audiences)})"
                if restricted else None,
            )
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
