"""Command line for the Kalulu manual generator."""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import yaml

from .capture import CaptureError, Shot, capture, find_frontend, find_godot
from .content import ContentError, ContentSet
from .render import build_pdf
from .shots import ShotLibrary

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
CAPTURED = BUILD / "screenshots"


def _shot_catalogue() -> dict:
    return (yaml.safe_load((ROOT / "content" / "shots.yaml").read_text(encoding="utf-8"))
            or {}).get("shots", {})


def _library() -> ShotLibrary:
    # Committed overrides first, then whatever the harness rendered.
    return ShotLibrary([ROOT / "assets" / "screenshots", CAPTURED], BUILD / ".cache")


def _selected(requested: list[str] | None, available: list[str], what: str) -> list[str]:
    if not requested:
        return available
    unknown = [r for r in requested if r not in available]
    if unknown:
        raise SystemExit(f"unknown {what}: {', '.join(unknown)} (have {', '.join(available)})")
    return requested


def cmd_capture(args: argparse.Namespace) -> int:
    content = ContentSet.load(ROOT)
    locales = _selected(args.locale, content.locales, "locale")
    catalogue = _shot_catalogue()
    keys = sorted(set(content.shot_keys()))

    wanted: list[Shot] = []
    for locale in locales:
        for key in keys:
            entry = catalogue.get(key)
            if entry is None:
                print(f"  ! {key}: not in content/shots.yaml, cannot capture")
                continue
            existing = CAPTURED / locale / f"{key}.png"
            if existing.exists() and not args.recapture:
                continue
            wanted.append(
                Shot(key=key, locale=locale, recipe=entry.get("recipe", "scene"),
                     args=entry.get("args", {}))
            )
    if not wanted:
        print("every screenshot is already captured (use --recapture to redo them)")
        return 0

    frontend = find_frontend(Path(args.frontend) if args.frontend else None)
    godot = find_godot(args.godot)
    print(f"capturing {len(wanted)} screenshot(s) from {frontend}")
    print("  a Godot window will open: capture cannot run headless, which renders blank")
    results = capture(wanted, CAPTURED, frontend=frontend, godot=godot, verbose=args.verbose)

    failed = 0
    for shot in wanted:
        result = results.get(f"{shot.locale}/{shot.key}")
        if result is None or not result.get("ok"):
            failed += 1
            reason = (result or {}).get("error", "no result from the harness")
            print(f"  FAIL {shot.locale}/{shot.key}: {reason}")
    print(f"captured {len(wanted) - failed}/{len(wanted)}")
    return 1 if failed else 0


def cmd_build(args: argparse.Namespace) -> int:
    content = ContentSet.load(ROOT)
    locales = _selected(args.locale, content.locales, "locale")
    audiences = _selected(args.audience, content.audiences, "audience")
    out_dir = Path(args.out) if args.out else BUILD / "manuals"

    if not args.no_capture:
        missing = _library().missing(sorted(set(content.shot_keys())), locales)
        if missing:
            print(f"{len(missing)} screenshot(s) not captured yet; rendering them first")
            capture_args = argparse.Namespace(
                locale=locales, recapture=False, frontend=args.frontend,
                godot=args.godot, verbose=args.verbose,
            )
            try:
                cmd_capture(capture_args)
            except CaptureError as exc:
                print(f"capture failed ({exc});\n  building with placeholders instead")

    library = _library()
    built, problems = [], 0
    for locale in locales:
        for audience in audiences:
            manual = content.build(locale, audience, strict=args.strict)
            path = out_dir / f"{manual.stem}.pdf"
            build_pdf(manual, path, library, labels=content.labels(locale))
            built.append((path, manual))
            size = path.stat().st_size / 1024
            flag = "" if manual.reviewed else "  [translation unreviewed]"
            print(f"  {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}"
                  f"  {size:.0f} KB{flag}")
            for warning in dict.fromkeys(manual.warnings):
                problems += 1
                print(f"      ! {warning}")

    for anchor in dict.fromkeys(library.unresolved):
        problems += 1
        print(f"  ! annotation anchor {anchor!r} matched no node in the capture"
              f" -- renamed in the app, or ambiguous across repeated sub-scenes")

    print(f"\n{len(built)} manual(s) in {out_dir}")
    if problems:
        print(f"{problems} problem(s) reported above")
    if args.strict and problems:
        return 1
    return 0


def cmd_check(_args: argparse.Namespace) -> int:
    content = ContentSet.load(ROOT)
    catalogue = _shot_catalogue()
    keys = sorted(set(content.shot_keys()))
    failures = 0

    print("content")
    for locale in content.locales:
        for audience in content.audiences:
            try:
                manual = content.build(locale, audience, strict=True)
            except ContentError as exc:
                failures += 1
                print(f"  FAIL {locale}/{audience}: {exc}")
                continue
            state = "ok" if manual.reviewed else "unreviewed translation"
            note = f", {len(manual.warnings)} warning(s)" if manual.warnings else ""
            print(f"  {locale}/{audience}: {len(manual.sections)} sections, {state}{note}")
            for warning in dict.fromkeys(manual.warnings):
                print(f"      ! {warning}")

    print("\nscreenshots")
    undefined = [k for k in keys if k not in catalogue]
    for key in undefined:
        failures += 1
        print(f"  FAIL {key}: used by the manual but absent from content/shots.yaml")
    unused = sorted(set(catalogue) - set(keys))
    for key in unused:
        print(f"  ! {key}: defined in shots.yaml but no step uses it")

    gaps = _library().missing(keys, content.locales)
    if gaps:
        for key, locales in sorted(gaps.items()):
            print(f"  - {key}: not captured for {', '.join(locales)}")
        print(f"  {len(gaps)}/{len(keys)} keys have at least one gap; run `capture`")
    else:
        print(f"  all {len(keys)} keys captured in every locale")
    return 1 if failures else 0


