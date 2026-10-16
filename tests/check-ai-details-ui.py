#!/usr/bin/env python3
"""Owned native chat UI only; no providers, OpenVINO, models or user history."""
import os
import faulthandler
from pathlib import Path
import subprocess
import sys
import tempfile
import time

assert os.environ.get("OOONANA_GUI_TEST_DISPLAY") == "1" and os.getuid() != 0
faulthandler.enable()
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana/ui"))
from common import Gdk, GLib, Gtk, apply_theme
import ai_app as ai

output = Path(sys.argv[1])
output.mkdir(parents=True, exist_ok=True)
findings, jobs = [], []
ai.run_async_task = lambda task, done: jobs.append((task, done))
ai.run_async = lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("Unexpected backend action"))
ai.run = lambda command, **_kwargs: (0, "active: nim\nlabel: Fixture provider" if command[-1] == "provider" else "active: fixture/model")
ai.AiWindow.offline_dialog = lambda *_args: (_ for _ in ()).throw(AssertionError("OpenVINO deferred"))
Gtk.Settings.get_default().set_property("gtk-xft-dpi", int(96 * 1024 * float(os.environ.get("OOONANA_GUI_TEXT_SCALE", "1.0"))))
apply_theme()


def check(condition, detail):
    if not condition:
        findings.append(detail)


def settle():
    deadline = time.monotonic() + .25
    while time.monotonic() < deadline:
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        time.sleep(.005)


def descendants(widget):
    yield widget
    if isinstance(widget, Gtk.Container):
        for child in widget.get_children():
            yield from descendants(child)


def capture(window, name):
    settle()
    screen = Gdk.get_default_root_window()
    rect = window.get_window().get_frame_extents()
    check(0 <= rect.x and rect.x + rect.width <= screen.get_width() and
          0 <= rect.y and rect.y + rect.height <= screen.get_height(), name + ": frame outside display")
    Gdk.pixbuf_get_from_window(screen, 0, 0, screen.get_width(), screen.get_height()).savev(str(output / (name + ".png")), "png", [], [])


def respond(name, inspect):
    def answer():
        dialog = next(item for item in Gtk.Window.list_toplevels() if isinstance(item, Gtk.Dialog) and item.get_visible())
        try:
            capture(dialog, name)
            inspect(dialog)
        finally:
            dialog.response(Gtk.ResponseType.CANCEL)
        return False
    GLib.timeout_add(350, answer)


