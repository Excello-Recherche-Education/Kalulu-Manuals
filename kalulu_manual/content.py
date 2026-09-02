"""Load the structure and the translations, and merge them into Manuals.

Two files decide what a manual says:

* `content/manual.yaml` — the *structure*, which is language-neutral: the order
  of sections and steps, which screenshot each step shows, where the arrows and
  circles go, and which audiences a step applies to.
* `content/strings/<locale>.yaml` — the *prose* for that language, keyed by the
  same ids.

They are separate because they rot at different rates and are edited by
different people: re-ordering a flow should not touch four translations, and
fixing a Portuguese sentence should not risk moving an arrow.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from .model import Annotation, Manual, Section, Step
from .uistrings import UIStrings

#: ``{learner}`` and friends — audience vocabulary, substituted per document.
VOCAB_REF = re.compile(r"\{([a-z_]+)\}")

#: Anything left in braces once the app labels and the vocabulary are in.
LEFTOVER_BRACE = re.compile(r"\{[^{}]*\}")


class ContentError(Exception):
    """The content files are inconsistent. Always fatal: a manual that is
    silently missing a step is worse than no manual."""


def _read_yaml(path: Path) -> dict:
    if not path.exists():
        raise ContentError(f"missing content file: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ContentError(f"{path}: expected a mapping at the top level")
    return data


def _annotation(raw: dict, where: str) -> Annotation:
    kind = raw.get("type")
    if kind not in {"ellipse", "rect", "arrow", "number"}:
        raise ContentError(f"{where}: unknown annotation type {kind!r}")
    box = raw.get("box")
    try:
        return Annotation(
            kind=kind,
            box=tuple(box) if box else None,  # type: ignore[arg-type]
            node=str(raw["node"]) if "node" in raw else None,
            pad=float(raw.get("pad", 0.012)),
            start=tuple(raw["from"]) if "from" in raw else None,  # type: ignore[arg-type]
            end=tuple(raw["to"]) if "to" in raw else None,  # type: ignore[arg-type]
            label=str(raw["label"]) if "label" in raw else None,
        )
    except (ValueError, TypeError) as exc:
        raise ContentError(f"{where}: {exc}") from exc


@dataclass
class ContentSet:
    """Everything on disk, parsed once and reused for every output document."""

    structure: dict
    strings: dict[str, dict]
    ui: UIStrings
    root: Path

    @classmethod
    def load(cls, root: Path) -> "ContentSet":
        structure = _read_yaml(root / "content" / "manual.yaml")
        ui = UIStrings.load(root / "content" / "ui_strings.csv")
        strings: dict[str, dict] = {}
        for locale in structure.get("locales", []):
            strings[locale] = _read_yaml(root / "content" / "strings" / f"{locale}.yaml")
        return cls(structure=structure, strings=strings, ui=ui, root=root)

    @property
    def locales(self) -> list[str]:
        return list(self.structure.get("locales", []))

    @property
    def audiences(self) -> list[str]:
        return list(self.structure.get("audiences", ["teacher"]))

    def labels(self, locale: str) -> dict[str, str]:
        """Chrome the renderer needs translated: 'Contents', the draft banner."""
        return dict((self.strings.get(locale) or {}).get("labels") or {})

    def shot_keys(self) -> list[str]:
        keys = []
        for section in self.structure.get("sections", []):
            for step in section.get("steps", []):
                if step.get("shot"):
                    keys.append(step["shot"])
        return keys

    # -- assembly -------------------------------------------------------------

    def build(self, locale: str, audience: str, *, strict: bool = False) -> Manual:
        if locale not in self.strings:
            raise ContentError(f"no strings file for locale {locale!r}")
        if audience not in self.audiences:
            raise ContentError(f"unknown audience {audience!r}")

        loc = self.strings[locale]
        warnings: list[str] = []
        vocab = (loc.get("vocabulary") or {}).get(audience)
        if vocab is None:
            raise ContentError(f"{locale}.yaml: no vocabulary for audience {audience!r}")

        def text(raw: str | None, where: str) -> str | None:
            """Resolve app labels, then audience vocabulary."""
            if raw is None:
                return None
            resolved, problems = self.ui.resolve(locale, raw, strict=strict)
            for problem in problems:
                warnings.append(f"{where}: {problem}")

            def sub(match: re.Match[str]) -> str:
                word = match.group(1)
                if word in vocab:
                    return str(vocab[word])
                warnings.append(f"{where}: no {audience} vocabulary for {{{word}}} in {locale}")
                return match.group(0)

            substituted = VOCAB_REF.sub(sub, resolved)
            # Anything still in braces is a placeholder nobody filled. It comes
            # from quoting an app string that carries its own runtime
            # placeholders -- ADULT_BOSS_BLOCK_PROMPT holds {1} {2} {3}, which
            # the game replaces with symbol names and the manual cannot -- and
            # it reaches the page as literal braces.
            leftover = LEFTOVER_BRACE.findall(substituted)
            if leftover:
                warnings.append(
                    f"{where}: unfilled placeholder(s) {', '.join(sorted(set(leftover)))}"
                    " -- quoting an app string that has runtime arguments?"
                )
            return substituted

        loc_sections = loc.get("sections") or {}
        sections: list[Section] = []
        for raw_section in self.structure.get("sections", []):
            sid = raw_section["id"]
            audiences = tuple(raw_section.get("audiences", ()))
            if audiences and audience not in audiences:
                continue
            translated = loc_sections.get(sid)
            if translated is None:
                raise ContentError(f"{locale}.yaml: section {sid!r} is not translated")
            loc_steps = translated.get("steps") or {}

            steps: list[Step] = []
            for raw_step in raw_section.get("steps", []):
                step_id = raw_step["id"]
                step_audiences = tuple(raw_step.get("audiences", ()))
                if step_audiences and audience not in step_audiences:
                    continue
                tr = loc_steps.get(step_id)
                if tr is None:
                    raise ContentError(
                        f"{locale}.yaml: step {sid}/{step_id!r} is not translated"
                    )
                where = f"{locale}/{audience} {sid}/{step_id}"
                body = text(tr.get("body"), where)
                if not body:
                    raise ContentError(f"{locale}.yaml: step {sid}/{step_id!r} has no body")
                steps.append(
                    Step(
                        id=step_id,
                        title=text(tr.get("title"), where),
                        body=body,
                        note=text(tr.get("note"), where),
                        shot=raw_step.get("shot"),
                        annotations=tuple(
                            _annotation(a, f"{sid}/{step_id}")
                            for a in raw_step.get("annotations", [])
                        ),
                        audiences=step_audiences,
                    )
                )
            if not steps:
                continue
            sections.append(
                Section(
                    id=sid,
                    title=text(translated.get("title"), f"{locale} {sid}") or sid,
                    intro=text(translated.get("intro"), f"{locale} {sid}"),
                    steps=tuple(steps),
                    audiences=audiences,
                )
            )

        meta = loc.get("meta") or {}
        subtitle_key = f"subtitle_{audience}"
        return Manual(
            locale=locale,
            audience=audience,
            title=text(meta.get("title"), f"{locale} meta") or "Kalulu",
            subtitle=text(meta.get(subtitle_key) or meta.get("subtitle"), f"{locale} meta") or "",
            app_version=str(self.structure.get("app_version", "")),
            reviewed=bool(loc.get("reviewed", False)),
            sections=tuple(sections),
            warnings=warnings,
        )
