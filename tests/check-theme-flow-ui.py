#!/usr/bin/env python3
"""Real theme toggles/new children on isolated nonroot X11; no power/audio/model actions."""
import configparser
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
assert os.getuid() == 1000 and os.environ.get("OOONANA_GUI_TEST_DISPLAY") == "1"

if len(sys.argv) > 1 and sys.argv[1] == "--paint":
    expected, image = sys.argv[2:]
    sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana/ui"))
    from common import Gdk, Gtk, apply_theme, light_appearance
    from controls_app import PowerWindow
    apply_theme()
    assert light_appearance() == (expected == "light")
    assert os.environ["GTK_THEME"] == "Adwaita" + (":dark" if expected == "dark" else "")
    settings = Gtk.Settings.get_default()
    settings.set_property("gtk-xft-dpi", round(96 * 1024 * float(os.environ["OOONANA_GUI_TEXT_SCALE"])))
    assert settings.get_property("gtk-application-prefer-dark-theme") == (expected == "dark")
    window = PowerWindow()
    window.show_all()
    for _ in range(25):
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        time.sleep(.015)
    screen = Gdk.get_default_root_window()
    bounds = window.get_window().get_frame_extents()
    assert bounds.x >= 0 and bounds.y >= 0 and bounds.x + bounds.width <= screen.get_width() and bounds.y + bounds.height <= screen.get_height(), bounds
    color = window.get_style_context().get_background_color(Gtk.StateFlags.NORMAL)
    rgb = tuple(round(channel * 255) for channel in (color.red, color.green, color.blue))
    assert rgb == ((245, 245, 247) if expected == "light" else (16, 19, 23)), rgb
    Gdk.pixbuf_get_from_window(screen, 0, 0, screen.get_width(), screen.get_height()).savev(image, "png", [], [])
    print("NATIVE_THEME_PAINT_OK", expected, rgb, "gtk", os.environ["GTK_THEME"], flush=True)
    window.destroy()
    raise SystemExit(0)

output = Path(sys.argv[1])
output.mkdir(parents=True, exist_ok=True)
assert subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode != 0
config = output / "i3.conf"
config.write_text("\n".join(line for line in (ROOT / "branding/i3/config").read_text().splitlines()
                           if not line.startswith("exec")) + "\n")
