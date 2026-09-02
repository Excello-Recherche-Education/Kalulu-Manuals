"""Render the manual's screenshots by driving the real app.

Kalulu-Frontend sits next to this repository, so the manual never ships a
hand-taken screenshot that quietly disagrees with the product. Every screen in
the manual is captured from the running game, in the language the manual is
written in, at the project's 2560x1800 reference viewport.

How it works: the harness in `kalulu_manual/godot/` is copied into the frontend
as `manual_capture/`, Godot runs it as a scene, it writes one PNG per shot, and
the directory is removed again. Kalulu-Frontend is left exactly as it was found
-- it is a public repository and owes the manuals nothing.

Two hard constraints, both learned the expensive way:

* **Never `--headless`.** The dummy rasterizer renders nothing and every PNG
  comes back blank. A windowed run is required, which is also why capture is a
  developer-machine step and not something CI does today.
* **Run the harness as a scene, not with `--script`.** A `--script` run compiles
  before the autoloads register, so `UserDataManager` and friends are missing
  and the menus fail in `_ready`.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

GODOT_ENV_VAR = "GODOT"
#: Where the harness is dropped inside the frontend. Deliberately not a dotted
#: name: Godot skips hidden directories when it scans, so `res://.foo/bar.gd`
#: never gets imported and cannot be loaded.
HARNESS_DIR = "manual_capture"


class CaptureError(Exception):
    pass


def find_frontend(explicit: Path | None = None) -> Path:
    """Locate Kalulu-Frontend: the flag, then $KALULU_FRONTEND, then next door."""
    candidates = []
    if explicit:
        candidates.append(explicit)
    env = os.environ.get("KALULU_FRONTEND")
    if env:
        candidates.append(Path(env))
    here = Path(__file__).resolve().parent.parent
    candidates.append(here.parent / "Kalulu-Frontend")
    for candidate in candidates:
        if (candidate / "project.godot").is_file():
            return candidate.resolve()
    tried = "\n  ".join(str(c) for c in candidates)
    raise CaptureError(
        "Kalulu-Frontend not found. Tried:\n  " + tried +
        "\nPass --frontend, or set KALULU_FRONTEND."
    )


def frontend_version(frontend: Path) -> str | None:
    """The app's own `config/version`, read from its project.godot.

    Not what the manual's cover states -- that is set by hand, and is meant to
    lag: development is internal, the manual is distributed. This is only for
    reporting the two side by side, so the gap is a decision rather than an
    oversight, and so documenting a version the app has not reached yet gets
    noticed.
    """
    project = frontend / "project.godot"
    if not project.is_file():
        return None
    for line in project.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("config/version="):
            return line.split("=", 1)[1].strip().strip('"')
    return None


def _kill_stragglers() -> None:
    """Make sure no Godot is left holding a window open.

    subprocess kills the process it started, but a Godot that was already
    wedged -- or one from an earlier interrupted run -- stays on screen waiting
    for somebody to close it. Nothing else on this machine runs the harness
    scene, so matching on it is safe.
    """
    subprocess.run(["pkill", "-f", f"{HARNESS_DIR}/capture.tscn"],
                   capture_output=True, check=False)


def find_languages(explicit: Path | None = None) -> Path | None:
    """Locate Kalulu-Languages, the sibling holding the content packs."""
    here = Path(__file__).resolve().parent.parent
    for candidate in (explicit, Path(os.environ.get("KALULU_LANGUAGES", "")),
                      here.parent / "Kalulu-Languages"):
        if candidate and (candidate / "fr_FR" / "language.db").is_file():
            return candidate.resolve()
    return None


def find_godot(explicit: str | None = None) -> str:
    """Resolve the Godot binary the same way scripts/kalulu-env.sh does."""
    if explicit:
        return explicit
    if os.environ.get(GODOT_ENV_VAR):
        return os.environ[GODOT_ENV_VAR]
    steam = (
        Path.home()
        / "Library/Application Support/Steam/steamapps/common/Godot Engine"
        / "Godot.app/Contents/MacOS/Godot"
    )
    if steam.is_file():
        return str(steam)
    for name in ("Godot", "godot4", "godot"):
        found = shutil.which(name)
        if found:
            return found
    raise CaptureError(
        "no Godot binary found. Set $GODOT (Kalulu-Main's scripts/kalulu-env.sh does)."
    )


def _check_harness_compiles(frontend: Path, godot: str) -> None:
    """Parse the harness before running it.

    A GDScript parse error is the worst failure mode here: Godot loads no main
    scene, opens an empty window and sits in it. Nothing times out inside the
    game, nothing is written, and the only symptom is a window someone has to
    close by hand. `--check-only` catches it in about a second, headless.
    """
    probe = subprocess.run(
        [godot, "--headless", "--path", str(frontend), "--check-only",
         "--script", f"res://{HARNESS_DIR}/capture.gd"],
        capture_output=True, text=True, timeout=120,
    )
    output = probe.stdout + probe.stderr
    # Only parse errors. `--check-only` resolves no autoloads, so it always
    # reports `Identifier not found: Database` and friends -- which is exactly
    # why the harness runs as a scene rather than through --script. Those are
    # expected; a parse error is not, and is the one that leaves a dead window.
    errors = [line for line in output.splitlines() if "Parse Error" in line]
    if errors:
        raise CaptureError(
            "the capture harness does not compile:\n  " + "\n  ".join(errors[:8])
        )


@dataclass
class Shot:
    """One screenshot request, as the harness expects it."""

    key: str
    locale: str
    recipe: str = "scene"
    args: dict | None = None

    def to_job(self) -> dict:
        return {
            "key": self.key,
            "locale": self.locale,
            "recipe": self.recipe,
            "args": self.args or {},
        }


#: Seconds a single batch may take. Generous because the gameplay screens are
#: slow: the gardens screen alone loads twelve garden scenes.
#: Shots per Godot process. A long run degrades: past a few dozen screenshots
#: the renderer starts handing back uniformly black frames, and the harness
#: cannot tell -- `save_png` succeeds on a black image. Restarting the process
#: every batch costs a few seconds of boot and makes it rare.
BATCH_SIZE = 12

#: Blank frames still slip through occasionally, so rejected shots are simply
#: taken again in a fresh process. One retry clears it in practice; the point of
#: the cap is that a screen which is *genuinely* unreachable still fails, rather
#: than looping.
MAX_ATTEMPTS = 3


def capture(
    shots: list[Shot],
    out_dir: Path,
    *,
    frontend: Path,
    godot: str,
    timeout: int = 900,
    verbose: bool = False,
) -> dict[str, dict]:
    """Run the harness in batches. Returns ``locale/key -> result``."""
    if not shots:
        return {}
    combined: dict[str, dict] = {}
    pending = list(shots)
    for attempt in range(1, MAX_ATTEMPTS + 1):
        fresh: dict[str, dict] = {}
        for start in range(0, len(pending), BATCH_SIZE):
            batch = pending[start:start + BATCH_SIZE]
            fresh.update(
                _capture_batch(batch, out_dir, frontend=frontend, godot=godot,
                               timeout=timeout, verbose=verbose)
            )
        _reject_blank(fresh)
        combined.update(fresh)
        retry = [s for s in pending if not combined.get(f"{s.locale}/{s.key}", {}).get("ok")]
        if not retry or attempt == MAX_ATTEMPTS:
            break
        print(f"  {len(retry)} capture(s) came back blank; retrying (attempt {attempt + 1})")
        pending = retry
    return combined


def _reject_blank(results: dict[str, dict]) -> None:
    """Mark uniformly-coloured captures as failures.

    A dead renderer still saves a PNG, so "the file exists" proves nothing --
    the same trap as Godot's export exit code. A screenshot of the app is never
    one flat colour, so that is a reliable tell.
    """
    try:
        from PIL import Image
    except ImportError:  # pragma: no cover - Pillow is a hard dependency
        return
    for name, result in results.items():
        if not result.get("ok") or not result.get("path"):
            continue
        path = Path(result["path"])
        if not path.exists():
            result["ok"] = False
            result["error"] = "the harness reported success but wrote no file"
            continue
        with Image.open(path) as image:
            extrema = image.convert("RGB").getextrema()
        if all(low == high for low, high in extrema):
            result["ok"] = False
            result["error"] = "blank capture (the renderer stopped drawing)"
            path.unlink(missing_ok=True)


def _capture_batch(
    shots: list[Shot],
    out_dir: Path,
    *,
    frontend: Path,
    godot: str,
    timeout: int,
    verbose: bool,
) -> dict[str, dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    harness_src = Path(__file__).resolve().parent / "godot"
    harness_dst = frontend / HARNESS_DIR
    if harness_dst.exists():
        shutil.rmtree(harness_dst)
    shutil.copytree(harness_src, harness_dst)

    work = out_dir / ".jobs"
    work.mkdir(exist_ok=True)
    jobs_path = work / "jobs.json"
    result_path = work / "results.json"
    # Delete last run's results first. Leaving them meant a batch whose Godot
    # died before writing anything -- a harness that failed to compile, say --
    # was read back as the *previous* batch's successes, so shots that never
    # ran were reported OK.
    result_path.unlink(missing_ok=True)
    # One PNG per key per locale, so two locales never race on one filename.
    jobs = {
        "out_dir": str(out_dir.resolve()),
        "result_path": str(result_path.resolve()),
        "shots": [s.to_job() for s in shots],
    }
    jobs_path.write_text(json.dumps(jobs, indent=2), encoding="utf-8")

    _check_harness_compiles(frontend, godot)

    env = {**os.environ, "KALULU_MANUAL_JOBS": str(jobs_path.resolve())}
    command = [
        godot,
        "--path",
        str(frontend),
        f"res://{HARNESS_DIR}/capture.tscn",
    ]
    # The harness has its own per-shot watchdog; this is the backstop for the
    # cases it cannot see, such as Godot never getting as far as running it.
    budget = min(timeout, 60 + 60 * len(shots))
    try:
        proc = subprocess.run(
            command, env=env, capture_output=True, text=True, timeout=budget,
            start_new_session=True,
        )
    except subprocess.TimeoutExpired as exc:
        _kill_stragglers()
        raise CaptureError(
            f"Godot did not finish within {budget}s for {len(shots)} shot(s); killed it"
        ) from exc
    finally:
        shutil.rmtree(harness_dst, ignore_errors=True)

    if verbose:
        print(proc.stdout)
        print(proc.stderr)

    # Godot's exit code is not a success signal -- it returns 0 from aborted
    # runs too. The results file is the only thing worth believing.
    if not result_path.exists():
        tail = "\n".join((proc.stdout + proc.stderr).strip().splitlines()[-15:])
        raise CaptureError(f"the harness wrote no results. Godot said:\n{tail}")

    results = json.loads(result_path.read_text(encoding="utf-8")).get("results", [])
    by_key: dict[str, dict] = {}
    for entry in results:
        by_key[f"{entry['locale']}/{entry['key']}"] = entry
        # Park the node rectangles beside the PNG so a later build can anchor
        # annotations without re-running Godot.
        rects = entry.pop("rects", None)
        if rects and entry.get("path"):
            Path(entry["path"]).with_suffix(".rects.json").write_text(
                json.dumps(rects, indent=1, sort_keys=True), encoding="utf-8"
            )
    return by_key
