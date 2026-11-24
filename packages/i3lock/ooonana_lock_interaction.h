/* Lock presentation state. Vendor i3lock still owns grabs, input and PAM. */
#include <dirent.h>
#include <spawn.h>
#include <sys/wait.h>
#include <time.h>

double ooonana_reveal;
int ooonana_power_menu;
int ooonana_battery = -1;
bool ooonana_power_error;
char ooonana_account[64];

extern char **environ;
int ooonana_power_at(int x, int y);

static ev_timer ooonana_animation;
static ev_child ooonana_power_child;
static bool ooonana_prompt;
static bool ooonana_reveal_down;
static int ooonana_pressed_control = -1;
static uint8_t ooonana_reveal_key;
static xcb_timestamp_t ooonana_reveal_release;
static double ooonana_animation_start;
static double ooonana_boot_offset;

static bool ooonana_active(void) {
    const char *value = getenv("OOONANA_LOCK_VISUALS");
    return value && strcmp(value, "1") == 0;
}

bool ooonana_caps_lock(void) {
    return xkb_state && xkb_state_mod_name_is_active(xkb_state, XKB_MOD_NAME_CAPS, XKB_STATE_MODS_LOCKED) == 1;
}

int ooonana_mask_length(void) {
    int characters = 0;
    for (int index = 0; index < input_position; index++) {
        /* i3lock stores a UTF-8 byte offset. Only count the leading bytes. */
        if (((unsigned char)password[index] & 0xc0) != 0x80) characters++;
    }
    return characters;
}

static void ooonana_reset_prompt(void) {
    ev_timer_stop(main_loop, &ooonana_animation);
    ooonana_prompt = false;
    ooonana_reveal = 0;
    ooonana_power_menu = 0;
    ooonana_pressed_control = -1;
    ooonana_reveal_key = 0;
    ooonana_reveal_down = false;
    ooonana_power_error = false;
    clear_input();
    retry_verification = false;
    if (xkb_compose_state) xkb_compose_state_reset(xkb_compose_state);
}

static bool ooonana_after_resume(void) {
#ifdef CLOCK_BOOTTIME
    struct timespec boot, running;
    if (clock_gettime(CLOCK_BOOTTIME, &boot) == 0 && clock_gettime(CLOCK_MONOTONIC, &running) == 0) {
        double offset = (boot.tv_sec - running.tv_sec) + (boot.tv_nsec - running.tv_nsec) / 1e9;
        bool resumed = offset - ooonana_boot_offset > .5;
        ooonana_boot_offset = offset;
        return resumed;
    }
#endif
    return false;
}

static void ooonana_animate(EV_P_ ev_timer *watcher, int revents) {
    (void)revents;
    double remaining = 1 - (ev_now(EV_A) - ooonana_animation_start) / .20;
    if (remaining <= 0) {
        remaining = 0;
        ev_timer_stop(EV_A_ watcher);
    }
    ooonana_reveal = 1 - remaining * remaining * remaining;
    redraw_screen();
}

static void ooonana_show_prompt(void) {
    ooonana_prompt = true;
    const char *reduced = getenv("OOONANA_LOCK_REDUCE_MOTION");
    if (reduced && strcmp(reduced, "1") == 0) {
        ooonana_reveal = 1;
        redraw_screen();
        return;
    }
    ev_now_update(main_loop);
    ooonana_animation_start = ev_now(main_loop);
    ev_timer_start(main_loop, &ooonana_animation);
}

static bool ooonana_key_gate(xcb_key_press_event_t *event, xkb_keysym_t key) {
    if (!ooonana_active()) return false;
    if (ooonana_after_resume()) {
        ooonana_reset_prompt();
        redraw_screen();
    }
    if (!ooonana_prompt) {
        if (key == XKB_KEY_Return || key == XKB_KEY_KP_Enter) {
            ooonana_reveal_key = event->detail;
            ooonana_reveal_down = true;
            ooonana_show_prompt();
        }
        return true;
    }
    /* Also ignore legacy repeat pairs with identical release/press timestamps. */
    if (event->detail == ooonana_reveal_key) {
        if (ooonana_reveal_down || event->time == ooonana_reveal_release) {
            ooonana_reveal_down = true;
            return true;
        }
        ooonana_reveal_key = 0;
    }
    if (ooonana_power_menu) {
        if (key == XKB_KEY_Escape) {
            ooonana_power_menu = 0;
            redraw_screen();
        }
        return true;
    }
    return false;
}

static void ooonana_key_released(xcb_key_release_event_t *event) {
    if (event->detail == ooonana_reveal_key) {
        ooonana_reveal_down = false;
        ooonana_reveal_release = event->time;
    }
}

