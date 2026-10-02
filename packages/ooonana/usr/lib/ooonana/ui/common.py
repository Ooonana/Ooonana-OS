#!/usr/bin/env python3
import os
import json
import signal
import shutil
import subprocess
import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Gdk, GLib, Gtk, Pango, PangoCairo  # noqa: E402
from ui_preferences import load_preferences, transition_ms  # noqa: E402


CSS = b"""
* { font-family: Sans; font-size: 10.5pt; }
window, dialog, .background { background: #101317; color: #f5f5f7; }
window.background, dialog.background, messagedialog.background { border-radius: 14px; }
decoration { background: #101317; border: 1px solid #343b46; border-radius: 14px; box-shadow: none; }
menu { background: #1b1f26; color: #f5f5f7; border: 1px solid #343b46; border-radius: 10px; padding: 6px; }
menuitem { padding: 9px 12px; border-radius: 7px; }
menuitem:hover { background: #303640; color: #ffb21a; }
headerbar { background: #1b1f26; color: #ffb21a; border-bottom: 1px solid #343b46; border-radius: 14px 14px 0 0; padding: 5px 10px; }
headerbar .title { font-weight: 700; }
headerbar .subtitle { color: #b4bdc8; }
.window-control { min-width: 18px; min-height: 18px; padding: 6px; border-radius: 9px; }
.close-control:hover { background: #b83832; color: #ffffff; border-color: #e85b52; }
.hero { background: #1b1f26; border-bottom: 1px solid #343b46; }
.hero-title { font-size: 24pt; font-weight: 800; color: #ffb21a; }
.badge { background: #32291a; color: #ffcf77; border: 1px solid #735b33; border-radius: 9px; padding: 4px 10px; }
.sidebar { background: #171b21; border-right: 1px solid #343b46; }
.sidebar row { margin: 3px 8px; padding: 10px 12px; border-left: 3px solid transparent; border-radius: 10px; transition: background-color 180ms ease-out; }
.sidebar row:selected { background: #303640; border-left-color: #ffb21a; color: #f5f5f7; }
.page-title { font-size: 19pt; font-weight: 700; color: #f5f5f7; }
.page-subtitle, .muted { color: #b4bdc8; }
.card { background: #1b1f26; border: 1px solid #343b46; border-radius: 14px; padding: 16px; }
.card-title { font-size: 12pt; font-weight: 700; color: #ffb21a; }
.status-good { color: #70d69b; font-weight: 700; }
.status-warn { color: #ffd37a; font-weight: 700; }
.status-bad { color: #ff675c; font-weight: 700; }
.status-neutral { color: #b4bdc8; }
button { background: #272c34; color: #f5f5f7; border: 1px solid #46505c; border-radius: 10px; padding: 8px 14px; transition: background-color 180ms ease-out; }
button:hover { background: #39414b; border-color: #ffb21a; }
button:focus, entry:focus, combobox button:focus { border-color: #ffb21a; box-shadow: 0 0 0 2px #73521e; }
button:disabled { background: #1b1f26; color: #78828f; border-color: #313944; }
button.suggested-action { background: #ffb21a; color: #101317; border-color: #ffb21a; font-weight: 700; }
button.suggested-action:disabled { background: #403624; color: #a5987f; border-color: #544733; }
button.destructive-action { background: #3b2324; color: #ffaaa3; border-color: #8a4749; }
button.destructive-action:disabled { background: #1b1f26; color: #78828f; border-color: #313944; }
entry, textview, textview text, textview.view, textview.view text, treeview, list {
  background: #15191f;
  color: #f5f5f7;
  border-color: #46505c;
}
entry { padding: 9px; border-radius: 10px; }
combobox button { min-height: 28px; }
checkbutton, radiobutton { padding: 4px 0; }
checkbutton check { background: #15191f; border: 1px solid #596574; border-radius: 4px; min-width: 14px; min-height: 14px; }
checkbutton check:checked { background: #ffb21a; color: #101317; border-color: #ffb21a; }
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
.spotlight-brand { color: #ffb21a; font-size: 12pt; font-weight: 800; }
.spotlight-search { font-size: 16pt; padding: 13px 16px; border-radius: 12px; }
.spotlight-results { background: #171b21; }
.spotlight-results row { padding: 10px 12px; border-top: 1px solid #303640; border-radius: 9px; transition: background-color 180ms ease-out; }
.spotlight-results row:hover, .spotlight-results row:selected { background: #303640; color: #ffffff; }
.spotlight-app-name { font-size: 11pt; font-weight: 700; }
"""

WINDOW_CONTROL_CSS = b"""
button.window-control { min-width: 18px; min-height: 18px; padding: 4px; border-radius: 99px; border: 1px solid #242830; color: #101317; box-shadow: none; }
button.close-control { background: #ff736b; }
button.minimize-control { background: #ffd16c; }
button.fullscreen-control { background: #7fd6a0; }
button.window-control:hover { border-color: #f5f5f7; }
button.window-control:focus { box-shadow: 0 0 0 2px #f5f5f7; }
"""


