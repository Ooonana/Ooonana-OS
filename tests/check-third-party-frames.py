#!/usr/bin/env python3
"""Real client/frame capture on explicitly isolated Xvfb/Xephyr; private profiles."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana/ui"))
from common import Gdk, Gtk
from window_controls import Manager, WIDTH
import i3_events

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("app", choices=("geany", "nemo", "chromium", "qterminal"))
parser.add_argument("output", type=Path)
parser.add_argument("--csd", action="store_true")
parser.add_argument("--compositor", action="store_true", help="Capture packaged rounding policy through private xrender compositor")
parser.add_argument("--disable-shader-cache", action="store_true", help="QA-only Chromium disk-cache isolation, sandbox remains enabled")
parser.add_argument("--gpu", action="store_true", help="Leave normal GPU selection enabled (device availability remains environment-dependent)")
parser.add_argument("--url", default="about:blank", help="Private browser probe page")
parser.add_argument("--file-dialog", action="store_true", help="Geany's real Open dialog: cancel and open an owned fixture")
args = parser.parse_args()
if args.file_dialog and args.app != "geany":
    parser.error("--file-dialog requires geany")
if os.environ.get("OOONANA_GUI_TEST_DISPLAY") != "1":
    raise SystemExit("Explicit isolated display required")
if subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode == 0:
    raise SystemExit("Refusing display with existing window manager")


def drain():
    while Gtk.events_pending():
        Gtk.main_iteration_do(False)


def wait(predicate):
    deadline = time.monotonic() + 30
    while True:
        result = predicate()
        if result:
            return result
        drain()
        assert time.monotonic() < deadline, "Client/frame timeout"
        time.sleep(0.03)


def find_client():
    def visit(node):
        if node.get("window"):
            klass = str((node.get("window_properties") or {}).get("class", "")).lower()
            if klass.startswith(args.app):
                return node
        for child in node.get("nodes", []) + node.get("floating_nodes", []):
            found = visit(child)
            if found:
                return found
        return None
    return visit(i3_events.request(i3_events.socket_path(), 4))


def browser_sandboxes():
    """Kernel state, not a command-line flag or version-specific internal page."""
    states = {}
    for process in browser_process_diagnostics():
        kind = next((argument.removeprefix("--type=") for argument in process["arguments"].split()
                     if argument.startswith("--type=")), "")
        if kind in ("renderer", "gpu-process"):
            states.setdefault(kind, []).append({"pid": process["pid"],
                "seccomp": int(process["seccomp"]), "no_new_privs": int(process["no_new_privs"])})
    return states


def browser_process_diagnostics():
    states = []
    for process in Path("/proc").glob("[0-9]*"):
        try:
            status = dict(line.split(":", 1) for line in process.joinpath("status").read_text().splitlines() if ":" in line)
            if "chrom" not in status.get("Name", "").lower():
                continue
            try:
                arguments = process.joinpath("cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
            except OSError as error:
                arguments = str(error)
            states.append({"pid": int(process.name), "ppid": status.get("PPid", "").strip(),
                           "seccomp": status.get("Seccomp", "").strip(),
                           "no_new_privs": status.get("NoNewPrivs", "").strip(), "arguments": arguments})
        except OSError:
            continue
    return states


def ready_browser_sandboxes():
    # Newly forked renderers briefly precede sandbox initialization. Wait for
    # the same nonempty snapshot to show actual filtering and privilege lock.
    states = browser_sandboxes()
    if not all(states.get(kind) for kind in ("renderer", "gpu-process")):
        return None
    if not all(state["seccomp"] == 2 and state["no_new_privs"] == 1
               for group in states.values() for state in group):
        return None
    return states


args.output.parent.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="ooonana-client-frame-") as temporary, args.output.with_suffix(".log").open("w") as log:
    fixture = Path(temporary)
    config = fixture / "i3.conf"
    config.write_text("\n".join(line for line in (ROOT / "branding/i3/config").read_text().splitlines()
                                if not line.startswith("exec")) + "\n")
    environment = {**os.environ, "GDK_BACKEND": "x11", "GTK_THEME": "Adwaita:dark",
                   "GTK_CSD": "1" if args.csd else "0", "XDG_CONFIG_HOME": str(fixture / "config"),
                   "XDG_CACHE_HOME": str(fixture / "cache"), "XDG_STATE_HOME": str(fixture / "state"),
                   "PATH": str(ROOT / "packages/ooonana/usr/bin") + ":" + os.environ["PATH"]}
    environment.pop("WAYLAND_DISPLAY", None)
    environment["NO_AT_BRIDGE"] = "1"
    os.environ["PATH"] = environment["PATH"]
    command = {
        "geany": ["geany", "--new-instance", "--config=" + str(fixture / "geany")],
        "nemo": ["nemo", "--no-desktop", str(fixture)],
        "qterminal": ["qterminal", "--workdir", str(fixture), "--execute", "/bin/sh"],
        "chromium": ["chromium", "--user-data-dir=" + str(fixture / "chromium"), "--no-first-run",
                     "--disable-background-networking", "--disable-component-update", "--password-store=basic",
                     "--disable-gpu", "about:blank"],
    }[args.app]
    if args.app == "chromium" and args.disable_shader_cache:
        command.insert(-1, "--disable-gpu-shader-disk-cache")
    if args.app == "chromium":
        command[-1] = args.url
        if args.gpu:
            command.remove("--disable-gpu")
    wm = subprocess.Popen(["i3", "-c", str(config)], stdout=log, stderr=log)
    client = None
    manager = None
    compositor = None
    try:
        wait(lambda: subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode == 0)
        if args.compositor:
            builder = (ROOT / "scripts/build-full-i3-rootfs.sh").read_text()
            policy = builder.split('"$ROOTFS/etc/ooonana/picom.conf" <<\'EOF\'\n', 1)[1].split("\nEOF", 1)[0]
            compositor_config = fixture / "picom.conf"
            compositor_config.write_text(policy)
            subprocess.run(["xsetroot", "-solid", "#555963"], check=True)
            compositor = subprocess.Popen(["picom", "--backend", "xrender", "--config", str(compositor_config)],
                                          stdout=log, stderr=log)
        client = subprocess.Popen(command, env=environment, stdout=log, stderr=log, start_new_session=True)
        wait(find_client)
        if args.app == "chromium":
            try:
                sandboxes = wait(ready_browser_sandboxes)
            except AssertionError:
                print("BROWSER_PROCESS_DIAGNOSTICS", json.dumps(browser_process_diagnostics()), flush=True)
                raise
            print("BROWSER_SANDBOX_STATE", json.dumps(sandboxes), flush=True)
        manager = Manager()
        manager.refresh()
        for _ in range(50):
            drain()
            time.sleep(0.03)
        node = find_client()
        assert node is not None and client.poll() is None
        assert compositor is None or compositor.poll() is None, "Private compositor failed; see capture log"
        properties = subprocess.run(["xprop", "-id", str(node["window"]), "_GTK_FRAME_EXTENTS", "_MOTIF_WM_HINTS"],
                                    capture_output=True, text=True).stdout
        root = Gdk.get_default_root_window()
        # IPC geometry/action success cannot certify black/unpainted surfaces.
        # Wait for actual composited traffic-light fills before saving evidence.
        def controls_painted():
            expected = ((255, 115, 107), (255, 209, 108), (127, 214, 160))
            for control in manager.controls.values():
                for button, color in zip(control.get_child().get_children(), expected):
                    origin = button.translate_coordinates(control, 0, 0)
                    if origin is None:
                        return False
                    x, y = control.get_position()
                    pixels = Gdk.pixbuf_get_from_window(root, x + origin[0] + 3,
                                                       y + origin[1] + 3,
                                                       button.get_allocated_width() - 6,
                                                       button.get_allocated_height() - 6)
                    if pixels is None:
                        return False
                    # Fullscreen glyph crosses the old single-pixel probe.
                    # Require painted fill area, not a specific glyph pixel.
                    data = pixels.get_pixels()
                    stride, channels = pixels.get_rowstride(), pixels.get_n_channels()
                    matches = sum(all(abs(data[row * stride + column * channels + channel] - target) <= 35
                        for channel, target in enumerate(color))
                        for row in range(pixels.get_height()) for column in range(pixels.get_width()))
                    if matches < 12:
                        return False
            return True
        Gdk.Display.get_default().sync()
        try:
            wait(controls_painted)
        except AssertionError:
            failed = args.output.with_name(args.output.stem + "-FAILED.png")
            Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height()).savev(str(failed), "png", [], [])
            details = []
            for control in manager.controls.values():
                local_pixels = Gdk.pixbuf_get_from_window(control.get_window(), 0, 0, WIDTH, control.get_size().height)
                if local_pixels is not None:
                    local_pixels.savev(str(args.output.with_name(args.output.stem + "-LOCAL.png")), "png", [], [])
                for button in control.get_child().get_children():
                    origin = button.translate_coordinates(control, 0, 0)
                    x, y = control.get_position()
                    pixels = Gdk.pixbuf_get_from_window(root, x + origin[0] + 3,
                        y + origin[1] + button.get_allocated_height() // 2, 1, 1)
                    details.append({"position": [x, y], "origin": list(origin),
                        "size": [button.get_allocated_width(), button.get_allocated_height()],
                        "pixel": list(pixels.get_pixels()[:3])})
            print("FAILED frame pixels:", json.dumps(details), flush=True)
            raise
        Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height()).savev(str(args.output), "png", [], [])
        record = {"app": args.app, "csd": args.csd, "compositor": args.compositor, "deco": node["deco_rect"], "rect": node["rect"],
                  "properties": properties, "controls": {str(k): list(v.get_size()) for k, v in manager.controls.items()}}
        args.output.with_suffix(".json").write_text(json.dumps(record, indent=2) + "\n")
        print(json.dumps(record), flush=True)
        assert node["rect"]["y"] >= 0, "Client titlebar opened above display"
        assert node["rect"]["y"] + node["rect"]["height"] <= root.get_height(), "Client opened below display"
        assert all(control.get_size().height == node["deco_rect"]["height"]
                   for control in manager.controls.values()), "Controls overlap client contents"
        identifier = node["id"]
        if not args.csd:
            wait(lambda: identifier in manager.controls)
        if args.file_dialog:
            def dialog_node():
                def visit(item):
                    if (item.get("window") and item.get("id") != identifier
                            and str((item.get("window_properties") or {}).get("class", "")).lower() == "geany"
                            and (item.get("window_properties") or {}).get("window_role") == "GtkFileChooserDialog"):
                        return item
                    for child in item.get("nodes", []) + item.get("floating_nodes", []):
                        found = visit(child)
                        if found:
                            return found
                    return None
                return visit(i3_events.request(i3_events.socket_path(), 4))

            def key(value):
                subprocess.run(["xdotool", "key", "--clearmodifiers", value], env=environment, check=True)

            subprocess.run(["i3-msg", f"[con_id={identifier}] focus"], check=True, capture_output=True)
            key("ctrl+o")
            dialog = wait(dialog_node)
            assert dialog["floating"] in ("auto_on", "user_on"), "File picker not floating"
            assert dialog["focused"], "File picker failed to receive keyboard focus"
            rectangle = dialog["rect"]
            print("FILE_DIALOG_GEOMETRY", json.dumps({"rect": rectangle,
                "deco": dialog["deco_rect"], "name": dialog.get("name"),
                "properties": dialog.get("window_properties")}), flush=True)
            manager.refresh()
            wait(controls_painted)
            Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height()).savev(
                str(args.output.with_name(args.output.stem + "-file-dialog-initial.png")), "png", [], [])
            assert rectangle["x"] >= 0 and rectangle["y"] >= 0
            assert rectangle["x"] + rectangle["width"] <= root.get_width()
            assert rectangle["y"] + rectangle["height"] <= root.get_height()
            manager.refresh()
            wait(controls_painted)
            Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height()).savev(
                str(args.output.with_name(args.output.stem + "-file-dialog.png")), "png", [], [])
            key("Escape")
            wait(lambda: dialog_node() is None)
            wait(lambda: find_client()["focused"])
            owned_file = fixture / "file-dialog.txt"
            owned_file.write_text("Ooonana private file-picker check\n", encoding="utf-8")
            key("ctrl+o")
            wait(lambda: (current := dialog_node()) and current.get("focused"))
            key("ctrl+l")
            key("ctrl+a")
            subprocess.run(["xdotool", "type", "--clearmodifiers", "--", str(owned_file)],
                           env=environment, check=True)
            key("Return")
            for _ in range(20):
                drain()
                time.sleep(0.03)
            if dialog_node() is not None:
                Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height()).savev(
                    str(args.output.with_name(args.output.stem + "-file-dialog-after-input.png")), "png", [], [])
                key("alt+o")
            wait(lambda: dialog_node() is None)
            wait(lambda: "file-dialog.txt" in find_client().get("name", ""))
            assert owned_file.read_text() == "Ooonana private file-picker check\n"
            print("PASS real Geany file picker: floating, focused, bounded, cancel, open private file", flush=True)
        if identifier in manager.controls:
            # Exercise current actions against real clients, not fake GTK windows.
            manager.controls[identifier].get_child().get_children()[1].clicked()
            wait(lambda: identifier not in manager.controls)
            subprocess.run(["ooonana-window-list", "--window-action", "show", str(identifier)],
                           env=environment, check=True, capture_output=True)
            wait(lambda: identifier in manager.controls)
            manager.controls[identifier].get_child().get_children()[2].clicked()
            wait(lambda: bool(find_client().get("fullscreen_mode")))
            wait(lambda: identifier not in manager.controls)
            subprocess.run(["ooonana-window-list", "--window-action", "fullscreen", str(identifier)],
                           env=environment, check=True, capture_output=True)
            wait(lambda: identifier in manager.controls)
            # Programmatic movement exercises real ConfigureNotify tracking.
            moved = subprocess.check_output(["i3-msg", f"[con_id={identifier}] floating enable, move position 160 100"], text=True)
            assert all(result["success"] for result in json.loads(moved)), moved
            node = find_client()
            rect, deco = node["rect"], node["deco_rect"]
            expected = (rect["x"] + deco["x"] + deco["width"] - WIDTH,
                        rect["y"] + deco["y"], deco["height"])
            wait(lambda: manager.controls[identifier].last_position == expected)
            control = manager.controls[identifier]
            wait(lambda: tuple(control.get_position()) == control.last_position[:2])
            control.get_child().get_children()[0].clicked()
            wait(lambda: find_client() is None)
            print("REAL_CLIENT_ACTIONS_OK minimize/restore/fullscreen/restore/move/close", flush=True)
    finally:
        if manager:
            manager.clear()
        # Always release private compositor/WM, even if browser exit stalls.
        try:
            for process in (compositor, wm):
                if process is not None and process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
        finally:
            if client and client.poll() is None:
                os.killpg(client.pid, signal.SIGTERM)
                try:
                    client.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(client.pid, signal.SIGKILL)
                    client.wait(timeout=10)
