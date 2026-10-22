#!/usr/bin/env python3
import os
import json
import signal
import shutil
import subprocess
import threading
from pathlib import Path
from ui_preferences import load_preferences, refresh_gtk_theme, resolved_theme, transition_ms

# GTK_THEME is read during toolkit initialization, before application CSS.
refresh_gtk_theme()
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Gdk, GLib, Gtk, Pango, PangoCairo  # noqa: E402


CSS = b"""
* { font-family: Sans; font-size: 10pt; }
window, dialog, .background { background: #101317; color: #f5f5f7; }
window.background, dialog.background, messagedialog.background { border-radius: 14px; }
decoration { background: #101317; border: 1px solid #343b46; border-radius: 14px; box-shadow: none; }
menu { background: #1b1f26; color: #f5f5f7; border: 1px solid #343b46; border-radius: 10px; padding: 6px; }
menuitem { padding: 9px 12px; border-radius: 7px; }
menuitem:hover { background: #303640; color: #ffb21a; }
tooltip { background: #1b1f26; color: #f5f5f7; border: 1px solid #414957; border-radius: 12px; padding: 6px; }
tooltip label { color: #f5f5f7; }
headerbar { background: #1b1f26; color: #ffb21a; border-bottom: 1px solid #343b46; border-radius: 14px 14px 0 0; min-height: 0; padding: 4px 10px; }
headerbar .title { font-weight: 700; color: #ffb21a; }
headerbar .subtitle { color: #b4bdc8; opacity: 1; }
headerbar button { margin-top: 0; margin-bottom: 0; }
.window-control { min-width: 16px; min-height: 16px; padding: 3px; margin: 0; border-radius: 99px; }
.close-control:hover { background: #b83832; color: #ffffff; border-color: #e85b52; }
.hero { background: #1b1f26; border-bottom: 1px solid #343b46; }
.hero-title { font-size: 18pt; font-weight: 800; color: #ffb21a; }
.badge { background: #32291a; color: #ffcf77; border: 1px solid #735b33; border-radius: 9px; padding: 4px 10px; }
.sidebar { background: #171b21; border-right: 1px solid #343b46; }
.sidebar row { margin: 3px 8px; padding: 10px 14px; border-left: 1px solid transparent; border-radius: 10px; transition: background-color 180ms ease-out; }
.sidebar row:hover { background: #22272f; }
.sidebar row:selected { background: #303640; border-left-color: #ffb21a; color: #f5f5f7; }
.sidebar row:focus, .spotlight-results row:focus { outline: 1px solid #ffb21a; outline-offset: -2px; }
.page-title { font-size: 14pt; font-weight: 700; color: #f5f5f7; }
.page-subtitle, .muted { color: #b4bdc8; }
.card { background: #1b1f26; border: 1px solid #343b46; border-radius: 14px; padding: 16px; }
.card-title { font-size: 11pt; font-weight: 700; color: #f5f5f7; }
.settings-section { background: #101317; border-bottom: 1px solid #343b46; padding: 0 0 12px 0; }
.settings-section:last-child { border-bottom: none; padding-bottom: 0; }
.status-good { color: #70d69b; font-weight: 700; }
.status-warn { color: #ffd37a; font-weight: 700; }
.status-bad { color: #ff675c; font-weight: 700; }
.status-neutral { color: #b4bdc8; }
button { background: #272c34; color: #f5f5f7; border: 1px solid #46505c; border-radius: 10px; min-height: 20px; padding: 5px 10px; transition: background-color 180ms ease-out; }
button:hover { background: #39414b; border-color: #596574; }
button:active { background: #20252c; border-color: #ffb21a; }
button:focus, entry:focus, combobox button:focus { border-color: #ffb21a; box-shadow: 0 0 0 2px #73521e; }
button:disabled { background: #1b1f26; color: #78828f; border-color: #313944; }
button.suggested-action { background: #ffb21a; color: #101317; border-color: #ffb21a; font-weight: 700; }
button.suggested-action:hover { background: #ffca5c; border-color: #ffca5c; }
button.suggested-action:active { background: #eaa21a; border-color: #eaa21a; }
button.suggested-action:disabled { background: #403624; color: #a5987f; border-color: #544733; }
button.destructive-action { background: #3b2324; color: #ffaaa3; border-color: #8a4749; }
button.destructive-action:hover { background: #523033; color: #ffd4cf; border-color: #b36161; }
button.destructive-action:active { background: #2f1c1d; color: #ffd4cf; border-color: #b36161; }
button.destructive-action:disabled { background: #1b1f26; color: #78828f; border-color: #313944; }
entry, textview, textview text, textview.view, textview.view text, treeview, list {
  background: #15191f;
  color: #f5f5f7;
  border-color: #46505c;
}
entry { min-height: 20px; padding: 5px 8px; border-radius: 10px; }
entry:hover { border-color: #778493; }
entry:focus { border-color: #ffb21a; }
entry selection, textview text selection { background: #ffcf77; color: #101317; }
combobox button { min-height: 20px; }
checkbutton, radiobutton { padding: 4px 0; }
checkbutton check { background: #15191f; border: 1px solid #596574; border-radius: 4px; min-width: 14px; min-height: 14px; }
checkbutton check:checked { background: #ffb21a; color: #101317; border-color: #ffb21a; }
checkbutton:hover check:not(:checked) { border-color: #9ca7b6; }
checkbutton:focus, radiobutton:focus { outline: 1px solid #ffb21a; outline-offset: 2px; }
treeview header button { background: #272c34; color: #ffcf77; padding: 7px; }
treeview:selected, row:selected { background: #303640; color: #ffffff; }
notebook header { background: #171b21; }
notebook tab { padding: 8px 14px; }
notebook tab:checked { color: #ffb21a; border-bottom: 2px solid #ffb21a; }
scale highlight { background: #ffb21a; }
scale trough { background: #343b46; min-height: 7px; border-radius: 5px; }
progressbar trough { background: #303640; min-height: 8px; border-radius: 6px; }
progressbar progress { background: #ffb21a; border-radius: 6px; }
progressbar text { color: #f5f5f7; font-weight: 700; }
scrollbar slider { background: #596574; border-radius: 6px; min-width: 8px; min-height: 8px; }
scrollbar slider:hover { background: #ffb21a; }
separator { background: #343b46; }
.spotlight { background: #171b21; border: 1px solid #ffb21a; border-radius: 18px; }
.spotlight-brand { color: #ffb21a; font-size: 11pt; font-weight: 800; }
.spotlight-search { font-size: 12pt; padding: 8px 12px; border-radius: 12px; }
.spotlight-results { background: #171b21; }
.spotlight-results row { padding: 10px 12px; border-top: 1px solid #303640; border-radius: 9px; transition: background-color 180ms ease-out; }
.spotlight-results row:hover, .spotlight-results row:selected { background: #303640; color: #ffffff; }
.spotlight-app-name { font-size: 10.5pt; font-weight: 700; }
"""

