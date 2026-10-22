#!/usr/bin/env python3
"""Real managed i3 frame recoloring/state preservation on an owned X11 display."""
import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time

assert os.getuid() == 1000 and os.environ.get("OOONANA_GUI_TEST_DISPLAY") == "1"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana/ui"))
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana"))
from common import Gdk, Gtk
from window_controls import Manager
from desktop_theme import XResources, PALETTES
import i3_events

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("output", type=Path)
parser.add_argument("--no-use-damage", action="store_true", help="Private Xvfb full-redraw/redirection adaptation only")
args = parser.parse_args()
output = args.output
output.mkdir(parents=True, exist_ok=True)
assert subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode != 0
Gtk.Settings.get_default().set_property("gtk-xft-dpi", round(96 * 1024 * float(os.environ["OOONANA_GUI_TEXT_SCALE"])))


def settle(seconds=.12):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        time.sleep(.01)


def wait(predicate, detail):
    end = time.monotonic() + 10
    while not predicate():
        assert time.monotonic() < end, detail
        settle(.03)


def command(text):
    reply = json.loads(subprocess.check_output(["i3-msg", text], text=True))
    assert all(item.get("success") for item in reply), reply


def tree():
    return json.loads(subprocess.check_output(["i3-msg", "-t", "get_tree"], text=True))


def leaves(klass="XTerm"):
    result = {}
    def visit(node, workspace=None):
        if node.get("type") == "workspace":
            workspace = node.get("name")
        if node.get("window") and node.get("window_properties", {}).get("class") == klass:
            result[node["name"]] = (node, workspace)
        for child in node.get("nodes", []) + node.get("floating_nodes", []):
            visit(child, workspace)
    visit(tree())
    return result


def state():
    return {name: (node["id"], node["window"], dict(node["rect"]), node.get("focused"),
                   node.get("fullscreen_mode"), workspace)
            for name, (node, workspace) in leaves().items()}


def sample(name):
    node, _ = leaves()[name]
    return frame_color(node)


def frame_color(node):
    root = Gdk.get_default_root_window()
    scale = root.get_scale_factor()
    rect, deco = node["rect"], node["deco_rect"]
    # Empty right end avoids title text, controls and rounded corner clipping.
    x = rect["x"] + deco["x"] + deco["width"] - 32 * scale
    y = rect["y"] + deco["y"] + deco["height"] // 2
    pixbuf = Gdk.pixbuf_get_from_window(root, x // scale, y // scale, 1, 1)
    return tuple(pixbuf.get_pixels()[:3])


def capture(name):
    settle(.25)
    root = Gdk.get_default_root_window()
    Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height()).savev(
        str(output / (name + ".png")), "png", [], [])