def apply_theme():
    provider = Gtk.CssProvider()
    provider.load_from_data(CSS)
    screen = Gdk.Screen.get_default()
    if screen:
        Gtk.StyleContext.add_provider_for_screen(
            screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
    settings = Gtk.Settings.get_default()
    if settings:
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


def button(label_text, icon_name=None, callback=None, style=None):
    widget = Gtk.Button.new_with_label(label_text)
    if icon_name:
        widget.set_image(icon(icon_name))
        widget.set_always_show_image(True)
    if callback:
        widget.connect("clicked", callback)
    if style:
        widget.get_style_context().add_class(style)
    return widget


def flow_row(widgets, max_children=8):
    widgets = list(widgets)
    row = Gtk.FlowBox()
    row.set_selection_mode(Gtk.SelectionMode.NONE)
    row.set_homogeneous(False)
    row.set_row_spacing(8)
    row.set_column_spacing(8)
    row.set_min_children_per_line(min(3, max_children, max(1, len(widgets))))
    row.set_max_children_per_line(max_children)
    row.set_valign(Gtk.Align.START)
    for widget in widgets:
        row.insert(widget, -1)
    return row


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
    display = Gdk.Display.get_default()
    monitor = (display.get_primary_monitor() or display.get_monitor(0)) if display else None
    if monitor:
        geometry = monitor.get_geometry()
        width, height = window.get_default_size()
        window.set_default_size(
            min(width, max(480, geometry.width - 64)) if width > 0 else width,
            min(height, max(320, geometry.height - 224)) if height > 0 else height,
        )
    bar = Gtk.HeaderBar()
    bar.set_show_close_button(False)
    bar.set_decoration_layout("")
    bar.set_title(title)
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
    maximize_button.set_image(icon("view-fullscreen-symbolic"))
    maximize_button.set_valign(Gtk.Align.CENTER)
    maximize_button.set_tooltip_text("Toggle fullscreen")
    maximize_button.set_name("ooonana-window-fullscreen")
    maximize_button.get_accessible().set_name("Toggle fullscreen")
    maximize_button.connect("clicked", maximize)
    maximize_button.get_style_context().add_class("window-control")
    maximize_button.get_style_context().add_class("fullscreen-control")

    minimize_button = Gtk.Button()
    minimize_button.set_image(icon("window-minimize-symbolic"))
    minimize_button.set_valign(Gtk.Align.CENTER)
    minimize_button.set_tooltip_text("Minimize window")
    minimize_button.set_name("ooonana-window-minimize")
    minimize_button.get_accessible().set_name("Minimize window")
    minimize_button.connect("clicked", minimize)
    minimize_button.get_style_context().add_class("window-control")
    minimize_button.get_style_context().add_class("minimize-control")

    close_button = Gtk.Button()
    close_button.set_image(icon("window-close-symbolic"))
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


def command_exists(name):
    return shutil.which(name) is not None


def admin_command(argv):
    if os.geteuid() == 0:
        return list(argv)
    helper = shutil.which("ooonana-run-admin")
    return [helper, *argv] if helper else list(argv)


def run(argv, admin=False, timeout=15, env=None, input_text=None):
    command = admin_command(argv) if admin else list(argv)
    command_env = os.environ.copy()
    if env:
        command_env.update(env)
    command_env["LC_ALL"] = "C"
    command_env["LANG"] = "C"
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
        for child in dialog.get_message_area().get_children():
            if isinstance(child, Gtk.Label):
                child.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
                child.set_max_width_chars(64)
        return dialog

    dialog = Gtk.Dialog(title=title, transient_for=parent, modal=True)
    dialog.set_wmclass("ooonana-app", "OoonanaApp")
    dialog.set_resizable(True)
    dialog.add_button("Close", Gtk.ResponseType.CLOSE)
    dialog.set_default_response(Gtk.ResponseType.CLOSE)
    width, height = 760, 520
    display = Gdk.Display.get_default()
    if display:
        monitor = display.get_monitor_at_window(parent.get_window()) if parent and parent.get_window() else None
        monitor = monitor or display.get_primary_monitor() or display.get_monitor(0)
        if monitor:
            workarea = monitor.get_workarea()
            width = max(1, min(width, workarea.width - 64))
            height = max(1, min(height, workarea.height - 64))
    dialog.set_default_size(width, height)

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
    area.pack_start(label(prompt), False, False, 0)
    entry = Gtk.Entry()
    entry.set_visibility(not secret)
    entry.set_activates_default(True)
    area.pack_start(entry, False, False, 0)
    dialog.set_default_response(Gtk.ResponseType.OK)
    dialog.show_all()
    value = entry.get_text().strip() if dialog.run() == Gtk.ResponseType.OK else ""
    dialog.destroy()
    return value


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