WINDOW_CONTROL_CSS = b"""
button.window-control { min-width: 16px; min-height: 16px; padding: 3px; margin: 0; border-radius: 99px; border: 1px solid #242830; color: #101317; box-shadow: none; }
button.close-control { background: #ff736b; }
button.minimize-control { background: #ffd16c; }
button.fullscreen-control { background: #7fd6a0; }
button.window-control:hover { border-color: #f5f5f7; }
button.close-control:active { background: #e65c55; }
button.minimize-control:active { background: #e6b955; }
button.fullscreen-control:active { background: #67b985; }
button.window-control:focus { box-shadow: 0 0 0 2px #f5f5f7; }
"""

# Native content roles must follow the same appearance as desktop GTK chrome.
# Semantic foregrounds stay readable; primary/destructive actions retain meaning.
LIGHT_CSS = b"""
window, dialog, .background { background: #f5f5f7; color: #1b1f26; }
decoration { background: #f5f5f7; border-color: #adb7c2; }
menu, tooltip, headerbar { background: #ffffff; color: #1b1f26; border-color: #adb7c2; }
tooltip label, headerbar .subtitle { color: #55616e; }
headerbar .title, .hero-title { color: #805600; }
menuitem:hover { background: #e9edf1; color: #1b1f26; }
.hero, .card { background: #ffffff; border-color: #adb7c2; }
.sidebar { background: #ffffff; border-color: #adb7c2; }
.sidebar row:hover { background: #eef1f5; }
.sidebar row:selected { background: #e9edf1; color: #1b1f26; }
.page-title, .card-title { color: #1b1f26; }
.page-subtitle, .muted, .status-neutral { color: #55616e; }
.settings-section { background: #f5f5f7; border-color: #adb7c2; }
.badge { background: #fff0cc; color: #6c4a00; border-color: #c3a563; }
.status-good { color: #25663f; }
.status-warn { color: #765300; }
.status-bad { color: #a52620; }
button { background: #e9edf1; color: #1b1f26; border-color: #adb7c2; box-shadow: none; }
button:hover { background: #d8dee6; border-color: #805600; }
button:active { background: #ffffff; border-color: #805600; }
button:disabled { background: #eef1f5; color: #687380; border-color: #cbd2da; }
button.suggested-action { background: #ffb21a; color: #101317; border-color: #ffb21a; }
button.suggested-action:hover { background: #ffca5c; }
button.suggested-action:active { background: #eaa21a; }
button.suggested-action:disabled { background: #eee2c9; color: #776b53; border-color: #d1c3a6; }
button.destructive-action { background: #fce9e7; color: #8d2621; border-color: #c98b86; }
button.destructive-action:hover { background: #f8d8d4; color: #7b1d18; }
button.destructive-action:active { background: #f1c3bd; color: #7b1d18; }
button.destructive-action:disabled { background: #eef1f5; color: #687380; border-color: #cbd2da; }
button:focus, entry:focus, combobox button:focus { outline: 2px solid #805600; outline-offset: -2px; box-shadow: none; border-color: #805600; }
.sidebar row:focus, .spotlight-results row:focus { outline-color: #805600; }
entry, textview, textview text, textview.view, textview.view text, treeview, list {
  background: #ffffff; color: #1b1f26; border-color: #adb7c2;
}
checkbutton check { background: #ffffff; border-color: #687380; }
treeview header button, notebook header { background: #e9edf1; color: #1b1f26; }
treeview:selected, row:selected { background: #e9edf1; color: #1b1f26; }
notebook tab:checked { color: #805600; }
scale trough, progressbar trough { background: #d8dee6; }
progressbar text { color: #1b1f26; }
scrollbar slider { background: #687380; }
separator { background: #adb7c2; }
.spotlight, .spotlight-results { background: #ffffff; border-color: #adb7c2; }
.spotlight-brand { color: #805600; }
.spotlight-results row { border-color: #e9edf1; }
.spotlight-results row:hover, .spotlight-results row:selected { background: #e9edf1; color: #1b1f26; }
"""