with tempfile.TemporaryDirectory(prefix="ooonana-ai-details-") as temporary:
    os.environ["XDG_STATE_HOME"] = temporary
    os.environ["XDG_CONFIG_HOME"] = temporary
    config = Path(temporary) / "i3.conf"
    config.write_text("\n".join(line for line in (ROOT / "branding/i3/config").read_text().splitlines() if not line.startswith("exec")) + "\n")
    assert subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode != 0
    wm = subprocess.Popen(["i3", "-c", str(config)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + 8
        while subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode:
            assert time.monotonic() < deadline
            time.sleep(.03)
        window = ai.AiWindow()
        task, done = jobs.pop()
        done(*task())
        window.show_all()
        capture(window, "ai-empty")
        text_height = window.send_button.create_pango_layout("Send").get_pixel_size()[1]
        check(window.send_button.get_allocated_height() <= max(36, text_height + 18), "Composer action oversized relative to text")
        check(window.message_scroll.get_allocated_height() >= 130, "Compact chat leaves too little conversation room")
        heading = ("Long multilingual heading 한글 " * 18)[:80]
        language = "language-with-long-name-" * 15
        code = "print('한글 fixture')\n" + "x" * 160
        window.append(heading, "Fixture message\n```" + language + "\n" + code + "\n```", window.ai_tag)
        capture(window, "ai-long-message")
        labels = [item for item in descendants(window.messages) if isinstance(item, Gtk.Label)]
        for value in (heading, language):
            item = next(item for item in labels if item.get_text() == value)
            check(item.get_tooltip_text() == value, "Long heading/language lacks full tooltip")
            check(item.get_preferred_width()[0] < 300, "Long heading/language forces window width")
        copy = next(item for item in descendants(window.messages) if isinstance(item, Gtk.Button) and item.get_accessible().get_name() == "Copy code")
        copy.clicked()
        check(Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).wait_for_text() == code, "Code copy altered full content")

        window.sidebar_toggle.set_active(True)
        window.search.set_text("no-such-fixture-chat")
        window.refresh_chats()
        capture(window, "ai-search-empty")
        check(any(isinstance(item, Gtk.Label) and "No matching chats" in item.get_text() and item.get_visible()
                  for item in descendants(window.sidebar_box)), "Search no-match state missing")
        window.search.set_text("")
        window.refresh_chats()
        check(len(window.chat_list.get_children()) == 1, "Clearing search did not restore chat")
        window.sidebar_toggle.set_active(False)

        before = list(window.store.threads)
        def inspect_delete(dialog):
            check(dialog.get_default_widget() is dialog.get_widget_for_response(Gtk.ResponseType.CANCEL), "Delete lacks default Cancel")
            check(dialog.get_destroy_with_parent(), "Delete dialog survives parent close")
        respond("ai-delete-cancel", inspect_delete)
        window.delete_chat()
        check(window.store.threads == before, "Cancel deleted history")

        before = window.composer.get_buffer().get_char_count()
        def inspect_attachment(dialog):
            check(dialog.get_modal() and dialog.get_destroy_with_parent(), "Attachment lacks managed modal lifecycle")
            check(dialog.get_default_widget() is dialog.get_widget_for_response(Gtk.ResponseType.CANCEL), "Attachment lacks default Cancel")
        respond("ai-attachment-cancel", inspect_attachment)
        window.attach_text()
        check(window.composer.get_buffer().get_char_count() == before, "Attachment Cancel changed draft")

        attachment = Path(temporary) / "fixture.txt"
        attachment.write_text("한글 attachment\n", encoding="utf-8")
        def select_attachment():
            dialog = next(item for item in Gtk.Window.list_toplevels() if isinstance(item, Gtk.Dialog) and item.get_visible())
            chooser = next(item for item in descendants(dialog) if isinstance(item, Gtk.FileChooserWidget))
            chooser.set_filename(str(attachment))
            deadline = time.monotonic() + 3
            def insert():
                if chooser.get_filename() != str(attachment) and time.monotonic() < deadline:
                    return True
                check(chooser.get_filename() == str(attachment), "Attachment selection did not settle")
                check(dialog.get_widget_for_response(Gtk.ResponseType.OK).get_sensitive(), "Selected attachment cannot insert")
                dialog.response(Gtk.ResponseType.OK)
                return False
            GLib.timeout_add(100, insert)
            return False
        GLib.timeout_add(250, select_attachment)
        window.attach_text()
        draft = window.composer.get_buffer()
        check("한글 attachment" in draft.get_text(draft.get_start_iter(), draft.get_end_iter(), True), "UTF-8 attachment missing from editable draft")
        check(not jobs, "Attachment unexpectedly submitted backend work")

        window.refresh_model()
        stale_task, stale_done = jobs.pop()
        window.refresh_model()
        _task, current_done = jobs.pop()
        current_done(0, ("active: gemini\nlabel: Fixture Gemini", "active: current-model"))
        stale_done(*stale_task())
        check(window.model_label.get_text() == "current-model", "Stale provider callback overwrote current result")

        window.refresh_model()
        _task, done = jobs.pop()
        try:
            done(1, "Fixture provider unavailable")
        except Exception as error:
            findings.append("Failed provider callback raises " + type(error).__name__)
        check("unavailable" in window.model_label.get_text().lower(), "Failed provider lookup masquerades as valid model")
        window.refresh_model()
        task, done = jobs.pop()
        done(*task())
        check(window.model_label.get_text() == "model", "Provider retry did not recover")
        window.refresh_model()
        task, done = jobs.pop()
        window.destroy()
        try:
            done(*task())
        except Exception as error:
            findings.append("Closed provider callback raises " + type(error).__name__)
        check(not jobs, "Closed window queued extra provider work")
        settle()
    finally:
        wm.terminate()
        wm.wait(timeout=5)

for finding in findings:
    print("AI_DETAILS_FINDING: " + finding)
if findings:
    raise SystemExit(1)
print("AI_DETAILS_UI_OK generic chat only; no OpenVINO or provider calls")