with tempfile.TemporaryDirectory(prefix="ooonana-frame-theme-") as temporary:
    base = Path(temporary)
    config, sentinel = base / "i3.conf", base / "exec-count"
    source = "\n".join(line for line in (ROOT / "branding/i3/config").read_text().splitlines()
                       if not line.startswith("exec")) + "\n"
    source += "exec_always --no-startup-id sh -c 'echo initial >>" + str(sentinel) + "'\n"
    config.write_text(source)
    preference = base / "config/ooonana/theme"
    preference.parent.mkdir(parents=True)
    preference.write_text("dark\n")
    env = dict(os.environ, XDG_CONFIG_HOME=str(base / "config"), OOONANA_THEME="dark", OOONANA_THEME_INHERITED="dark")
    env.pop("OOONANA_THEME_OVERRIDE", None)
    server = XResources()
    original = server.read("RESOURCE_MANAGER")
    custom = b'! retain custom frame-test resource\nFrameQA.value: untouched\n'
    assert server.replace("RESOURCE_MANAGER", original, custom)
    subprocess.run(["ooonana-theme-env", "apply"], env=env, capture_output=True, check=True, timeout=25)
    wm = subprocess.Popen(["i3", "-c", str(config)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    processes = []
    compositor = None
    manager = None
    try:
        wait(lambda: subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode == 0, "Private i3 unavailable")
        assert json.loads(subprocess.check_output(["i3-msg", "-t", "get_version"], text=True))["ooonana_frame_theme_api"] == 1
        wait(lambda: sentinel.exists(), "Startup sentinel absent")
        builder = (ROOT / "scripts/build-full-i3-rootfs.sh").read_text()
        policy = builder.split('"$ROOTFS/etc/ooonana/picom.conf" <<\'EOF\'\n', 1)[1].split("\nEOF", 1)[0]
        if args.no_use_damage:
            # Existing WSL/Xvfb adaptation used by third-party frame probes.
            # Never modify production compositor policy or claim physical GPU QA.
            policy = policy.replace("use-damage = true;", "use-damage = false;")
            policy = policy.replace("unredir-if-possible = true;", "unredir-if-possible = false;")
        print("FRAME_THEME_COMPOSITOR", "private full-redraw/redirection" if args.no_use_damage else "packaged damage/redirection policy", flush=True)
        compositor_config = base / "picom.conf"
        compositor_config.write_text(policy)
        compositor_log = (output / "picom.log").open("w")
        compositor = subprocess.Popen(["picom", "--backend", "xrender", "--config", str(compositor_config)],
                                       stdout=compositor_log, stderr=compositor_log)
        settle(.3)
        assert compositor.poll() is None, "Private compositor failed"
        for name in ("FrameA", "FrameB", "OtherWorkspace", "Minimized"):
            processes.append(subprocess.Popen(["xterm", "-title", name, "-bg", "#15191f", "-fg", "#f5f5f7", "-e", "sleep", "110"], env=env,
                                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        wait(lambda: len(leaves()) == 4, "Owned frame clients absent")
        command('[title="^FrameA$"] resize set 600 px 300 px, move absolute position 30 px 140 px; '
                '[title="^FrameB$"] resize set 400 px 300 px, move absolute position 750 px 140 px; '
                '[title="^OtherWorkspace$"] move container to workspace 2; '
                '[title="^Minimized$"] move scratchpad; [title="^FrameA$"] focus')
        manager = Manager()
        manager.refresh()
        settle(.3)
        baseline = state()
        # Reserved native namespace must refuse malformed bytes without ever
        # passing suffixes/NULs/command chains to i3's normal command parser.
        wm_socket = os.fsdecode(server.read("I3_SOCKET_PATH").rstrip(b"\0"))
        for payload in (b"ooonana_frame_theme", b"ooonana_frame_theme light\0",
                        b"ooonana_frame_theme light\0; workspace 9",
                        b"ooonana_frame_theme light; workspace 9",
                        b"ooonana_frame_theme light\n", b"ooonana_frame_theme LIGHT",
                        b"ooonana_frame_theme dark extra", b"ooonana_frame_themeevil"):
            color = sample("FrameA")
            with socket.socket(socket.AF_UNIX) as connection:
                connection.settimeout(3)
                connection.connect(wm_socket)
                i3_events.send(connection, 0, payload)
                kind, reply = i3_events.receive(connection)
            assert kind == 0 and isinstance(reply, list) and len(reply) == 1 and reply[0].get("success") is False, (payload, reply)
            assert state() == baseline and sample("FrameA") == color, payload
        for selected in ("light", "dark"):
            result = subprocess.run(["ooonana-theme-env", "toggle"], env=env, capture_output=True, text=True, check=True, timeout=25)
            (output / (selected + "-apply.log")).write_text(result.stdout + result.stderr)
            assert "Theme:" not in result.stderr, result.stderr
            assert preference.read_text() == selected + "\n"
            expected = tuple(bytes.fromhex(PALETTES[selected]["focused"][0][1:]))
            wait(lambda: sample("FrameA") == expected, "Focused frame did not repaint " + selected + " " + str(sample("FrameA")))
            assert state() == baseline, "Theme update changed clients/focus/geometry/workspace/scratchpad"
            assert wm.poll() is None and sentinel.read_text().splitlines() == ["initial"], "Theme update restarted WM/autostarts"
            assert server.read("RESOURCE_MANAGER").startswith(custom), "Unrelated X resources changed"
            inactive = sample("FrameB")
            candidates = [tuple(bytes.fromhex(PALETTES[selected][role][0][1:])) for role in ("unfocused", "focused_inactive")]
            assert inactive in candidates, (selected, inactive, candidates)
            manager.refresh()
            capture(selected + "-live-frames")
            print("FRAME_THEME_LIVE_OK", selected, expected, "inactive", inactive, "wm-scale", manager.control_scale, flush=True)
        # Real preferred GTK clients, current controls and current compositor.
        schemes = base / "config/geany/colorschemes"
        schemes.mkdir(parents=True)
        for scheme in (ROOT / "packages/ooonana/usr/share/geany/colorschemes").glob("*.conf"):
            shutil.copyfile(scheme, schemes / scheme.name)
        for selected in ("light", "dark"):
            preference.write_text(selected + "\n")
            result = subprocess.run(["ooonana-theme-env", "apply"], env=env, capture_output=True, text=True, check=True, timeout=25)
            assert "Theme:" not in result.stderr, result.stderr
            expected = tuple(bytes.fromhex(PALETTES[selected]["focused"][0][1:]))
            for wrapper, klass in (("ooonana-editor", "Geany"), ("ooonana-files", "Nemo")):
                process = subprocess.Popen([wrapper], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                processes.append(process)
                wait(lambda: bool(leaves(klass)), "Real GTK client unavailable " + klass)
                manager.refresh()
                settle(1)
                node, _ = next(iter(leaves(klass).values()))
                assert node.get("focused") and frame_color(node) == expected, (selected, klass, frame_color(node))
                if args.no_use_damage:
                    def joined_client():
                        root = Gdk.get_default_root_window()
                        scale = root.get_scale_factor()
                        rect, client = node["rect"], node["window_rect"]
                        left, top = rect["x"] + client["x"], rect["y"] + client["y"]
                        y = (top + 2 * scale) // scale
                        colors = []
                        for x in (left + 2 * scale, left + client["width"] // 2,
                                  left + client["width"] - 3 * scale):
                            pixel = Gdk.pixbuf_get_from_window(root, x // scale, y, 1, 1)
                            if pixel is None:
                                return False
                            colors.append(tuple(pixel.get_pixels()[:3]))
                        return (colors[1] != (0, 0, 0) and
                                all(max(abs(a - b) for a, b in zip(color, colors[1])) <= 8 for color in (colors[0], colors[2])))
                    wait(joined_client, "Client top corners cut away below i3 frame " + selected + " " + klass)
                    print("FRAME_CLIENT_JOIN_OK", selected, klass, "scale", manager.control_scale, flush=True)
                if klass == "Nemo" and args.no_use_damage:
                    def menu_painted():
                        root = Gdk.get_default_root_window()
                        scale = root.get_scale_factor()
                        rect, deco = node["rect"], node["deco_rect"]
                        pixels = Gdk.pixbuf_get_from_window(root,
                            (rect["x"] + rect["width"] - 30 * scale) // scale,
                            (rect["y"] + deco["height"] + 10 * scale) // scale, 1, 1)
                        return pixels is not None and tuple(pixels.get_pixels()[:3]) != (0, 0, 0)
                    wait(menu_painted, "Nemo menu remains unpainted under private full-redraw mode")
                capture(selected + "-" + klass.lower())
                command("[con_id=%d] kill" % node["id"])
                wait(lambda: not leaves(klass), "Owned GTK client retained")
        command('[title="^FrameA$"] focus')
        settle()
        assert state() == baseline
        # Color-only IPC must not parse/reload modified files, reset custom
        # runtime gaps, leave resize mode or disturb fullscreen clients.
        command('gaps inner current set 17; gaps left all set 23')
        def workspace_gaps():
            result = {}
            def visit(node):
                if node.get("type") == "workspace":
                    result[node["name"]] = node.get("gaps")
                for child in node.get("nodes", []) + node.get("floating_nodes", []):
                    visit(child)
            visit(tree())
            return result
        gaps = workspace_gaps()
        command('mode "resize"')
        config.write_text(source + "invalid_frame_qa_directive\n")
        preference.write_text("light\n")
        result = subprocess.run(["ooonana-theme-env", "apply"], env=env, capture_output=True, text=True, check=True, timeout=25)
        assert "Theme:" not in result.stderr, result.stderr
        assert workspace_gaps() == gaps and state() == baseline
        assert json.loads(subprocess.check_output(["i3-msg", "-t", "get_binding_state"], text=True))["name"] == "resize"
        command('mode "default"')
        command('[title="^FrameB$"] fullscreen enable')
        settle()
        full = state()
        preference.write_text("dark\n")
        result = subprocess.run(["ooonana-theme-env", "apply"], env=env, capture_output=True, text=True, check=True, timeout=25)
        assert "Theme:" not in result.stderr and state() == full and workspace_gaps() == gaps
        assert sentinel.read_text().splitlines() == ["initial"]
        print("FRAME_THEME_UI_OK live colors; same WM/windows/focus/geometry/workspaces/minimized/fullscreen; no autostarts; custom resources/gaps/mode; no config reload; malformed packets refused", flush=True)
        # Same candidate with native-control opt-in disabled must not expose
        # or accept this private palette protocol. Only owned test WM restarts.
        wm.terminate()
        wm.wait(timeout=5)
        config.write_text(source)
        wm = subprocess.Popen(["i3", "-c", str(config)], env=dict(env, OOONANA_WINDOW_CONTROLS=""),
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        wait(lambda: subprocess.run(["i3-msg", "-t", "get_version"], capture_output=True).returncode == 0, "Disabled private WM unavailable")
        version = json.loads(subprocess.check_output(["i3-msg", "-t", "get_version"], text=True))
        assert version["ooonana_frame_theme_api"] == 0
        wm_socket = os.fsdecode(server.read("I3_SOCKET_PATH").rstrip(b"\0"))
        with socket.socket(socket.AF_UNIX) as connection:
            connection.settimeout(3)
            connection.connect(wm_socket)
            i3_events.send(connection, 0, b"ooonana_frame_theme light")
            kind, reply = i3_events.receive(connection)
        assert kind == 0 and reply[0].get("success") is False, reply
        print("FRAME_THEME_DISABLED_OK capability zero, valid palette command refused", flush=True)
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)
        wm.terminate()
        wm.wait(timeout=5)
        if compositor is not None:
            if compositor.poll() is None:
                compositor.terminate()
                compositor.wait(timeout=5)
            compositor_log.close()
        server.close()
