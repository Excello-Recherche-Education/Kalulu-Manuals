"""What changed in the app that the guides might have to explain.

A guide is rebuilt for every release, and the screenshots are recaptured every
time, so a screen that merely *looks* different needs nothing from anybody. The
danger is the other kind of change: a screen whose behaviour moved, a new
screen nobody has written a step for, a button retexted so a sentence quoting
it now describes something else. A recapture cannot notice any of those, and
neither can a person reading a hundred-commit changelog.

So this compares two points in Kalulu-Frontend and reports only what bears on
the manual, mapped back to the steps it would touch:

* **changed screens** — a diff of the scenes and scripts behind the screens the
  manual photographs, resolved through `shots.yaml` to the steps that show them;
* **interface strings** — keys added, removed or retexted in
  `kalulu_localization.csv`, with the retexted ones cross-checked against the
  `{ui:KEY}` references in the prose, since those are the sentences that now
  read differently;
* **undocumented screens** — menu scenes that `shots.yaml` has no shot for, so
  a screen added three releases ago and never covered still gets named.

Everything here is advisory. It answers "is there anything to write?", and a
person answers it; nothing in the report blocks a build.
"""
from __future__ import annotations

import csv
import io
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .uistrings import UI_REF

#: The app's own screens, which is all the manual is about. Gameplay lives
#: elsewhere and is described in prose rather than photographed step by step,
#: so a change to a minigame is not this report's business.
SCREEN_DIRS = ("sources/menus/", "sources/ui/")

#: Where the app keeps its interface translations, inside the frontend.
UI_CSV = "kalulu_localization.csv"

#: Godot bookkeeping that changes with its own file and means nothing to a
#: manual. A .gd.uid moving is the editor renumbering, not a screen changing.
NOISE_SUFFIXES = (".uid", ".import", ".translation")


class ScanError(Exception):
    """The comparison cannot be made — a ref that does not exist, usually."""


def _git(frontend: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(frontend), *args],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise ScanError((result.stderr or result.stdout).strip() or " ".join(args))
    return result.stdout


def _resolve(frontend: Path, ref: str) -> str:
    """Turn a ref into a commit, with a clear error when it is not there."""
    try:
        return _git(frontend, "rev-parse", "--verify", f"{ref}^{{commit}}").strip()
    except ScanError as exc:
        raise ScanError(
            f"{ref!r} is not a commit in Kalulu-Frontend ({exc}). A guides"
            " release compares the app between two game/<version> tags, so the"
            " previous version's tag has to be fetched: git -C Kalulu-Frontend"
            " fetch --tags"
        ) from exc


# -- the pieces of the report -------------------------------------------------


@dataclass
class ChangedScreen:
    """A scene or script behind a documented screen, and what shows it."""

    path: str
    shots: list[str] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)


@dataclass
class StringChange:
    key: str
    kind: str  # added | removed | retexted
    #: Locales whose text moved, for a retext. Empty for added and removed.
    locales: list[str] = field(default_factory=list)
    #: Steps quoting this key as {ui:KEY}, which is what makes a retext matter.
    steps: list[str] = field(default_factory=list)


@dataclass
class Scan:
    since: str
    until: str
    since_ref: str
    until_ref: str
    screens: list[ChangedScreen] = field(default_factory=list)
    strings: list[StringChange] = field(default_factory=list)
    undocumented: list[str] = field(default_factory=list)
    #: Commits touching the screen directories, as a count only: the subjects
    #: are in the frontend's log and repeating them here buries the findings.
    screen_commits: int = 0

    @property
    def anything(self) -> bool:
        return bool(self.screens or self.strings or self.undocumented)

    @property
    def needs_a_decision(self) -> bool:
        """Whether a person should look before this release's guides go out.

        An undocumented screen has been undocumented for a while and does not
        make *this* release's guide wrong, so it is reported without holding
        anything up. A changed screen or a retexted string does.
        """
        return bool(self.screens or self.strings)


# -- mapping the app back onto the manual -------------------------------------


def _shot_scenes(root: Path) -> dict[str, list[str]]:
    """``res://`` scene path -> the shot keys that photograph it."""
    catalogue = yaml.safe_load((root / "content" / "shots.yaml").read_text(encoding="utf-8")) or {}
    by_scene: dict[str, list[str]] = {}
    for key, entry in (catalogue.get("shots") or {}).items():
        scene = ((entry or {}).get("args") or {}).get("scene")
        if scene:
            by_scene.setdefault(str(scene), []).append(key)
    return by_scene


