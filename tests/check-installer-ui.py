#!/usr/bin/env python3
"""Render only the builder's YAD form. Never execute an installer or touch disks."""
import argparse
import configparser
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import time

if os.environ.get("OOONANA_GUI_TEST_DISPLAY") != "1" or os.getuid() == 0:
    raise SystemExit("Dedicated nonroot test display required")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana/ui"))
from common import Gdk, Gtk
from gi.repository import GdkX11

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("output", type=Path)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
findings = []


def check(condition, detail):
    if not condition:
        findings.append(detail)
        print("INSTALLER_UI_FINDING: " + detail, flush=True)


def settle(seconds=.12):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        time.sleep(.005)


for section in ("--help-form", "--help-general", "--help-all"):
    result = subprocess.run(["yad", section], text=True, capture_output=True, timeout=5)
    (args.output / (section.removeprefix("--") + ".txt")).write_text(result.stdout + result.stderr)

source = (ROOT / "scripts/build-full-i3-rootfs.sh").read_text()
theme_script = args.output / "ooonana-theme-env"
theme_script.write_text(source.split('"$ROOTFS/usr/bin/ooonana-theme-env" <<\'EOF\'\n', 1)[1].split("\nEOF", 1)[0])
subprocess.run(["sh", str(theme_script), "apply"], check=True, capture_output=True, timeout=20)
scale = float(os.environ.get("OOONANA_GUI_TEXT_SCALE", "1.0"))
settings_path = Path(os.environ["HOME"]) / ".config/gtk-3.0/settings.ini"
settings = configparser.RawConfigParser()
settings.read(settings_path)
settings["Settings"]["gtk-xft-dpi"] = str(round(96 * 1024 * scale))
settings["Settings"]["gtk-font-name"] = "Serif 11"
with settings_path.open("w") as stream:
    settings.write(stream, space_around_delimiters=False)
subprocess.run(["sh", str(theme_script), "apply"], check=True, capture_output=True, timeout=20)
after_apply = configparser.RawConfigParser()
after_apply.read(settings_path)
check(after_apply.get("Settings", "gtk-font-name") == "Serif 11" and
      after_apply.getint("Settings", "gtk-xft-dpi", fallback=-1) == round(96 * 1024 * scale),
      "Theme apply discards saved font/DPI preferences")
settings["Settings"]["gtk-font-name"] = "Sans 10"
settings["Settings"]["gtk-xft-dpi"] = "98304"
with settings_path.open("w") as stream:
    settings.write(stream, space_around_delimiters=False)
# GDK's documented per-process font-resolution override avoids an XSettings
# manager silently defeating a settings.ini-only stress fixture.
child_env = {**os.environ, "GDK_DPI_SCALE": str(scale)}
probe_code = """import gi,json; gi.require_version('Gtk','3.0'); from gi.repository import Gtk,Gdk; s=Gtk.Settings.get_default(); w=Gtk.Label(label='Scale probe'); print(json.dumps(dict(dpi=s.get_property('gtk-xft-dpi'), resolution=Gdk.Screen.get_default().get_resolution(), pixels=w.get_layout().get_pixel_size()[1])))"""
scale_probe = json.loads(subprocess.check_output([sys.executable, "-c", probe_code], env=child_env, text=True, timeout=8))
(args.output / "scale-probe.json").write_text(json.dumps(scale_probe))
print("INSTALLER_SCALE_PROBE " + json.dumps(scale_probe), flush=True)
check(15 * scale <= scale_probe["pixels"] <= 19 * scale, "Requested text scale did not reach rendered GTK font metrics")
helper = source.split('"$ROOTFS/usr/bin/ooonana-installer-gui" <<\'EOF\'\n', 1)[1].split("\nEOF", 1)[0]
form = helper.split('form="$(yad ', 1)[1].split('2>/dev/null || true)"', 1)[0]
prelude = helper.split("form_width=720", 1)[1].split('form="$(yad ', 1)[0]
# Execute only geometry/field-display formatting, never the installer helper.
# Environment contains literal fixture devices; no disk enumeration is called.
assert "lsblk" not in prelude and "ooonana-install" not in prelude
fixture_disks = "/dev/fixtureUSB 32G Owned USB !model:literal\\path\n/dev/fixtureSSD 512G " + "LongModel" * 12
argument_script = "default_target=''\nform_width=720" + prelude + '\nset -- ' + form + "\npython3 -c 'import json,sys; print(json.dumps(sys.argv[1:]))' \"$@\"\n"
form_arguments = json.loads(subprocess.check_output(["sh"], input=argument_script,
                           env={**child_env, "disk_summary": fixture_disks}, text=True, timeout=10))
