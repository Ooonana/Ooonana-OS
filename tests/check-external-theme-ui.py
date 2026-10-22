#!/usr/bin/env python3
"""Held-open GTK/Geany/Nemo on private X11; no installed desktop mutation."""
import json
import os
from pathlib import Path
import select
import shutil
import subprocess
import sys
import tempfile
import time

assert os.getuid() == 1000 and os.environ.get("OOONANA_GUI_TEST_DISPLAY") == "1"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana"))
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk

if "--worker" in sys.argv:
    import cairo
    from gi.repository import GdkX11
    window = Gtk.Window(title="External GTK theme observer")
    window.set_default_size(280, 80)
    window.add(Gtk.Button(label="Keyboard focus"))
    window.show_all()
    def snapshot(*_args):
        if not sys.stdin.readline():
            Gtk.main_quit()
            return False
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 20, 20)
        Gtk.render_background(window.get_style_context(), cairo.Context(surface), 0, 0, 20, 20)
        surface.flush()
        offset = 10 * surface.get_stride() + 40
        settings = Gtk.Settings.get_default()
        print(json.dumps({"theme": settings.get_property("gtk-theme-name"),
            "color": list(bytes(surface.get_data()[offset:offset+3])[::-1]),
            "named_bg": str(window.get_style_context().lookup_color("ooonana_bg")),
            "animations": settings.get_property("gtk-enable-animations"),
            "dpi": settings.get_property("gtk-xft-dpi"),
            "xid": GdkX11.X11Window.get_xid(window.get_window())}), flush=True)
        return True
    GLib.io_add_watch(sys.stdin.fileno(), GLib.IO_IN | GLib.IO_HUP, snapshot)
    Gtk.main()
    raise SystemExit(0)

from xsettings_session import Manager
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana/ui"))
from window_controls import Manager as WindowControls
output = Path(sys.argv[1])
output.mkdir(parents=True, exist_ok=True)


def wait(predicate, detail):
    until = time.monotonic() + 10
    while not predicate():
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        assert time.monotonic() < until, detail
        time.sleep(.04)


def settle(seconds=.25):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        time.sleep(.01)


def clients():
    tree = json.loads(subprocess.check_output(["i3-msg", "-t", "get_tree"], text=True))
    result = {}
    def visit(node, workspace=""):
        if node.get("type") == "workspace":
            workspace = node["name"]
        if node.get("window"):
            result[node["window"]] = (node, workspace)
        for child in node.get("nodes", []) + node.get("floating_nodes", []):
            visit(child, workspace)
    visit(tree)
    return result


def state():
    return {xid: (node["id"], node["rect"], node.get("focused"), node.get("fullscreen_mode"), workspace)
            for xid, (node, workspace) in clients().items()}


def command(text):
    assert all(row.get("success") for row in json.loads(subprocess.check_output(["i3-msg", text], text=True)))


def request(worker):
    worker.stdin.write("snapshot\n"); worker.stdin.flush()
    assert select.select([worker.stdout], [], [], 5)[0], "External GTK worker unavailable"
    return json.loads(worker.stdout.readline())


def stop(child):
    if child is not None and child.poll() is None:
        child.terminate()
        child.wait(timeout=5)