def cmd_shots(_args: argparse.Namespace) -> int:
    content = ContentSet.load(ROOT)
    library = _library()
    keys = sorted(set(content.shot_keys()))
    width = max(len(k) for k in keys)
    print(f"{'key'.ljust(width)}  " + "  ".join(l.ljust(6) for l in content.locales))
    for key in keys:
        cells = []
        for locale in content.locales:
            path, used = library.source_for(key, locale)
            cells.append(("yes" if used == locale else "dflt" if path else "-").ljust(6))
        print(f"{key.ljust(width)}  " + "  ".join(cells))
    return 0


def cmd_annotations(args: argparse.Namespace) -> int:
    """Tile every annotated screenshot into one image, to be looked at.

    Annotations are the one part of a manual that no amount of validation can
    confirm: an anchor can resolve perfectly and still circle the wrong thing.
    A circle landed on one code symbol instead of the whole student card and
    the build reported nothing wrong, because nothing was wrong -- the node
    just was not the one meant. Looking is the only check that catches that.
    """
    from PIL import Image, ImageDraw

    content = ContentSet.load(ROOT)
    locale = (args.locale or [content.locales[0]])[0]
    library = _library()

    tiles: list[tuple[str, Image.Image]] = []
    for section in content.structure.get("sections", []):
        for step in section.get("steps", []):
            if not step.get("annotations") or not step.get("shot"):
                continue
            manual = content.build(locale, content.audiences[0])
            found = next(
                (s for s in manual.sections if s.id == section["id"]), None
            )
            model_step = next(
                (s for s in found.steps if s.id == step["id"]), None
            ) if found else None
            if model_step is None or not model_step.annotations:
                continue
            resolved = library.resolve(model_step.shot, locale, model_step.annotations)
            image = resolved.image.copy()
            image.thumbnail((620, 620))
            tiles.append((f"{section['id']} / {step['id']}", image))

    if not tiles:
        print("no annotated steps")
        return 0

    columns = 3
    tile_w = max(t.width for _, t in tiles)
    tile_h = max(t.height for _, t in tiles) + 20
    rows = (len(tiles) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * tile_w, rows * tile_h), (255, 255, 255))
    draw = ImageDraw.Draw(sheet)
    for index, (label, image) in enumerate(tiles):
        x, y = (index % columns) * tile_w, (index // columns) * tile_h
        sheet.paste(image, (x, y + 20))
        draw.text((x + 4, y + 5), label, fill=(0, 0, 0))

    out = Path(args.out) if args.out else BUILD / f"annotations_{locale}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    print(f"{len(tiles)} annotated step(s) -> {out}")
    for anchor in dict.fromkeys(library.unresolved):
        print(f"  ! anchor {anchor!r} matched no node in the capture")
    return 1 if library.unresolved else 0


def cmd_sync_ui_strings(args: argparse.Namespace) -> int:
    source = Path(args.csv) if args.csv else find_frontend() / "kalulu_localization.csv"
    if not source.is_file():
        raise SystemExit(f"not found: {source}")
    destination = ROOT / "content" / "ui_strings.csv"
    shutil.copyfile(source, destination)
    print(f"{destination.relative_to(ROOT)} refreshed from {source}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="kalulu-manual",
        description="Generate the Kalulu user manuals from the app itself.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def common(sub: argparse.ArgumentParser) -> None:
        sub.add_argument("--locale", action="append", help="repeatable; default every locale")
        sub.add_argument("--frontend", help="path to Kalulu-Frontend (default: next door)")
        sub.add_argument("--godot", help="Godot binary (default: $GODOT, then Steam, then PATH)")
        sub.add_argument("--verbose", action="store_true", help="echo Godot's output")

    build = subparsers.add_parser("build", help="render the PDFs")
    common(build)
    build.add_argument("--audience", action="append", help="teacher | parent")
    build.add_argument("--out", help="output directory (default build/manuals)")
    build.add_argument("--strict", action="store_true",
                       help="fail on missing screenshots or untranslated UI keys")
    build.add_argument("--no-capture", action="store_true",
                       help="never launch Godot; use what is already on disk")
    build.set_defaults(func=cmd_build)

    cap = subparsers.add_parser("capture", help="render the screenshots from the app")
    common(cap)
    cap.add_argument("--recapture", action="store_true", help="redo screenshots already on disk")
    cap.set_defaults(func=cmd_capture)

    chk = subparsers.add_parser("check", help="validate content without building")
    chk.set_defaults(func=cmd_check)

    lst = subparsers.add_parser("shots", help="screenshot coverage per locale")
    lst.set_defaults(func=cmd_shots)

    ann = subparsers.add_parser(
        "annotations", help="contact sheet of every annotated screenshot, to eyeball")
    ann.add_argument("--locale", action="append", help="default: the first locale")
    ann.add_argument("--out", help="output PNG (default build/annotations_<locale>.png)")
    ann.set_defaults(func=cmd_annotations)

    sync = subparsers.add_parser("sync-ui-strings",
                                 help="refresh the vendored copy of the app's translations")
    sync.add_argument("csv", nargs="?", help="path to kalulu_localization.csv")
    sync.set_defaults(func=cmd_sync_ui_strings)

    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (ContentError, CaptureError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
