#!/usr/bin/env python3
"""Opt-in titlebar room for native-sized controls; pinned i3 4.24 source only."""
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FRAME_THEME_C = r'''/* Palette-only IPC: never parse config, change gaps/modes, or restart. */
static bool ooonana_frame_theme(ipc_client *client, const uint8_t *message, uint32_t message_size) {
    static const char prefix[] = "ooonana_frame_theme";
    if (message_size < sizeof(prefix) - 1 || memcmp(message, prefix, sizeof(prefix) - 1) != 0) {
        return false;
    }
    const bool light = message_size == sizeof("ooonana_frame_theme light") - 1 &&
        memcmp(message, "ooonana_frame_theme light", message_size) == 0;
    const bool dark = message_size == sizeof("ooonana_frame_theme dark") - 1 &&
        memcmp(message, "ooonana_frame_theme dark", message_size) == 0;
    const bool success = ooonana_control_scale() > 0 && (light || dark);
    if (success) {
        /* background, text, indicator; keep frame edges blended into header. */
        static const char *const paper[4][3] = {
            {"#ffffff", "#805600", "#805600"},
            {"#e9edf1", "#55616e", "#adb7c2"},
            {"#f5f5f7", "#55616e", "#adb7c2"},
            {"#fae9e7", "#9e2929", "#9e2929"}
        };
        static const char *const graphite[4][3] = {
            {"#1b1f26", "#ffb21a", "#ffb21a"},
            {"#101317", "#b4bdc8", "#414957"},
            {"#171b21", "#b4bdc8", "#414957"},
            {"#3b2324", "#ff675c", "#ff675c"}
        };
        const char *const (*palette)[3] = light ? paper : graphite;
        struct Colortriple *targets[] = {&config.client.focused, &config.client.unfocused,
            &config.client.focused_inactive, &config.client.urgent};
        for (int i = 0; i < 4; i++) {
            targets[i]->background = draw_util_hex_to_color(palette[i][0]);
            targets[i]->border = targets[i]->child_border = targets[i]->background;
            targets[i]->text = draw_util_hex_to_color(palette[i][1]);
            targets[i]->indicator = draw_util_hex_to_color(palette[i][2]);
        }
        if (!config.client.got_focused_tab_title) {
            config.client.focused_tab_title = config.client.focused_inactive;
        }
        Con *con;
        TAILQ_FOREACH (con, &all_cons, all_cons) {
            FREE(con->deco_render_params);
        }
        tree_render();
    }
    const char *reply = success ? "[{\"success\":true}]" : "[{\"success\":false,\"error\":\"Invalid or disabled Ooonana frame theme\"}]";
    ipc_send_client_message(client, strlen(reply), I3_IPC_REPLY_TYPE_COMMAND, (const uint8_t *)reply);
    return true;
}

'''


