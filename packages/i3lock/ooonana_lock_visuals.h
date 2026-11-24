/* Ooonana's X11 lock presentation. No password bytes or authentication here. */
#include <time.h>

extern double ooonana_reveal;
extern int ooonana_power_menu, ooonana_battery;
extern bool ooonana_power_error, ooonana_caps_lock(void);
extern char ooonana_account[64];

static bool ooonana_lock_visuals(void) {
    const char *value = getenv("OOONANA_LOCK_VISUALS");
    return value && strcmp(value, "1") == 0;
}

static bool ooonana_light_mode(void) {
    return strcmp(color, "f5f5f7") == 0;
}

static void ooonana_rgb(cairo_t *ctx, unsigned int rgb) {
    cairo_set_source_rgb(ctx, ((rgb >> 16) & 255) / 255.0,
                         ((rgb >> 8) & 255) / 255.0, (rgb & 255) / 255.0);
}

static void ooonana_rounded_rect(cairo_t *ctx, double x, double y, double w, double h, double r) {
    cairo_new_sub_path(ctx);
    cairo_arc(ctx, x + w - r, y + r, r, -M_PI / 2, 0);
    cairo_arc(ctx, x + w - r, y + h - r, r, 0, M_PI / 2);
    cairo_arc(ctx, x + r, y + h - r, r, M_PI / 2, M_PI);
    cairo_arc(ctx, x + r, y + r, r, M_PI, 3 * M_PI / 2);
    cairo_close_path(ctx);
}

static void ooonana_center(cairo_t *ctx, const char *text, double x, double baseline, double size) {
    cairo_text_extents_t extents;
    cairo_save(ctx);
    for (const unsigned char *character = (const unsigned char *)text; *character; character++) {
        if (*character >= 0xe0) {
            cairo_select_font_face(ctx, "Noto Sans CJK KR", CAIRO_FONT_SLANT_NORMAL, CAIRO_FONT_WEIGHT_NORMAL);
            break;
        }
    }
    char visible[256];
    size_t length = strnlen(text, sizeof(visible) - 4);
    bool truncated = text[length] != '\0';
    while (length && ((unsigned char)text[length] & 0xc0) == 0x80) length--;
    cairo_set_font_size(ctx, size);
    for (;;) {
        memcpy(visible, text, length);
        strcpy(visible + length, truncated ? "..." : "");
        cairo_text_extents(ctx, visible, &extents);
        if (extents.width <= 280 || !length) break;
        truncated = true;
        do { length--; } while (length && ((unsigned char)text[length] & 0xc0) == 0x80);
    }
    cairo_move_to(ctx, x - extents.width / 2 - extents.x_bearing, baseline);
    cairo_show_text(ctx, visible);
    cairo_restore(ctx);
}

/* Tabular display digits, with rounded ends even on vertical strokes. */
static void ooonana_digit(cairo_t *ctx, char digit) {
    switch (digit) {
        case '0':
            cairo_move_to(ctx, 17, 4);
            cairo_curve_to(ctx, 8, 4, 6, 12, 6, 21);
            cairo_curve_to(ctx, 6, 30, 8, 38, 17, 38);
            cairo_curve_to(ctx, 26, 38, 28, 30, 28, 21);
            cairo_curve_to(ctx, 28, 12, 26, 4, 17, 4);
            cairo_close_path(ctx);
            break;
        case '1':
            cairo_move_to(ctx, 8, 11);
            cairo_line_to(ctx, 18, 4);
            cairo_line_to(ctx, 18, 38);
            cairo_move_to(ctx, 8, 38);
            cairo_line_to(ctx, 27, 38);
            break;
        case '2':
            cairo_move_to(ctx, 7, 10);
            cairo_curve_to(ctx, 13, 0, 28, 3, 27, 12);
            cairo_curve_to(ctx, 26, 22, 10, 27, 7, 38);
            cairo_line_to(ctx, 28, 38);
            break;
        case '3':
            cairo_move_to(ctx, 7, 4);
            cairo_line_to(ctx, 27, 4);
            cairo_line_to(ctx, 17, 18);
            cairo_curve_to(ctx, 33, 17, 34, 38, 18, 38);
            cairo_curve_to(ctx, 13, 38, 9, 36, 6, 33);
            break;
        case '4':
            cairo_move_to(ctx, 22, 4);
            cairo_line_to(ctx, 5, 26);
            cairo_line_to(ctx, 29, 26);
            cairo_move_to(ctx, 23, 15);
            cairo_line_to(ctx, 23, 38);
            break;
        case '5':
            cairo_move_to(ctx, 27, 4);
            cairo_line_to(ctx, 9, 4);
            cairo_line_to(ctx, 7, 20);
            cairo_curve_to(ctx, 15, 15, 28, 17, 28, 27);
            cairo_curve_to(ctx, 28, 39, 14, 41, 6, 34);
            break;
        case '6':
            cairo_move_to(ctx, 26, 5);
            cairo_curve_to(ctx, 14, 1, 6, 12, 6, 26);
            cairo_curve_to(ctx, 6, 42, 29, 42, 28, 27);
            cairo_curve_to(ctx, 28, 17, 15, 15, 7, 23);
            break;
        case '7':
            cairo_move_to(ctx, 6, 4);
            cairo_line_to(ctx, 28, 4);
            cairo_curve_to(ctx, 21, 15, 16, 26, 13, 38);
            break;
        case '8':
            cairo_move_to(ctx, 17, 21);
            cairo_curve_to(ctx, 3, 21, 3, 4, 17, 4);
            cairo_curve_to(ctx, 31, 4, 31, 21, 17, 21);
            cairo_curve_to(ctx, 2, 21, 2, 38, 17, 38);
            cairo_curve_to(ctx, 32, 38, 32, 21, 17, 21);
            cairo_close_path(ctx);
            break;
        case '9':
            cairo_move_to(ctx, 27, 19);
            cairo_curve_to(ctx, 19, 27, 6, 25, 6, 15);
            cairo_curve_to(ctx, 5, 0, 28, 0, 28, 16);
            cairo_curve_to(ctx, 28, 30, 20, 39, 9, 38);
            break;
    }
    cairo_stroke(ctx);
}