def light_appearance():
    selected = resolved_theme()
    if selected:
        return selected == "light"
    override = os.environ.get("GTK_THEME", "")
    if override:
        return not override.endswith((":dark", "-dark"))
    settings = Gtk.Settings.get_default()
    return bool(settings and not settings.get_property("gtk-application-prefer-dark-theme"))


def chart_colors():
    """Opaque drawing-area roles shared by native plots, in the active theme."""
    colors = ({"background": "#ffffff", "grid": "#d8dee6", "text": "#1b1f26",
               "muted": "#55616e", "accent": "#805600", "green": "#25663f", "blue": "#0065a8"}
              if light_appearance() else
              {"background": "#15191f", "grid": "#343b46", "text": "#f5f5f7",
               "muted": "#b4bdc8", "accent": "#ffb21a", "green": "#70d69b", "blue": "#74c9ff"})
    return {name: tuple(int(value[index:index + 2], 16) / 255 for index in (1, 3, 5))
            for name, value in colors.items()}


_theme_provider = None


def apply_theme():
    global _theme_provider
    managed = refresh_gtk_theme()
    if _theme_provider is None:
        _theme_provider = Gtk.CssProvider()
    _theme_provider.load_from_data(CSS + (LIGHT_CSS if light_appearance() else b""))
    screen = Gdk.Screen.get_default()
    if screen:
        Gtk.StyleContext.add_provider_for_screen(
            screen, _theme_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
    settings = Gtk.Settings.get_default()
    if settings:
        if managed:
            settings.set_property("gtk-application-prefer-dark-theme", managed == "dark")
        settings.set_property("gtk-enable-animations", not load_preferences()["reduce_motion"])


def is_wsl_session():
    if os.environ.get("WSL_DISTRO_NAME"):
        return True
    try:
        return "microsoft" in Path("/proc/sys/kernel/osrelease").read_text().lower()
    except OSError:
        return False


def host_radio_unavailable(kind):
    if not is_wsl_session():
        return False
    if kind == "wifi":
        return not any(Path("/sys/class/net").glob("*/wireless"))
    if kind == "bluetooth":
        return not any(Path("/sys/class/bluetooth").glob("hci*"))
    return False


def icon(name, size=Gtk.IconSize.BUTTON):
    theme = Gtk.IconTheme.get_default()
    fallbacks = {
        "preferences-desktop-peripherals-symbolic": "input-mouse-symbolic",
        "preferences-desktop-theme-symbolic": "applications-graphics-symbolic",
        "preferences-system-bluetooth-symbolic": "bluetooth-symbolic",
        "text-x-log-symbolic": "view-list-symbolic",
        "utilities-system-monitor-symbolic": "computer-symbolic",
    }
    if theme and not theme.has_icon(name):
        name = fallbacks.get(name, "application-x-executable-symbolic")
    return Gtk.Image.new_from_icon_name(name, size)


def window_control_icon(name):
    image = icon(name)
    image.set_pixel_size(12)
    return image


def button(label_text, icon_name=None, callback=None, style=None):
    widget = Gtk.Button.new_with_label(label_text)
    widget.set_halign(Gtk.Align.START)
    if icon_name:
        image = icon(icon_name)
        image.set_margin_end(6)
        widget.set_image(image)
        widget.set_always_show_image(True)
    if callback:
        widget.connect("clicked", callback)
    if style:
        widget.get_style_context().add_class(style)
    return widget


def flow_row(widgets, max_children=8, min_children=3):
    widgets = list(widgets)
    row = Gtk.FlowBox()
    row.set_selection_mode(Gtk.SelectionMode.NONE)
    row.set_homogeneous(False)
    row.set_row_spacing(8)
    row.set_column_spacing(8)
    row.set_min_children_per_line(min(max(1, min_children), max_children, max(1, len(widgets))))
    row.set_max_children_per_line(max_children)
    row.set_valign(Gtk.Align.START)
    for widget in widgets:
        row.insert(widget, -1)
        widget.get_parent().set_can_focus(False)
    return row


def more_actions(widgets, name="More actions"):
    """Native disclosure for secondary tools, with normal keyboard navigation."""
    control = Gtk.MenuButton(label="More")
    control.set_halign(Gtk.Align.START)
    control.set_image(icon("view-more-symbolic"))
    control.set_always_show_image(True)
    control.get_accessible().set_name(name)
    control.set_tooltip_text(name)
    popover = Gtk.Popover.new(control)
    content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    content.set_border_width(12)
    for widget in widgets:
        content.pack_start(widget, False, False, 0)
        widget.connect("clicked", lambda *_args: popover.popdown())
    popover.add(content)
    content.show_all()
    control.set_popover(popover)
    return control


def fit_dialog(dialog, width, height=-1):
    """Leave room for WM decorations; do not request an entire display's height."""
    display = Gdk.Display.get_default()
    parent = dialog.get_transient_for()
    monitor = display.get_monitor_at_window(parent.get_window()) if display and parent and parent.get_window() else None
    if display:
        monitor = monitor or display.get_primary_monitor() or display.get_monitor(0)
    if monitor:
        area = monitor.get_workarea()
        width = min(width, max(1, area.width - 48))
        if height > 0:
            # CSD titlebars grow with user text scaling; a fixed reserve can
            # place an otherwise scrollable window outside a small display.
            titlebar = dialog.get_titlebar()
            reserve = max(96, titlebar.get_preferred_height()[1] + 64) if titlebar else 96
            height = min(height, max(1, area.height - reserve))
    dialog.set_default_size(width, height)
    dialog.set_position(Gtk.WindowPosition.CENTER_ON_PARENT if parent else Gtk.WindowPosition.CENTER)
    if not getattr(dialog, "_ooonana_fit_connected", False):
        dialog._ooonana_fit_connected = True
        dialog.connect("map-event", lambda widget, _event: (
            GLib.timeout_add(80, fit_initial_position, widget), False)[1])


def fit_initial_position(window):
    """Clamp initial CSD placement after WM/map size negotiation, never dragging."""
    native = window.get_window()
    display = Gdk.Display.get_default()
    if not native or not window.get_visible() or not display:
        return False
    monitor = display.get_monitor_at_window(native)
    if not monitor:
        return False
    area, frame = monitor.get_workarea(), native.get_frame_extents()
    x = max(area.x, min(frame.x, area.x + area.width - frame.width))
    y = max(area.y, min(frame.y, area.y + area.height - frame.height))
    if (x, y) != (frame.x, frame.y):
        current_x, current_y = window.get_position()
        window.set_position(Gtk.WindowPosition.NONE)
        window.move(current_x + x - frame.x, current_y + y - frame.y)
    return False


def i3_window_action(window, action):
    native = window.get_window()
    if native is None or not command_exists("i3-msg"):
        return False
    try:
        gi.require_version("GdkX11", "3.0")
        from gi.repository import GdkX11
        identifier = GdkX11.X11Window.get_xid(native)
        result = subprocess.run(
            ["i3-msg", f"[id={identifier}] {action}"], capture_output=True,
            text=True, timeout=3, check=False,
        )
        return result.returncode == 0 and any(item.get("success") for item in json.loads(result.stdout))
    except (ImportError, ValueError, TypeError, OSError, subprocess.SubprocessError):
        return False


def header(window, title, subtitle="", icon_name="preferences-system-symbolic"):
    window.set_resizable(True)
    window.set_wmclass("ooonana-app", "OoonanaApp")
    app_icons = {"Ooonana AI": "ai", "Ooonana Spotlight": "apps", "Ooonana Settings": "settings", "Ooonana Control Center": "settings", "Ooonana Wi-Fi": "wifi", "Ooonana Bluetooth": "bluetooth", "Ooonana Task Manager": "task-manager", "Ooonana Health": "health", "Ooonana Updates": "updates", "Ooonana Setup": "setup", "Ooonana Notifications": "notifications", "Ooonana Packages": "packages", "Ooonana Music": "music", "Ooonana Controls": "controls"}
    app_icons.update({"Ooonana Sound": "controls", "Ooonana Brightness": "controls", "Ooonana Power": "controls"})
    app_title = title if title in app_icons else window.get_title()
    if app_title in app_icons:
        window.set_icon_name("ooonana-" + app_icons[app_title])
        window.set_role(app_title.casefold().replace(" ", "-"))
    display = Gdk.Display.get_default()
    monitor = (display.get_primary_monitor() or display.get_monitor(0)) if display else None
    if monitor:
        geometry = monitor.get_geometry()
        minimum_width, minimum_height = window.get_size_request()
        window.set_size_request(
            min(minimum_width, max(320, geometry.width - 64)) if minimum_width > 0 else minimum_width,
            min(minimum_height, max(240, geometry.height - 144)) if minimum_height > 0 else minimum_height,
        )
        width, height = window.get_default_size()
        window.set_default_size(
            min(width, max(480, geometry.width - 64)) if width > 0 else width,
            min(height, max(320, geometry.height - 224)) if height > 0 else height,
        )
    bar = Gtk.HeaderBar()
    bar.set_show_close_button(False)
    bar.set_decoration_layout("")
    bar.set_title(title)
    # GTK otherwise reserves a second title line even without a subtitle.
    # Let real content, controls and user text scaling determine header height.
    bar.set_has_subtitle(bool(subtitle))
    bar.set_subtitle(subtitle)

    def minimize(_widget):
        if not i3_window_action(window, "move scratchpad"):
            window.iconify()

    def maximize(_widget):
        if i3_window_action(window, "fullscreen toggle"):
            return
        if window.is_maximized():
            window.unmaximize()
        else:
            window.maximize()

    maximize_button = Gtk.Button()
    maximize_button.set_image(window_control_icon("view-fullscreen-symbolic"))
    maximize_button.set_valign(Gtk.Align.CENTER)
    maximize_button.set_tooltip_text("Toggle fullscreen")
    maximize_button.set_name("ooonana-window-fullscreen")
    maximize_button.get_accessible().set_name("Toggle fullscreen")
    maximize_button.connect("clicked", maximize)
    maximize_button.get_style_context().add_class("window-control")
    maximize_button.get_style_context().add_class("fullscreen-control")

    minimize_button = Gtk.Button()
    minimize_button.set_image(window_control_icon("window-minimize-symbolic"))
    minimize_button.set_valign(Gtk.Align.CENTER)
    minimize_button.set_tooltip_text("Minimize window")
    minimize_button.set_name("ooonana-window-minimize")
    minimize_button.get_accessible().set_name("Minimize window")
    minimize_button.connect("clicked", minimize)
    minimize_button.get_style_context().add_class("window-control")
    minimize_button.get_style_context().add_class("minimize-control")

    close_button = Gtk.Button()
    close_button.set_image(window_control_icon("window-close-symbolic"))
    close_button.set_valign(Gtk.Align.CENTER)
    close_button.set_tooltip_text("Close")
    close_button.set_name("ooonana-window-close")
    close_button.get_accessible().set_name("Close window")
    close_button.connect("clicked", lambda _widget: window.close())
    close_button.get_style_context().add_class("window-control")
    close_button.get_style_context().add_class("close-control")
    controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
    controls.set_valign(Gtk.Align.CENTER)
    for control in (close_button, minimize_button, maximize_button):
        provider = Gtk.CssProvider()
        provider.load_from_data(WINDOW_CONTROL_CSS)
        control.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_USER + 1)
        controls.pack_start(control, False, False, 0)
    bar.pack_start(controls)
    if icon_name:
        bar.pack_start(icon(icon_name, Gtk.IconSize.LARGE_TOOLBAR))
    window.set_titlebar(bar)
    return bar


