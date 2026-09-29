/*
 * Pigskin Footbrawl -- Statically Recompiled
 *
 * Original ROM: PIGSKIN ((C) RSI 1992.SEP)
 *
 * The game's main loop runs inside entry_point() and never returns; it
 * waits for frames in TRAP #0 (spin until the VBlank counter $FF3850
 * reaches $FFFD18) and sends sound commands with TRAP #4. So the frame is
 * driven from genrecomp's scanline clock: at VBlank it calls
 * pigskin_vblank(), which runs the game's VBlank handler and presents.
 * Debugging workflow: docs/debugging.md.
 */

#include <genrecomp/genrecomp.h>
#include <genrecomp/bus.h>
#include <genrecomp/input.h>
#include <genrecomp/platform.h>
#include <genrecomp/func_table.h>
#include "recomp/recomp_funcs.h"
#include <stdio.h>
#include <stdlib.h>

static int s_frame_count = 0;

/* VBlank callback — called from bus_tick_cycles when the simulated
 * scanline counter crosses the active display boundary.
 *
 * IMPORTANT: This runs inside bus_tick_cycles with a reentrancy guard,
 * so we can't call genrecomp_end_frame() here (it does bus accesses
 * that would re-enter). Instead, just run the game's VBlank handler
 * and set a flag for frame rendering. Frame rendering happens in a
 * separate hook. */
static void pigskin_vblank(void) {
    /* Poll SDL events and update input BEFORE the game's VBlank handler,
     * so the game sees fresh input state when it reads I/O ports. */
    if (!genrecomp_begin_frame()) {
        printf("\nWindow closed, exiting.\n");
        genrecomp_shutdown();
        exit(0);
    }

    /* Run the game's VBlank handler AFTER input update */
    func_table_call(0x0E9220); /* vec_irq6_vblank, via the dispatcher so its tail jumps run */

    /* Render VDP output and present frame */
    genrecomp_end_frame();


    s_frame_count++;
    if (s_frame_count <= 10 || (s_frame_count % 60 == 0)) {
        printf("Frame %d (SP=$%08X)\n", s_frame_count, g_m68k.a[7]);
        /* PIGSKIN_STACK=1: where is the main thread? (see docs/debugging.md) */
        if (getenv("PIGSKIN_STACK")) {
            func_table_dump_stack(stdout);
            printf("  a0=%06X a1=%06X a2=%06X d0=%08X d1=%08X\n",
                   g_m68k.a[0], g_m68k.a[1], g_m68k.a[2], g_m68k.d[0], g_m68k.d[1]);
        }
        fflush(stdout);
    }
}

int main(int argc, char *argv[]) {
    argc = platform_parse_args(argc, argv);

    printf("Pigskin Footbrawl -- Static Recompilation\n");
    printf("==========================================\n\n");

    if (!genrecomp_init("Pigskin Footbrawl (Recompiled)", 3)) {
        fprintf(stderr, "Failed to initialize genrecomp\n");
        return 1;
    }

    /* Load original ROM for data (graphics, sound, tables) */
    const char *rom_path = (argc > 1) ? argv[1]
        : "Jerry Glanville's Pigskin Footbrawl (USA).gen";
    if (!genrecomp_load_rom(rom_path)) {
        fprintf(stderr, "Failed to load ROM: %s\n", rom_path);
        return 1;
    }

    /* Register all recompiled functions */
    recomp_register_all();

    /* Register VBlank callback — this drives the entire frame loop
     * since the game never returns from entry_point(). */
    bus_set_vblank_callback(pigskin_vblank);

    /* Set initial CPU state */
    g_m68k.a[7] = 0xFFFD00;
    g_m68k.pc = 0x000200;
    m68k_set_sr(0x2700); /* supervisor mode, all interrupts masked */

    /* Run the game. This call never returns — the game's main loop
     * runs inside via TRAP-based cooperative scheduling, with frame
     * rendering handled by the VBlank callback above. */
    printf("Starting game...\n");
    fflush(stdout);
    func_table_call(0x000200); /* entry_point */

    /* If we somehow get here, clean up */
    printf("entry_point() returned unexpectedly\n");
    genrecomp_shutdown();
    return 0;
}