root = Gdk.get_default_root_window()
command = ["/usr/bin/yad", *form_arguments]
(args.output / "form-command.json").write_text(json.dumps(command))
assert command.count("--field") == 17, "Readonly disk row + 16 semantic fields required"
assert "--scroll" in command and "--focus-field=2" in command, "Mode and later fields must remain reachable"
assert "--button=Cancel:1" in command and "--button=Review installation:0" in command
assert not any(item in command for item in ("--command", "--plug", "--listen")), "Interactive side effect refused"


def key(*keys):
    subprocess.run(["xdotool", "key", "--clearmodifiers", *keys], check=True, timeout=4)
    settle(.03)


def type_entry(text):
    key("ctrl+a")
    subprocess.run(["xdotool", "type", "--clearmodifiers", "--delay", "0", text], check=True, timeout=4)


def run_window(command, name, interact):
    assert not any(item in command for item in ("--command", "--plug", "--listen")), "Interactive side effect refused"
    xid_path = args.output / (name + ".xid")
    assert not xid_path.exists(), "Output must be fresh"
    with (args.output / (name + ".log")).open("w") as log:
        process = subprocess.Popen([*command, "--print-xid=" + str(xid_path)], stdout=subprocess.PIPE, stderr=log, text=True, env=child_env)
        try:
            deadline = time.monotonic() + 8
            window = None
            while window is None:
                assert process.poll() is None, "YAD dialog exited before capture"
                if xid_path.is_file() and xid_path.read_text().strip():
                    xid = int(xid_path.read_text().strip(), 0)
                    window = GdkX11.X11Window.foreign_new_for_display(Gdk.Display.get_default(), xid)
                assert time.monotonic() < deadline, "Owned installer dialog unavailable"
                time.sleep(.03)
            subprocess.run(["xdotool", "windowactivate", "--sync", str(xid)], check=True, timeout=4)
            settle(.25)
            bounds = window.get_frame_extents()
            Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height()).savev(str(args.output / (name + ".png")), "png", [], [])
            check(0 <= bounds.x and bounds.x + bounds.width <= root.get_width() and
                  0 <= bounds.y and bounds.y + bounds.height <= root.get_height(),
                  f"{name}: {bounds.width}x{bounds.height} at {bounds.x},{bounds.y} outside display")
            return interact(process)
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)


