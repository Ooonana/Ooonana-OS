#!/usr/bin/env python3
import os
import signal
import shutil
import subprocess
import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402


CSS = b"""
* { font-family: Sans; font-size: 10pt; }
window, dialog, .background { background: #080a0d; color: #f7ead0; }
headerbar { background: #11161d; color: #ffb21a; border-bottom: 1px solid #2a3442; padding: 4px 8px; }
headerbar .title { font-weight: 700; }
headerbar .subtitle { color: #9ba5b4; }
.hero { background: #11161d; border-bottom: 1px solid #29313c; }
.hero-title { font-size: 24pt; font-weight: 800; color: #ffb21a; }
.badge { background: #2a2110; color: #ffca61; border: 1px solid #795a18; border-radius: 4px; padding: 3px 8px; }
.sidebar { background: #0d1117; border-right: 1px solid #2a3442; }
.sidebar row { padding: 10px 14px; border-left: 3px solid transparent; }
.sidebar row:selected { background: #1b222c; border-left-color: #ffb21a; color: #ffb21a; }
.page-title { font-size: 18pt; font-weight: 700; color: #f7ead0; }
.page-subtitle, .muted { color: #9ba5b4; }
.card { background: #11161d; border: 1px solid #29313c; border-radius: 6px; padding: 14px; }
.card-title { font-size: 12pt; font-weight: 700; color: #ffb21a; }
.status-good { color: #70d69b; font-weight: 700; }
.status-warn { color: #ffd37a; font-weight: 700; }
.status-bad { color: #ff675c; font-weight: 700; }
button { background: #171e27; color: #f7ead0; border: 1px solid #364252; border-radius: 4px; padding: 7px 12px; }
button:hover { background: #222c38; border-color: #ffb21a; }
button.suggested-action { background: #ffb21a; color: #080a0d; border-color: #ffb21a; font-weight: 700; }
button.destructive-action { background: #351918; color: #ff8b82; border-color: #76332f; }
entry, textview, treeview, list { background: #0d1117; color: #f7ead0; border-color: #364252; }
entry { padding: 8px; border-radius: 4px; }
combobox button { min-height: 28px; }
checkbutton, radiobutton { padding: 4px 0; }
treeview header button { background: #171e27; color: #ffb21a; padding: 6px; }
treeview:selected, row:selected { background: #283441; color: #ffffff; }
notebook header { background: #0d1117; }
notebook tab { padding: 8px 14px; }
notebook tab:checked { color: #ffb21a; border-bottom: 2px solid #ffb21a; }
scale highlight { background: #ffb21a; }
scale trough { background: #2a3442; min-height: 6px; border-radius: 3px; }
scrollbar slider { background: #4d5a69; border-radius: 4px; min-width: 7px; min-height: 7px; }
scrollbar slider:hover { background: #ffb21a; }
separator { background: #29313c; }
"""


def apply_theme():
    provider = Gtk.CssProvider()
    provider.load_from_data(CSS)
    screen = Gdk.Screen.get_default()
    if screen:
        Gtk.StyleContext.add_provider_for_screen(
            screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )


def icon(name, size=Gtk.IconSize.BUTTON):
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


def header(window, title, subtitle="", icon_name="preferences-system-symbolic"):
    bar = Gtk.HeaderBar()
    bar.set_show_close_button(True)
    bar.set_title(title)
    bar.set_subtitle(subtitle)
    bar.set_decoration_layout("menu:minimize,maximize,close")
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
    try:
        owns_session = True
        try:
            process = subprocess.Popen(
                command,
                text=True,
                stdin=subprocess.PIPE if input_text is not None else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=env,
                start_new_session=True,
            )
        except PermissionError:
            owns_session = False
            process = subprocess.Popen(
                command,
                text=True,
                stdin=subprocess.PIPE if input_text is not None else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=env,
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


def message(parent, title, text, kind=Gtk.MessageType.INFO):
    dialog = Gtk.MessageDialog(
        transient_for=parent,
        modal=True,
        message_type=kind,
        buttons=Gtk.ButtonsType.CLOSE,
        text=title,
    )
    dialog.format_secondary_text(text)
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
