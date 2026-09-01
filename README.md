# Kalulu-Manuals

Source project for the **Kalulu user manuals**.

[Kalulu](https://github.com/Excello-Recherche-Education) is an open-source educational
app that helps children learn to read through the decoding (grapheme-phoneme) method,
developed by [Excello Recherche & Éducation](https://github.com/Excello-Recherche-Education).

This repository will hold a **generator** that produces **one manual per language Kalulu
ships** from a single shared source: the common structure and illustrations are written
once, and the generator emits a separate, complete, self-contained document per language,
ready to hand to teachers, parents and volunteers.

It contains no application code — the game itself lives in
[Kalulu-Frontend](https://github.com/Excello-Recherche-Education/Kalulu-Frontend).

## Status

Just created — the generator and the manual content are not written yet. The technology,
the source format and the output format are still to be chosen.

## Languages

**One manual per shipped language, always.** Kalulu currently ships `fr_FR`, `es_AR`,
`es_CO`, `es_UY` and `pt_BR`, so the generator emits **five** documents.

The three Spanish variants may well end up word-for-word identical — that is fine and
expected. They still get their own manual each. Nothing is ever shared at the *output*
level: a reader of the Colombian manual must never be handed the Argentinian one, even
when the two are byte-identical. Deduplicating the output is not an optimisation to make
later; it is the thing not to do.

Sharing happens at the *source* level instead: whatever is common lives in one place, and
each language overrides only what differs. Adding a sixth language should mean adding a
language entry, not copying a manual.

## Layout

To be defined as the project takes shape.

## Building the manuals

To be documented once the generator exists.

## Conventions

- Written language: **English** for code, comments, commit messages and repository
  documentation. The manual content itself is authored in the languages it is generated for.
- This repository is consumed as a git submodule of the private `Kalulu-Main`
  superproject, which tracks its `main` branch.

## License

To be defined.
