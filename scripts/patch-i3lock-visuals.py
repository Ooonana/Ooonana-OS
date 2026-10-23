#!/usr/bin/env python3
"""Exact pinned i3lock2.16 presentation patch. Authentication/input unchanged."""
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TICK = '''/* Ooonana clock: minute-aligned redraw only, no input/auth state changes. */
static void ooonana_clock_tick(EV_P_ ev_periodic *watcher, int revents) {
    (void)watcher;
    (void)revents;
    redraw_screen();
}

'''
START = '''    const char *ooonana_visuals = getenv("OOONANA_LOCK_VISUALS");
    if (ooonana_visuals && strcmp(ooonana_visuals, "1") == 0) {
        static ev_periodic ooonana_clock;
        ev_periodic_init(&ooonana_clock, ooonana_clock_tick, 0., 60., NULL);
        ev_periodic_start(main_loop, &ooonana_clock);
    }
'''


def replacements():
    return {
        "i3lock.c": [
            ("static void input_done(void);\n", "static void input_done(void);\n" + TICK),
            ("    ev_loop(main_loop, 0);\n", START + "    ev_loop(main_loop, 0);\n"),
        ],
        "unlock_indicator.c": [
            ("#define BUTTON_RADIUS 90", "#define BUTTON_RADIUS (ooonana_lock_visuals() ? 54 : 90)"),
            ("static void display_button_text(\n", '#include "ooonana_lock_visuals.h"\n\nstatic void display_button_text(\n'),
            ("    if (use_dark_text) {", "    if (ooonana_lock_visuals()) {\n        ooonana_lock_ink(ctx);\n    } else if (use_dark_text) {"),
            ("    if (unlock_indicator &&\n", "    ooonana_lock_heading(xcb_ctx, resolution, scaling_factor);\n    if (unlock_indicator &&\n"),
            ("        cairo_set_line_width(ctx, 10.0);", "        cairo_set_line_width(ctx, ooonana_lock_visuals() ? 4.0 : 10.0);"),
            ("        cairo_fill_preserve(ctx);", "        if (ooonana_lock_visuals()) ooonana_lock_fill(ctx);\n        cairo_fill_preserve(ctx);"),
            ("        cairo_stroke(ctx);\n\n        /* Draw an inner seperator line. */", "        if (ooonana_lock_visuals()) ooonana_lock_stroke(ctx);\n        cairo_stroke(ctx);\n\n        /* Draw an inner seperator line. */"),
            ("        cairo_set_line_width(ctx, 2.0);", "        cairo_set_line_width(ctx, ooonana_lock_visuals() ? 1.0 : 2.0);"),
            ("        char buf[4];", "        char buf[16];"),
            ("        cairo_set_font_size(ctx, 28.0);", "        cairo_set_font_size(ctx, ooonana_lock_visuals() ? 16.0 : 28.0);"),
            ('                text = "Wrong!";', '                text = ooonana_lock_visuals() ? "Try again" : "Wrong!";'),
            ('                        snprintf(buf, sizeof(buf), "%d", failed_attempts);', '                        snprintf(buf, sizeof(buf), ooonana_lock_visuals() ? "%d failed" : "%d", failed_attempts);'),
            ("                    cairo_set_font_size(ctx, 32.0);", "                    cairo_set_font_size(ctx, ooonana_lock_visuals() ? 14.0 : 32.0);"),
            ("            cairo_set_font_size(ctx, 14.0);", "            cairo_set_font_size(ctx, ooonana_lock_visuals() ? 12.0 : 14.0);"),
            ("display_button_text(ctx, modifier_string, 28., use_dark_text);", "display_button_text(ctx, modifier_string, ooonana_lock_visuals() ? 20. : 28., use_dark_text);"),
            ("display_button_text(ctx, layout_string, -28., use_dark_text);", "display_button_text(ctx, layout_string, ooonana_lock_visuals() ? -20. : -28., use_dark_text);"),
        ],
    }


def patch(source):
    results = {}
    for name, changes in replacements().items():
        path = source / name
        text = path.read_text()
        if "ooonana_lock_visuals" in text or "ooonana_clock_tick" in text:
            raise ValueError("Already patched i3lock source")
        for before, after in changes:
            expected = 2 if before.strip() in ("cairo_set_line_width(ctx, 10.0);", "cairo_set_font_size(ctx, 14.0);") else 1
            if text.count(before) != expected:
                raise ValueError("Unexpected pinned source anchor in " + name + ": " + before[:70])
            text = text.replace(before, after)
        results[path] = text
    header = source / "ooonana_lock_visuals.h"
    if header.exists():
        raise ValueError("Existing lock presentation header")
    # Validate whole patch before writing any source file.
    for path, text in results.items():
        path.write_text(text)
    header.write_text((ROOT / "packages/i3lock/ooonana_lock_visuals.h").read_text())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    patch(parser.parse_args().source)