def fill_form(process):
    key("alt+m", "End")  # Last mode: custom partitions. No installer exists.
    expected = ["", "Custom partitions"]
    values = ["/dev/fixtureUSB-root", "/dev/fixtureUSB-home", "/dev/fixtureUSB-swap", "/dev/fixtureUSB-efi"]
    for text in values:
        key("Tab")
        type_entry(text)
    expected.extend(values)
    for value in ("FALSE", "FALSE", "FALSE", "TRUE"):
        key("Tab", "space")
        expected.append(value)
    for text in ("fixture-user", " fixture|password ", "fixture-host"):
        key("Tab")
        type_entry(text)
        expected.append(text)
    key("Tab", "End")
    expected.append("light")
    for text in ("file:///fixture/repository", "/fixture/root", "1024"):
        key("Tab")
        type_entry(text)
        expected.append(text)
    settle()
    Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height()).savev(str(args.output / "installer-last-field.png"), "png", [], [])
    key("Tab", "Tab", "space")
    output, _ = process.communicate(timeout=4)
    check(process.returncode == 0, "Keyboard Review did not accept the bare form")
    actual = output.rstrip("\n").split("\x1f")
    if actual and actual[-1] == "":
        actual.pop()
    check(actual == expected, "Keyboard traversal returned incorrect field values or lost password spaces")
    # Exercise production semantic offset with the actual keyboard-generated
    # wire result; do not run any of the install/dry-run path.
    field_function = helper.split("field() {", 1)[1].split("\n}", 1)[0]
    decoded = subprocess.check_output(["sh", "-c", "field() {" + field_function +
        '\n}\nfor number in 1 2 11 16; do field "$number"; done'],
        env={**os.environ, "form": output.rstrip("\n"), "separator": "\x1f"}, text=True, timeout=4).splitlines()
    check(decoded == ["Custom partitions", values[0], " fixture|password ", "1024"],
          "Readonly row shifted production disk/password field mapping")
    guard = helper[helper.index('if [ "${form#'):helper.index('\nfield() {')]
    wire = output.rstrip("\n")
    for data, accepted in ((wire, True), (wire[1:], False),
                           (wire + "\x1f", False), (wire[:-1], False)):
        result = subprocess.run(["sh", "-c", "yad() { return 0; }\n" + guard],
                                env={**os.environ, "form": data, "separator": "\x1f"},
                                text=True, capture_output=True, timeout=4)
        check((result.returncode == 0) == accepted,
              "Production form guard accepted malformed or rejected valid fields")


def cancel_dialog(process, default=False):
    if default:
        key("Return")
        settle()
        check(process.poll() is None or process.returncode != 0,
              "Enter in read-only preview approved installation")
    if process.poll() is None:
        key("Escape")
    output, _ = process.communicate(timeout=4)
    check(process.returncode != 0 and not output.strip(), "Default/escape did not cancel review")


preview = args.output / "preview.txt"
preview.write_text("Fixture preview only. No installer command executed.\nTarget: /dev/fixtureUSB, 32 GiB\nRoot: explicit fixture partition, format yes\nHome/swap/EFI: explicit fixture partitions\nUnrelated SSD/SD: untouched by this fixture\n" * 8)


def dialog_command(title, filename):
    fragment = helper.split('yad --center --title "' + title + '"', 1)[1].split("2>/dev/null", 1)[0]
    for variable, value in (("$review_width", str(min(860, root.get_width() - 48))),
                            ("$review_height", str(min(560, root.get_height() - 96))),
                            ("$review_text_width", str(max(12, min(50, (min(860, root.get_width() - 48) - 64) //
                              max(1, round(12 * scale)))))),
                            ("$preview", str(filename)), ("$log", str(filename))):
        fragment = fragment.replace(variable, value)
    return ["/usr/bin/yad", "--center", "--title", title, *shlex.split(fragment.replace("\\\n", " "))]


assert subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode != 0
with tempfile.TemporaryDirectory(prefix="ooonana-installer-ui-") as temporary:
    config = Path(temporary) / "i3.conf"
    config.write_text("\n".join(line for line in (ROOT / "branding/i3/config").read_text().splitlines() if not line.startswith("exec")) + "\n")
    wm = subprocess.Popen(["i3", "-c", str(config)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + 8
        while subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode:
            assert time.monotonic() < deadline
            time.sleep(.03)
        run_window(command, "installer-form", fill_form)
        review = dialog_command("Ooonana Install Preview", preview)
        check("--default-button=1" in review, "Final review lacks explicit default Cancel")
        run_window(review, "installer-preview", lambda process: cancel_dialog(process, default=True))
        blocked = dialog_command("Ooonana Install Blocked", preview)
        run_window(blocked, "installer-blocked", cancel_dialog)
    finally:
        wm.terminate()
        wm.wait(timeout=5)

if findings:
    raise SystemExit(1)
print("INSTALLER_UI_OK owned YAD keyboard/form/review/blocked; no disk enumeration, backend or installation command executed")
