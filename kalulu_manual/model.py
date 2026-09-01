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
    audiences: tuple[str, ...] = ()  # empty means every audience

    def applies_to(self, audience: str) -> bool:
        return not self.audiences or audience in self.audiences


@dataclass(frozen=True)
class Section:
    id: str
    title: str
    intro: str | None
    steps: tuple[Step, ...]
    audiences: tuple[str, ...] = ()

    def applies_to(self, audience: str) -> bool:
        return not self.audiences or audience in self.audiences

    def for_audience(self, audience: str) -> "Section":
        return Section(
            id=self.id,
            title=self.title,
            intro=self.intro,
            steps=tuple(s for s in self.steps if s.applies_to(audience)),
            audiences=self.audiences,
        )


@dataclass(frozen=True)
class Manual:
    """A single built document: one locale, one audience."""

    locale: str
    audience: str
    title: str
    subtitle: str
    app_version: str
    reviewed: bool
    sections: tuple[Section, ...]
    #: Non-fatal problems found while assembling — missing screenshots,
    #: untranslated UI keys. Surfaced in the build report and, when the
    #: translation is unreviewed, on the cover.
    warnings: list[str] = field(default_factory=list)

    @property
    def stem(self) -> str:
        return f"Kalulu-Manual_{self.audience}_{self.locale}"
