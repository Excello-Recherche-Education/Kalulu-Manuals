"""The app's own translated interface labels.

The single most common way a user manual goes wrong is naming a button
something the app does not call it — in one language, after a retranslation
nobody thought to propagate. So the manual never spells a label itself. Step
text writes ``{ui:SETTINGS}`` and this module resolves it from the very CSV the
game builds its translations from, per locale.

The CSV is vendored at `content/ui_strings.csv` rather than read out of a
Kalulu-Frontend checkout: the manuals must build on a machine that has only
this repository, and pinning the copy means a manual is reproducible for the
app version it was written against. Refresh it with:

    kalulu-manual sync-ui-strings ../Kalulu-Frontend/kalulu_localization.csv
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

#: ``{ui:KEY}`` inside any translated string.
UI_REF = re.compile(r"\{ui:([A-Z0-9_]+)\}")


class MissingUIString(KeyError):
    """A step referenced a UI key the app's CSV does not define."""


@dataclass(frozen=True)
class UIStrings:
    """Interface labels keyed by ``locale -> key``."""

    by_locale: dict[str, dict[str, str]]
    source: Path

    @classmethod
    def load(cls, path: Path) -> "UIStrings":
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.reader(handle))
        if not rows:
            raise ValueError(f"{path} is empty")
        header = rows[0]
        if header[0] != "keys":
            raise ValueError(f"{path}: expected a 'keys' first column, found {header[0]!r}")
        locales = header[1:]
        by_locale: dict[str, dict[str, str]] = {loc: {} for loc in locales}
        for row in rows[1:]:
            if not row or not row[0]:
                continue
            key = row[0]
            for index, locale in enumerate(locales, start=1):
                if index < len(row) and row[index]:
                    by_locale[locale][key] = row[index]
        return cls(by_locale=by_locale, source=path)

    @property
    def locales(self) -> list[str]:
        return sorted(self.by_locale)

    def label(self, locale: str, key: str) -> str:
        """The app's label for ``key`` in ``locale``.

        Falls back to the base locale, then to the key itself — which is what
        the game displays too when a translation is missing, so the manual
        matches the screen even when the screen is wrong.
        """
        table = self.by_locale.get(locale)
        if table and key in table:
            return table[key]
        raise MissingUIString(f"{key!r} has no {locale} translation in {self.source.name}")

    def resolve(self, locale: str, text: str, *, strict: bool = True) -> tuple[str, list[str]]:
        """Substitute every ``{ui:KEY}`` in ``text``. Returns (text, problems)."""
        problems: list[str] = []

        def replace(match: re.Match[str]) -> str:
            key = match.group(1)
            try:
                return self.label(locale, key)
            except MissingUIString as exc:
                problems.append(str(exc))
                if strict:
                    return f"«{key}»"
                return key

        return UI_REF.sub(replace, text), problems

    def keys_used(self, text: str) -> set[str]:
        return set(UI_REF.findall(text))
