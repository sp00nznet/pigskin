/*
 * Pigskin Footbrawl -- Statically Recompiled
 *
 * Original ROM: PIGSKIN ((C) RSI 1992.SEP)
 *
 * This game uses a TRAP-based cooperative task scheduler. The game's main
 * loop runs INSIDE entry_point() and never returns — it yields via TRAP #0
 * (wait for VBlank) and TRAP #4 (yield to scheduler). The VBlank callback
 * handles frame rendering and SDL event pumping.
 */

#include <genrecomp/genrecomp.h>
#include <genrecomp/bus.h>
#include <genrecomp/input.h>
#include "recomp/recomp_funcs.h"
#include <stdio.h>

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
    vec_irq6_vblank();

    /* Render VDP output and present frame */
    genrecomp_end_frame();


    s_frame_count++;
    if (s_frame_count <= 10 || (s_frame_count % 60 == 0)) {
        printf("Frame %d (SP=$%08X)\n", s_frame_count, g_m68k.a[7]);
        fflush(stdout);
    }
}

int main(int argc, char *argv[]) {
    (void)argc; (void)argv;

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
    printf("Registered %d recompiled functions\n\n", 1164);

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
    entry_point();

    /* If we somehow get here, clean up */
    printf("entry_point() returned unexpectedly\n");
    genrecomp_shutdown();
    return 0;
}