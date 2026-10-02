import re
import signal
import subprocess
import threading
import os
from common import Gdk, GLib, Gtk, button, label, icon

AI_CSS = b"""
.ai-window { background: #101317; }
.ai-window headerbar { color: #f5f5f7; background: #1b1f26; }
.ai-sidebar { background: #171b21; border-right: 1px solid #343b46; }
.ai-sidebar button { background: transparent; border-color: transparent; padding: 10px 14px; }
.ai-sidebar button.suggested-action { background: #ffb21a; color: #101317; }
.ai-sidebar list { background: transparent; }
.ai-sidebar row { padding: 10px 12px; margin: 3px 0; border-radius: 10px; border-left: 3px solid transparent; }
.ai-sidebar row:selected { background: #303640; border-left-color: #ffb21a; }
.ai-user { background: #272c34; padding: 14px 18px; border-radius: 14px; }
.ai-assistant { background: #1b1f26; padding: 16px; border: 1px solid #343b46; border-radius: 14px; }
.ai-heading { color: #ffb21a; font-weight: 700; }
.ai-code { background: #101317; border: 1px solid #343b46; border-radius: 10px; }
.ai-code-header { background: #171b21; padding: 5px 12px; border-bottom: 1px solid #343b46; }
.ai-code textview, .ai-code textview text { background: #101317; font-family: Monospace; }
.ai-composer { background: #1b1f26; border: 1px solid #46505c; border-radius: 18px; padding: 8px; }
.ai-composer textview, .ai-composer textview text { background: #1b1f26; }
.ai-composer button { min-width: 20px; padding: 10px; border-radius: 12px; }
.ai-utility { padding: 6px 12px; }
button.ai-model, button.ai-model:hover { background: transparent; border-color: transparent; box-shadow: none; padding: 0; }
.ai-wide * { font-size: 14.5pt; }
.ai-wide headerbar * { font-size: 13pt; }
.ai-wide .ai-heading { font-size: 11.5pt; }
.ai-wide .ai-speaker { font-size: 11.5pt; }
.ai-wide .ai-hint { font-size: 10.5pt; }
.ai-wide .ai-composer { border-radius: 22px; }
.ai-wide .ai-sidebar button { border-radius: 14px; }
"""


def apply_ai_theme(window):
    window.get_style_context().add_class("ai-window")
    provider = Gtk.CssProvider()
    provider.load_from_data(AI_CSS)
    Gtk.StyleContext.add_provider_for_screen(window.get_screen(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)


def message_widget(message):
    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    user = message["role"] == "user"
    outer.set_halign(Gtk.Align.END if user else Gtk.Align.FILL)
    heading = message.get("heading") or ("You" if user else "Ooonana")
    speaker = label(heading, "muted" if user else "ai-heading", wrap=False)
    speaker.get_style_context().add_class("ai-speaker")
    outer.pack_start(speaker, False, False, 0)
    bubble = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    bubble.get_style_context().add_class("ai-user" if user else "ai-assistant")
    parts = re.split(r"(```[^\n]*\n.*?```)", message["content"], flags=re.S)
    for part in parts:
        if not part.strip():
            continue
        if part.startswith("```") and part.endswith("```"):
            language, code = part[3:-3].split("\n", 1)
            code = code.rstrip("\n")
            block = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            block.get_style_context().add_class("ai-code")
            toolbar = Gtk.Box(spacing=8)
            toolbar.get_style_context().add_class("ai-code-header")
            toolbar.pack_start(label(language or "text", "muted", wrap=False), True, True, 0)
            copy = button("", "edit-copy-symbolic", lambda _widget, text=code: Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(text, -1))
            copy.set_tooltip_text("Copy code")
            copy.get_accessible().set_name("Copy code")
            toolbar.pack_end(copy, False, False, 0)
            block.pack_start(toolbar, False, False, 0)
            view = Gtk.TextView(editable=False, cursor_visible=False)
            view.set_monospace(True)
            view.set_wrap_mode(Gtk.WrapMode.NONE)
            view.set_left_margin(14)
            view.set_top_margin(12)
            view.set_bottom_margin(12)
            view.get_buffer().set_text(code)
            scroll = Gtk.ScrolledWindow()
            scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
            scroll.set_min_content_height(min(240, 28 + 20 * (code.count("\n") + 1)))
            scroll.add(view)
            block.pack_start(scroll, True, True, 0)
            bubble.pack_start(block, False, False, 0)
        else:
            text = label(part.strip())
            text.set_selectable(True)
            text.set_max_width_chars(68)
            bubble.pack_start(text, False, False, 0)
    outer.pack_start(bubble, False, False, 0)
    return outer


def sidebar_button(title, icon_name, callback, primary=False):
    widget = Gtk.Button()
    row = Gtk.Box(spacing=14)
    row.pack_start(icon(icon_name, Gtk.IconSize.LARGE_TOOLBAR), False, False, 0)
    row.pack_start(label(title, wrap=False), True, True, 0)
    widget.add(row)
    widget.connect("clicked", callback)
    if primary:
        widget.get_style_context().add_class("suggested-action")
    return widget


class ChatRequest:
    """Own only CLI child; cancellation never stops shared local API."""
    def __init__(self, command, context, callback):
        self.lock = threading.Lock()
        self.process = None
        self.cancelled = False
        self.callback = callback
        threading.Thread(target=self._run, args=(command, context), daemon=True).start()

    def cancel(self):
        with self.lock:
            self.cancelled = True
            if self.process and self.process.poll() is None:
                try:
                    os.killpg(self.process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
        timer = threading.Timer(3, self._force_stop)
        timer.daemon = True
        timer.start()

    def _force_stop(self):
        with self.lock:
            if self.cancelled and self.process and self.process.poll() is None:
                try:
                    os.killpg(self.process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass

    def _run(self, command, context):
        try:
            with self.lock:
                if self.cancelled:
                    GLib.idle_add(self.callback, 130, "Request cancelled. Shared API remains running.")
                    return
                self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)
            try:
                output, _ = self.process.communicate(context, timeout=300)
            except subprocess.TimeoutExpired:
                self.cancel()
                try:
                    output, _ = self.process.communicate(timeout=3)
                except subprocess.TimeoutExpired:
                    os.killpg(self.process.pid, signal.SIGKILL)
                    output, _ = self.process.communicate()
            if self.cancelled:
                status, output = 130, "Request cancelled. Shared API may still finish generation."
            else:
                status = self.process.returncode
        except (OSError, ValueError) as error:
            status, output = 1, str(error)
        GLib.idle_add(self.callback, status, output[-100000:])
