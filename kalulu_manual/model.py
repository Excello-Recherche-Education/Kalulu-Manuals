"""The shape of a manual, once structure and translations have been merged."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Annotation:
    """A mark drawn onto a screenshot.

    Coordinates are fractions of the screenshot (0..1), never pixels, so a
    re-capture at a different resolution keeps every annotation in place.
    """

    kind: str  # ellipse | rect | arrow | number
    box: tuple[float, float, float, float] | None = None  # x, y, w, h
    #: Unique node name (``%TeacherButton``) to anchor to, instead of a box.
    #: Preferred: the capture reports where the node actually landed, so the
    #: mark follows the button when the layout or the language changes.
    node: str | None = None
    pad: float = 0.012  # breathing room around an anchored node, in page units
    start: tuple[float, float] | None = None  # arrow tail
    end: tuple[float, float] | None = None  # arrow head
    label: str | None = None  # for kind == number

    def __post_init__(self) -> None:
        anchored = self.box is not None or self.node is not None
        if self.kind in {"ellipse", "rect", "number"} and not anchored:
            raise ValueError(f"annotation {self.kind!r} needs a box or a node")
        if self.kind == "arrow" and not (anchored or (self.start and self.end)):
            raise ValueError("annotation 'arrow' needs a node, or start and end")


@dataclass(frozen=True)
class Step:
    """One instruction: a paragraph, usually with a screenshot under it."""

    id: str
    body: str
    title: str | None = None
    shot: str | None = None
    note: str | None = None
    annotations: tuple[Annotation, ...] = ()
    #: The audiences this step is *only* for. Empty means every reader, which
    #: is the overwhelming majority: one manual serves teachers and parents
    #: alike, and the handful of steps that do not are marked on the page
    #: rather than split into a second document. A step naming every known
    #: audience is normalised to empty when the manual is assembled.
    audiences: tuple[str, ...] = ()

    @property
    def is_shared(self) -> bool:
        return not self.audiences


@dataclass(frozen=True)
class Section:
    id: str
    title: str
    intro: str | None
    steps: tuple[Step, ...]
    #: As on a Step, and just as rare — no section is audience-specific today.
    audiences: tuple[str, ...] = ()

    @property
    def is_shared(self) -> bool:
        return not self.audiences


@dataclass(frozen=True)
class Manual:
    """A single built document: one locale, every audience.

    There used to be one per audience, which meant a teacher and a parent had
    to know which of two files was theirs before they had read a word of
    either. They now get the same document; the few steps that apply to one
    and not the other are labelled where they stand.
    """

    locale: str
    title: str
    subtitle: str
    app_version: str
    reviewed: bool
    sections: tuple[Section, ...]
    #: Every audience the document covers, in the order they should be listed.
    #: From `audiences:` in manual.yaml, and it drives both the chips on
    #: audience-specific steps and the callout at each point the flow forks.
    audiences: tuple[str, ...] = ()
    #: Non-fatal problems found while assembling — missing screenshots,
    #: untranslated UI keys. Surfaced in the build report and, when the
    #: translation is unreviewed, on the cover.
    warnings: list[str] = field(default_factory=list)

    #: The file this manual is written to, without the extension. Set from the
    #: locale's own `filenames:` block, because these are handed to the public:
    #: a Spanish reader should not be downloading "manual_es". Falls back to
    #: the internal scheme when a language has not named itself yet.
    filename: str = ""

    @property
    def stem(self) -> str:
        return self.filename or f"Kalulu-Manual_{self.locale}"
