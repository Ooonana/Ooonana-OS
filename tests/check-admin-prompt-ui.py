#!/usr/bin/env python3
"""Real askpass component on owned X11; no sudo, credentials or host changes."""
import argparse
from contextlib import redirect_stdout
import io
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana/ui"))
from common import Gdk, GLib, Gtk, run

assert os.getuid() == 1000 and os.environ.get("OOONANA_GUI_TEST_DISPLAY") == "1"
assert subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode != 0
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("output", type=Path)
parser.add_argument("--baseline", action="store_true")
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
Gtk.Settings.get_default().set_property("gtk-xft-dpi", int(96 * 1024 * float(os.environ["OOONANA_GUI_TEXT_SCALE"])))
findings = []


def check(condition, message):
    if not condition:
        findings.append(message)
        print("ADMIN_PROMPT_FINDING", message, file=sys.__stdout__, flush=True)


def descendants(widget):
    yield widget
    if isinstance(widget, Gtk.Container):
        for child in widget.get_children():
            yield from descendants(child)


def settle():
    end = time.monotonic() + 0.1
    while time.monotonic() < end:
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        time.sleep(0.01)


with tempfile.TemporaryDirectory(prefix="ooonana-admin-prompt-") as temporary:
    config = Path(temporary) / "i3.conf"
    config.write_text("\n".join(line for line in (ROOT / "branding/i3/config").read_text().splitlines()
                               if not line.startswith("exec")) + "\n")
    wm = subprocess.Popen(["i3", "-c", str(config)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        end = time.monotonic() + 8
        while subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode:
            assert time.monotonic() < end, "Private window manager unavailable"
            time.sleep(0.02)
        for action in ("cancel", "close", "blank", "accept"):
            callback_errors = []

            def interact():
                dialog = next(item for item in Gtk.Window.list_toplevels()
                              if isinstance(item, Gtk.Dialog) and item.get_visible())
                try:
                    dialog.get_window().focus(Gdk.CURRENT_TIME)
                    entry = next(item for item in descendants(dialog) if isinstance(item, Gtk.Entry))
                    settle()
                    root = Gdk.get_default_root_window()
                    frame = dialog.get_window().get_frame_extents()
                    check(0 <= frame.x and frame.x + frame.width <= root.get_width() and
                          0 <= frame.y and frame.y + frame.height <= root.get_height(),
                          action + ": authorization dialog outside display")
                    check(bool(entry.get_accessible().get_name()), action + ": password field has no accessible name")
                    check(not entry.get_visibility() and entry.get_input_purpose() == Gtk.InputPurpose.PASSWORD,
                          action + ": password entry not protected")
                    check(dialog.get_focus() is entry, action + ": password field lacks initial keyboard focus")
                    for response in (Gtk.ResponseType.CANCEL, Gtk.ResponseType.OK):
                        button = dialog.get_widget_for_response(response)
                        position = button.translate_coordinates(dialog, 0, 0)
                        check(position is not None and position[0] >= 0 and position[1] >= 0 and
                              position[0] + button.get_allocated_width() <= dialog.get_allocated_width() and
                              position[1] + button.get_allocated_height() <= dialog.get_allocated_height(),
                              action + ": authorization action outside dialog")
                    # Capture before entering even the deliberately fake secret.
                    Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height()).savev(
                        str(args.output / (action + ".png")), "png", [], [])
                    if action != "blank":
                        entry.set_text("  owned-fixture-only  ")
                    if action == "close":
                        dialog.close()
                    else:
                        subprocess.run(["xdotool", "key", "--clearmodifiers",
                                        "Escape" if action == "cancel" else "Return"], check=True)
                except Exception as exc:
                    callback_errors.append(type(exc).__name__)
                    dialog.response(Gtk.ResponseType.CANCEL)
                return False

            GLib.timeout_add(250, interact)
            captured = io.StringIO()
            code = 0
            previous_path = sys.path[:]
            with redirect_stdout(captured):
                try:
                    runpy.run_path(str(ROOT / "packages/ooonana/usr/bin/ooonana-admin-askpass"), run_name="__main__")
                except SystemExit as exc:
                    code = exc.code
                finally:
                    sys.path[:] = previous_path
            assert not callback_errors, "Private prompt driver failed: " + ", ".join(callback_errors)
            if action == "accept":
                assert code == 0 and captured.getvalue() == "  owned-fixture-only  \n", "Accepted secret pipe contract changed"
            else:
                assert code == 1 and not captured.getvalue(), "Cancelled/blank authorization leaked output"
            assert not any(isinstance(item, Gtk.Dialog) and item.get_visible() for item in Gtk.Window.list_toplevels())
        print("ADMIN_PROMPT_RESULTS", findings, flush=True)
        if not args.baseline:
            assert not findings, "; ".join(findings)
        if not findings:
            print("ADMIN_PROMPT_UI_OK actual askpass, bounds, secret accessibility, Escape/close/Enter, pipe privacy", flush=True)

        # Real common -> generated admin helper -> sudo -> askpass cancellation.
        # Private sudoers permits only /bin/true, always requires authentication;
        # no password is entered here and no package command is submitted.
        assert os.environ.get("OOONANA_GUI_TEST_ADMIN_POLICY") == "1"
        # Parent verifies exact private policy before dropping UID. Do not make
        # protected sudoers readable merely to let this nonroot probe inspect it.
        assert Path("/etc/sudoers").stat().st_uid == 0
        assert Path("/etc/sudoers").stat().st_mode & 0o777 == 0o440
        policy = (ROOT / "tests/fixtures/admin-prompt.sudoers").read_text()
        assert "ooonana ALL=(root) PASSWD: /bin/true" in policy and "NOPASSWD" not in policy
        assert not any(Path("/etc/sudoers.d").iterdir())
        assert run(["sudo", "-n", "/bin/true"], timeout=3)[0] != 0, "Refusing passwordless admin fixture"
        assert run(["doas", "-n", "/bin/true"], timeout=3)[0] != 0, "Refusing passwordless fallback fixture"
        from packages_app import PackagesWindow
        from health_app import HealthWindow

        def cancel_auth(window, name, ready):
            seen = []
            deadline = time.monotonic() + 12

            def cancel():
                found = subprocess.run(["xdotool", "search", "--onlyvisible", "--name",
                                        "^Authorize( administration)?$"], capture_output=True, text=True)
                if found.returncode == 0 and found.stdout.strip():
                    identifier = found.stdout.splitlines()[0]
                    root = Gdk.get_default_root_window()
                    Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height()).savev(
                        str(args.output / (name + "-authorize.png")), "png", [], [])
                    subprocess.run(["xdotool", "windowfocus", identifier], check=True)
                    subprocess.run(["xdotool", "key", "--clearmodifiers", "Escape"], check=True)
                    seen.append(identifier)
                    return False
                return time.monotonic() < deadline and not ready()

            watcher = GLib.timeout_add(50, cancel)
            while not ready() and time.monotonic() < deadline:
                settle()
            if not seen and GLib.MainContext.default().find_source_by_id(watcher):
                GLib.source_remove(watcher)
            if not ready() or len(seen) != 1:
                print("ADMIN_ROUTE_FAILURE", name, window.status.get_text(), flush=True)
                root = Gdk.get_default_root_window()
                Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height()).savev(
                    str(args.output / (name + "-failure.png")), "png", [], [])
                print(run(["i3-msg", "-t", "get_tree"], timeout=2)[1], flush=True)
            assert ready() and len(seen) == 1, name + ": real sudo cancellation did not finish"
            assert "failed" in window.status.get_text().lower(), name + ": cancellation falsely reports success"
            root = Gdk.get_default_root_window()
            Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height()).savev(
                str(args.output / (name + "-cancelled.png")), "png", [], [])

        package_window = PackagesWindow()
        package_window.show_all()
        for attempt in ("package-admin", "package-admin-retry"):
            package_window.execute("Administrator check", ["/bin/true"], admin=True, mutating=True, timeout=15)
            cancel_auth(package_window, attempt, lambda: not package_window.busy)
            assert not package_window.write_pending and all(button.get_sensitive() for button in package_window.action_buttons)
        package_window.destroy()
        health_window = HealthWindow()
        health_window.show_all()
        deadline = time.monotonic() + 25
        while health_window.pending and time.monotonic() < deadline:
            settle()
        assert not health_window.pending, "Actual isolated health report did not settle"
        health_window.request(["/bin/true"], "Administrator check", 15, admin=True)
        cancel_auth(health_window, "health-admin", lambda: not health_window.pending)
        assert all(button.get_sensitive() for button in health_window.actions)
        health_window.destroy()
        print("ADMIN_CANCEL_ROUTE_OK actual sudo/askpass to Packages and Health, retry, controls restored; no package transaction", flush=True)
    finally:
        for item in Gtk.Window.list_toplevels():
            item.destroy()
        wm.terminate()
        wm.wait(timeout=5)
