#!/usr/bin/env python3
"""Real client/frame capture on explicitly isolated Xvfb/Xephyr; private profiles."""
import argparse
import json
import os
from pathlib import Path
import shlex
import signal
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.parse import unquote, urlsplit
from gi.repository import Gio, GLib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana/ui"))
from common import Gdk, Gtk
from window_controls import Manager, WIDTH
import i3_events

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("app", choices=("geany", "nemo", "chromium", "qterminal", "firefox"))
parser.add_argument("output", type=Path)
parser.add_argument("--csd", action="store_true")
parser.add_argument("--compositor", action="store_true", help="Capture packaged rounding policy through private xrender compositor")
parser.add_argument("--no-use-damage", action="store_true", help="WSL/Xvfb full-redraw compositor mode; not physical GPU evidence")
parser.add_argument("--disable-shader-cache", action="store_true", help="QA-only Chromium disk-cache isolation, sandbox remains enabled")
parser.add_argument("--gpu", action="store_true", help="Leave normal GPU selection enabled (device availability remains environment-dependent)")
parser.add_argument("--url", default="about:blank", help="Private browser probe page")
parser.add_argument("--file-dialog", action="store_true", help="Real Open dialog: cancel and open an owned fixture")
parser.add_argument("--qt-details", action="store_true", help="Real Qt Session menu and settings dialog; cancel without applying preferences")
parser.add_argument("--qt-pickers", action="store_true", help="Private Qt font/image picker cancel and owned-image selection")
parser.add_argument("--inspect-firefox-first-run", action="store_true",
                    help="QA-only: expand diagnostic choices and capture; never accept Terms")
parser.add_argument("--accept-firefox-qa-terms", action="store_true",
                    help="Explicit human-authorized disposable QA consent only; turn diagnostics off first")
parser.add_argument("--wait-for-file-trace", action="store_true",
                    help="Private QA only: wait for host's read-only syscall tracer before selecting file")
args = parser.parse_args()
if args.no_use_damage and not args.compositor:
    parser.error("--no-use-damage requires --compositor")
if args.file_dialog and args.app not in ("geany", "firefox"):
    parser.error("--file-dialog requires geany or firefox")
if args.qt_details and args.app != "qterminal":
    parser.error("--qt-details requires qterminal")
if args.qt_pickers and not args.qt_details:
    parser.error("--qt-pickers requires --qt-details")
if (args.inspect_firefox_first_run or args.accept_firefox_qa_terms) and args.app != "firefox":
    parser.error("First-run QA options require firefox")
if args.inspect_firefox_first_run and args.accept_firefox_qa_terms:
    parser.error("Choose inspection or explicit QA consent, not both")
if args.wait_for_file_trace and (args.app != "firefox" or not args.file_dialog):
    parser.error("File tracing requires Firefox picker probe")
if os.environ.get("OOONANA_GUI_TEST_DISPLAY") != "1":
    raise SystemExit("Explicit isolated display required")
