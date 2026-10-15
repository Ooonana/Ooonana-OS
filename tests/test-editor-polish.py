#!/usr/bin/env python3
"""Fresh editor defaults only; user choices/symlinks and argv stay untouched."""
import configparser
import os
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parents[1]
source = (root / "scripts/build-full-i3-rootfs.sh").read_text()
marker = '  install -D -m 0755 /dev/stdin "$ROOTFS/usr/bin/ooonana-editor" <<\'EOF\'\n'
helper = source.split(marker, 1)[1].split("\nEOF\n", 1)[0]

with tempfile.TemporaryDirectory(prefix="ooonana-editor-polish-") as temporary:
    work = Path(temporary)
    bin_dir = work / "bin"
    bin_dir.mkdir()
    launcher = work / "editor"
    launcher.write_text(helper)
    launcher.chmod(0o755)
    (bin_dir / "geany").write_text('#!/bin/sh\nprintf "%s\\n" "$@" >"$QA_ARGV"\n')
    (bin_dir / "geany").chmod(0o755)
    (bin_dir / "ooonana-theme-env").write_text('#!/bin/sh\nprintf \'OOONANA_THEME="%s"\\n\' "$QA_THEME"\n')
    (bin_dir / "ooonana-theme-env").chmod(0o755)
    env = dict(os.environ, PATH=f"{bin_dir}:{os.environ['PATH']}",
               XDG_CONFIG_HOME=str(work / "config"), QA_ARGV=str(work / "argv"), QA_THEME="dark")
    subprocess.run([launcher, "file with spaces.txt", "second.txt"], env=env, check=True)
    config = work / "config/geany/geany.conf"
    parser = configparser.ConfigParser()
    parser.read(config)
    assert parser["geany"]["color_scheme"] == "ooonana-dark.conf"
    assert parser["geany"]["editor_font"] == "Monospace 11"
    assert parser["geany"]["pref_toolbar_icon_size"] == "2"
    assert not parser["geany"].getboolean("msgwindow_visible")
    assert config.stat().st_mode & 0o777 == 0o600
    toolbar = config.with_name("ui_toolbar.xml")
    assert toolbar.stat().st_mode & 0o777 == 0o600
    actions = [item.attrib["action"] for item in ET.parse(toolbar).findall(".//toolitem")]
    assert actions == ["New", "Open", "Save", "NavBack", "NavFor", "Search", "Build", "Run"]
    assert (work / "argv").read_text().splitlines() == ["file with spaces.txt", "second.txt"]
    config.write_text("[geany]\ncolor_scheme=custom.conf\n")
    before = config.read_bytes()
    subprocess.run([launcher], env=env, check=True)
    assert config.read_bytes() == before
    custom_toolbar = b'<ui><toolbar name="GeanyToolbar"><toolitem action="Open" /></toolbar></ui>'
    toolbar.write_bytes(custom_toolbar)
    config.unlink()
    protected = work / "protected"
    protected.write_text("user data")
    config.symlink_to(protected)
    subprocess.run([launcher], env=env, check=True)
    assert protected.read_text() == "user data" and config.is_symlink()
    config.unlink()
    env["QA_THEME"] = "light"
    subprocess.run([launcher], env=env, check=True)
    parser.read(config)
    assert parser["geany"]["color_scheme"] == "ooonana-light.conf"
    assert toolbar.read_bytes() == custom_toolbar

assert source.count("toolbar button { background: @ooonana_panel; border: 0;") == 2
assert "toolbar button:focus { outline: 2px solid @ooonana_accent;" in source
assert source.count("toolbar entry { min-height: 20px;") == 2
for state in ("button:active", "button.suggested-action:hover", "button.suggested-action:active",
              "button.destructive-action:hover", "button.destructive-action:active"):
    assert source.count(state + " {") == 2, state
assert source.count("headerbar .subtitle { color: @ooonana_muted; opacity: 1; }") == 2

def luminance(color):
    channels = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    channels = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in channels]
    return sum(v * weight for v, weight in zip(channels, (0.2126, 0.7152, 0.0722)))

for theme in ("dark", "light"):
    scheme = configparser.ConfigParser()
    scheme.read(root / f"packages/ooonana/usr/share/geany/colorschemes/ooonana-{theme}.conf")
    palette = scheme["named_colors"]
    background = luminance(palette["bg"])
    for name in ("fg", "muted", "gutter", "amber", "blue", "green", "violet", "rose"):
        foreground = luminance(palette[name])
        ratio = (max(foreground, background) + 0.05) / (min(foreground, background) + 0.05)
        assert ratio >= 4.5, (theme, name, ratio)
print("ok editor-polish: dark/light first-run, compact toolbar, focus, preserved prefs/symlink/argv")