static void ooonana_clock(cairo_t *ctx, const char *time, double x, double center, double size) {
    const double advance = 34, separator = 18;
    double scale = size / 48;
    cairo_save(ctx);
    cairo_translate(ctx, x - (4 * advance + separator) / 2 * scale, center - 21 * scale);
    cairo_scale(ctx, scale, scale);
    cairo_set_line_cap(ctx, CAIRO_LINE_CAP_ROUND);
    cairo_set_line_join(ctx, CAIRO_LINE_JOIN_ROUND);
    cairo_set_line_width(ctx, 9.5);
    for (const char *character = time; *character; character++) {
        if (*character == ':') {
            cairo_arc(ctx, separator / 2, 13, 4.5, 0, 2 * M_PI);
            cairo_fill(ctx);
            cairo_arc(ctx, separator / 2, 29, 4.5, 0, 2 * M_PI);
            cairo_fill(ctx);
            cairo_translate(ctx, separator, 0);
        } else {
            ooonana_digit(ctx, *character);
            cairo_translate(ctx, advance, 0);
        }
    }
    cairo_restore(ctx);
}

struct ooonana_monitor {
    double x, y, width, height, scale;
};

static struct ooonana_monitor ooonana_monitor_at(int index, uint32_t *resolution, double scale) {
    double width = xr_screens > 0 ? xr_resolutions[index].width : resolution[0];
    double height = xr_screens > 0 ? xr_resolutions[index].height : resolution[1];
    scale = fmax(.1, fmin(scale, fmin(width / 335, height / 310)));
    return (struct ooonana_monitor){
        xr_screens > 0 ? xr_resolutions[index].x : 0,
        xr_screens > 0 ? xr_resolutions[index].y : 0,
        width / scale, height / scale, scale
    };
}

static void ooonana_wallpaper(cairo_t *ctx, double width, double height) {
    if (!img || cairo_surface_status(img) != CAIRO_STATUS_SUCCESS) return;
    double iw = cairo_image_surface_get_width(img), ih = cairo_image_surface_get_height(img);
    if (iw <= 0 || ih <= 0) return;
    double scale = fmin(width / iw, height / ih);
    cairo_save(ctx);
    ooonana_rgb(ctx, 0x080a0d);
    cairo_paint(ctx);
    cairo_translate(ctx, (width - iw * scale) / 2, (height - ih * scale) / 2);
    cairo_scale(ctx, scale, scale);
    cairo_set_source_surface(ctx, img, 0, 0);
    cairo_pattern_set_filter(cairo_get_source(ctx), CAIRO_FILTER_BILINEAR);
    cairo_rectangle(ctx, 0, 0, iw, ih);
    cairo_clip(ctx);
    cairo_paint_with_alpha(ctx, .67);
    cairo_restore(ctx);
}

