/* Ooonana's opt-in i3 titlebar metrics. Native GTK controls remain authoritative.
 * SPDX-License-Identifier: MIT
 */
#ifndef OOONANA_CONTROLS_H
#define OOONANA_CONTROLS_H

#include <stdlib.h>
#include <string.h>

#define OOONANA_CONTROL_SIZE 24
#define OOONANA_CONTROL_GAP 5
#define OOONANA_CONTROL_INSET 14
#define OOONANA_CONTROL_ICON 12
#define OOONANA_CONTROL_WIDTH (3 * OOONANA_CONTROL_SIZE + 2 * OOONANA_CONTROL_GAP)

static inline int ooonana_control_scale(void) {
    const char *mode = getenv("OOONANA_WINDOW_CONTROLS");
    if (mode == NULL || strcmp(mode, "left") != 0) {
        return 0;
    }
    const char *value = getenv("GDK_SCALE");
    if (value == NULL || *value == '\0') {
        return 1;
    }
    char *end;
    const long scale = strtol(value, &end, 10);
    return *end == '\0' && scale >= 1 && scale <= 4 ? (int)scale : 1;
}

static inline int ooonana_titlebar_height(void) {
    return (OOONANA_CONTROL_SIZE + 8) * ooonana_control_scale();
}

static inline double ooonana_font_dpi(double dpi) {
    const int scale = ooonana_control_scale();
    /* Xft may already carry physical HiDPI. Never apply that scale twice. */
    return scale > 1 && dpi < 96.0 * scale ? 96.0 * scale : dpi;
}

static inline int ooonana_titlebar_left(int frame_width) {
    const int scale = ooonana_control_scale();
    if (scale == 0 || frame_width < (OOONANA_CONTROL_INSET + OOONANA_CONTROL_WIDTH) * scale) {
        return 0;
    }
    return (OOONANA_CONTROL_INSET + OOONANA_CONTROL_WIDTH + 12) * scale;
}

#endif