def label(text="", css=None, xalign=0.0, wrap=True):
    widget = Gtk.Label(label=text, xalign=xalign)
    widget.set_line_wrap(wrap)
    if wrap:
        widget.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        widget.set_max_width_chars(60)
    if css:
        widget.get_style_context().add_class(css)
    return widget


def page_intro(title, subtitle):
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    box.pack_start(label(title, "page-title"), False, False, 0)
    box.pack_start(label(subtitle, "page-subtitle"), False, False, 0)
    return box


def card(title, description="", icon_name=None):
    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    outer.get_style_context().add_class("card")
    heading = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    if icon_name:
        heading.pack_start(icon(icon_name, Gtk.IconSize.LARGE_TOOLBAR), False, False, 0)
    heading.pack_start(label(title, "card-title"), True, True, 0)
    outer.pack_start(heading, False, False, 0)
    if description:
        outer.pack_start(label(description, "muted"), False, False, 0)
    return outer


def section(title, description="", icon_name=None):
    """Open settings group: divider instead of nested rounded card."""
    outer = card(title, description, icon_name)
    outer.get_style_context().remove_class("card")
    outer.get_style_context().add_class("settings-section")
    outer.set_spacing(8)
    return outer


def command_exists(name):
    return shutil.which(name) is not None


def admin_command(argv):
    if os.geteuid() == 0:
        return list(argv)
    helper = shutil.which("ooonana-run-admin")
    return [helper, *argv] if helper else list(argv)


