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