with tempfile.TemporaryDirectory(prefix="ooonana-external-theme-") as temporary:
    base = Path(temporary)
    config = base / "i3.conf"
    config.write_text("\n".join(line for line in (ROOT / "branding/i3/config").read_text().splitlines()
                                if not line.startswith("exec")) + "\n")
    env = dict(os.environ, XDG_CONFIG_HOME=str(base / "config"), OOONANA_THEME="dark", OOONANA_THEME_INHERITED="dark")
    env.pop("GTK_THEME", None)
    env.pop("OOONANA_THEME_OVERRIDE", None)
    preference = base / "config/ooonana/theme"
    preference.parent.mkdir(parents=True)
    preference.write_text("dark\n")
    ini = base / "config/gtk-3.0/settings.ini"
    ini.parent.mkdir(parents=True)
    dpi = round(96 * 1024 * float(os.environ["OOONANA_GUI_TEXT_SCALE"]))
    ini.write_text("[Settings]\ngtk-xft-dpi=" + str(dpi) + "\n")
    wm = bridge = worker = compositor = None
    apps = []
    logs = []
    def launch(args, name):
        log = (output / (name + ".log")).open("w")
        logs.append(log)
        return subprocess.Popen(args, env=env, stdout=log, stderr=log)
    try:
        wm = launch(["i3", "-c", str(config)], "i3")
        wait(lambda: subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode == 0, "Private WM missing")
        subprocess.run(["ooonana-theme-env", "apply"], env=env, check=True, capture_output=True, timeout=25)
        # Private full-redraw/redirection workaround already documented for Xvfb.
        builder = (ROOT / "scripts/build-full-i3-rootfs.sh").read_text()
        policy = builder.split('"$ROOTFS/etc/ooonana/picom.conf" <<\'EOF\'\n', 1)[1].split("\nEOF", 1)[0]
        policy = policy.replace("use-damage = true;", "use-damage = false;").replace("unredir-if-possible = true;", "unredir-if-possible = false;")
        (base / "picom.conf").write_text(policy)
        compositor = launch(["picom", "--backend", "xrender", "--config", str(base / "picom.conf")], "picom")
        bridge = launch([sys.executable, "/usr/lib/ooonana/xsettings_session.py"], "xsettings")
        log = (output / "observer.log").open("w"); logs.append(log)
        worker = subprocess.Popen([sys.executable, __file__, "--worker"], env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log, text=True, bufsize=1)
        wait(lambda: request(worker)["theme"] == "OoonanaGraphite", "Initial Xsettings unavailable")
        observer = request(worker)["xid"]
        command('[id=%d] floating enable, resize set 280 px 100 px, move absolute position 1100 px 650 px' % observer)
        controls = WindowControls()
        # Duplicate must retain current owner, not signal/restart it.
        subprocess.run([sys.executable, "/usr/lib/ooonana/xsettings_session.py"], env=env, check=True, capture_output=True, timeout=5)
        contender = Manager()
        try:
            assert not contender.claim(), "Existing display manager replaced"
        finally:
            contender.close()
        schemes = base / "config/geany/colorschemes"
        schemes.mkdir(parents=True)
        for scheme in (ROOT / "packages/ooonana/usr/share/geany/colorschemes").glob("*.conf"):
            shutil.copyfile(scheme, schemes / scheme.name)
        for wrapper, klass in (("ooonana-editor", "Geany"), ("ooonana-files", "Nemo")):
            apps.append(launch([wrapper], klass))
            wait(lambda: any(node.get("window_properties", {}).get("class") == klass for node, _space in clients().values()), klass + " missing")
            scale = Gdk.get_default_root_window().get_scale_factor()
            command('[class="^' + klass + '$"] resize set %d px %d px, move absolute position 30 px 80 px' % (600 * scale, 360 * scale))
            controls.refresh()
        time.sleep(.6)
        editor = base / "config/geany/geany.conf"
        editor_before = editor.read_bytes()
        for selected, expected in (("light", [245, 245, 247]), ("dark", [16, 19, 23])):
            baseline = state()
            preference.write_text(selected + "\n")
            subprocess.run(["ooonana-theme-env", "apply"], env=env, capture_output=True, check=True, timeout=25)
            time.sleep(.2)
            print("EXTERNAL_THEME_SNAPSHOT", selected, request(worker), flush=True)
            wait(lambda: request(worker)["color"] == expected, "Held-open GTK did not repaint " + selected)
            snapshot = request(worker)
            assert snapshot["dpi"] == dpi and bridge.poll() is None
            assert state() == baseline, "Theme changed window identity/geometry/focus/workspace/fullscreen"
            for klass in ("Geany", "Nemo"):
                node = next(node for node, _space in clients().values() if node.get("window_properties", {}).get("class") == klass)
                command('[con_id=%d] focus' % node["id"])
                controls.refresh()
                settle()
                root = Gdk.get_default_root_window()
                scale = root.get_scale_factor()
                def painted():
                    rect, client = node["rect"], node["window_rect"]
                    pixel = Gdk.pixbuf_get_from_window(root, (rect["x"] + client["x"] + client["width"] // 2) // scale,
                        (rect["y"] + client["y"] + 2 * scale) // scale, 1, 1)
                    return pixel is not None and list(pixel.get_pixels()[:3]) == expected
                wait(painted, "Held-open " + klass + " client paint not updated " + selected)
                settle(.15)
                Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height()).savev(str(output / (selected + "-" + klass.lower() + ".png")), "png", [], [])
                print("EXTERNAL_LIVE_PAINT_OK", selected, klass, node["window"], flush=True)
            assert editor.read_bytes() == editor_before, "User editor choices overwritten"
        # Reduced Motion propagates without theme/name/window restart.
        ui = preference.with_name("ui.json")
        ui.write_text('{"reduce_motion":true}')
        subprocess.run(["ooonana-theme-env", "apply"], env=env, check=True, capture_output=True, timeout=25)
        wait(lambda: request(worker)["animations"] is False, "Reduced Motion handoff missing")
        # Invalid atomic replacement retains last valid published set, then recovers.
        xconfig = preference.with_name("xsettingsd.conf")
        original = xconfig.read_text()
        replacement = xconfig.with_name(".xsettings.invalid")
        replacement.write_text('Net/ThemeName "broken')
        replacement.replace(xconfig)
        time.sleep(.2)
        assert request(worker)["theme"] == "OoonanaGraphite" and bridge.poll() is None
        replacement.write_text(original.replace('"OoonanaGraphite"', '"OoonanaPaper"'))
        replacement.replace(xconfig)
        wait(lambda: request(worker)["theme"] == "OoonanaPaper", "Xsettings did not recover after valid replacement")
        # Another real owner taking selection must make our bridge leave,
        # never kill or reclaim that independent manager's window.
        foreign = Manager()
        try:
            atom = foreign.lib.XInternAtom(foreign.display, b"_XSETTINGS_S0", 0)
            window = foreign.lib.XCreateSimpleWindow(foreign.display, foreign.root, -1, -1, 1, 1, 0, 0, 0)
            foreign.lib.XSetSelectionOwner(foreign.display, atom, window, 0)
            foreign.lib.XSync(foreign.display, 0)
            wait(lambda: bridge.poll() is not None, "Transferred manager did not leave")
            assert bridge.returncode == 0 and foreign.lib.XGetSelectionOwner(foreign.display, atom) == window
        finally:
            foreign.close()
        print("EXTERNAL_THEME_UI_OK same held GTK/Geany/Nemo windows; exact live paint; geometry/focus/workspaces; DPI; editor preservation; duplicate ownership; reduced motion; malformed/recovery", flush=True)
    finally:
        for child in apps + [worker, bridge, compositor, wm]:
            stop(child)
        for log in logs:
            log.close()
