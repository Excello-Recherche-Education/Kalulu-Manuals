"""Screenshot resolution, annotation and placeholders.

A screenshot is looked up by key, per locale, because the app's interface is
translated: the French manual must not show a Spanish screen. The chain is

    assets/screenshots/<locale>/<key>.png
    assets/screenshots/_default/<key>.png
    a generated placeholder

Placeholders exist so the manual always builds. A missing capture then shows up
as a labelled hole in the PDF and a line in the build report, which is much
harder to overlook than a crash nobody ran.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .model import Annotation

#: Everything is drawn against this reference width, then scaled by the caller.
PLACEHOLDER_SIZE = (1600, 1000)
STROKE = (211, 46, 47)  # theme.ANNOTATION, in RGB for Pillow
NAVY = (42, 54, 125)
GREY = (112, 107, 111)
LAVENDER = (242, 235, 245)

_FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    name = "kalulu_mulish_bold.ttf" if bold else "kalulu_mulish_regular.ttf"
    path = _FONT_DIR / name
    if path.exists():
        try:
            return ImageFont.truetype(str(path), size)
        except OSError:
            pass
    return ImageFont.load_default(size)


@dataclass(frozen=True)
class Resolved:
    """A screenshot ready to be placed on the page."""

    key: str
    path: Path | None  # None when this is a generated placeholder
    image: Image.Image
    is_placeholder: bool
    used_locale: str | None  # which locale's capture was actually used


class ShotLibrary:
    """Finds, annotates and caches the screenshots for one build.

    Two roots are searched in order:

    1. `assets/screenshots/` -- committed overrides, for the rare screen the
       harness cannot reach (a device-specific dialog, say). Wins deliberately:
       a human who has put a file there has a reason.
    2. `build/screenshots/` -- what the capture harness rendered from the app.
       Gitignored: these are derived files, and re-deriving them is one command.
    """

    def __init__(self, roots: list[Path], cache_dir: Path) -> None:
        self.roots = roots
        #: Node names an annotation asked for that the capture never saw --
        #: usually a control renamed in the app. Reported by the build.
        self.unresolved: list[str] = []
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def source_for(self, key: str, locale: str) -> tuple[Path | None, str | None]:
        for root in self.roots:
            for candidate_locale in (locale, "_default"):
                for suffix in (".png", ".jpg", ".jpeg"):
                    path = root / candidate_locale / f"{key}{suffix}"
                    if path.exists():
                        return path, candidate_locale
        return None, None

    def missing(self, keys: list[str], locales: list[str]) -> dict[str, list[str]]:
        """``key -> locales with no capture at all``, for the build report."""
        report: dict[str, list[str]] = {}
        for key in keys:
            gaps = [loc for loc in locales if self.source_for(key, loc)[0] is None]
            if gaps:
                report[key] = gaps
        return report

    def resolve(
        self, key: str, locale: str, annotations: tuple[Annotation, ...]
    ) -> Resolved:
        path, used = self.source_for(key, locale)
        if path is None:
            image = self._placeholder(key, locale)
            placeholder = True
        else:
            image = Image.open(path).convert("RGB")
            placeholder = False
        if annotations:
            image = self._annotate(image, annotations, self._rects(path))
        return Resolved(
            key=key, path=path, image=image, is_placeholder=placeholder, used_locale=used
        )

    def render_to_cache(self, resolved: Resolved, locale: str, fingerprint: str = "") -> Path:
        """Write the annotated image out; ReportLab wants a file, not a buffer.

        The annotations are part of the cache key. One screen is often shown
        several times with different marks on it -- the settings screen appears
        three times in the teacher manual -- and leaving them out of the digest
        made all three share one file, so whichever was rendered first won and
        the other two silently carried the wrong arrows.
        """
        digest = hashlib.sha1(
            f"{resolved.key}|{locale}|{resolved.path}|{resolved.image.size}|{fingerprint}".encode()
        ).hexdigest()[:12]
        out = self.cache_dir / f"{resolved.key}.{locale}.{digest}.png"
        resolved.image.save(out, "PNG")
        return out

    # -- drawing --------------------------------------------------------------

    @staticmethod
    def _rects(path: Path | None) -> dict[str, list[float]]:
        """Where each named control landed, recorded during capture."""
        if path is None:
            return {}
        sidecar = path.with_suffix(".rects.json")
        if not sidecar.exists():
            return {}
        try:
            return json.loads(sidecar.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def _box_for(
        self, ann: Annotation, rects: dict[str, list[float]]
    ) -> tuple[float, float, float, float] | None:
        if ann.node:
            found = rects.get(ann.node)
            if found is None:
                self.unresolved.append(ann.node)
                return ann.box
            x, y, w, h = found
            pad = ann.pad
            return (x - pad, y - pad, w + 2 * pad, h + 2 * pad)
        return ann.box

    def _annotate(
        self,
        image: Image.Image,
        annotations: tuple[Annotation, ...],
        rects: dict[str, list[float]] | None = None,
    ) -> Image.Image:
        image = image.copy()
        draw = ImageDraw.Draw(image)
        w, h = image.size
        # Scale the pen with the capture so a 4K screenshot is not hairlined.
        width = max(3, round(min(w, h) * 0.006))

        def px(point: tuple[float, float]) -> tuple[float, float]:
            return point[0] * w, point[1] * h

        rects = rects or {}
        for ann in annotations:
            box = self._box_for(ann, rects)
            if ann.kind == "arrow":
                if box:
                    # Point at the anchored node from its upper right, the way
                    # the hand-drawn manuals did.
                    x, y, bw, bh = box
                    end = (x + bw, y + bh / 2)
                    start = (min(0.97, end[0] + 0.09), max(0.03, end[1] - 0.10))
                elif ann.start and ann.end:
                    start, end = ann.start, ann.end
                else:
                    continue
                self._arrow(draw, px(start), px(end), width)
                continue
            if not box:
                continue
            x, y, bw, bh = box
            shape = (x * w, y * h, (x + bw) * w, (y + bh) * h)
            if ann.kind == "ellipse":
                draw.ellipse(shape, outline=STROKE, width=width)
            elif ann.kind == "rect":
                draw.rounded_rectangle(shape, radius=width * 3, outline=STROKE, width=width)
            else:
                self._badge(draw, shape, ann.label or "1", width)
        return image

    @staticmethod
    def _arrow(
        draw: ImageDraw.ImageDraw,
        start: tuple[float, float],
        end: tuple[float, float],
        width: int,
    ) -> None:
        import math

        draw.line([start, end], fill=STROKE, width=width)
        angle = math.atan2(end[1] - start[1], end[0] - start[0])
        head = width * 5
        for offset in (2.6, -2.6):
            draw.line(
                [
                    end,
                    (
                        end[0] + head * math.cos(angle + offset),
                        end[1] + head * math.sin(angle + offset),
                    ),
                ],
                fill=STROKE,
                width=width,
            )

    @staticmethod
    def _badge(
        draw: ImageDraw.ImageDraw, shape: tuple[float, float, float, float], label: str, width: int
    ) -> None:
        draw.ellipse(shape, fill=STROKE, outline=(255, 255, 255), width=max(2, width // 2))
        size = int((shape[3] - shape[1]) * 0.62)
        font = _font(max(10, size), bold=True)
        cx, cy = (shape[0] + shape[2]) / 2, (shape[1] + shape[3]) / 2
        draw.text((cx, cy), label, fill=(255, 255, 255), font=font, anchor="mm")

    def _placeholder(self, key: str, locale: str) -> Image.Image:
        w, h = PLACEHOLDER_SIZE
        image = Image.new("RGB", (w, h), LAVENDER)
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, w - 1, h - 1), outline=NAVY, width=6)
        for x in range(-h, w, 60):  # hatching, so nobody mistakes it for a screen
            draw.line([(x, h), (x + h, 0)], fill=(226, 216, 233), width=14)
        draw.rectangle((0, 0, w - 1, h - 1), outline=NAVY, width=6)

        draw.text((w / 2, h / 2 - 90), "SCREENSHOT NEEDED", font=_font(58, bold=True),
                  fill=NAVY, anchor="mm")
        draw.text((w / 2, h / 2), key, font=_font(46), fill=STROKE, anchor="mm")
        draw.text((w / 2, h / 2 + 70), f"assets/screenshots/{locale}/{key}.png",
                  font=_font(32), fill=GREY, anchor="mm")
        draw.text((w / 2, h - 60),
                  "capture this screen in the app, in this language, and drop the file in",
                  font=_font(28), fill=GREY, anchor="mm")
        return image