static void ooonana_password(cairo_t *ctx, double x, double y, unsigned int ink, unsigned int muted) {
    bool wrong = auth_state == STATE_AUTH_WRONG;
    unsigned int accent = wrong ? (ooonana_light_mode() ? 0x9e2929 : 0xff8178)
                                : (ooonana_light_mode() ? 0x805600 : 0xffb21a);
    double left = x - 101;
    ooonana_rounded_rect(ctx, left, y - 18, 202, 36, 8);
    ooonana_rgb(ctx, ooonana_light_mode() ? 0xf0f1f3 : 0x101317);
    cairo_fill_preserve(ctx);
    ooonana_rgb(ctx, accent);
    cairo_set_line_width(ctx, 1.5);
    cairo_stroke(ctx);
    cairo_rectangle(ctx, left + 14, y - 1, 10, 8);
    cairo_new_sub_path(ctx);
    cairo_arc(ctx, left + 19, y - 1, 4, M_PI, 2 * M_PI);
    cairo_stroke(ctx);

    ooonana_rgb(ctx, ink);
    if (input_position > 0) {
        /* Keep the fixed mask and never expose even the number of typed characters. */
        for (int dot = 0; dot < 4; dot++) {
            cairo_arc(ctx, left + 38 + dot * 11, y, 2.4, 0, 2 * M_PI);
            cairo_fill(ctx);
        }
    } else {
        ooonana_rgb(ctx, muted);
        cairo_set_font_size(ctx, 13);
        cairo_move_to(ctx, left + 36, y + 5);
        cairo_show_text(ctx, "Password");
    }
}

static void ooonana_card(cairo_t *ctx, double width, double y, struct tm local) {
    double x = width / 2;
    bool light = ooonana_light_mode();
    unsigned int ink = light ? 0x1b1f26 : 0xf5f5f7;
    unsigned int muted = light ? 0x55616e : 0xb4bdc8;
    ooonana_rounded_rect(ctx, x - 153, y, 306, 156, 12);
    ooonana_rgb(ctx, light ? 0xf5f5f7 : 0x1b1f26);
    cairo_fill_preserve(ctx);
    ooonana_rgb(ctx, light ? 0xadb7c2 : 0x596474);
    cairo_set_line_width(ctx, 1);
    cairo_stroke(ctx);
    ooonana_rgb(ctx, light ? 0x805600 : 0xffb21a);
    cairo_arc(ctx, x, y + 22, 12, 0, 2 * M_PI);
    cairo_fill(ctx);
    ooonana_rgb(ctx, light ? 0xffffff : 0x101317);
    char initial[] = {ooonana_account[0] >= 'a' && ooonana_account[0] <= 'z'
                       ? ooonana_account[0] - 'a' + 'A' : 'O', 0};
    ooonana_center(ctx, initial, x, y + 27, 13);
    ooonana_rgb(ctx, ink);
    const char *period = local.tm_hour < 12 ? "morning" : local.tm_hour < 18 ? "afternoon" : "evening";
    char greeting[128];
    snprintf(greeting, sizeof(greeting), "Good %s%s%s", period,
             ooonana_account[0] ? ", " : "", ooonana_account);
    ooonana_center(ctx, greeting, x, y + 53, 15);
    ooonana_password(ctx, x, y + 81, ink, muted);

    ooonana_rgb(ctx, muted);
    if (ooonana_caps_lock()) {
        ooonana_rgb(ctx, light ? 0x805600 : 0xffb21a);
        ooonana_center(ctx, "Caps Lock", x + 94, y + 121, 12);
    }
    if (show_keyboard_layout && layout_string) {
        cairo_save(ctx);
        cairo_rectangle(ctx, x - 141, y + 106, ooonana_caps_lock() ? 190 : 282, 18);
        cairo_clip(ctx);
        ooonana_rgb(ctx, muted);
        ooonana_center(ctx, layout_string, x - (ooonana_caps_lock() ? 46 : 0), y + 121, 12);
        cairo_restore(ctx);
    }
    const char *status = "Press Enter to unlock";
    char attempts[40];
    if (auth_state == STATE_AUTH_WRONG) {
        ooonana_rgb(ctx, light ? 0x9e2929 : 0xff8178);
        status = "Incorrect password. Try again.";
    } else if (auth_state == STATE_AUTH_VERIFY) {
        status = "Checking password…";
    } else if (show_failed_attempts && failed_attempts > 0) {
        snprintf(attempts, sizeof(attempts), "%d failed attempt%s", failed_attempts,
                 failed_attempts == 1 ? "" : "s");
        status = attempts;
    }
    ooonana_center(ctx, status, x, y + 141, 12);
}