static void ooonana_power_finished(EV_P_ ev_child *watcher, int revents) {
    (void)revents;
    ev_child_stop(EV_A_ watcher);
    if (!WIFEXITED(watcher->rstatus) || WEXITSTATUS(watcher->rstatus) != 0) {
        ooonana_power_error = true;
        if (!ooonana_prompt) {
            ooonana_prompt = true;
            ooonana_reveal = 1;
        }
        redraw_screen();
    }
}

static void ooonana_request_power(int action) {
    if (ev_is_active(&ooonana_power_child)) return;
    const char *verb = action == 2 ? "suspend" : action == 3 ? "reboot" : "poweroff";
    char *const arguments[] = {"loginctl", "--no-ask-password", (char *)verb, NULL};
    pid_t child;
    ooonana_power_menu = 0;
    ooonana_power_error = posix_spawn(&child, "/usr/bin/loginctl", NULL, NULL, arguments, environ) != 0;
    if (!ooonana_power_error) {
        ev_child_init(&ooonana_power_child, ooonana_power_finished, child, 0);
        ev_child_start(main_loop, &ooonana_power_child);
        if (action == 2) ooonana_reset_prompt();
    }
}

static void ooonana_pointer_pressed(xcb_button_press_event_t *event) {
    if (event->detail == 1 && ooonana_prompt && ooonana_reveal >= 1)
        ooonana_pressed_control = ooonana_power_at(event->root_x, event->root_y);
}

static void ooonana_pointer_released(xcb_button_release_event_t *event) {
    if (event->detail != 1) return;
    int pressed = ooonana_pressed_control;
    ooonana_pressed_control = -1;
    if (!ooonana_prompt || ooonana_reveal < 1) return;
    int hit = ooonana_power_at(event->root_x, event->root_y);
    if (pressed != hit) return;
    if (hit == 1) {
        ooonana_power_menu = ooonana_power_menu ? 0 : 1;
        ooonana_power_error = false;
    } else if (hit == 2 && ooonana_power_menu == 1) {
        ooonana_request_power(hit);
    } else if (hit >= 3 && ooonana_power_menu == 1) {
        ooonana_power_menu = hit;
    } else if (hit == 5 && ooonana_power_menu >= 3) {
        ooonana_request_power(ooonana_power_menu);
    } else if (ooonana_power_menu) {
        ooonana_power_menu = 0;
    } else {
        return;
    }
    redraw_screen();
}

static int ooonana_read_battery(void) {
    DIR *supplies = opendir("/sys/class/power_supply");
    if (!supplies) return -1;
    int total = 0, count = 0;
    struct dirent *device;
    while ((device = readdir(supplies))) {
        char path[512], value[32];
        snprintf(path, sizeof(path), "/sys/class/power_supply/%s/type", device->d_name);
        FILE *file = fopen(path, "r");
        if (!file) continue;
        bool battery = fscanf(file, "%31s", value) == 1 && strcmp(value, "Battery") == 0;
        fclose(file);
        if (!battery) continue;
        snprintf(path, sizeof(path), "/sys/class/power_supply/%s/scope", device->d_name);
        file = fopen(path, "r");
        if (file) {
            bool peripheral = fscanf(file, "%31s", value) == 1 && strcmp(value, "Device") == 0;
            fclose(file);
            if (peripheral) continue;
        }
        snprintf(path, sizeof(path), "/sys/class/power_supply/%s/capacity", device->d_name);
        file = fopen(path, "r");
        if (!file) continue;
        int percent;
        if (fscanf(file, "%d", &percent) == 1 && percent >= 0 && percent <= 100) {
            total += percent;
            count++;
        }
        fclose(file);
    }
    closedir(supplies);
    return count ? total / count : -1;
}

static void ooonana_clock_tick(EV_P_ ev_periodic *watcher, int revents) {
    (void)watcher;
    (void)revents;
    static time_t minute = -1, battery_check = -1;
    time_t now = time(NULL);
    bool redraw = now / 60 != minute;
    minute = now / 60;
    if (ooonana_after_resume()) {
        ooonana_reset_prompt();
        redraw = true;
    }
    if (now / 30 != battery_check) {
        battery_check = now / 30;
        int percent = ooonana_read_battery();
        redraw |= percent != ooonana_battery && ooonana_prompt;
        ooonana_battery = percent;
    }
    if (redraw) redraw_screen();
}

static void ooonana_start_ui(void) {
    if (!ooonana_active()) return;
    struct passwd *account = getpwuid(getuid());
    if (account) snprintf(ooonana_account, sizeof(ooonana_account), "%s", account->pw_name);
    (void)ooonana_after_resume();
    ooonana_battery = ooonana_read_battery();
    ev_timer_init(&ooonana_animation, ooonana_animate, 0, .016);
    static ev_periodic clock;
    ev_periodic_init(&clock, ooonana_clock_tick, 0, 1, NULL);
    ev_periodic_start(main_loop, &clock);
}
