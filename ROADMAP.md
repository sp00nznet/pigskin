# Roadmap

## Next

- Listen to the audio in a windowed run; fix whatever is wrong.
- Play one match to the final whistle and check the results screen.
- Find the bad pointer behind the `$BC8Fxx` unmapped reads
  (docs/debugging.md, Known issues).
- Two-player.
- Replay the scripted inputs on both genrecomp's reference runner and this
  build and compare state at checkpoints: this title's slice of genrecomp's
  planned conformance harness.

## Deferred

- The title screen's cut-off bottom rows. They need H-interrupts from
  genrecomp (its ROADMAP).
- Linux and macOS: genrecomp builds there, but Setup and play are
  Windows-only for now.
- Moving `tools/generate_recomp.py` into genrecomp as the shared generator.

## Out of scope

- Distributing the ROM, generated source or builds that include game data.
- Commercial use (Genesis Plus GX's licence).
