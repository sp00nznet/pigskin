# Debugging the recompilation

How Pigskin went from "SEGA logo, then black" to in-game, and how to do it
again next time something breaks. The toolkit side (clock, DMA, Z80, input,
macros, tail jumps) is in genrecomp `docs/recomp-runtime.md`.

## The loop: diff against the reference

genrecomp builds `genrecomp_ref`, which plays the ROM on GPGX's own 68K
interpreter. Run both headless with the same inputs and compare:

```
cd build/Release
genrecomp_ref.exe --headless --frames 2400 --record ref.mp4 rom.gen
pigskin.exe       --headless --frames 2400 --record rc.mp4  rom.gen
ffmpeg -i rc.mp4 -vf "select='not(mod(n\,200))',scale=320:-1,tile=4x3" -frames:v 1 sheet.png
```

A contact sheet of each shows which screen the recomp stops on. Then dump
state and find what differs:

```
genrecomp_ref.exe --headless --frames 1600 --ram-dump ref:10 rom.gen
pigskin.exe       --headless --frames 1600 --ram-dump rc:10  rom.gen
```

Each dump is 64K RAM (GPGX's byte-swapped layout: XOR the address with 1),
32 VDP registers, CRAM, VSRAM and VRAM. Comparing VDP registers is usually the
fastest lead: the first black screen came down to register 23 (DMA source high
byte) being `$00` instead of `$7F`.

When the recomp hangs, `PIGSKIN_STACK=1` prints the shadow call stack every 60
frames. The deepest entry is where the main thread is blocked:

```
Frame 1080 (SP=$00FFFCFE)
call stack (3): $0EA82E $0E8CD6 $0E8944
```

`$0E8944` is the sound-command mailbox: the 68K waits for the Z80 driver to
clear `$A01FC0`. The Z80 wasn't being run.

## Scripted input

`--press FRAME:BUTTONS[:LEN]` holds buttons from a frame. This reaches kickoff
of a real one-player game (Options, skill level, story, kickoff):

```
pigskin.exe --headless --frames 6000 --record game.mp4 ^
  --press 2300:START:10 --press 2600:START:10 --press 2900:START:10 ^
  --press 3200:START:10 rom.gen
```

## Generator fixes (now genrecomp `tools/recompiler/`)

**Fall-through regions.** The analyzer splits code at every address something
branches to from outside, so a loop whose head is such an address spans two C
functions, and its back-edge was a recursive call. `$0ED5CE` loops on `$0ED5D4`
once per frame and grew the C stack by one call per frame on the title screen.
Functions that run into each other are now a region: every entry point is
emitted with the whole region's code and starts with a `goto` to its own label,
so every branch inside the region is a `goto`. This replaced three hand-patched
loops in the old generated source. It costs code size: about 26K lines became
38K.

**Tail jumps.** Every jump out of a function, and every fall-through into the
next region, is `{ func_table_tail(x); return; }`. The play loop jumps between
`$0EB3C2` and `$0EE024` forever; as nested calls it hit the depth-500 abort ten
seconds into a game.

**Computed calls.** `move.l #ret,-(a7); jmp (a5)` calls through a register and
returns to `ret`. This was first a special case in the generator; genrecomp
now handles it generally: JSR pushes the real return address and RTS follows
whatever the 68K stack holds (genrecomp `docs/recomp-runtime.md`).

## Known issues

- The task switcher returns into another task's saved PC, which isn't an
  entry point; genrecomp logs `RTS to $0EF4AC (expected ...) has no
  function; returning` and falls back to a plain return, which is correct
  here.
- The title screen's bottom rows are cut off; probably an H-interrupt split,
  which the recomp doesn't raise.
- Audio is mixed but not recorded by `--record`, and has not been heard in a
  windowed run yet.