static void ooonana_power(cairo_t *ctx, double width, double height) {
    double right = width - 18, bottom = height - 18;
    double center = right - 17, middle = bottom - 17;
    ooonana_rounded_rect(ctx, right - 34, bottom - 34, 34, 34, 8);
    ooonana_rgb(ctx, 0x1b1f26);
    cairo_fill_preserve(ctx);
    ooonana_rgb(ctx, 0x596474);
    cairo_set_line_width(ctx, 1);
    cairo_stroke(ctx);

    ooonana_rgb(ctx, 0xf5f5f7);
    cairo_set_line_cap(ctx, CAIRO_LINE_CAP_ROUND);
    cairo_set_line_width(ctx, 1.7);
    cairo_arc(ctx, center, middle + 1, 7, -M_PI / 3, 4 * M_PI / 3);
    cairo_move_to(ctx, center, middle - 9);
    cairo_line_to(ctx, center, middle - 1);
    cairo_stroke(ctx);
    if (ooonana_battery >= 0) {
        double left = right - 112;
        cairo_rectangle(ctx, left, middle - 5, 21, 10);
        cairo_stroke(ctx);
        cairo_rectangle(ctx, left + 23, middle - 2, 2, 4);
        cairo_rectangle(ctx, left + 2, middle - 3, 17 * ooonana_battery / 100.0, 6);
        cairo_fill(ctx);
        char charge[8];
        snprintf(charge, sizeof(charge), "%d%%", ooonana_battery);
        ooonana_center(ctx, charge, right - 57, middle + 4, 13);
    }

    if (!ooonana_power_menu && !ooonana_power_error) return;
    double left = right - 152, top = bottom - 132;
    ooonana_rounded_rect(ctx, left, top, 152, 90, 9);
    ooonana_rgb(ctx, 0x1b1f26);
    cairo_fill_preserve(ctx);
    ooonana_rgb(ctx, 0x596474);
    cairo_stroke(ctx);
    ooonana_rgb(ctx, 0xf5f5f7);
    if (ooonana_power_error && !ooonana_power_menu) {
        ooonana_center(ctx, "Power action unavailable", left + 76, top + 48, 11);
    } else if (ooonana_power_menu == 1) {
        ooonana_center(ctx, "Sleep", left + 76, top + 20, 13);
        ooonana_center(ctx, "Restart", left + 76, top + 50, 13);
        ooonana_center(ctx, "Shut down", left + 76, top + 80, 13);
    } else {
        ooonana_center(ctx, ooonana_power_menu == 3 ? "Restart computer?" : "Shut down computer?",
                      left + 76, top + 20, 12);
        ooonana_rgb(ctx, 0xffb21a);
        ooonana_center(ctx, "Confirm", left + 76, top + 50, 13);
        ooonana_rgb(ctx, 0xf5f5f7);
        ooonana_center(ctx, "Cancel", left + 76, top + 80, 13);
    }
}

int ooonana_power_at(int x, int y) {
    struct ooonana_monitor monitor = ooonana_monitor_at(0, last_resolution, get_dpi_value() / 96.0);
    double right = monitor.width - 18 - (x - monitor.x) / monitor.scale;
    double bottom = monitor.height - 18 - (y - monitor.y) / monitor.scale;
    if (right >= 0 && right < 34 && bottom >= 0 && bottom < 34) return 1;
    if (right >= 0 && right < 152 && bottom >= 42 && bottom < 132) {
        int row = (132 - bottom) / 30;
        if (ooonana_power_menu == 1) return row + 2;
        if (ooonana_power_menu >= 3 && row == 1) return 5;
    }
    return 0;
}

static void ooonana_lock_heading(cairo_t *ctx, uint32_t *resolution, double scale) {
    if (!ooonana_lock_visuals()) return;
    time_t now = time(NULL);
    struct tm local;
    char clock[16], date[96];
    if (!localtime_r(&now, &local) || !strftime(clock, sizeof(clock), "%H:%M", &local) ||
        !strftime(date, sizeof(date), "%A, %e %B", &local)) return;
    int count = xr_screens > 0 ? xr_screens : 1;
    for (int index = 0; index < count; index++) {
        struct ooonana_monitor monitor = ooonana_monitor_at(index, resolution, scale);
        double width = monitor.width, height = monitor.height;
        cairo_save(ctx);
        cairo_translate(ctx, monitor.x, monitor.y);
        cairo_scale(ctx, monitor.scale, monitor.scale);
        cairo_rectangle(ctx, 0, 0, width, height);
        cairo_clip(ctx);
        ooonana_wallpaper(ctx, width, height);
        unsigned int clock_ink = img || !ooonana_light_mode() ? 0xf5f5f7 : 0x1b1f26;
        ooonana_rgb(ctx, clock_ink);
        double middle = height / 2;
        double progress = index == 0 ? ooonana_reveal : 0;
        ooonana_clock(ctx, clock, width / 2, middle - 104 * progress, 58);
        if (progress > 0) {
            cairo_push_group(ctx);
            cairo_select_font_face(ctx, "sans-serif", CAIRO_FONT_SLANT_NORMAL, CAIRO_FONT_WEIGHT_NORMAL);
            ooonana_rgb(ctx, clock_ink);
            ooonana_center(ctx, date, width / 2, middle - 58, 16);
            ooonana_card(ctx, width, middle - 38, local);
            ooonana_power(ctx, width, height);
            cairo_pop_group_to_source(ctx);
            cairo_paint_with_alpha(ctx, progress);
        }
        cairo_restore(ctx);
    }
}