def run(argv, admin=False, timeout=15, env=None, input_text=None, utf8=False):
    command = admin_command(argv) if admin else list(argv)
    command_env = os.environ.copy()
    if env:
        command_env.update(env)
    command_env["LC_ALL"] = "C"
    command_env["LANG"] = "C"
    if utf8:
        # Human metadata needs UTF-8; parser-facing commands keep C by default.
        command_env["LC_ALL"] = command_env["LANG"] = "C.UTF-8"
    try:
        owns_session = True
        try:
            process = subprocess.Popen(
                command,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdin=subprocess.PIPE if input_text is not None else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=command_env,
                start_new_session=True,
            )
        except PermissionError:
            owns_session = False
            process = subprocess.Popen(
                command,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdin=subprocess.PIPE if input_text is not None else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=command_env,
            )
        try:
            output, _ = process.communicate(input=input_text, timeout=timeout)
            return process.returncode, output.strip()
        except subprocess.TimeoutExpired:
            if owns_session:
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
            output, _ = process.communicate()
            detail = output.strip()
            suffix = f"\nTimed out after {timeout} seconds" if detail else f"Timed out after {timeout} seconds"
            return 124, detail + suffix
    except OSError as exc:
        return 124, str(exc)


def system_dbus_ready():
    if not Path("/run/dbus/system_bus_socket").exists():
        return False
    rc, _output = run(
        [
            "dbus-send",
            "--system",
            "--print-reply",
            "--dest=org.freedesktop.DBus",
            "/",
            "org.freedesktop.DBus.ListNames",
        ],
        timeout=3,
    )
    return rc == 0


