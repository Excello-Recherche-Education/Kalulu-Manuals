# Kalulu-Manuals

Source project for the **Kalulu user manuals**.

[Kalulu](https://github.com/Excello-Recherche-Education) is an open-source educational
app that helps children learn to read through the decoding (grapheme-phoneme) method,
developed by [Excello Recherche & Éducation](https://github.com/Excello-Recherche-Education).

This repository will hold a **generator** that produces **one manual per language** from a
single shared source: the common structure and illustrations are written once, and the
generator emits a separate, complete document for each language Kalulu is available in,
ready to hand to teachers, parents and volunteers.

It contains no application code — the game itself lives in
[Kalulu-Frontend](https://github.com/Excello-Recherche-Education/Kalulu-Frontend).

## Status

Just created — the generator and the manual content are not written yet. The technology,
the source format and the output format are still to be chosen.

## Languages

Kalulu currently ships `fr_FR`, `es_AR`, `es_CO`, `es_UY` and `pt_BR`. Whether that means
five manuals (one per locale) or three (one per language, with the Spanish variants
sharing a document) is still open, and depends on how much the Spanish packs actually
diverge. The generator should be written so the answer is a configuration choice rather
than a rewrite.

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
