#!/usr/bin/env python3
"""Patch pinned i3lock presentation and reveal gating, preserving PAM and grabs."""
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEADERS = ("ooonana_lock_visuals.h", "ooonana_lock_interaction.h")
INPUTS = ("scripts/patch-i3lock-visuals.py", *(f"packages/i3lock/{name}" for name in HEADERS))


def replacements():
    return {
        "i3lock.c": [
            ("\nstatic void discard_passwd_cb(", '\n#include "ooonana_lock_interaction.h"\n\nstatic void discard_passwd_cb('),
            ("    ksym = xkb_state_key_get_one_sym(xkb_state, event->detail);\n",
             "    ksym = xkb_state_key_get_one_sym(xkb_state, event->detail);\n"
             "    if (ooonana_key_gate(event, ksym)) return;\n"),
            ("                handle_key_press((xcb_key_press_event_t *)event);\n                break;\n",
             "                handle_key_press((xcb_key_press_event_t *)event);\n                break;\n\n"
             "            case XCB_KEY_RELEASE:\n"
             "                ooonana_key_released((xcb_key_release_event_t *)event);\n"
             "                break;\n\n"
             "            case XCB_BUTTON_PRESS:\n"
             "                ooonana_pointer_pressed((xcb_button_press_event_t *)event);\n"
             "                break;\n\n"
             "            case XCB_BUTTON_RELEASE:\n"
             "                ooonana_pointer_released((xcb_button_release_event_t *)event);\n"
             "                break;\n"),
            ("    ev_invoke(main_loop, xcb_check, 0);\n",
             "    ooonana_start_ui();\n    ev_invoke(main_loop, xcb_check, 0);\n"),
            ("    if (image_raw_format != NULL && image_path != NULL) {",
             "    const char *wallpaper = getenv(\"OOONANA_LOCK_WALLPAPER\");\n"
             "    if (ooonana_active() && !image_path && wallpaper && *wallpaper) image_path = strdup(wallpaper);\n"
             "    if (image_raw_format != NULL && image_path != NULL) {"),
        ],
        "xcb.c": [
            ("XCB_NONE,            /* which events to let through */",
             "getenv(\"OOONANA_LOCK_VISUALS\") ? XCB_EVENT_MASK_BUTTON_PRESS | XCB_EVENT_MASK_BUTTON_RELEASE : XCB_NONE,"),
        ],
        "unlock_indicator.c": [
            ("static void display_button_text(\n", '#include "ooonana_lock_visuals.h"\n\nstatic void display_button_text(\n'),
            ("    if (img) {\n", "    if (img && !ooonana_lock_visuals()) {\n"),
            ("    if (unlock_indicator &&\n",
             "    ooonana_lock_heading(xcb_ctx, resolution, scaling_factor);\n"
             "    if (unlock_indicator && !ooonana_lock_visuals() &&\n"),
        ],
    }


def revert_main(text):
    for before, after in reversed(replacements()["i3lock.c"]):
        if text.count(after) != 1:
            raise ValueError("Missing or duplicated lock UI patch in pinned main source")
        text = text.replace(after, before)
    return text


def patch(source):
    results = {}
    for name, changes in replacements().items():
        path = source / name
        text = path.read_text(encoding="utf-8")
        for before, after in changes:
            if after in text or text.count(before) != 1:
                raise ValueError("Unexpected pinned source anchor in " + name + ": " + before[:70])
            text = text.replace(before, after)
        results[path] = text
    for name in HEADERS:
        header = source / name
        if header.exists():
            raise ValueError("Existing lock presentation header")
        results[header] = (ROOT / "packages/i3lock" / name).read_text(encoding="utf-8")
    # Validate the whole patch before writing any source file.
    for path, text in results.items():
        path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    patch(parser.parse_args().source)