def run_async(argv, callback, admin=False, timeout=30, env=None, input_text=None):
    def worker():
        result = run(
            argv,
            admin=admin,
            timeout=timeout,
            env=env,
            input_text=input_text,
        )
        GLib.idle_add(callback, *result)

    threading.Thread(target=worker, daemon=True).start()


def run_async_task(task, callback):
    def worker():
        try:
            result = task()
        except Exception as exc:  # Keep worker failures visible in the UI.
            result = (1, str(exc))
        GLib.idle_add(callback, *result)

    threading.Thread(target=worker, daemon=True).start()


def launch(argv, admin=False):
    command = admin_command(argv) if admin else list(argv)
    try:
        try:
            subprocess.Popen(command, start_new_session=True)
        except PermissionError:
            subprocess.Popen(command)
        return True
    except OSError:
        return False


def message_dialog(parent, title, text, kind=Gtk.MessageType.INFO):
    if len(text) <= 600 and text.count("\n") <= 8:
        dialog = Gtk.MessageDialog(
            transient_for=parent,
            modal=True,
            message_type=kind,
            buttons=Gtk.ButtonsType.CLOSE,
            text=title,
        )
        dialog.format_secondary_text(text)
        display = Gdk.Display.get_default()
        monitor = display.get_monitor_at_window(parent.get_window()) if display and parent and parent.get_window() else None
        if display:
            monitor = monitor or display.get_primary_monitor() or display.get_monitor(0)
        # GTK's fixed 64-character natural width can exceed a small monitor at
        # large text scales. Preserve normal density; wrap to the real budget.
        text_budget = max(1, monitor.get_workarea().width - 160) if monitor else None
        text_height = 0
        for child in dialog.get_message_area().get_children():
            if isinstance(child, Gtk.Label):
                child.set_line_wrap(True)
                child.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
                metrics = child.get_pango_context().get_metrics(None, None)
                # GtkLabel budgets characters by the larger char/digit metric.
                char_width = max(1, metrics.get_approximate_char_width() / Pango.SCALE,
                                 metrics.get_approximate_digit_width() / Pango.SCALE)
                child.set_max_width_chars(min(64, max(1, int(text_budget / char_width))) if text_budget else 64)
                if text_budget:
                    measured = child.get_layout().copy()
                    measured.set_width(int(text_budget * Pango.SCALE))
                    measured.set_wrap(Pango.WrapMode.WORD_CHAR)
                    text_height += measured.get_pixel_size()[1]
        if not monitor or text_height + 160 <= monitor.get_workarea().height:
            fit_dialog(dialog, -1)
            return dialog
        # A short character count can still be tall at large text sizes. Reuse
        # the existing scrollable diagnostics view rather than clip its actions.
        dialog.destroy()

    dialog = Gtk.Dialog(title=title, transient_for=parent, modal=True)
    header(dialog, title, "", "dialog-information-symbolic")
    dialog.set_resizable(True)
    dialog.add_button("Close", Gtk.ResponseType.CLOSE)
    dialog.set_default_response(Gtk.ResponseType.CLOSE)
    fit_dialog(dialog, 760, 520)

    area = dialog.get_content_area()
    area.set_border_width(16)
    area.set_spacing(12)
    heading = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
    icon_name = {
        Gtk.MessageType.ERROR: "dialog-error-symbolic",
        Gtk.MessageType.WARNING: "dialog-warning-symbolic",
    }.get(kind, "dialog-information-symbolic")
    heading.pack_start(icon(icon_name), False, False, 0)
    title_label = label(title, "card-title")
    title_label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
    title_label.set_max_width_chars(64)
    heading.pack_start(title_label, True, True, 0)
    area.pack_start(heading, False, False, 0)

    view = Gtk.TextView()
    view.set_editable(False)
    view.set_monospace(True)
    view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
    view.set_left_margin(12)
    view.set_right_margin(12)
    view.set_top_margin(10)
    view.set_bottom_margin(10)
    view.get_buffer().set_text(text)
    scroll = Gtk.ScrolledWindow()
    scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    scroll.add(view)
    area.pack_start(scroll, True, True, 0)

    copy_button = Gtk.Button()
    copy_button.set_image(icon("edit-copy-symbolic"))
    copy_button.set_tooltip_text("Copy diagnostics")
    copy_button.get_accessible().set_name("Copy diagnostics")
    copy_button.connect("clicked", lambda *_: Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(text, -1))
    dialog.get_action_area().pack_start(copy_button, False, False, 0)
    dialog.show_all()
    return dialog


