#!/usr/bin/env python3
"""Private managed GTK package review/health states. Every command is mocked."""
import argparse
import json
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
import packages_app as packages
import health_app as health

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("output", type=Path)
parser.add_argument("--baseline", action="store_true")
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
assert subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode != 0
apply_theme()
findings, jobs, messages = [], [], []


def check(condition, text):
    if not condition:
        findings.append(text)


def settle():
    deadline = time.monotonic() + 0.15
    while time.monotonic() < deadline:
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        time.sleep(0.005)


def capture(window, name):
    settle()
    screen = Gdk.get_default_root_window()
    rect = window.get_window().get_frame_extents()
    check(0 <= rect.x and rect.x + rect.width <= screen.get_width() and
          0 <= rect.y and rect.y + rect.height <= screen.get_height(), name + ": frame outside screen")
    Gdk.pixbuf_get_from_window(screen, 0, 0, screen.get_width(), screen.get_height()).savev(
        str(args.output / (name + ".png")), "png", [], [])


def text(view):
    buffer = view.get_buffer()
    return buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)


def respond(response, name):
    def callback():
        dialog = next(item for item in Gtk.Window.list_toplevels() if isinstance(item, Gtk.Dialog))
        check(dialog.get_default_widget() is dialog.get_widget_for_response(Gtk.ResponseType.CANCEL),
              name + ": review does not default to Cancel")
        capture(dialog, name)
        dialog.response(response)
        return False
    GLib.timeout_add(100, callback)


for module in (packages, health):
    module.run_async = lambda command, done, **kwargs: jobs.append((command, done, kwargs))
    module.load_preferences = lambda: {"reduce_motion": True}
packages.message = lambda _parent, title, *_args: messages.append(title)
packages.ask_text = lambda *_args, **_kwargs: "geany"

