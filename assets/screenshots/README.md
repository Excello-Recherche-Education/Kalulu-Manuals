# Screenshot overrides

Almost every screenshot in the manuals is rendered from the running app by
`kalulu-manual capture`, into the gitignored `build/screenshots/`. Nothing needs
to live here.

This directory is the escape hatch, searched *before* the captured ones:

    assets/screenshots/<locale>/<key>.png   this language
    assets/screenshots/_default/<key>.png   any language

Put a file here only when the harness genuinely cannot reach a screen — a
hardware permission dialog, an OS share sheet, something that only appears on a
real device. A committed override wins over a fresh capture forever, so it will
happily go on showing an old screen long after the app has changed. Prefer
teaching the harness a new recipe in `content/shots.yaml`.