wm = subprocess.Popen(["i3", "-c", str(config)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
children = []

def wait(predicate, detail):
    deadline = time.monotonic() + 12
    while not predicate():
        assert time.monotonic() < deadline, detail
        time.sleep(.05)

def clients():
    tree = json.loads(subprocess.check_output(["i3-msg", "-t", "get_tree"], text=True))
    found = []
    def visit(node):
        if node.get("window"):
            found.append(node)
        for child in node.get("nodes", []) + node.get("floating_nodes", []):
            visit(child)
    visit(tree)
    return found

def close_clients():
    for item in clients():
        subprocess.run(["i3-msg", "[con_id=%d] kill" % item["id"]], check=True, capture_output=True)
    wait(lambda: not clients(), "Owned theme clients did not close")

try:
    wait(lambda: subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode == 0, "Private i3 unavailable")
    with tempfile.TemporaryDirectory(prefix="ooonana-theme-flow-") as temporary:
        base = Path(temporary)
        initial = dict(os.environ, XDG_CONFIG_HOME=str(base / "config"))
        for key in ("OOONANA_THEME", "OOONANA_THEME_INHERITED", "OOONANA_THEME_OVERRIDE"):
            initial.pop(key, None)
        preference = base / "config/ooonana/theme"
        preference.parent.mkdir(parents=True)
        preference.write_text("dark\n")
        schemes = base / "config/geany/colorschemes"
        schemes.mkdir(parents=True)
        for scheme in (ROOT / "packages/ooonana/usr/share/geany/colorschemes").glob("*.conf"):
            shutil.copyfile(scheme, schemes / scheme.name)
        # Export exactly what the real desktop helper emits, once. This parent
        # deliberately keeps stale dark values through both later toggles.
        inherited = dict(initial)
        for line in subprocess.check_output(["ooonana-theme-env", "env"], env=initial, text=True).splitlines():
            if line.startswith("export "):
                continue
            key, value = line.split("=", 1)
            inherited[key] = shlex.split(value)[0]
        assert inherited["OOONANA_THEME_INHERITED"] == "dark"
        for selected in ("light", "dark"):
            result = subprocess.run(["ooonana-theme-env", "toggle"], env=inherited, capture_output=True, text=True, check=True, timeout=25)
            (output / (selected + "-apply.log")).write_text(result.stdout + result.stderr)
            assert preference.read_text() == selected + "\n"
            assert preference.stat().st_mode & 0o777 == 0o600
            parser = configparser.ConfigParser()
            parser.read(base / "config/gtk-3.0/settings.ini")
            assert parser["Settings"].getboolean("gtk-application-prefer-dark-theme") == (selected == "dark")
            assert inherited["GTK_THEME"] == "Adwaita:dark", "Fixture repaired stale parent environment"
            subprocess.run([sys.executable, __file__, "--paint", selected, str(output / (selected + "-native.png"))],
                           env=inherited, check=True, timeout=15)
            wait(lambda: not clients(), "Native paint client retained")
            for wrapper, command in (("ooonana-editor", "geany"), ("ooonana-files", "nemo")):
                process = subprocess.Popen([wrapper], env=inherited, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                children.append(process)
                wait(lambda: any(item.get("window_properties", {}).get("class", "").lower() == command for item in clients()), "Real themed app unavailable: " + wrapper)
                item = next(item for item in clients() if item.get("window_properties", {}).get("class", "").lower() == command)
                pid = int(subprocess.check_output(["xdotool", "getwindowpid", str(item["window"])], text=True))
                process_env = dict(pair.split(b"=", 1) for pair in Path("/proc/%d/environ" % pid).read_bytes().split(b"\0") if b"=" in pair)
                assert process_env[b"GTK_THEME"].decode() == "Adwaita" + (":dark" if selected == "dark" else ""), process_env.get(b"GTK_THEME")
                # X11 MapNotify can precede first application paint. A mapped
                # Nemo frame alone previously captured wallpaper, not its UI.
                time.sleep(1)
                subprocess.run(["maim", str(output / (selected + "-" + command + ".png"))], check=True, capture_output=True)
                close_clients()
                print("PREFERRED_APP_THEME_OK", selected, command, flush=True)
            # Existing Geany profile remains user-owned on subsequent toggles.
            parser.read(base / "config/geany/geany.conf")
            assert parser["geany"]["color_scheme"] == "ooonana-light.conf"
        preference.write_text("light\n")
        subprocess.run([sys.executable, __file__, "--paint", "dark", str(output / "explicit-dark-native.png")],
                       env=dict(inherited, OOONANA_THEME_OVERRIDE="dark"), check=True, timeout=15)
        # Linked and unwritable user preferences must fail without false success.
        preference.unlink()
        protected = base / "managed-theme"
        protected.write_text("light\n")
        preference.symlink_to(protected)
        result = subprocess.run(["ooonana-theme-env", "toggle"], env=inherited, capture_output=True, timeout=8)
        assert result.returncode and protected.read_text() == "light\n" and preference.is_symlink()
        preference.unlink()
        preference.write_text("light\n")
        preference.parent.chmod(0o500)
        try:
            result = subprocess.run(["ooonana-theme-env", "toggle"], env=inherited, capture_output=True, timeout=8)
            assert result.returncode and preference.read_text() == "light\n"
        finally:
            preference.parent.chmod(0o700)
    print("THEME_FLOW_UI_OK actual toggle both ways; stale session; native GTK/base chrome; real Geany/Nemo; explicit override; atomic/link/permission refusal", flush=True)
finally:
    for child in children:
        if child.poll() is None:
            child.terminate()
            child.wait(timeout=5)
    wm.terminate()
    wm.wait(timeout=5)
