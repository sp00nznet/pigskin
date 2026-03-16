# PIGSKIN FOOTBRAWL: RECOMPILED

```
  ____  ___ ____ ____  _  _____ _   _
 |  _ \|_ _/ ___/ ___|| |/ /_ _| \ | |
 | |_) || | |  _\___ \| ' / | ||  \| |
 |  __/ | | |_| |___) | . \ | || |\  |
 |_|   |___\____|____/|_|\_\___|_| \_|
          F O O T B R A W L
```

**A static recompilation of Jerry Glanville's Pigskin Footbrawl (Sega Genesis, 1992)**

> *"It's not just football. It's medieval football. With swords."*

This project takes the original Motorola 68000 machine code from the Genesis ROM and translates it ahead-of-time into native C, then compiles it to run natively on modern hardware. No emulator in the loop -- the recompiled code IS the CPU, and real Genesis hardware (VDP, YM2612, PSG, Z80) is provided by [genrecomp](https://github.com/sp00nznet/genrecomp) via Genesis Plus GX.

---

## What Is This Game?

Pigskin Footbrawl is a 1992 Sega Genesis port of the 1990 Bally Midway arcade game. It's a medieval-themed football game where two teams of armored warriors battle it out on a field littered with obstacles, weapons, and... well, brawling. It was directed by George Petro and designed by the legendary team at Midway. Jerry Glanville (real NFL coach) lent his name to the Genesis version.

Think NFL Blitz meets Dungeons & Dragons. On a Sega Genesis. In 1992.

---

## Project Status

| Component | Status | Details |
|-----------|--------|---------|
| ROM Analysis | **Done** | 328 functions, 19,209 instructions discovered |
| Code Generation | **Done** | ~24K lines of recompiled C across 7 source files |
| Function Registration | **Done** | All 328 functions registered in dispatch table |
| Entry Point | **Done** | Genesis init -> main game loop wired up |
| VBlank Handler | **Done** | IRQ6 handler ($0E9220) connected |
| Jump Table Discovery | **Done** | 61 jump tables, 209 targets found |
| Build System | **Done** | CMake + MSVC, links against genrecomp |
| MOVEM Support | **Done** | Full register list parsing, push/pop/load/store |
| Indirect JSR/JMP | **Done** | 14 genuine indirect calls through address registers |
| Memory-dest Ops | **Done** | ADD/SUB/AND/OR/BCLR/etc. to memory addresses |
| MSVC Compat | **Done** | No GCC extensions, builds clean on MSVC 2022 |
| Cross-func Branches | **Done** | Auto-detected and converted to func_table_call |
| Compilation | **Done** | Compiles + links to 2.5MB native .exe |
| Full Gameplay | **Not Yet** | Stub functions need recompilation, runtime testing |

### Code Coverage

```
ROM Size:        1,048,576 bytes (1024 KB)
Code Discovered:    ~80 KB (7.6% of ROM)
Data (gfx/snd):   ~946 KB (92.4% of ROM)
Functions:              328
Instructions:        19,209
Call Edges:             157
Jump Tables:             61
Native Binary:      2.5 MB (.exe)
Compile Errors:         0
Link Errors:            0 (4 stubs for undiscovered functions)
```

The ROM is mostly data -- graphics tiles, sprite data, sound samples, level layouts. The actual game logic is compact, which tracks for a 1992 Genesis sports game.

---

## How It Works

### The Pipeline

```
 .gen ROM file
      |
      v
 [analyze_rom.py]     -- Recursive-descent M68K disassembly
      |                   Function boundary detection
      |                   Jump table scanning
      |                   Cross-reference analysis
      v
 functions.json        -- Machine-readable function map
      |
      v
 [generate_recomp.py]  -- M68K -> C translation
      |                    Capstone disassembly -> genrecomp macros
      |                    bus_read/write for memory access
      |                    goto-based control flow
      v
 src/recomp/*.c        -- Native C code (7 files, 327 functions)
 src/main.c            -- Game lifecycle (init -> frame loop -> shutdown)
      |
      v
 [CMake + compiler]    -- Links against genrecomp + Genesis Plus GX
      |
      v
 pigskin.exe           -- Native executable, real Genesis hardware
```

### What the Recompiled Code Looks Like

Original M68K:
```asm
  0ECA24:  CLR.W   ($FF8E76).l
  0ECA2A:  CLR.W   ($FFB53A).l
  0ECA30:  MOVE.B  #$03, ($FFB9A8).l
  0ECA36:  LEA     $080000, A0
  0ECA3C:  MOVE.W  #$0040, D1
```

Recompiled C:
```c
    bus_write16(0xFF8E76, 0);
    g_m68k.flag_N = false; g_m68k.flag_Z = true;
    bus_write16(0xFFB53A, 0);
    g_m68k.flag_N = false; g_m68k.flag_Z = true;
    bus_write8(0xFFB9A8, 0x3);
    g_m68k.a[0] = 0x080000;
    g_m68k.d[1] = (g_m68k.d[1] & 0xFFFF0000u) | ((uint16_t)(0x40));
```

Every M68K instruction becomes a C statement. Registers live in `g_m68k`. Memory goes through `bus_read`/`bus_write` which hits real Genesis Plus GX hardware. Branches become `goto`. Calls go through `func_table_call()`.

---

## Building

### Prerequisites

- CMake 3.16+
- C compiler (MSVC, Clang, or GCC)
- SDL2 development libraries
- [genrecomp](https://github.com/sp00nznet/genrecomp) checked out alongside this project

### Directory Layout

```
gen/
  genrecomp/        <-- Genesis recomp toolkit
  pigskin/          <-- This project (you are here)
```

### Build

```bash
cd pigskin
cmake -B build
cmake --build build
```

### Run

```bash
./build/pigskin "Jerry Glanville's Pigskin Footbrawl (USA).gen"
```

You'll need the original ROM file. This project does not include it.

---

## Tools

### `tools/analyze_rom.py`

Disassembles the ROM and discovers functions:

```bash
python tools/analyze_rom.py rom.gen --stats --output functions.json
```

Options:
- `--stats` -- Print function size rankings and coverage stats
- `--disasm` -- Full disassembly dump
- `--disasm-func 0E8FE0` -- Disassemble a specific function

### `tools/generate_recomp.py`

Generates recompiled C from the ROM:

```bash
python tools/generate_recomp.py rom.gen --output-dir src/recomp/
```

---

## Architecture

Built on the [genrecomp](https://github.com/sp00nznet/genrecomp) toolkit, which provides:

- **M68K CPU Context** -- D0-D7, A0-A7, all flags, all 16 condition codes, complete arithmetic/shift/rotate macros
- **Memory Bus** -- 24-bit big-endian, routed through Genesis Plus GX
- **VDP** -- Real Video Display Processor rendering (320x224)
- **YM2612** -- Real FM synthesis audio
- **PSG** -- SN76489 programmable sound generator
- **Z80** -- Sound driver coprocessor
- **I/O** -- Controller input (3-button and 6-button pads)
- **SDL2 Platform** -- Window, audio output, keyboard/gamepad input

---

## What's Next

- [x] ~~Implement MOVEM~~ -- Done! Full register list parsing
- [x] ~~Resolve indirect JSR/JMP~~ -- Done! 14 genuine indirect calls handled
- [x] ~~Memory-destination operations~~ -- Done! ADD/SUB/AND/OR/BCLR/etc. to memory
- [x] ~~MSVC compatibility~~ -- Done! Builds clean on Visual Studio 2022
- [x] ~~Cross-function branch detection~~ -- Done! Auto-converted to func_table_call
- [x] ~~Compile + link~~ -- Done! 2.5MB native executable
- [ ] Recompile the 4 stub functions ($0E8FE0, $0EAD36, $0FB294, $0FB1C2)
- [ ] Test with a Genesis emulator side-by-side for comparison debugging
- [ ] Map RAM addresses to meaningful variable names
- [ ] Identify and label game subsystems (rendering, input, AI, sound)
- [ ] Get to title screen
- [ ] Get to gameplay
- [ ] Full playable recompilation

---

## Related Projects

This is part of the [sp00nznet](https://github.com/sp00nznet) recompilation ecosystem:

- [genrecomp](https://github.com/sp00nznet/genrecomp) -- Genesis/Mega Drive recomp toolkit (what powers this project)
- [recompclass](https://github.com/sp00nznet/recompclass) -- Learn static recompilation from scratch

---

## License

MIT. The recompilation tools and generated code are open source. You'll need your own legally obtained ROM to use this.
