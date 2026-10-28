#!/usr/bin/env python3
"""Owned i3/GApplication flyout interactions; private null sound, no hardware writes."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "packages/ooonana/usr/lib/ooonana/ui"
sys.path.insert(0, str(UI))
from common import Gdk, Gio, GLib, Gtk, run_async_task
from shell_flyout import ShellApplication

assert os.getuid() == 1000 and os.environ.get("OOONANA_GUI_TEST_DISPLAY") == "1"


def settle(seconds=.2):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        time.sleep(.01)


def wait(predicate, detail, seconds=15):
    until = time.monotonic() + seconds
    while not predicate():
        assert time.monotonic() < until, detail
        settle(.02)
    settle()


if sys.argv[1:2] == ["--worker"]:
    marker = Path(sys.argv[2])
    app = ShellApplication()
    def finish_after_dismiss():
        def task():
            time.sleep(.35)
            marker.write_text("finished")
            return 0, ""
        run_async_task(task, lambda *_: None)
        app.dismiss(False)
        return False
    GLib.idle_add(finish_after_dismiss)
    raise SystemExit(app.run(["owned-shell-worker", "apps"]))

assert subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode
assert not Path("/dev/snd").exists()
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
Gtk.Settings.get_default().set_property("gtk-xft-dpi", round(96 * 1024 * float(os.environ["OOONANA_GUI_TEXT_SCALE"])))


def tree():
    return json.loads(subprocess.check_output(["i3-msg", "-t", "get_tree"], text=True))


def clients(node=None):
    node = tree() if node is None else node
    result = [node] if node.get("window") else []
    for child in node.get("nodes", []) + node.get("floating_nodes", []): result.extend(clients(child))
    return result


def command(text):
    result = json.loads(subprocess.check_output(["i3-msg", text], text=True))
    assert all(item.get("success") for item in result), result


def stop(process):
    if process is not None and process.poll() is None:
        process.terminate(); process.wait(timeout=5)


with tempfile.TemporaryDirectory(prefix="ooonana-shell-session-") as temporary:
    fixture = Path(temporary)
    config = fixture / "i3.conf"
    # Runtime placement must work with older/custom configs too.
    config.write_text("\n".join(line for line in (ROOT / "branding/i3/config").read_text().splitlines()
                               if not line.startswith("exec") and "OoonanaFlyout" not in line) + "\n")
    socket = fixture / "pulse.sock"
    pulse_config = fixture / "pulse.pa"
    pulse_config.write_text(f"load-module module-native-protocol-unix socket={socket} auth-anonymous=1\n"
                            "load-module module-null-sink sink_name=qa_silent\n")
    os.environ.update(PULSE_SERVER="unix:" + str(socket))
    logs = (out / "services.log").open("w")
    wm = subprocess.Popen(["i3", "-c", str(config)], stdout=logs, stderr=logs)
    pulse = parent = None
    app = ShellApplication()
    failures = []
    try:
        wait(lambda: subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode == 0, "Owned i3 unavailable")
        pulse = subprocess.Popen(["pulseaudio", "-n", "--daemonize=no", "--exit-idle-time=-1", "--use-pid-file=no", "--file=" + str(pulse_config)], stdout=logs, stderr=logs)
        wait(lambda: socket.exists() and pulse.poll() is None, "Null PulseAudio unavailable")
        parent = subprocess.Popen(["xterm", "-title", "Ooonana QA Parent", "-e", "sleep", "180"], stdout=logs, stderr=logs)
        wait(lambda: any(item.get("name") == "Ooonana QA Parent" for item in clients()), "Owned parent unavailable")
        parent_node = next(item for item in clients() if item.get("name") == "Ooonana QA Parent")
        parent_id, parent_xid = parent_node["id"], parent_node["window"]
        command(f"[con_id={parent_id}] focus")

        def capture(name):
            settle(.3)
            root = Gdk.get_default_root_window()
            Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height()).savev(str(out / (name + ".png")), "png", [], [])

        def verify(kind):
            wait(lambda: app.window is not None and app.window.is_active(), "Flyout did not take keyboard focus: " + kind)
            settle(.3)
            raw = [item for item in clients() if (item.get("window_properties") or {}).get("class") == "OoonanaFlyout"]
            assert len(raw) == 1 and raw[0].get("border") == "none", raw
            rect = app.window.get_window().get_frame_extents()
            area = app.window.get_display().get_monitor_at_window(app.window.get_window()).get_workarea()
            assert area.x <= rect.x and rect.x + rect.width <= area.x + area.width, (kind, rect)
            assert area.y + 30 <= rect.y and rect.y + rect.height <= area.y + area.height - 40, (kind, rect)
            assert app.window.get_skip_taskbar_hint() and app.window.get_skip_pager_hint() and not app.window.get_decorated()

        def remote(module, *args):
            assert module == "launcher_app.py"
            process = subprocess.Popen(["/bin/sh", str(ROOT / "packages/ooonana/usr/bin/ooonana-shell"), "apps", *args], stdout=logs, stderr=logs)
            wait(lambda: process.poll() is not None, "Remote flyout command stalled")
            assert process.returncode == 0

        def driver():
            app.hold()  # Test lifetime only; separate worker below proves real hold behavior.
            try:
                verify("apps")
                app.window.search.set_text("no matching application qa")
                settle()
                assert app.window.empty_state.get_visible()
                capture("apps-empty")
                subprocess.run(["xdotool", "key", "--clearmodifiers", "Escape"], check=True)
                wait(lambda: app.window is None, "Escape did not dismiss launcher")
                wait(lambda: next(item for item in clients() if item["id"] == parent_id).get("focused"), "Escape failed to restore exact parent")
                remote("launcher_app.py", "--panel")
                verify("panel launcher")
                assert app.controller.anchor == "left"
                # Actual triggering click and separate CLI process must toggle,
                # rather than close then reopen after the outside-click timer.
                subprocess.run(["xdotool", "mousemove", "30", "20", "click", "1"], check=True)
                remote("launcher_app.py", "--panel")
                assert app.window is None, "Panel toggle reopened launcher"
                remote("launcher_app.py")
                verify("dock launcher")
                desktop = fixture / "owned.desktop"
                desktop.write_text("[Desktop Entry]\nType=Application\nName=Owned handoff\nExec=xterm -title Ooonana-QA-Launched -e sleep 30\n")
                app.window.launch_app(Gio.DesktopAppInfo.new_from_filename(str(desktop)))
                wait(lambda: app.window is None and any(item["name"] == "Ooonana-QA-Launched" for item in clients()), "Launcher did not hand off and dismiss")
                opened = next(item for item in clients() if item["name"] == "Ooonana-QA-Launched")
                command(f"[con_id={opened['id']}] kill")
                command(f"[con_id={parent_id}] focus")
                for kind in ("notifications", "controls", "audio", "brightness", "wifi", "bluetooth", "power"):
                    app.show_surface(kind)
                    verify(kind)
                    wait(lambda: not any(app.pending.values()), "Initial request did not settle: " + kind, seconds=55)
                    if kind == "notifications":
                        subprocess.run(["notify-send", "--app-name=Owned QA", "Screenshot saved", "Review copy ready."], check=True)
                        app.window.refresh(collect_popups=True)
                        wait(lambda: not app.window.refreshing and bool(app.window.records), "Real notification did not appear in flyout")
                    if kind == "controls":
                        capture("controls")
                        app.window._shell_initial_focus.grab_focus()
                        for _ in range(24):
                            if app.window.get_focus() is app.window.settings_button:
                                break
                            subprocess.run(["xdotool", "key", "Tab"], check=True)
                            settle(.025)
                        assert app.window.get_focus() is app.window.settings_button, "Footer unreachable by keyboard"
                        footer_button = app.window.settings_button
                        point = footer_button.translate_coordinates(app.window, 0, 0)
                        assert point is not None and min(point) >= 4
                        assert point[0] + footer_button.get_allocated_width() <= app.window.get_allocated_width() - 4
                        assert point[1] + footer_button.get_allocated_height() <= app.window.get_allocated_height() - 4, "Footer/focus outline clips at viewport edge"
                        if not app.window.brightness.ready and not app.window.brightness.busy:
                            assert not app.window.brightness_controls.get_visible(), "Unavailable backlight leaves dead controls"
                        capture("controls-footer")
                        app.window._shell_initial_focus.grab_focus()
                        settle()
                    if kind in ("notifications", "audio"):
                        capture(kind)
                current = app.window
                assert app.do_command_line(type("Command", (), {"get_arguments": lambda _: ["qa", "invalid;touch nope"]})()) == 2
                assert app.window is current
                app.show_surface("audio")
                wait(lambda: not any(app.pending.values()), "Sound initial state pending")
                old = app.window
                dialog = Gtk.Dialog(title="Owned nested dialog", transient_for=old, modal=True)
                dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
                dialog.show_all(); dialog.present(); settle(.35)
                assert app.window is old and old.get_visible(), "Nested dialog dismissed its flyout"
                dialog.destroy(); settle(.25)
                assert app.window is old, "Nested dialog close dismissed parent"
                wait(lambda: old.is_active(), "Nested dialog did not restore parent focus")
                authorize = []
                prompt_env = {**os.environ, **app.command_environment()}
                def askpass():
                    result = subprocess.run([sys.executable, str(ROOT / "packages/ooonana/usr/bin/ooonana-admin-askpass")],
                                            env=prompt_env, stdout=subprocess.PIPE, stderr=logs, text=True, timeout=15)
                    return result.returncode, result.stdout
                run_async_task(askpass, lambda rc, output: authorize.append((rc, output)))
                wait(lambda: any(item.get("name", "").startswith("Authorize") for item in clients()), "Separate askpass did not appear")
                settle(.35)
                assert app.window is old and old.get_visible(), "Authorization prompt dismissed flyout"
                auth = next(item for item in clients() if item.get("name", "").startswith("Authorize"))
                assert auth["window_properties"]["transient_for"] == next(item["window"] for item in clients() if item.get("window_properties", {}).get("class") == "OoonanaFlyout")
                subprocess.run(["xdotool", "key", "--clearmodifiers", "Escape"], check=True)
                wait(lambda: bool(authorize), "Cancelled authorization did not return")
                assert authorize == [(1, "")], "Cancelled askpass returned secret/output"
                settle(.5)
                assert app.window is old and old.is_active(), "Authorization cancellation lost parent/focus"
                done = []
                run_async_task(lambda: (time.sleep(.4), (0, "finished"))[1], lambda *_: done.append(True))
                app.dismiss(False)
                app.show_surface("brightness")
                assert app.waiting, "Hidden control request allowed overlapping mutation"
                wait(lambda: done and app.window is not None and not app.waiting and not any(app.pending.values()), "Pending request did not resume controls")
                app.dismiss(True)
                command(f"[con_id={parent_id}] fullscreen enable")
                baseline = next(item for item in clients() if item["id"] == parent_id)
                app.show_surface("apps")
                verify("fullscreen apps")
                during = next(item for item in clients() if item["id"] == parent_id)
                assert during["fullscreen_mode"] == baseline["fullscreen_mode"] and during["rect"] == baseline["rect"], "Flyout interrupted fullscreen"
                app.dismiss(True)
                settle()
                after = next(item for item in clients() if item["id"] == parent_id)
                assert after["fullscreen_mode"] == baseline["fullscreen_mode"] and after["rect"] == baseline["rect"]
                command(f"[con_id={parent_id}] fullscreen disable")
                app.show_surface("notifications")
                verify("click focus")
                rect = next(item for item in clients() if item["id"] == parent_id)["rect"]
                subprocess.run(["xdotool", "mousemove", str(rect["x"] + 12), str(rect["y"] + 60)], check=True)
                settle(.3)
                assert app.window is not None, "Hover dismissed flyout"
                subprocess.run(["xdotool", "click", "1"], check=True)
                wait(lambda: app.window is None, "Outside application click did not dismiss")
                assert next(item for item in clients() if item["id"] == parent_id).get("focused"), "Dismissal stole outside-click focus"
                app.show_surface("notifications")
                verify("outside dismissal")
                subprocess.run(["xdotool", "mousemove", "30", "150", "click", "1"], check=True)
                wait(lambda: app.window is None, "Outside click did not dismiss")
                print("SHELL_FLYOUT_UI_OK actual i3/GApplication, anchors, keyboard/dismissal, nested dialogs, worker serialization, fullscreen preservation", flush=True)
            except Exception as error:
                import traceback
                traceback.print_exc()
                capture("failure")
                failures.append(repr(error))
                print("SHELL_FLYOUT_FAILURE", repr(error), json.dumps(clients()), flush=True)
            finally:
                app.dismiss(False); app.release(); app.quit()
            return False
        GLib.idle_add(driver)
        app.run(["owned-shell-qa", "apps"])
        assert not failures, failures
        marker = out / "worker-finished"
        subprocess.run(["dbus-run-session", "--", sys.executable, __file__, "--worker", str(marker)], check=True, timeout=15)
        assert marker.read_text() == "finished", "Dismissal killed in-flight request"
        print("SHELL_FLYOUT_WORKER_OK actual separate process stays alive until result after last window closes", flush=True)
        cold = subprocess.Popen(["dbus-run-session", "--", "/bin/sh", str(ROOT / "packages/ooonana/usr/bin/ooonana-shell"), "apps", "--panel"], stdout=logs, stderr=logs)
        try:
            wait(lambda: cold.poll() is not None or any(item.get("window_properties", {}).get("class") == "OoonanaFlyout" for item in clients()), "Cold launcher did not start")
            assert cold.poll() is None, "Cold client failed instead of starting primary"
            opened = next(item for item in clients() if item.get("window_properties", {}).get("class") == "OoonanaFlyout")
            command(f"[con_id={opened['id']}] focus")
            subprocess.run(["xdotool", "key", "--clearmodifiers", "Escape"], check=True)
            wait(lambda: cold.poll() is not None, "Cold primary did not exit after dismissal")
            assert cold.returncode == 0
            print("SHELL_FLYOUT_COLD_OK real CLI starts missing primary and exits on Escape", flush=True)
        finally:
            stop(cold)
    finally:
        app.dismiss(False)
        stop(parent); stop(pulse); stop(wm); logs.close()