def replacements():
    return {
        "src/render.c": [
            ('#include "all.h"\n', '#include "all.h"\n#include "ooonana_controls.h"\n'),
            ("    return deco_height;\n", "    return max(deco_height, ooonana_titlebar_height());\n"),
        ],
        "src/x.c": [
            ('#include "all.h"\n', '#include "all.h"\n#include "ooonana_controls.h"\n'),
            ("    const int deco_width = (int)con->deco_rect.width;\n",
             "    const int control_space = win ? ooonana_titlebar_left((int)con->deco_rect.width) : 0;\n"
             "    const int deco_width = max(0, (int)con->deco_rect.width - control_space);\n"
             "    const int deco_x = con->deco_rect.x + control_space;\n"
             "    if (deco_width == 0) {\n        goto copy_pixmaps;\n    }\n"),
            ("con->deco_rect.x + mark_offset_x,", "deco_x + mark_offset_x,"),
            ("con->deco_rect.x + title_offset_x,", "deco_x + title_offset_x,"),
            ("con->deco_rect.x + icon_offset_x,", "deco_x + icon_offset_x,"),
        ],
        "libi3/font.c": [
            ('#include "libi3.h"\n', '#include "libi3.h"\n#include "ooonana_controls.h"\n'),
            ('    pango_cairo_context_set_resolution(context, get_dpi_value());\n',
             '    pango_cairo_context_set_resolution(context, ooonana_font_dpi(get_dpi_value()));\n'),
        ],
        "src/ipc.c": [
            ('#include "all.h"\n', '#include "all.h"\n#include "ooonana_controls.h"\n'),
            ('    ystr("human_readable");\n    ystr(i3_version);\n',
             '    ystr("human_readable");\n    ystr(i3_version);\n\n'
             '    ystr("ooonana_control_api");\n    y(integer, 1);\n'
             '    ystr("ooonana_control_scale");\n    y(integer, ooonana_control_scale());\n'
             '    ystr("ooonana_frame_theme_api");\n    y(integer, ooonana_control_scale() > 0 ? 1 : 0);\n'),
            ('IPC_HANDLER(run_command) {\n', FRAME_THEME_C +
             'IPC_HANDLER(run_command) {\n'
             '    if (ooonana_frame_theme(client, message, message_size)) {\n        return;\n    }\n'),
        ],
        "src/handlers.c": [
            ('#include "all.h"\n', '#include "all.h"\n#include "ooonana_controls.h"\n'),
            ('    } else if (atom == A__NET_WM_STATE_DEMANDS_ATTENTION) {\n',
             '    } else if (ooonana_control_scale() > 0 && atom == A__NET_WM_STATE_MAXIMIZED_VERT) {\n'
             '        /* Native/client-owned maximize buttons share Ooonana fullscreen.\n'
             '         * Only VERT acts: GTK sends both axes in one message. */\n'
             '        if (change == _NET_WM_STATE_TOGGLE ||\n'
             '            (con->fullscreen_mode != CF_NONE && change == _NET_WM_STATE_REMOVE) ||\n'
             '            (con->fullscreen_mode == CF_NONE && change == _NET_WM_STATE_ADD)) {\n'
             '            con_toggle_fullscreen(con, CF_OUTPUT);\n        }\n'
             '    } else if (atom == A__NET_WM_STATE_DEMANDS_ATTENTION) {\n'),
            ('                                A_WM_STATE, A_WM_STATE, 32, 2, data);\n',
             '                                A_WM_STATE, A_WM_STATE, 32, 2, data);\n'
             '            if (ooonana_control_scale() > 0 && event->format == 32) {\n'
             '                Con *con = con_by_window_id(event->window);\n'
             '                if (con != NULL) {\n'
             '                    scratchpad_move(con);\n                    tree_render();\n'
             '                }\n            }\n'),
        ],
    }


def patch(source, check=False):
    if source.is_symlink():
        raise ValueError("Expected real extracted source directory")
    source = source.resolve(strict=True)
    if source == ROOT or not source.is_dir() or source.name != "i3-4.24":
        raise ValueError("Expected separate extracted i3 source")
    changes = {}
    for name, edits in replacements().items():
        path = source / name
        if path.is_symlink() or not path.resolve(strict=True).is_relative_to(source):
            raise ValueError("Source path escapes candidate: " + name)
        text = path.read_text(encoding="utf-8")
        if "ooonana_controls.h" in text:
            raise ValueError("Source already modified: " + name)
        for before, after in edits:
            if text.count(before) != 1:
                raise ValueError("Pinned i3 4.24 source differs: " + name + " / " + before.strip())
            text = text.replace(before, after, 1)
        changes[path] = text
    header = source / "include/ooonana_controls.h"
    if header.exists() or header.is_symlink() or not header.parent.resolve(strict=True).is_relative_to(source):
        raise ValueError("Refusing existing/escaped controls header")
    # Check every hunk/path before any source write; never a partial version guess.
    if not check:
        for path, text in changes.items():
            path.write_text(text, encoding="utf-8", newline="\n")
        header.write_bytes((ROOT / "packages/i3wm/ooonana_controls.h").read_bytes())
    return len(changes)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    print("I3_CONTROLS_SOURCE_OK", patch(args.source, args.check), "files; check=" + str(args.check))