with tempfile.TemporaryDirectory(prefix="ooonana-package-ui-") as temporary:
    config = Path(temporary) / "i3.conf"
    config.write_text("\n".join(line for line in (ROOT / "branding/i3/config").read_text().splitlines()
                               if not line.startswith("exec")) + "\n")
    wm = subprocess.Popen(["i3", "-c", str(config)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + 8
        while subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode:
            assert time.monotonic() < deadline
            time.sleep(0.03)
        window = packages.PackagesWindow()
        window.show_all()
        for method, verb, answer in (("install_package", "get", Gtk.ResponseType.CANCEL),
                                     ("remove_package", "remove", Gtk.ResponseType.OK),
                                     ("upgrade_system", "upgrade", Gtk.ResponseType.CANCEL)):
            getattr(window, method)()
            command, done, _kwargs = jobs.pop()
            preview = command[-1] == "--dry-run"
            check(preview, verb + ": mutation submitted without review")
            if preview:
                respond(answer, "package-" + verb + "-review")
                done(0, "Fixture plan only\n" + "Would change dependency metadata and package payload.\n" * 20)
                if answer == Gtk.ResponseType.OK:
                    command, apply_done, _kwargs = jobs.pop()
                    check(command[1] == verb and "--dry-run" not in command, "Approval did not dispatch expected action")
                    check(window.before_close(), "Mutating transaction allowed normal close")
                    apply_done(1, "Permission denied fixture; no command executed.")
                    check(not window.before_close(), "Completed operation still blocks close")
                else:
                    check(not jobs, "Cancel submitted a mutation")
            else:
                done(1, "Blocked by fixture; no backend command executed.")
        packages.ask_text = lambda *_args, **_kwargs: "--force"
        window.remove_package()
        check(not jobs, "Package input accepted CLI option instead of package ID")
        if jobs:
            jobs.pop()[1](1, "Fixture refuses command")
        for invalid in ("geany chromium", "a" * 252):
            packages.ask_text = lambda *_args, value=invalid, **_kwargs: value
            window.install_package()
            check(not jobs, "Ambiguous/oversized package ID accepted")
        window.upgrade_system()
        window.upgrade_system()
        check(len(jobs) == 1 and not window.before_close(), "Duplicate preview or read-only close guard wrong")
        jobs.pop()[1](1, "Offline repository fixture")
        check(not jobs and window.status.get_style_context().has_class("status-bad"), "Failed preview submitted mutation")
        original_confirm = window.confirm_plan
        window.confirm_plan = lambda *_args: (_ for _ in ()).throw(AssertionError("No-op/empty plan opened approval"))
        for output in ("", "no upgrades"):
            window.upgrade_system()
            jobs.pop()[1](0, output)
            check(not jobs, "No-op/empty plan submitted mutation")
        window.confirm_plan = original_confirm
        capture(window, "packages-final")
        window.destroy()

        closing = packages.PackagesWindow()
        closing.show_all()
        closing.upgrade_system()
        def close_parent():
            closing.destroy()
            def release_orphan():
                for dialog in Gtk.Window.list_toplevels():
                    if isinstance(dialog, Gtk.Dialog) and dialog.get_transient_for() is closing and dialog.get_visible():
                        check(False, "Closing Packages leaves orphan review dialog")
                        dialog.response(Gtk.ResponseType.CANCEL)
                return False
            GLib.timeout_add(500, release_orphan)
            return False
        GLib.timeout_add(100, close_parent)
        jobs.pop()[1](0, "Fixture upgrade plan")
        check(closing.closed and not jobs, "Closing review parent submitted a mutation")

        sample = dict(kernel="fixture-kernel", architecture="x86_64", mode="live / developer", wsl=True,
            memory_bytes=dict(MemTotal=8 * 1024**3, MemAvailable=3 * 1024**3, SwapTotal=2 * 1024**3, SwapFree=1024**3),
            zram=[dict(device="zram0", logical_capacity=4 * 1024**3, original_data=300 * 1024**2,
                       compressed_data=100 * 1024**2, physical_consumption=110 * 1024**2)],
            services=dict(dbus=dict(state="ready", probe="system bus reply"),
                          audio=dict(state="not-ready", probe="audio server reply; no playback")),
            devices=dict(network=["eth0"], audio=[], bluetooth=[], gpu=[]), helpers=dict(i3=True, openvino=False),
            reboot_required=True, audio_playback_tested=False, hardware_functionality_tested=False)
        window = health.HealthWindow()
        window.show_all()
        jobs.pop()[1](0, json.dumps(sample, indent=2))
        check("memory_bytes" not in text(window.view) and "3.0 GiB" in text(window.view), "Health defaults to unreadable JSON")
        check("attention" in window.status.get_text().lower(), "Unready services falsely appear healthy/complete")
        check("physical" in text(window.view).lower(), "Health hides zram physical consumption distinction")
        capture(window, "health-summary")
        check(window.view.get_allocated_height() >= 150, "Health chrome crowds readable report")
        window.copy_button.clicked()
        check(json.loads(Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).wait_for_text()) == sample,
              "Copy does not preserve exact diagnostic data")
        toggle = getattr(window, "raw_toggle", None)
        check(toggle is not None, "Health has no raw diagnostic disclosure")
        if toggle:
            toggle.set_active(True)
            check(json.loads(text(window.view)) == sample, "Raw diagnostic disclosure loses fields")
            toggle.set_active(False)
        respond(Gtk.ResponseType.CANCEL, "health-metadata-cancel")
        window.refresh_repo()
        check(not jobs, "Metadata Cancel submitted update")
        respond(Gtk.ResponseType.OK, "health-metadata-review")
        window.refresh_repo()
        command, done, kwargs = jobs.pop()
        check(command == ["ooonana", "update"] and kwargs.get("admin"), "Confirmed metadata update lacks admin helper")
        done(1, "Fixture authentication denied; no command executed.")
        window.check()
        jobs.pop()[1](0, "not valid JSON")
        check("unrecognized" in window.status.get_text().lower(), "Malformed health output gets a success badge")
        capture(window, "health-malformed")
        # Actual backend schema, but private namespace has no host bus/audio.
        real = subprocess.run([sys.executable, str(ROOT / "packages/ooonana/usr/bin/ooonana-health"), "--json"],
                              text=True, capture_output=True, check=True, timeout=20)
        window.check()
        jobs.pop()[1](0, real.stdout)
        check(window.summary_output is not None and "Service endpoints" in text(window.view), "Actual report schema not rendered")
        capture(window, "health-real-isolated")
        window.destroy()
    finally:
        wm.terminate()
        wm.wait(timeout=5)

for finding in findings:
    print("PACKAGE_HEALTH_FINDING: " + finding, flush=True)
if findings and not args.baseline:
    raise SystemExit(1)
if not findings:
    print("PACKAGE_HEALTH_UI_OK cancel/approval/close guard; package IDs; readable/raw health and honest warning states")
