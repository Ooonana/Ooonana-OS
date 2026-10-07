#!/usr/bin/env python3
"""Isolated GTK interactions; owned fixture processes only, no provider/audio."""
import os
from pathlib import Path
import sys
import tempfile
import time

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "packages/ooonana/usr/lib/ooonana/ui"))
from common import Gdk, GLib, Gtk, apply_theme
import ai_app
from chat_widgets import ChatRequest


def spin(condition, timeout=5):
    deadline = time.monotonic() + timeout
    while not condition():
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        if time.monotonic() >= deadline:
            raise AssertionError("GTK fixture timeout")
        time.sleep(0.02)


def descendants(widget):
    yield widget
    if isinstance(widget, Gtk.Container):
        for child in widget.get_children():
            yield from descendants(child)


with tempfile.TemporaryDirectory() as temporary:
    os.environ["XDG_STATE_HOME"] = temporary
    os.environ["XDG_CONFIG_HOME"] = temporary
    ai_app.run = lambda command, **kwargs: (0, "active: nim\nlabel: Fixture provider" if command[-1] == "provider" else "active: Fixture model")
    calls = []

    def fixture_request(command, context, callback):
        calls.append((command, context))
        return ChatRequest([sys.executable, "-c", 'print("Fixture reply\\n```shell\\necho fixture\\n```")'], context, callback)

    ai_app.ChatRequest = fixture_request
    apply_theme()
    window = ai_app.AiWindow()
    window.show_all()
    spin(lambda: "Fixture" in window.model_label.get_text())
    # Small-window chat remains usable, with explicit access to hidden tools.
    from types import SimpleNamespace
    window.resized(window, SimpleNamespace(width=640))
    assert window.layout_mode == "compact" and window.sidebar_toggle.get_visible()
    assert not window.sidebar_revealer.get_reveal_child()
    window.sidebar_toggle.set_active(True)
    assert window.sidebar_revealer.get_reveal_child()
    window.resized(window, SimpleNamespace(width=1000))
    assert window.layout_mode == "normal" and not window.sidebar_toggle.get_visible()
    assert window.sidebar_revealer.get_reveal_child()
    window.composer.get_buffer().set_text("First fixture question")
    event = Gdk.EventKey()
    event.keyval = Gdk.KEY_Return
    event.state = Gdk.ModifierType.SHIFT_MASK
    assert not window.composer_key(window.composer, event)
    event.state = Gdk.ModifierType(0)
    assert window.composer_key(window.composer, event)
    spin(lambda: window.request is None)
    assert window.current["messages"][-1]["role"] == "assistant"
    assert calls and "--context-stdin" in calls[0][0]
    copy = next(widget for widget in descendants(window.messages) if isinstance(widget, Gtk.Button) and widget.get_accessible().get_name() == "Copy code")
    copy.clicked()
    assert Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).wait_for_text() == "echo fixture"
    first = window.current
    window.new_chat()
    window.append("You", "Second fixture topic", window.user_tag)
    window.search.set_text("First fixture")
    window.refresh_chats()
    assert len(window.chat_list.get_children()) == 1
    window.chat_list.select_row(window.chat_list.get_row_at_index(0))
    assert window.current is first
    GLib.timeout_add(20, lambda: (next(widget for widget in Gtk.Window.list_toplevels() if isinstance(widget, Gtk.MessageDialog)).response(Gtk.ResponseType.OK), False)[1])
    window.delete_chat()
    assert first not in window.store.threads
    cancelled = []
    request = ChatRequest(["/bin/sh", "-c", "sleep 30"], "[]", lambda rc, output: cancelled.append((rc, output)))
    request.cancel()
    spin(lambda: bool(cancelled))
    assert cancelled[0][0] == 130
    window.disconnect_by_func(window.closed)
    window.destroy()
print("GTK_AI_CHAT_RUNTIME_OK")