def message(parent, title, text, kind=Gtk.MessageType.INFO):
    dialog = message_dialog(parent, title, text, kind)
    dialog.run()
    dialog.destroy()


def ask_text(parent, title, prompt, secret=False):
    dialog = Gtk.Dialog(title=title, transient_for=parent, modal=True)
    dialog.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Continue", Gtk.ResponseType.OK)
    dialog.set_default_size(460, -1)
    area = dialog.get_content_area()
    area.set_spacing(10)
    area.set_border_width(16)
    prompt_label = label(prompt)
    area.pack_start(prompt_label, False, False, 0)
    entry = Gtk.Entry()
    entry.set_visibility(not secret)
    entry.get_accessible().set_name(prompt)
    prompt_label.set_mnemonic_widget(entry)
    if secret:
        entry.set_input_purpose(Gtk.InputPurpose.PASSWORD)
    entry.set_activates_default(True)
    area.pack_start(entry, False, False, 0)
    dialog.set_default_response(Gtk.ResponseType.OK)
    dialog.show_all()
    entry.grab_focus()
    value = entry.get_text() if dialog.run() == Gtk.ResponseType.OK else ""
    dialog.destroy()
    return value if secret else value.strip()


def read_file(path, default=""):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return default


def set_busy(widget, busy=True):
    widget.set_sensitive(not busy)
    window = widget.get_toplevel()
    if isinstance(window, Gtk.Window) and window.get_window():
        cursor = Gdk.Cursor.new_from_name(window.get_display(), "wait") if busy else None
        window.get_window().set_cursor(cursor)
