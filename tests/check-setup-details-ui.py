#!/usr/bin/env python3
"""Private Setup form/review checks. No account, disk or network changes."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

assert os.environ.get("OOONANA_GUI_TEST_DISPLAY") == "1" and os.getuid() != 0
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana/ui"))
from common import Gdk, GLib, Gtk, apply_theme
import setup_app as setup

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
Gtk.Settings.get_default().set_property("gtk-xft-dpi", round(96 * 1024 * float(os.environ.get("OOONANA_GUI_TEXT_SCALE", "1.0"))))
apply_theme()
findings, workers, notices = [], [], []
setup.run = setup.launch = lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("Unexpected Setup command"))
setup.message = lambda _parent, title, *_args: notices.append(title)
setup.load_preferences = lambda: {"reduce_motion": True}
real_thread = setup.threading.Thread


class DeferredWorker:
    def __init__(self, *, target, daemon):
        self.target = target

    def start(self):
        workers.append(self.target)


def check(condition, text):
    if not condition:
        findings.append(text)
        print("SETUP_DETAILS_FINDING: " + text, flush=True)


def settle(seconds=.16):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
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
    root = Gdk.get_default_root_window()
    rect = window.get_window().get_frame_extents()
    check(0 <= rect.x and rect.x + rect.width <= root.get_width() and
          0 <= rect.y and rect.y + rect.height <= root.get_height(), name + ": frame outside display")
    Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height()).savev(str(out / (name + ".png")), "png", [], [])


def review_response(window, inspect, response=Gtk.ResponseType.CANCEL):
    def answer():
        dialog = next(item for item in Gtk.Window.list_toplevels() if isinstance(item, Gtk.Dialog) and item.get_visible())
        try:
            capture(dialog, "setup-review")
            check(dialog.get_default_widget() == dialog.get_widget_for_response(Gtk.ResponseType.CANCEL), "Review does not default to Back")
            inspect(dialog)
        finally:
            if not window.closed:
                dialog.response(response)
        return False
    GLib.timeout_add(250, answer)


assert subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode != 0
with tempfile.TemporaryDirectory(prefix="ooonana-setup-details-") as temporary:
    config = Path(temporary) / "i3.conf"
    config.write_text("\n".join(line for line in (ROOT / "branding/i3/config").read_text().splitlines() if not line.startswith("exec")) + "\n")
    wm = subprocess.Popen(["i3", "-c", str(config)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        until = time.monotonic() + 8
        while subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode:
            assert time.monotonic() < until
            time.sleep(.03)
        setup.threading.Thread = DeferredWorker
        window = setup.SetupWindow()
        window.show_all()
        window.network_combo.set_active_id("static")
        settle(.25)
        capture(window, "setup-static")
        scroll = next(w for w in descendants(window) if isinstance(w, Gtk.ScrolledWindow))
        for name in ("user_entry", "password_entry", "password_confirm", "network_combo", "address_entry", "gateway_entry", "dns_entry", "theme_combo", "repo_entry", "zram_combo", "disk_swap_check"):
            field = getattr(window, name)
            field.grab_focus()
            settle(.06)
            position = field.translate_coordinates(scroll, 0, 0)
            check(position is not None and position[1] >= 0 and position[1] + field.get_allocated_height() <= scroll.get_allocated_height(), name + ": focused field clipped")
        window.user_entry.set_text("Bad user!")
        window.repo_entry.grab_focus()
        window.apply(window.apply_button)
        check(window.get_focus() is window.user_entry, "Invalid user does not focus its field")
        check(not workers, "Invalid input dispatched Setup")
        window.user_entry.set_text("ooonana")
        window.address_entry.set_text("192.0.2.10/24")
        window.gateway_entry.set_text("192.0.2.1")
        window.dns_entry.set_text("192.0.2.53")
        window.repo_entry.set_text("file:///fixture/repository")
        secret = " fixture password "
        window.password_entry.set_text(secret)
        window.password_confirm.set_text(secret)
        invalid_cases = (
            (window.password_confirm, "different", "Password confirmation"),
            (window.address_entry, "192.0.2.10/99", "IPv4 prefix"),
            (window.gateway_entry, "not-an-ip", "IPv4 gateway"),
            (window.dns_entry, "192.0.2.53,invalid", "IPv4 DNS"),
            (window.repo_entry, "https://", "Repository host"),
        )
        for field, value, name in invalid_cases:
            previous = field.get_text()
            field.set_text(value)
            values, error = window.validate()
            check(values is None and bool(error), name + ": invalid input accepted")
            if error:
                window.apply(window.apply_button)
                check(window.get_focus() is field, name + ": error focus missing")
                check(secret == window.password_entry.get_text(), name + ": secret draft lost")
            field.set_text(previous)
        window.dns_entry.set_text("192.0.2.53 192.0.2.54")
        values, error = window.validate()
        check(not error and values["dns"] == "192.0.2.53,192.0.2.54" and values["password"] == secret, "Valid DNS normalization/password spaces lost")

        def inspect_review(dialog):
            check(dialog.get_destroy_with_parent(), "Review outlives Setup parent")
            text = "\n".join(item.get_text() for item in descendants(dialog) if isinstance(item, Gtk.Label))
            check(secret not in text and "file:///fixture/repository" in text and "192.0.2.10/24" in text, "Review omits routing/source or exposes password")
            window.apply(window.apply_button)
            check(sum(isinstance(item, Gtk.Dialog) and item.get_visible() for item in Gtk.Window.list_toplevels()) == 1, "Reentrant Apply opens duplicate review")

        review_response(window, inspect_review)
        window.apply(window.apply_button)
        check(not workers and not window.pending, "Back dispatched Setup")
        review_response(window, inspect_review, Gtk.ResponseType.OK)
        window.apply(window.apply_button)
        check(len(workers) == 1 and window.pending and not window.content.get_sensitive() and not window.cancel_button.get_sensitive(), "Approved Setup is not serialized")
        check(not window.spinner.get_property("active"), "Setup ignores reduced motion")
        window.apply(window.apply_button)
        check(len(workers) == 1 and window.before_close(), "Pending Setup allows duplicate dispatch/close")
        window.finished(window.apply_button, 1, "Fixture permission denied")
        check(not window.pending and window.content.get_sensitive() and "permission denied" in window.status.get_text() and "partial" in window.status.get_text(), "Setup failure has no persistent partial-change/retry feedback")
        check(window.password_entry.get_text() == secret, "Setup failure loses draft")
        capture(window, "setup-error")
        workers.clear()

        def close_parent(dialog):
            window.destroy()
            # Old implementation leaves an independent modal alive. Release it
            # to reproduce the stale-approval path without hanging the fixture.
            if not dialog.get_destroy_with_parent():
                dialog.response(Gtk.ResponseType.OK)

        review_response(window, close_parent)
        window.apply(window.apply_button)
        check(not workers, "Closed-parent review approval dispatched Setup")
    finally:
        setup.threading.Thread = real_thread
        wm.terminate()
        wm.wait(timeout=5)

if findings:
    raise SystemExit(1)
print("SETUP_DETAILS_UI_OK focus, bounds, review cancellation and closed-parent refusal; no backend commands")
