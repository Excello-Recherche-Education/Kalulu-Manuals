# Kalulu-Manuals

Generator for the **Kalulu user manuals**: one PDF per language, with every
screenshot rendered from the running app.

[Kalulu](https://github.com/Excello-Recherche-Education) is an open-source
educational app that helps children learn to read through the decoding
(grapheme-phoneme) method, developed by
[Excello Recherche & Éducation](https://github.com/Excello-Recherche-Education).

## What it produces

```
build/manuals/
├── Kalulu-Manuel-fr.pdf
├── Kalulu-Manual-es.pdf
├── Kalulu-Manual-pt-BR.pdf
└── Kalulu-Manuale-it.pdf
```

One file per language, and **one file is all there is per language**: a reader
picks their language and nothing else. There used to be eight — a teacher
manual and a parent manual each — which asked whoever downloaded one to decide
whether they were "more a teacher or a parent" before reading a word of
either, for four steps of difference out of thirty-four. See "Audiences".

The names come from each language's own `filenames:` block, because these
files are handed to the public: a Spanish reader should not be downloading
`manual_es`. ASCII only and no spaces, since they travel through download
links and mail attachments; the locale tag stays because every language is
offered from one page, and the build refuses to start if two manuals would
land on one filename.

Each covers how the game is played — the chain of gardens, what a lesson is,
bosses, the brain screen — then creating an account, signing in, how a child
signs in with a symbol code, and adding, renaming and deleting students, with a
screenshot of every screen involved.

They are navigable, not just printable: the table of contents is clickable and
carries page numbers, and every section and step is a bookmark in the reader's
sidebar. Page numbers come from a two-pass build, so they are the real ones.

## The installation help

One more PDF lives here, and it is not one of the manuals:

```
installation-help/Kalulu Installation Help.pdf
```

It covers getting a desktop build to launch — placing the two Windows files and
answering SmartScreen, and on macOS the several ways past Gatekeeper for an app
that is not signed. It exists because that was two separate documents, a Word
file for Windows and a PDF for macOS, and a person downloading a build could not
tell which one they needed until they opened it. Now it opens on a contents page
that sends them to their platform.

```bash
python tools/build_installation_help.py
```

**It is the one PDF committed to this repository.** The manuals are not, because
they are regenerated from the app on every release and would only bloat the
history. This one is written by hand, does not change per release, and the
release pipeline attaches it to every GitHub release — so it has to be in a
fresh clone, and cannot live in the gitignored `build/`.

## Why generate them

The manuals used to be Google Docs: a paragraph, a pasted screenshot, a red
circle drawn by hand. That shape was right. What was wrong is that a person had
to keep four languages and two audiences in step, and re-paste every screenshot
whenever a screen changed. Four things follow from generating instead:

- **Screenshots come from the app, in the manual's language.** No screen is
  photographed by hand, so a redesign reaches every manual on the next build.
- **Button names come from the app's own translations.** The text writes
  `{ui:SETTINGS}`; the build resolves it to *Paramètres*, *Configuración*,
  *Parâmetros* or *Impostazioni* from the same CSV the game ships. The manual
  cannot call a button something the app does not.
- **Annotations are anchored to nodes, not coordinates.** A circle is placed on
  `%AddStudentButton`, and the capture reports where that button actually
  landed. Hand-measured boxes would be wrong in three languages out of four,
  because a button is not the same width in Italian as in French.
- **The audience split is computed, not written down.** A step marked
  `audiences: [teacher]` gets its chip, and the callout at the fork names the
  step numbers around it. Re-order the account flow and the callout follows;
  a sentence saying "teachers, skip to step 7" would not.

## Languages

**One manual per language Kalulu's interface is translated into**, which today
is four: `fr`, `es`, `pt_BR`, `it`.

> Note this is *not* the same list as the language **content packs**
> (`fr_FR`, `es_AR`, `es_CO`, `es_UY`, `pt_BR`). Those are what children learn
> to read in; these are what the interface speaks. A manual explains the
> interface, so it follows the interface. The list lives in `content/manual.yaml`
> under `locales` — change it there if that judgement is wrong.

Two Spanish variants sharing one manual is fine and expected; the manuals do not
deduplicate.

Only French is authored and reviewed. The other three are translated from it and
carry a **draft banner on the cover** until their `reviewed:` flag is set to
`true` in `content/strings/<locale>.yaml`.

## Audiences

Teacher and parent, in **one document**. The app really does differ between
them — a parent names each child during registration, a teacher only says how
many students a device has and renames them afterwards — but that is five
steps out of forty-three, and splitting the manual in two over five steps made
every reader answer a question about themselves before they could download
anything.

`audiences:` in `content/manual.yaml` still marks those steps. It no longer
splits the output; it drives two marks on the page instead:

- a **chip** above the step title — *Enseignant uniquement*, *Solo genitore* —
  tinted per audience, so a reader skims past what is not theirs by colour
  rather than by reading every label. The wording is the app's own name for the
  account type, from `ui_strings.csv`, so a reader recognises the answer they
  gave;
- a **fork callout** wherever the flow genuinely splits: *Enseignant : étapes 4
  à 6 · Parent : étape 7 · Tout le monde se retrouve ensuite à l'étape 8.*
  Assembled from the structure, so the numbers are always the real ones. A run
  that only one audience appears in is not a fork and gets no callout — its
  chip already says everything.

The first step of the manual explains both, before the reader meets either.
`kalulu-manual check` prints the restricted steps, since one file no longer
makes the split visible as two.

`vocabulary:` in each language file is now a plain glossary: a word the
document leans on, named once so every section names it the same way.

## Content packs

The gameplay screens read their letters from a language **pack**, and the packs
are not the manual's languages: Kalulu teaches reading in five locales
(`fr_FR`, `es_AR`, `es_CO`, `es_UY`, `pt_BR`) and its interface speaks four.
There is no Italian pack at all. `content/shots.yaml` maps each manual to a
pack and says out loud where one borrows another language's letters; packs are
read straight from the sibling `Kalulu-Languages` checkout, so a capture does
not depend on which packs happen to be installed on this machine.

## Requirements

- Python 3.11+
- **Kalulu-Frontend checked out next to this repository.** The generator drives
  it to take the screenshots. Cloning
  [Kalulu-Main](https://github.com/Excello-Recherche-Education/Kalulu-Main)
  with `--recurse-submodules` puts both in the right place.
- Godot 4.7, for capture only. Found via `$GODOT`, then the Steam install, then
  `PATH` — the same order as Kalulu-Main's `scripts/kalulu-env.sh`.

```bash
uv venv && uv pip install -e .
```

## Usage

```bash
kalulu-manual build            # capture anything missing, then render every PDF
kalulu-manual build --locale fr
kalulu-manual build --no-capture     # never launch Godot; use what is on disk
kalulu-manual capture --recapture    # re-render every screenshot from the app
kalulu-manual check                  # validate content, report gaps, build nothing
kalulu-manual shots                  # screenshot coverage per language
kalulu-manual sync-ui-strings        # refresh the app's translations from the frontend
```

`--strict` turns missing screenshots and untranslated interface keys into a
non-zero exit, for CI.

## How capture works

`kalulu_manual/godot/` is copied into the frontend as `manual_capture/`, Godot
runs it as a scene, it writes one PNG per screen plus a sidecar recording where
every named control landed, and the directory is deleted again. **Kalulu-Frontend
is left exactly as it was found** — it is a public repository and owes the
manuals nothing.

Three constraints, each learned the hard way:

- **Never `--headless`.** The dummy rasterizer renders nothing and every PNG
  comes back blank. Capture needs a window, which is why it is a
  developer-machine step rather than a CI one today.
- **Run the harness as a scene, not with `--script`.** A `--script` run compiles
  before the autoloads register, so `UserDataManager` and the rest are missing
  and every menu fails in `_ready`.
- **A saved PNG proves nothing.** Past roughly fifty screenshots in one process
  the renderer starts returning uniformly black frames and `save_png` still
  succeeds. Capture therefore runs in batches and rejects any image that is one
  flat colour.

## Layout

```
content/
├── manual.yaml            structure: sections, steps, which screenshot, which annotations
├── shots.yaml             how each screenshot is produced from the app
├── ui_strings.csv         vendored copy of the app's translations
└── strings/<locale>.yaml  the prose, the glossary, and the audience wording
kalulu_manual/
├── cli.py       build | capture | check | shots | sync-ui-strings
├── content.py   merges structure with translations
├── capture.py   drives Godot
├── godot/       the harness copied into the frontend
├── shots.py     screenshot lookup, annotation, placeholders
├── render.py    the PDF
└── theme.py     palette and fonts, from the app's design tokens
assets/
├── fonts/       Mulish (OFL), converted to TrueType — see tools/otf_to_ttf.py
└── screenshots/ overrides for screens the harness cannot reach
```

Structure and prose are separate files on purpose: re-ordering a flow should not
touch four translations, and fixing a Portuguese sentence should not move an
arrow.

A screen that cannot be captured does not fail the build — it renders as a
labelled placeholder and is listed in the build report, which is much harder to
overlook than a crash nobody ran.

## Conventions

- Written language: **English** for code, comments, commit messages and this
  README. The manual content itself is authored in the languages it is
  generated for.
- This repository is consumed as a git submodule of the private `Kalulu-Main`
  superproject, which tracks its `main` branch.

## License

To be defined. Note that `assets/fonts/` carries Mulish under the SIL Open Font
License; see `assets/fonts/OFL.txt`.
