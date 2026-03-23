/*
 * Pigskin Footbrawl -- Statically Recompiled
 * Auto-generated main entry point
 *
 * Original ROM: PIGSKIN ((C) RSI 1992.SEP)
 */

#include <genrecomp/genrecomp.h>
#include <genrecomp/bus.h>
#include "recomp/recomp_funcs.h"
#include <stdio.h>

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

    /* Register VBlank callback so VBlank-driven counters advance
     * during tight polling loops (TRAP #0 wait-for-VBlank etc.) */
    bus_set_vblank_callback(vec_irq6_vblank);

    /* Set initial CPU state */
    g_m68k.a[7] = 0xFFFD00;
    g_m68k.pc = 0x000200;
    m68k_set_sr(0x2700); /* supervisor mode, all interrupts masked */

    /* Run initialization (original entry point at $000200) */
    printf("Running entry_point()...\n");
    fflush(stdout);
    entry_point();
    printf("entry_point() returned, entering main loop\n");
    fflush(stdout);

    /* Main game loop */
    int frame = 0;
    while (genrecomp_begin_frame()) {
        /* Trigger VBlank and run VBlank handler */
        genrecomp_trigger_vblank();
        vec_irq6_vblank();

        genrecomp_end_frame();

        if (frame < 10 || (frame % 60 == 0)) {
            printf("Frame %d complete\n", frame);
            fflush(stdout);
        }
        frame++;
    }

    genrecomp_shutdown();
    return 0;
}