def _steps_by_shot(root: Path) -> dict[str, list[str]]:
    """Shot key -> ``section/step`` ids that show it."""
    structure = yaml.safe_load((root / "content" / "manual.yaml").read_text(encoding="utf-8")) or {}
    by_shot: dict[str, list[str]] = {}
    for section in structure.get("sections", []):
        for step in section.get("steps", []):
            if step.get("shot"):
                by_shot.setdefault(step["shot"], []).append(f"{section['id']}/{step['id']}")
    return by_shot


def _steps_by_ui_key(root: Path) -> dict[str, list[str]]:
    """UI key -> ``locale section/step`` wherever the prose quotes it.

    Read from the strings files rather than from the built manual, because a
    key may be quoted in one language and not another -- a translator writing
    around a label instead of citing it -- and that asymmetry is exactly the
    kind of thing worth seeing here.
    """
    by_key: dict[str, list[str]] = {}
    for path in sorted((root / "content" / "strings").glob("*.yaml")):
        locale = path.stem
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for sid, section in (data.get("sections") or {}).items():
            for field_name in ("title", "intro"):
                for key in UI_REF.findall(str((section or {}).get(field_name) or "")):
                    by_key.setdefault(key, []).append(f"{locale} {sid}")
            for step_id, step in ((section or {}).get("steps") or {}).items():
                text = " ".join(
                    str((step or {}).get(name) or "") for name in ("title", "body", "note")
                )
                for key in UI_REF.findall(text):
                    by_key.setdefault(key, []).append(f"{locale} {sid}/{step_id}")
    return by_key


def _read_ui_csv(blob: str) -> tuple[list[str], dict[str, dict[str, str]]]:
    """The frontend's localization CSV as ``locale -> key -> text``."""
    rows = list(csv.reader(io.StringIO(blob)))
    if not rows:
        return [], {}
    locales = rows[0][1:]
    table: dict[str, dict[str, str]] = {loc: {} for loc in locales}
    for row in rows[1:]:
        if not row or not row[0]:
            continue
        for index, locale in enumerate(locales, start=1):
            if index < len(row):
                table[locale][row[0]] = row[index]
    return locales, table


def _all_keys(table: dict[str, dict[str, str]]) -> set[str]:
    keys: set[str] = set()
    for per_locale in table.values():
        keys |= set(per_locale)
    return keys


# -- the scan -----------------------------------------------------------------


def scan(root: Path, frontend: Path, since: str, until: str = "HEAD") -> Scan:
    """Compare the app at two refs and report what the guides may need."""
    since_sha = _resolve(frontend, since)
    until_sha = _resolve(frontend, until)
    result = Scan(since=since, until=until, since_ref=since_sha[:9], until_ref=until_sha[:9])
    if since_sha == until_sha:
        return result

    changed = [
        line for line in
        _git(frontend, "diff", "--name-only", f"{since_sha}..{until_sha}").splitlines()
        if line
    ]

    # -- changed screens ------------------------------------------------------
    by_scene = _shot_scenes(root)
    by_shot = _steps_by_shot(root)
    screen_files = [
        p for p in changed
        if p.startswith(SCREEN_DIRS) and not p.endswith(NOISE_SUFFIXES)
    ]
    for path in sorted(screen_files):
        # A step's screenshot comes from a .tscn, but the behaviour a step
        # describes usually lives in the .gd beside it, so both map to the
        # same shot. Match on the path with the extension dropped.
        stem = re.sub(r"\.(tscn|gd)$", "", path)
        shots = sorted({
            key
            for scene, keys in by_scene.items()
            if re.sub(r"\.tscn$", "", scene.removeprefix("res://")) == stem
            for key in keys
        })
        steps = sorted({step for key in shots for step in by_shot.get(key, [])})
        result.screens.append(ChangedScreen(path=path, shots=shots, steps=steps))

    if screen_files:
        result.screen_commits = len([
            line for line in _git(
                frontend, "log", "--oneline", f"{since_sha}..{until_sha}", "--", *SCREEN_DIRS
            ).splitlines() if line
        ])

    # -- interface strings ----------------------------------------------------
    if UI_CSV in changed:
        _, before = _read_ui_csv(_git(frontend, "show", f"{since_sha}:{UI_CSV}"))
        _, after = _read_ui_csv(_git(frontend, "show", f"{until_sha}:{UI_CSV}"))
        cited = _steps_by_ui_key(root)
        old_keys, new_keys = _all_keys(before), _all_keys(after)
        for key in sorted(new_keys - old_keys):
            result.strings.append(StringChange(key=key, kind="added"))
        for key in sorted(old_keys - new_keys):
            result.strings.append(
                StringChange(key=key, kind="removed", steps=sorted(set(cited.get(key, []))))
            )
        for key in sorted(old_keys & new_keys):
            moved = sorted(
                locale for locale in after
                if locale in before and before[locale].get(key) != after[locale].get(key)
            )
            if moved:
                result.strings.append(StringChange(
                    key=key, kind="retexted", locales=moved,
                    steps=sorted(set(cited.get(key, []))),
                ))

    # -- screens the manual has never covered ---------------------------------
    #
    # Only in folders the manual already photographs something from. A Godot
    # project is full of scenes that are not screens -- a flower, a patch of
    # night sky, a button -- and listing those as undocumented screens would
    # bury the one real find under thirty non-findings. Affinity by folder
    # needs no list of names to keep up to date: the day a folder gets its
    # first shot, its other scenes start being reported.
    documented = {
        re.sub(r"\.tscn$", "", scene.removeprefix("res://")) for scene in by_scene
    }
    documented_dirs = {str(Path(scene).parent) for scene in documented}
    listed = _git(frontend, "ls-tree", "-r", "--name-only", until_sha, "--", "sources/menus")
    for path in sorted(line for line in listed.splitlines() if line.endswith(".tscn")):
        if re.sub(r"\.tscn$", "", path) in documented:
            continue
        if str(Path(path).parent) in documented_dirs:
            result.undocumented.append(path)
    return result


