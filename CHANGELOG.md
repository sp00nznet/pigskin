# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Needs
genrecomp#1-#5 (branch `chore/house-style` until merged).

## [Unreleased]

### Added
- In game: attract mode, title, menus and full one-player matches run.
- Headless runs, recording and scripted input via genrecomp's flags.
- `PIGSKIN_STACK=1` prints the shadow call stack every second.
- `Setup.cmd`: checks prerequisites, generates the source from your ROM,
  builds, smoke-tests, and leaves `Play Pigskin.cmd`.
- `docs/debugging.md`, `LICENSE`, `ROADMAP.md`, this changelog.

### Changed
- The generator groups functions that run into each other into regions, so
  loops across split points are `goto`s rather than recursive calls.
- Jumps out of a function and fall-through are tail jumps
  (`func_table_tail`); `push ret; jmp (An)` is emitted as a call then a
  jump to `ret`.
- Entry point and VBlank handler are entered through `func_table_call`.

### Removed
- Generated source (`src/recomp/`) and the ROM-derived `functions.json` are
  no longer tracked; both are generated locally from your ROM. Earlier
  commits still contain them.
- Disassembly and generated-code excerpts from the README.
- The hand-patched loops in the generated source, now handled by the
  generator.

## Earlier work - 2026-03 (untagged)

Recompiler, TRAP dispatch, VBlank-driven frame loop; the SEGA logo rendered.