if args.app == "firefox" and os.getuid() != 1000:
    raise SystemExit("Firefox probe requires real nonroot desktop UID1000")
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
        if args.app == "firefox":
            kind = "renderer" if "-contentproc" in process["arguments"] else ""
        else:
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
            try:
                arguments = process.joinpath("cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
            except OSError as error:
                arguments = str(error)
            if args.app == "firefox":
                if "firefox" not in arguments:
                    continue
            elif "chrom" not in status.get("Name", "").lower():
                continue
            states.append({"pid": int(process.name), "ppid": status.get("PPid", "").strip(),
                           "uid": status.get("Uid", "").strip(), "gid": status.get("Gid", "").strip(),
                           "seccomp": status.get("Seccomp", "").strip(),
                           "no_new_privs": status.get("NoNewPrivs", "").strip(), "arguments": arguments})
        except OSError:
            continue
    return states


def ready_browser_sandboxes():
    # Newly forked renderers briefly precede sandbox initialization. Wait for
    # the same nonempty snapshot to show actual filtering and privilege lock.
    states = browser_sandboxes()
    required = ("renderer",) if args.app == "firefox" else ("renderer", "gpu-process")
    if not all(states.get(kind) for kind in required):
        return None
    if not all(state["seccomp"] == 2 and state["no_new_privs"] == 1
               for group in states.values() for state in group):
        return None
    return states


def document_diagnostics(owned_file, environment):
    """Read only the document selected in this private test, never grant access."""
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    def call(method, signature=None, values=()):
        return bus.call_sync("org.freedesktop.portal.Documents", "/org/freedesktop/portal/documents",
            "org.freedesktop.portal.Documents", method,
            GLib.Variant(signature, values) if signature else None, None,
            Gio.DBusCallFlags.NONE, 5000, None).unpack()
    documents = call("List", "(s)", ("org.mozilla.firefox",))[0]
    mountpoint = Path(os.fsdecode(bytes(call("GetMountPoint")[0]).rstrip(b"\0")))
    matches = [ident for ident, path in documents.items()
               if os.fsdecode(bytes(path).rstrip(b"\0")) == str(owned_file)]
    print("CURRENT_DOCUMENT_IDS", matches, "MOUNTPOINT", str(mountpoint), flush=True)
    for ident in matches:
        path, permissions = call("Info", "(s)", (ident,))
        print("CURRENT_DOCUMENT_INFO", os.fsdecode(bytes(path).rstrip(b"\0")), permissions, flush=True)
        for base in (mountpoint, mountpoint / "by-app/org.mozilla.firefox"):
            path = base / ident / owned_file.name
            try:
                value = path.stat()
                print("DOCUMENT_VIEW", str(path), oct(value.st_mode), value.st_uid,
                      os.access(path, os.R_OK), path.read_bytes() == owned_file.read_bytes(), flush=True)
            except OSError as error:
                print("DOCUMENT_VIEW_ERROR", str(path), str(error), flush=True)
        instances = subprocess.run(["flatpak", "ps", "--columns=instance,application,pid"],
                                   capture_output=True, text=True, env=environment, timeout=5)
        print("FLATPAK_INSTANCES", instances.stdout, instances.stderr, flush=True)
        for row in instances.stdout.splitlines():
            fields = row.split()
            if len(fields) != 3 or fields[1] != "org.mozilla.firefox" or not fields[0].isdigit():
                continue
            paths = [f"/run/user/1000/doc/{ident}/{owned_file.name}",
                     f"/run/flatpak/doc/{ident}/{owned_file.name}"]
            result = subprocess.run(["flatpak", "enter", fields[0], "/bin/sh", "-c",
                'id; for item do printf "SANDBOX_DOCUMENT %s " "$item"; '
                'if test -r "$item"; then head -c 64 "$item"; else ls -ld "$item"; fi; done',
                "document-probe", *paths], capture_output=True, text=True, env=environment, timeout=5)
            print("SANDBOX_DOCUMENT_PROBE", result.returncode, result.stdout, result.stderr, flush=True)


args.output.parent.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="ooonana-client-frame-") as temporary, args.output.with_suffix(".log").open("w") as log:
    fixture = Path(temporary)
    config = fixture / "i3.conf"
    config.write_text("\n".join(line for line in (ROOT / "branding/i3/config").read_text().splitlines()
                                if not line.startswith("exec")) + "\n")
    theme = os.environ.get("OOONANA_THEME", "dark")
    builder = (ROOT / "scripts/build-full-i3-rootfs.sh").read_text()
    helper_directory = fixture / "bin"
    helper_directory.mkdir()
    for name in ("ooonana-theme-env", "ooonana-editor"):
        script = builder.split(f'"$ROOTFS/usr/bin/{name}" <<\'EOF\'\n', 1)[1].split("\nEOF", 1)[0]
        path = helper_directory / name
        path.write_text(script)
        path.chmod(0o700)
    environment = {**os.environ, "GDK_BACKEND": "x11", "GTK_THEME": "Adwaita" if theme == "light" else "Adwaita:dark",
                   "GTK_CSD": "1" if args.csd else "0", "XDG_CONFIG_HOME": str(fixture / "config"),
                   "XDG_CACHE_HOME": str(fixture / "cache"), "XDG_STATE_HOME": str(fixture / "state"),
                   "PATH": str(helper_directory) + ":" + str(ROOT / "packages/ooonana/usr/bin") + ":" + os.environ["PATH"]}
    environment.pop("WAYLAND_DISPLAY", None)
    environment["NO_AT_BRIDGE"] = "1"
    os.environ["PATH"] = environment["PATH"]
    subprocess.run([str(helper_directory / "ooonana-theme-env"), "apply"], env=environment,
                   stdout=log, stderr=log, check=True, timeout=20)
    # Launch Qt with the same safe theme selection the real session exports.
    theme_environment = subprocess.check_output([str(helper_directory / "ooonana-theme-env"), "env"],
                                              env=environment, text=True, timeout=10)
    for line in theme_environment.splitlines():
        if line.startswith("export QT_QPA_PLATFORMTHEME="):
            environment["QT_QPA_PLATFORMTHEME"] = shlex.split(line.split("=", 1)[1])[0]
    if args.app == "geany":
        schemes = fixture / "config/geany/colorschemes"
        schemes.mkdir(parents=True)
        for path in (ROOT / "packages/ooonana/usr/share/geany/colorschemes").glob("*.conf"):
            shutil.copyfile(path, schemes / path.name)
    command = {
        "geany": [str(helper_directory / "ooonana-editor"), "--new-instance", "--config=" + str(fixture / "config/geany")],
        "nemo": ["nemo", "--no-desktop", str(fixture)],
        "qterminal": ["qterminal", "--workdir", str(fixture), "--execute", "/bin/sh"],
        "firefox": ["ooonana-firefox", "run", "--no-remote", "--private-window", "about:blank"],
        "chromium": ["chromium", "--user-data-dir=" + str(fixture / "chromium"), "--no-first-run",
                     "--disable-background-networking", "--disable-component-update", "--password-store=basic",
                     "--disable-gpu", "about:blank"],
    }[args.app]
    if args.app == "firefox":
        if args.file_dialog:
            environment.setdefault("MOZ_LOG", "Widget:5")
            environment.setdefault("MOZ_SANDBOX_LOGGING", "1")
        # Owned QA profile only: no production onboarding/terms acceptance or
        # diagnostic-data submission. Flatpak persists .mozilla at this path.
        profile_name = "ooonana-qa-" + fixture.name
        profile = Path.home() / ".var/app/org.mozilla.firefox/.mozilla" / profile_name
        assert profile.resolve().is_relative_to(Path.home().resolve()) and not profile.exists()
        profile.mkdir(mode=0o700, parents=True)
        preferences = {
            "browser.aboutwelcome.enabled": False,
            "browser.startup.firstrunSkipsHomepage": True,
            "browser.startup.homepage_override.mstone": "ignore",
            "browser.shell.checkDefaultBrowser": False,
            "datareporting.healthreport.uploadEnabled": False,
            "datareporting.policy.dataSubmissionEnabled": False,
            "toolkit.telemetry.enabled": False,
        }
        (profile / "user.js").write_text("\n".join(
            f"user_pref({json.dumps(name)}, {json.dumps(value)});" for name, value in preferences.items()) + "\n")
        command[2:2] = ["--profile", str(Path.home() / ".mozilla" / profile_name)]
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
        if args.app == "firefox":
            subprocess.run(["gdbus", "call", "--session", "--dest", "org.freedesktop.portal.Documents",
                "--object-path", "/org/freedesktop/portal/documents", "--method", "org.freedesktop.portal.Documents.GetMountPoint"],
                stdout=log, stderr=log, timeout=15, check=True)
        if args.compositor:
            builder = (ROOT / "scripts/build-full-i3-rootfs.sh").read_text()
            policy = builder.split('"$ROOTFS/etc/ooonana/picom.conf" <<\'EOF\'\n', 1)[1].split("\nEOF", 1)[0]
            if args.no_use_damage:
                policy = policy.replace("use-damage = true;", "use-damage = false;")
                policy = policy.replace("unredir-if-possible = true;", "unredir-if-possible = false;")
            compositor_config = fixture / "picom.conf"
            compositor_config.write_text(policy)
            subprocess.run(["xsetroot", "-solid", "#555963"], check=True)
            compositor_command = ["picom", "--backend", "xrender", "--config", str(compositor_config)]
            if args.no_use_damage:
                compositor_command.append("--no-use-damage")
            compositor = subprocess.Popen(compositor_command,
                                          stdout=log, stderr=log)
        client = subprocess.Popen(command, env=environment, stdout=log, stderr=log, start_new_session=True)
        wait(find_client)
        if args.app in ("chromium", "firefox"):
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
        if args.app == "nemo":
            rectangle = node["rect"]
            # This owned fixture has blue Adwaita folders. A flat dark client
            # can still pass a pure-black test; require actual folder painting.
            content = Gdk.pixbuf_get_from_window(root, rectangle["x"] + 180,
                rectangle["y"] + node["deco_rect"]["height"] + 80,
                min(500, rectangle["width"] - 188), min(280, rectangle["height"] - 110))
            data, channels, stride = content.get_pixels(), content.get_n_channels(), content.get_rowstride()
            samples = [data[y * stride + x * channels:y * stride + x * channels + 3]
                       for y in range(0, content.get_height(), 8) for x in range(0, content.get_width(), 8)]
            painted = sum(blue > red + 25 and green > red + 15 for red, green, blue in samples)
            print(f"NEMO_PAINTED_FOLDER_SAMPLES {painted}", flush=True)
            assert painted >= 5, "Nemo folder contents unpainted; control-state success is insufficient"
        record = {"app": args.app, "csd": args.csd, "compositor": args.compositor, "full_redraw": args.no_use_damage,
                  "deco": node["deco_rect"], "rect": node["rect"],
                  "properties": properties, "controls": {str(k): list(v.get_size()) for k, v in manager.controls.items()}}
        if args.app == "firefox":
            record["qa_profile"] = profile.name
        args.output.with_suffix(".json").write_text(json.dumps(record, indent=2) + "\n")
        print(json.dumps(record), flush=True)
        assert node["rect"]["y"] >= 0, "Client titlebar opened above display"
        assert node["rect"]["y"] + node["rect"]["height"] <= root.get_height(), "Client opened below display"
        assert all(control.get_size().height == node["deco_rect"]["height"]
                   for control in manager.controls.values()), "Controls overlap client contents"
        identifier = node["id"]
        if not args.csd:
            wait(lambda: identifier in manager.controls)
        if args.qt_details:
            def qt_settings():
                def visit(item):
                    if item.get("window") and item.get("name") == "Terminal settings":
                        return item
                    for child in item.get("nodes", []) + item.get("floating_nodes", []):
                        found = visit(child)
                        if found:
                            return found
                    return None
                return visit(i3_events.request(i3_events.socket_path(), 4))

            def qt_key(*values):
                subprocess.run(["xdotool", "key", "--clearmodifiers", *values], env=environment, check=True)

            def qt_capture(suffix):
                for _ in range(20):
                    drain()
                    time.sleep(0.03)
                Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height()).savev(
                    str(args.output.with_name(args.output.stem + suffix + ".png")), "png", [], [])

            subprocess.run(["i3-msg", f"[con_id={identifier}] focus"], check=True, capture_output=True)
            # QTerminal intentionally sends Alt-letter combinations to shells.
            # Open its observed native Session menu without changing that pref.
            rectangle = find_client()["rect"]
            subprocess.run(["xdotool", "mousemove", "--sync", str(rectangle["x"] + 30),
                            str(rectangle["y"] + node["deco_rect"]["height"] + 10), "click", "1"],
                           env=environment, check=True)
            qt_capture("-session-menu")
            # Observed English/100% native menu: duplicate P accelerators and
            # separator navigation differ from ordinary GTK menu assumptions.
            # Refuse uncalibrated variants instead of blind shortcut retries.
            assert (root.get_width(), root.get_height()) in ((1024, 768), (640, 600))
            assert os.environ.get("OOONANA_GUI_TEXT_SCALE") == "1.0"
            subprocess.run(["xdotool", "mousemove", "--sync", str(rectangle["x"] + 90),
                            str(rectangle["y"] + node["deco_rect"]["height"] + 120), "click", "1"],
                           env=environment, check=True)
            try:
                dialog = wait(qt_settings)
            except AssertionError:
                qt_capture("-settings-failure")
                args.output.with_name(args.output.stem + "-settings-failure.json").write_text(
                    json.dumps(i3_events.request(i3_events.socket_path(), 4), indent=2))
                raise
            assert dialog["focused"] and dialog["floating"] in ("auto_on", "user_on")
            qt_capture("-settings-appearance")
            dialog = qt_settings()
            args.output.with_name(args.output.stem + "-settings.json").write_text(json.dumps(dialog, indent=2))
            rectangle = dialog["rect"]
            assert rectangle["x"] >= 0 and rectangle["y"] >= 0, "Qt settings opens above/left of display"
            assert rectangle["x"] + rectangle["width"] <= root.get_width(), "Qt settings wider than display"
            assert rectangle["y"] + rectangle["height"] <= root.get_height(), "Qt settings below display"
            if args.qt_pickers:
                def qt_child(title):
                    def visit(item):
                        if item.get("window") and item.get("name") == title:
                            return item
                        for child in item.get("nodes", []) + item.get("floating_nodes", []):
                            found = visit(child)
                            if found:
                                return found
                        return None
                    return visit(i3_events.request(i3_events.socket_path(), 4))

                def qt_child_open(title, suffix, offset):
                    subprocess.run(["xdotool", "mousemove", "--sync",
                        str(rectangle["x"] + rectangle["width"] - 62),
                        str(rectangle["y"] + dialog["deco_rect"]["height"] + offset), "click", "1"],
                        env=environment, check=True)
                    try:
                        wait(lambda: (child := qt_child(title)) and child["focused"])
                    except AssertionError:
                        qt_capture(suffix + "-failure")
                        args.output.with_name(args.output.stem + suffix + "-failure.json").write_text(
                            json.dumps(i3_events.request(i3_events.socket_path(), 4), indent=2))
                        raise
                    qt_capture(suffix)
                    child = qt_child(title)
                    args.output.with_name(args.output.stem + suffix + ".json").write_text(json.dumps(child, indent=2))
                    bounds = child["rect"]
                    assert child["window_properties"].get("transient_for") == dialog["window"], title + " lost settings parent"
                    assert child["floating"] in ("auto_on", "user_on"), title
                    assert bounds["x"] >= 0 and bounds["y"] >= 0, title + " clips titlebar"
                    assert bounds["x"] + bounds["width"] <= root.get_width(), title + " clips width"
                    assert bounds["y"] + bounds["height"] <= root.get_height(), title + " clips actions"
                    return child

                font_title = "Select Terminal Font"
                qt_child_open(font_title, "-font-picker", 32)
                qt_key("Escape")
                wait(lambda: qt_child(font_title) is None)
                wait(lambda: qt_settings()["focused"])
                image_title = "Choose a background image"
                qt_child_open(image_title, "-image-picker", 354)
                qt_key("Escape")
                wait(lambda: qt_child(image_title) is None)
                wait(lambda: qt_settings()["focused"])
                owned_image = fixture / "private background image.png"
                shutil.copyfile(ROOT / "branding/boot-mark.png", owned_image)
                qt_child_open(image_title, "-image-picker-reopened", 354)
                qt_key("ctrl+l", "ctrl+a")
                subprocess.run(["xdotool", "type", "--clearmodifiers", "--", str(owned_image)],
                               env=environment, check=True)
                qt_key("Return")
                try:
                    wait(lambda: qt_child(image_title) is None)
                except AssertionError:
                    qt_capture("-image-selection-failure")
                    raise
                wait(lambda: qt_settings()["focused"])
                subprocess.run(["xdotool", "mousemove", "--sync",
                    str(rectangle["x"] + rectangle["width"] - 180),
                    str(rectangle["y"] + dialog["deco_rect"]["height"] + 354), "click", "1"],
                    env=environment, check=True)
                qt_key("ctrl+a", "ctrl+c")
                selected = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).wait_for_text()
                assert selected == str(owned_image), "Qt pending image field differs from selected owned file"
                qt_capture("-image-pending")
                print("QT_PICKERS_OK font parent/cancel, image cancel/reopen/select, exact private pending path", flush=True)
            # Focus the observed native category list; arrows must change pages
            # without editing settings, activating Apply or touching user files.
            subprocess.run(["xdotool", "mousemove", "--sync", str(rectangle["x"] + 45),
                            str(rectangle["y"] + dialog["deco_rect"]["height"] + 19), "click", "1"],
                           env=environment, check=True)
            qt_key("Home")
            for page in ("window", "behavior", "shortcuts", "dropdown", "bookmarks"):
                qt_key("Down")
                qt_capture("-settings-" + page)
            moved_y = root.get_height() - rectangle["height"] + 6
            subprocess.run(["i3-msg", f"[con_id={dialog['id']}] move absolute position {rectangle['x']} px {moved_y} px"],
                           env=environment, check=True, capture_output=True)
            for _ in range(15):
                drain()
                time.sleep(0.03)
            assert qt_settings()["rect"]["y"] == moved_y, "Initial placement correction fought later user movement"
            subprocess.run(["i3-msg", f"[con_id={dialog['id']}] move absolute position {rectangle['x']} px {rectangle['y']} px"],
                           env=environment, check=True, capture_output=True)
            qt_key("Escape")
            wait(lambda: qt_settings() is None)
            assert find_client() is not None, "Settings Cancel closed terminal"
            if args.qt_pickers:
                preferences = fixture / "config/qterminal.org/qterminal.ini"
                assert str(owned_image) not in preferences.read_text(), "Settings Cancel persisted pending image"
                print("QT_PICKER_OUTER_CANCEL_OK pending image not applied", flush=True)
            print("QT_SETTINGS_CANCEL_OK actual Session/Preferences, focused/bounded modal, six category captures, Escape", flush=True)
        if args.inspect_firefox_first_run or args.accept_firefox_qa_terms:
            # This explicit inspection mode is limited to the observed private
            # 1024x768 Firefox QA surface. Refuse drift instead of blind input.
            assert root.get_width() == 1024 and root.get_height() == 768
            def terms_visible():
                pixels = Gdk.pixbuf_get_from_window(root, 460, 388, 104, 36)
                if pixels is None:
                    return False
                data, stride, channels = pixels.get_pixels(), pixels.get_rowstride(), pixels.get_n_channels()
                return sum(all(abs(data[y * stride + x * channels + channel] - value) < 12
                               for channel, value in enumerate((183, 158, 255)))
                           for y in range(pixels.get_height()) for x in range(pixels.get_width())) > 1000
            wait(terms_visible)
            Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height()).savev(
                str(args.output.with_name(args.output.stem + "-terms-initial.png")), "png", [], [])
            subprocess.run(["xdotool", "mousemove", "--sync", "512", "552", "click", "1"],
                           env=environment, check=True)
            for _ in range(25):
                drain()
                time.sleep(0.03)
            Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height()).savev(
                str(args.output.with_name(args.output.stem + "-terms-diagnostics.png")), "png", [], [])
            if args.inspect_firefox_first_run:
                print("FIREFOX_FIRST_RUN_INSPECT_ONLY: diagnostic choices captured; no consent/picker claim", flush=True)
                raise SystemExit(3)
            # Consent was delegated by the human for disposable QA only. Never
            # skip onboarding via a preference or enable diagnostics on consent.
            assert profile.name == "ooonana-qa-" + fixture.name
            assert profile.parent == Path.home() / ".var/app/org.mozilla.firefox/.mozilla"
            interfaces = {line.split(":", 1)[0].strip() for line in Path("/proc/net/dev").read_text().splitlines()
                          if ":" in line}
            assert interfaces <= {"lo"}, "QA consent requires an isolated network"
            def diagnostic_fill():
                pixels = Gdk.pixbuf_get_from_window(root, 303, 596, 12, 12)
                assert pixels is not None
                data, stride, channels = pixels.get_pixels(), pixels.get_rowstride(), pixels.get_n_channels()
                return sum(all(abs(data[y * stride + x * channels + channel] - value) < 12
                               for channel, value in enumerate((183, 158, 255)))
                           for y in range(12) for x in range(12))
            assert diagnostic_fill() > 60, "Unrecognized diagnostic checkbox state; no consent"
            subprocess.run(["xdotool", "mousemove", "--sync", "309", "602", "click", "1"],
                           env=environment, check=True)
            wait(lambda: terms_visible() and diagnostic_fill() < 10)
            Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height()).savev(
                str(args.output.with_name(args.output.stem + "-terms-diagnostics-off.png")), "png", [], [])
            subprocess.run(["xdotool", "mousemove", "--sync", "512", "406", "click", "1"],
                           env=environment, check=True)
            # Button hover/pressed color is not proof the modal has closed.
            # Wait for the observed private-page surface at all three points.
            def private_page_ready():
                return all(tuple(Gdk.pixbuf_get_from_window(root, x, y, 1, 1).get_pixels()[:3]) == (28, 27, 34)
                           for x, y in ((260, 180), (300, 200), (760, 200)))
            wait(private_page_ready)
            print("FIREFOX_QA_TERMS_ACCEPTED: disposable profile, visibly unchecked diagnostics, private network", flush=True)
        if args.file_dialog:
            def dialog_node():
                def visit(item):
                    properties = item.get("window_properties") or {}
                    klass = str(properties.get("class", "")).lower()
                    owner = klass == "geany" if args.app == "geany" else "portal" in klass
                    if (item.get("window") and item.get("id") != identifier
                            and owner and properties.get("window_role") == "GtkFileChooserDialog"):
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
            next_open = [0.0]
            def request_open_dialog():
                current = dialog_node()
                if current:
                    return current
                # A cold browser can finish onboarding before its chrome
                # shortcuts are connected. Repeat only the non-mutating Open
                # request, and never send input once the chooser exists.
                if time.monotonic() >= next_open[0]:
                    key("ctrl+o")
                    next_open[0] = time.monotonic() + 1.0
                return None
            try:
                dialog = wait(request_open_dialog)
            except AssertionError:
                tree = i3_events.request(i3_events.socket_path(), 4)
                args.output.with_name(args.output.stem + "-dialog-failure.json").write_text(json.dumps(tree, indent=2))
                Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height()).savev(
                    str(args.output.with_name(args.output.stem + "-dialog-failure.png")), "png", [], [])
                raise
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
            if args.wait_for_file_trace:
                print("FILE_TRACE_READY", flush=True)
                wait(lambda: Path("/qa/trace-ready").is_dir())
            key("Return")
            for _ in range(20):
                drain()
                time.sleep(0.03)
            if dialog_node() is not None:
                Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height()).savev(
                    str(args.output.with_name(args.output.stem + "-file-dialog-after-input.png")), "png", [], [])
                # GTK portal uses "Select"; Geany's own dialog uses "Open".
                key("alt+s" if args.app == "firefox" else "alt+o")
            wait(lambda: dialog_node() is None)
            try:
                if args.app == "firefox":
                    clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
                    next_copy, selected_uri = [0.0], [None]
                    def document_loaded():
                        if time.monotonic() < next_copy[0]:
                            return False
                        next_copy[0] = time.monotonic() + 1.0
                        key("ctrl+l")
                        key("ctrl+c")
                        uri = clipboard.wait_for_text() or ""
                        parsed = urlsplit(uri)
                        if (parsed.scheme != "file" or parsed.netloc or "/doc/" not in parsed.path
                                or Path(unquote(parsed.path)).name != owned_file.name):
                            return False
                        rectangle = find_client()["rect"]
                        subprocess.run(["xdotool", "mousemove", "--sync",
                            str(rectangle["x"] + 40), str(rectangle["y"] + 122), "click", "1"],
                            env=environment, check=True)
                        key("ctrl+a")
                        key("ctrl+c")
                        content = clipboard.wait_for_text() or ""
                        if content.strip() != owned_file.read_text().strip():
                            return False
                        selected_uri[0] = uri
                        return True
                    # Private Firefox intentionally keeps a generic WM title.
                    # Verify actual browser URL and rendered document selection.
                    wait(document_loaded)
                    wait(ready_browser_sandboxes)
                    print("FIREFOX_DOCUMENT_UI_OK", selected_uri[0], "private X11 clipboard/content", flush=True)
                    Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height()).savev(
                        str(args.output.with_name(args.output.stem + "-file-opened.png")), "png", [], [])
                else:
                    wait(lambda: "file-dialog.txt" in find_client().get("name", ""))
            except AssertionError:
                args.output.with_name(args.output.stem + "-open-failure.json").write_text(
                    json.dumps(i3_events.request(i3_events.socket_path(), 4), indent=2))
                Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height()).savev(
                    str(args.output.with_name(args.output.stem + "-open-failure.png")), "png", [], [])
                if args.app == "firefox":
                    try:
                        print("PORTAL_MOUNTS", [line for line in Path("/proc/self/mountinfo").read_text().splitlines()
                            if "fuse.portal" in line], flush=True)
                        print("OWNED_FILE_ACCESS", oct(owned_file.stat().st_mode), owned_file.stat().st_uid,
                              os.access(owned_file, os.R_OK), flush=True)
                        document_diagnostics(owned_file, environment)
                        processes = [{key: row[key] for key in ("pid", "ppid", "uid", "gid", "seccomp", "no_new_privs")}
                                     for row in browser_process_diagnostics()
                                     if row["arguments"].startswith("/app/lib/firefox/firefox")]
                        print("BROWSER_FILE_FAILURE_PROCESSES", json.dumps(processes), flush=True)
                    except Exception as error:
                        print("PORTAL_DIAGNOSTIC_FAILED", type(error).__name__, str(error), flush=True)
                raise
            assert owned_file.read_text() == "Ooonana private file-picker check\n"
            print(f"PASS real {args.app} file picker: floating, focused, bounded, cancel, open private file", flush=True)
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
            if args.app == "qterminal":
                def exit_dialog():
                    def visit(item):
                        if item.get("window") and item.get("name") == "Exit QTerminal":
                            return item
                        for child in item.get("nodes", []) + item.get("floating_nodes", []):
                            found = visit(child)
                            if found:
                                return found
                        return None
                    return visit(i3_events.request(i3_events.socket_path(), 4))

                dialog = wait(exit_dialog)
                assert dialog["focused"] and dialog["floating"] in ("auto_on", "user_on")
                rectangle = dialog["rect"]
                assert rectangle["x"] >= 0 and rectangle["y"] >= 0
                assert rectangle["x"] + rectangle["width"] <= root.get_width()
                assert rectangle["y"] + rectangle["height"] <= root.get_height()
                manager.refresh()
                wait(controls_painted)
                Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height()).savev(
                    str(args.output.with_name(args.output.stem + "-exit-dialog.png")), "png", [], [])
                subprocess.run(["xdotool", "key", "--clearmodifiers", "Escape"], env=environment, check=True)
                wait(lambda: exit_dialog() is None)
                assert find_client() is not None, "Cancel closed Qt terminal"
                wait(lambda: identifier in manager.controls)
                manager.controls[identifier].get_child().get_children()[0].clicked()
                wait(exit_dialog)
                subprocess.run(["xdotool", "key", "--clearmodifiers", "alt+y"], env=environment, check=True)
                print("QT_CLOSE_DIALOG_OK focus/bounds/cancel/confirm", flush=True)
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
