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
| ROM Analysis | **Done** | 1,164 functions, 19,291 instructions discovered |
| Code Generation | **Done** | ~60K lines of recompiled C across 24 source files |
| Function Registration | **Done** | All 1,164 functions registered in dispatch table |
| Cross-func Resolution | **Done** | Iterative splitting until all call targets are registered |
| Entry Point | **Done** | Genesis init -> main game loop wired up |
| VBlank Handler | **Done** | IRQ6 handler ($0E9220) connected + VBlank callback |
| Jump Table Discovery | **Done** | 61 jump tables, 209 targets found |
| Prologue Scanning | **Done** | LINK/MOVEM patterns in unvisited ROM |
| Build System | **Done** | CMake + MSVC, links against genrecomp |
| MOVEM Support | **Done** | Full register list parsing, push/pop/load/store |
| BTST Memory Fix | **Done** | Memory BTST always byte-sized (Capstone says .l, wrong) |
| Memory-dest Ops | **Done** | ADD/SUB/AND/OR/BCLR/etc. to memory addresses |
| MSVC Compat | **Done** | No GCC extensions, builds clean on MSVC 2022 |
| Cross-func Branches | **Done** | Auto-detected and converted to func_table_call |
| VDP Cycle Sim | **Done** | v_counter advances during bus accesses |
| DMA Busy Flag | **Done** | Auto-cleared so DMA wait loops don't spin forever |
| Z80 Bus Grant | **Done** | Pre-granted, I/O stubs prevent fm_reset crashes |
| TRAP Dispatch | **Done** | TRAP instructions call their vector handlers |
| Hardware Init | **Done** | Boots through VDP/Z80/DMA init to task scheduler |
| Compilation | **Done** | Compiles + links to native .exe, zero errors |
| Task Scheduler | **In Progress** | Game uses RAM function pointers for task dispatch |
| Full Gameplay | **Not Yet** | Need indirect call resolution for task system |

### Code Coverage

```
ROM Size:        1,048,576 bytes (1024 KB)
Code Discovered:    ~80 KB (7.6% of ROM)
Data (gfx/snd):   ~946 KB (92.4% of ROM)
Functions:            1,164 (346 from analysis + 818 from cross-func splitting)
Instructions:        19,291
Call Edges:             176
Jump Tables:             61
Explicit Seeds:          10
Prologue Patterns:        9
Native Binary:        ~3 MB (.exe)
Compile Errors:          0
Link Errors:             0
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
      |                   Jump table + prologue scanning
      |                   Explicit seed addresses
      v
 functions.json        -- Machine-readable function map
      |
      v
 [generate_recomp.py]  -- M68K -> C translation
      |                    Iterative cross-function resolution
      |                    BTST memory fix (always byte-sized)
      |                    TRAP -> func_table_call dispatch
      v
 src/recomp/*.c        -- Native C code (24 files, 1,164 functions)
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

## Runtime Fixes

The recompiled code runs natively, but several Genesis hardware behaviors need simulation:

- **VDP Cycle Simulation** -- The VDP V/H counter advances during bus accesses so scanline-polling loops terminate naturally
- **DMA Busy Auto-Clear** -- VDP DMA completes "instantly" in recompiled code since there's no cycle-accurate interleaving
- **Z80 Bus Pre-Grant** -- The Z80 bus is pre-granted and BUSREQ/RESET writes are stubbed to prevent fm_reset crashes
- **VBlank Callback** -- VBlank handler fires automatically when the simulated scanline counter crosses line 224
- **TRAP Dispatch** -- TRAP instructions push SR/PC on the emulated stack and dispatch to the vector handler via func_table_call

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

Features:
- Recursive-descent from vectors + jump table targets
- Explicit seed addresses for functions unreachable by static analysis
- Prologue scanning (LINK A5/A6, MOVEM.L patterns) in unvisited ROM
- Address-load pattern detection (LEA, PEA, MOVE.L #imm)

### `tools/generate_recomp.py`

Generates recompiled C from the ROM:

```bash
python tools/generate_recomp.py rom.gen --output-dir src/recomp/
```

Features:
- Iterative cross-function target resolution (splits functions until stable)
- BTST memory operand fix (always byte-sized regardless of Capstone suffix)
- All M68K addressing modes including post-increment, pre-decrement, indexed
- TRAP instruction dispatch to vector handlers

---

## Architecture

Built on the [genrecomp](https://github.com/sp00nznet/genrecomp) toolkit, which provides:

- **M68K CPU Context** -- D0-D7, A0-A7, all flags, all 16 condition codes, complete arithmetic/shift/rotate macros
- **Memory Bus** -- 24-bit big-endian with cycle simulation, routed through Genesis Plus GX
- **VDP** -- Real Video Display Processor rendering (320x224) with HV counter simulation
- **YM2612** -- Real FM synthesis audio (via ymfm)
- **PSG** -- SN76489 programmable sound generator
- **Z80** -- Sound driver coprocessor (RAM mapped for M68K access)
- **I/O** -- Controller input (3-button and 6-button pads)
- **SDL2 Platform** -- Window, audio output, keyboard/gamepad input

---

## What's Next

- [x] ~~Implement MOVEM~~ -- Full register list parsing
- [x] ~~Memory-destination operations~~ -- ADD/SUB/AND/OR/BCLR/etc. to memory
- [x] ~~MSVC compatibility~~ -- Builds clean on Visual Studio 2022
- [x] ~~Cross-function branch detection~~ -- Auto-converted to func_table_call
- [x] ~~Compile + link~~ -- Native executable, zero errors
- [x] ~~Recompile stub functions~~ -- All 4 stubs replaced with real code
- [x] ~~BTST memory fix~~ -- Byte-sized reads for memory BTST (Capstone bug)
- [x] ~~VDP cycle simulation~~ -- Scanline counter advances during execution
- [x] ~~DMA busy flag~~ -- Auto-cleared on bus access
- [x] ~~Z80 bus management~~ -- Pre-granted, safe I/O stubs
- [x] ~~TRAP dispatch~~ -- Handlers called via func_table_call
- [x] ~~Iterative function splitting~~ -- 346 -> 1,164 functions
- [x] ~~Hardware init boot~~ -- Past VDP/Z80/DMA init to task scheduler
- [ ] Resolve RAM-stored function pointers (task scheduler indirect calls)
- [ ] Implement task fiber/coroutine system for TRAP-based scheduling
- [ ] Test with a Genesis emulator side-by-side for comparison debugging
- [ ] Map RAM addresses to meaningful variable names
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
