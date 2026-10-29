/* Presentation only. Never reads password, performs auth, or changes grabs. */
#include <time.h>

static bool ooonana_lock_visuals(void) {
    const char *value = getenv("OOONANA_LOCK_VISUALS");
    return value && strcmp(value, "1") == 0;
}

static bool ooonana_lock_paper(void) {
    return strcmp(color, "f5f5f7") == 0;
}

static void ooonana_lock_rgb(cairo_t *ctx, unsigned int color) {
    cairo_set_source_rgb(ctx, ((color >> 16) & 255) / 255.0,
                         ((color >> 8) & 255) / 255.0, (color & 255) / 255.0);
}

static bool ooonana_lock_error(void) {
    return auth_state == STATE_AUTH_WRONG || auth_state == STATE_I3LOCK_LOCK_FAILED ||
        unlock_state == STATE_NOTHING_TO_DELETE;
}

static void ooonana_lock_ink(cairo_t *ctx) {
    ooonana_lock_rgb(ctx, ooonana_lock_error()
        ? (ooonana_lock_paper() ? 0x9e2929 : 0xff675c)
        : (ooonana_lock_paper() ? 0x1b1f26 : 0xf5f5f7));
}

static void ooonana_lock_fill(cairo_t *ctx) {
    ooonana_lock_rgb(ctx, ooonana_lock_error()
        ? (ooonana_lock_paper() ? 0xfae9e7 : 0x3b2324)
        : (ooonana_lock_paper() ? 0xffffff : 0x1b1f26));
}

static void ooonana_lock_stroke(cairo_t *ctx) {
    ooonana_lock_rgb(ctx, ooonana_lock_error()
        ? (ooonana_lock_paper() ? 0x9e2929 : 0xff675c)
        : (ooonana_lock_paper() ? 0x805600 : 0xffb21a));
}

static void ooonana_lock_centered(cairo_t *ctx, const char *text, double width, double y, double size) {
    cairo_text_extents_t extents;
    cairo_set_font_size(ctx, size);
    cairo_text_extents(ctx, text, &extents);
    cairo_move_to(ctx, width / 2 - extents.width / 2 - extents.x_bearing, y);
    cairo_show_text(ctx, text);
}

static void ooonana_lock_heading(cairo_t *ctx, uint32_t *resolution, double scale) {
    if (!ooonana_lock_visuals()) return;
    time_t now = time(NULL);
    struct tm local;
    char clock[16], date[64];
    if (!localtime_r(&now, &local) || !strftime(clock, sizeof(clock), "%H:%M", &local) ||
        !strftime(date, sizeof(date), "%a, %b %e", &local)) return;
    int count = xr_screens > 0 ? xr_screens : 1;
    for (int monitor = 0; monitor < count; monitor++) {
        double x = xr_screens > 0 ? xr_resolutions[monitor].x : 0;
        double y = xr_screens > 0 ? xr_resolutions[monitor].y : 0;
        double width = (xr_screens > 0 ? xr_resolutions[monitor].width : resolution[0]) / scale;
        double height = (xr_screens > 0 ? xr_resolutions[monitor].height : resolution[1]) / scale;
        if (width < 180 || height < 180) continue;
        cairo_save(ctx);
        cairo_translate(ctx, x, y);
        cairo_scale(ctx, scale, scale);
        cairo_rectangle(ctx, 0, 0, width, height);
        cairo_clip(ctx);
        cairo_select_font_face(ctx, "sans-serif", CAIRO_FONT_SLANT_NORMAL, CAIRO_FONT_WEIGHT_NORMAL);
        ooonana_lock_rgb(ctx, ooonana_lock_paper() ? 0x1b1f26 : 0xf5f5f7);
        double baseline = height < 360 ? 30 : fmin(80, height * .18);
        ooonana_lock_centered(ctx, clock, width, baseline, height < 360 ? 24 : 32);
        ooonana_lock_rgb(ctx, ooonana_lock_paper() ? 0x55616e : 0xb4bdc8);
        ooonana_lock_centered(ctx, date, width, baseline + 22, 14);
        if (height >= 300)
            ooonana_lock_centered(ctx, "Type password to unlock", width,
                                  fmin(baseline + 48, height / 2 - 68), 13);
        ooonana_lock_centered(ctx, "Ooonana OS", width, height - 24, 12);
        cairo_restore(ctx);
    }
}