# -- reporting ----------------------------------------------------------------


def _wrapped(items: list[str], *, indent: str = "", width: int = 78) -> list[str]:
    """``items`` as comma-separated lines, so a long list stays one block."""
    lines: list[str] = []
    current = indent
    for index, item in enumerate(items):
        piece = item + ("," if index < len(items) - 1 else "")
        if current != indent and len(current) + 1 + len(piece) > width:
            lines.append(current)
            current = indent
        current += (" " if current != indent else "") + piece
    if current != indent:
        lines.append(current)
    return lines


def render(result: Scan, *, undocumented_limit: int = 12) -> str:
    """The report, as the release script prints it."""
    out: list[str] = []
    out.append(f"comparing Kalulu-Frontend  {result.since} ({result.since_ref})"
               f"  ->  {result.until} ({result.until_ref})")
    if result.since_ref == result.until_ref:
        out.append("  the two refs are the same commit: nothing changed in the app")
        return "\n".join(out)

    out.append("")
    out.append(">>> changed screens")
    if not result.screens:
        out.append("    none -- no scene or script behind a documented screen moved")
    else:
        out.append(f"    {len(result.screens)} file(s) over {result.screen_commits} commit(s)")
        for screen in result.screens:
            out.append(f"    {screen.path}")
            if screen.steps:
                out.append(f"        documents: {', '.join(screen.steps)}")
            else:
                out.append("        no step photographs this one"
                           " -- behaviour only, or an undocumented screen")

    out.append("")
    out.append(">>> interface strings")
    if not result.strings:
        out.append("    none -- kalulu_localization.csv did not change")
    else:
        # Retexted and removed first, and one per line: those are the ones that
        # make an existing sentence wrong. Added keys are a block -- no single
        # one is actionable, but a run of them with a common prefix is a
        # feature that arrived without a step to explain it, which is the
        # thing worth seeing.
        for change in result.strings:
            if change.kind == "added":
                continue
            mark = "~" if change.kind == "retexted" else "-"
            detail = (f"retexted in {', '.join(change.locales)}"
                      if change.kind == "retexted" else "REMOVED")
            out.append(f"    {mark} {change.key}  {detail}")
            if change.steps:
                out.append(f"        quoted by: {', '.join(change.steps)}")
            elif change.kind == "removed":
                out.append("        not quoted by the manual")
        added = [c.key for c in result.strings if c.kind == "added"]
        if added:
            out.append(f"    + {len(added)} new key(s):")
            out.extend(_wrapped(added, indent=" " * 8))
            out.append("        a run of new keys sharing a prefix is usually a"
                       " whole feature; check it has a step")

    out.append("")
    out.append(">>> screens with no screenshot in the manual")
    if not result.undocumented:
        out.append("    none -- every menu scene has a shot")
    else:
        shown = result.undocumented[:undocumented_limit]
        for path in shown:
            out.append(f"    {path}")
        if len(result.undocumented) > len(shown):
            out.append(f"    ... and {len(result.undocumented) - len(shown)} more")
        out.append("    (long-standing, not this release's doing -- listed so it"
                   " is a decision rather than an oversight)")
    return "\n".join(out)
