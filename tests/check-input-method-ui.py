#!/usr/bin/env python3
"""Real Fcitx Hangul/GTK/Qt/clipboard and lock interaction on owned X11 only."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

assert os.getuid() == 1000 and os.environ.get("OOONANA_GUI_TEST_DISPLAY") == "1"
os.environ.update(json.loads(subprocess.check_output(["ooonana-input-method", "--json-env"], text=True)))
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"packages/ooonana/usr/lib/ooonana/ui"))
from common import Gdk, Gtk, apply_theme, header
output = Path(sys.argv[1]); output.mkdir(parents=True, exist_ok=True)
Gtk.Settings.get_default().set_property("gtk-xft-dpi", round(96*1024*float(os.environ.get("OOONANA_GUI_TEXT_SCALE", "1"))))
apply_theme()


def command(*args):
    return subprocess.run(args, capture_output=True, text=True, check=True, timeout=6)


def drain(seconds=.1):
    until = time.monotonic()+seconds
    while time.monotonic() < until:
        while Gtk.events_pending(): Gtk.main_iteration_do(False)
        time.sleep(.005)


def wait(predicate, detail, timeout=12):
    until = time.monotonic()+timeout
    while not predicate():
        assert time.monotonic() < until, detail
        drain(.04)


def key(*keys):
    command("xdotool", "key", "--clearmodifiers", *keys); drain()


def activate():
    command("fcitx5-remote", "-s", "hangul")
    command("fcitx5-remote", "-c")
    key("ctrl+space")
    wait(lambda: command("fcitx5-remote").stdout.strip() == "2", "IME hotkey failed")


def type_hangul():
    command("xdotool", "type", "--clearmodifiers", "--delay", "60", "gksrma")
    key("BackSpace")
    command("xdotool", "type", "--clearmodifiers", "f")


def capture(name):
    root = Gdk.get_default_root_window()
    Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height()).savev(str(output/(name+".png")), "png", [], [])


wm = window = terminal = locker = None
with tempfile.TemporaryDirectory(prefix="ooonana-ime-wm-") as directory:
    config = Path(directory)/"i3.conf"
    config.write_text("\n".join(line for line in (ROOT/"branding/i3/config").read_text().splitlines() if not line.startswith("exec"))+"\n")
    try:
        installed_config = Path.home()/".config/i3/config"
        installed_config.parent.mkdir(parents=True, exist_ok=True)
        installed_config.write_text(config.read_text())
        session_env = {**os.environ, "OOONANA_SKIP_SETUP": "1", "OOONANA_NO_AUDIO": "1"}
        for name in ("GTK_IM_MODULE", "QT_IM_MODULE", "XMODIFIERS", "GTK_IM_MODULE_FILE"):
            session_env.pop(name, None)
        wm = subprocess.Popen(["ooonana-i3-session"], env=session_env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        wait(lambda: subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode == 0, "Private i3 unavailable")
        inherited = dict(item.split(b"=", 1) for item in Path(f"/proc/{wm.pid}/environ").read_bytes().split(b"\0") if b"=" in item)
        for name, value in ((b"GTK_IM_MODULE", b"fcitx"), (b"QT_IM_MODULE", b"fcitx"), (b"XMODIFIERS", b"@im=fcitx")):
            assert inherited.get(name) == value, "Actual session failed to configure input method"
        assert inherited.get(b"GTK_IM_MODULE_FILE"), "Actual session omitted GTK module cache"
        command("ooonana-input-method", "--start")
        # State 0 is healthy before an input context has focus. --check avoids
        # autoactivating a second daemon while the requested one starts.
        def ready():
            result = subprocess.run(["fcitx5-remote", "--check"], capture_output=True, text=True, timeout=3)
            return result.returncode == 0 and result.stdout.strip() in ("0", "1", "2")
        wait(ready, "Fcitx not ready")
        profile = Path.home()/".config/fcitx5/profile"
        assert "Name=hangul" in profile.read_text()
        before = profile.read_bytes()
        command("ooonana-input-method", "--start")
        assert profile.read_bytes() == before, "Existing IME profile overwritten"
        daemons = []
        for path in Path('/proc').glob('[0-9]*/cmdline'):
            try:
                arguments = path.read_bytes().split(b'\0')
                if arguments[0].rsplit(b'/', 1)[-1] == b'fcitx5':
                    status = path.with_name('status').read_text()
                    rss = int(next(line.split()[1] for line in status.splitlines() if line.startswith('VmRSS:')))
                    daemons.append(dict(arguments=[item.decode() for item in arguments if item], rss_kib=rss))
            except (OSError, StopIteration):
                pass  # An owned short-lived duplicate can exit between reads.
        assert len(daemons) == 1, daemons
        assert '--disable=clipboard' in daemons[0]['arguments'], "Default clipboard-history addon unexpectedly enabled"
        window = Gtk.Window(title="Ooonana input QA"); window.set_default_size(560, 260)
        header(window, "Input check", "Private Korean and clipboard fixture")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12); box.set_border_width(18)
        first, second = Gtk.Entry(), Gtk.Entry()
        first.get_accessible().set_name("Korean input")
        second.get_accessible().set_name("Clipboard destination")
        box.pack_start(first, False, False, 0); box.pack_start(second, False, False, 0)
        window.add(box); window.show_all(); window.present(); drain(.3)
        first.grab_focus(); window.get_window().focus(Gdk.CURRENT_TIME); drain()
        command("xdotool", "type", "--clearmodifiers", "Latin")
        wait(lambda: first.get_text() == "Latin", "Fresh IME profile unexpectedly changes default Latin input")
        key("ctrl+a", "BackSpace")
        activate(); type_hangul(); key("space")
        wait(lambda: first.get_text() == "한글 ", "Native GTK Hangul/Backspace composition failed")
        key("ctrl+a", "ctrl+c", "Tab", "ctrl+v")
        wait(lambda: second.get_text() == "한글 ", "Private clipboard/focus traversal failed")
        capture("gtk-hangul-clipboard")
        destination = output/"qt.txt"
        with (output/"qterminal.log").open("w") as log:
            terminal = subprocess.Popen(["qterminal", "-e", "/bin/sh", "/source/tests/fixtures/read-ime-input.sh", str(destination)], stdout=log, stderr=log)
            wait(lambda: subprocess.run(["xdotool", "search", "--onlyvisible", "--class", "qterminal"], capture_output=True).returncode == 0, "Qt terminal unavailable")
            ids = command("xdotool", "search", "--onlyvisible", "--class", "qterminal").stdout.splitlines()
            command("xdotool", "windowactivate", "--sync", ids[-1]); drain(.4)
            activate(); type_hangul(); key("Return")
            wait(lambda: destination.exists(), "Qt input method failed to commit")
            assert destination.read_text() == "한글", destination.read_text()
            terminal.wait(timeout=8)
        # Active IME must not alter the locker's raw password input/grabs.
        window.present(); first.grab_focus(); drain()
        activate()
        locker = subprocess.Popen(["ooonana-lock", "--foreground"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        drain(.5); assert locker.poll() is None
        command("xdotool", "type", "--delay", "20", "Ooonana-private-lock-QA-20261023"); key("Return")
        assert locker.wait(timeout=12) == 0, "Active IME changed real PAM password input"
        (output/"receipt.json").write_text(json.dumps(dict(gtk_hangul=True, backspace=True,
            clipboard_and_tab=True, qt_hangul=True, profile_preserved=True,
            real_lock_with_active_ime=True, actual_session_environment=True,
            input_daemons=daemons, physical_wslg_certified=False), indent=2)+"\n")
        print("INPUT_METHOD_UI_OK real Hangul/Backspace/GTK/Qt/private clipboard; saved profile; real PAM with active IME", flush=True)
    finally:
        if locker is not None and locker.poll() is None: locker.terminate(); locker.wait(timeout=5)
        if terminal is not None and terminal.poll() is None: terminal.terminate(); terminal.wait(timeout=5)
        if window is not None: window.destroy()
        subprocess.run(["fcitx5-remote", "-e"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        if wm is not None: wm.terminate(); wm.wait(timeout=5)
