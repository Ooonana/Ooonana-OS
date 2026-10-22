#!/usr/bin/env python3
"""Real generated shell/native selection parity; private preferences only."""
import os
import json
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana/ui"))
from ui_preferences import resolved_theme

SOURCE = (ROOT / "scripts/build-full-i3-rootfs.sh").read_text()
HELPER = SOURCE.split('"$ROOTFS/usr/bin/ooonana-theme-env" <<\'EOF\'\n', 1)[1].split("\nEOF", 1)[0]


@unittest.skipIf(sys.platform == "win32", "Generated POSIX helper")
class ThemeSelection(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="ooonana-theme-selection-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.user = self.base / "xdg/ooonana/theme"
        self.system = self.base / "system-theme"
        self.user.parent.mkdir(parents=True)
        self.helper = self.base / "theme-env"
        self.helper.write_text(HELPER.replace("/etc/ooonana/theme", str(self.system)))
        self.helper.chmod(0o700)
        self.env = {"HOME": str(self.base / "home"), "XDG_CONFIG_HOME": str(self.base / "xdg")}

    def select(self, **values):
        env = {**self.env, **values}
        original_open = Path.open
        def private_open(path, *args, **kwargs):
            return original_open(self.system if path == Path("/etc/ooonana/theme") else path, *args, **kwargs)
        with patch.dict(os.environ, env, clear=True), patch.object(Path, "open", private_open):
            native = resolved_theme()
        # Only env mode: this cannot apply a theme or write system settings.
        result = subprocess.run(["sh", str(self.helper), "env"], env=env, capture_output=True, text=True, check=True, timeout=5)
        shell = {}
        for line in result.stdout.splitlines():
            if line.startswith(("OOONANA_THEME=", "OOONANA_THEME_INHERITED=", "GTK_THEME=")):
                name, value = line.split("=", 1)
                shell[name] = shlex.split(value)[0]
        self.assertEqual(shell["OOONANA_THEME"], native or "dark")
        return native, shell

    def test_saved_theme_supersedes_automatic_session_export(self):
        for saved, inherited in (("light", "dark"), ("dark", "light")):
            self.user.write_text(saved + "\n")
            native, shell = self.select(OOONANA_THEME=inherited, OOONANA_THEME_INHERITED=inherited)
            self.assertEqual(native, saved)
            self.assertEqual(shell["OOONANA_THEME_INHERITED"], saved)
            self.assertEqual(shell["GTK_THEME"], "Adwaita" + (":dark" if saved == "dark" else ""))

    def test_explicit_legacy_and_changed_values_still_override(self):
        self.user.write_text("light\n")
        for values in ({"OOONANA_THEME": "dark"},
                       {"OOONANA_THEME": "dark", "OOONANA_THEME_INHERITED": "light"},
                       {"OOONANA_THEME": "dark", "OOONANA_THEME_INHERITED": "dark", "OOONANA_THEME_OVERRIDE": "dark"}):
            native, _ = self.select(**values)
            self.assertEqual(native, "dark")

    def test_system_fallback_invalid_values_and_missing_final_newline(self):
        self.system.write_text("light\n")
        for text in ("unknown\n", "dark\r\n", "light" * 100, ""):
            self.user.write_text(text)
            native, _ = self.select(OOONANA_THEME="dark", OOONANA_THEME_INHERITED="dark")
            self.assertEqual(native, "light")
        self.user.write_text("dark")
        self.assertEqual(self.select()[0], "dark")
        self.user.write_bytes(b"\xff\xfe")
        self.assertEqual(self.select()[0], "light")
        self.user.write_bytes(b"dark\n\xff")
        self.assertEqual(self.select()[0], "dark")

    def test_xdg_preference_and_no_mutation(self):
        legacy = self.base / "home/.config/ooonana/theme"
        legacy.parent.mkdir(parents=True)
        legacy.write_text("light\n")
        self.user.write_text("dark\n")
        self.user.chmod(0o400)
        before = self.user.read_bytes()
        self.assertEqual(self.select()[0], "dark")
        self.assertEqual(self.user.read_bytes(), before)
        self.assertEqual(legacy.read_text(), "light\n")

    def test_invalid_environment_is_never_emitted_as_shell(self):
        self.user.write_text("light\n")
        unsafe = "dark; touch /never-created"
        native, shell = self.select(OOONANA_THEME=unsafe, OOONANA_THEME_INHERITED=unsafe, OOONANA_THEME_OVERRIDE=unsafe)
        self.assertEqual(native, "light")
        self.assertEqual(shell["OOONANA_THEME_INHERITED"], "light")

    def test_preferred_apps_refresh_owned_theme_preserve_path_custom_theme_and_argv(self):
        self.user.write_text("light\n")
        bin_dir = self.base / "bin"
        bin_dir.mkdir()
        (bin_dir / "ooonana-theme-env").symlink_to(self.helper)
        trace = self.base / "launch.json"
        stub = "#!/usr/bin/env python3\nimport json, os, sys\nfrom pathlib import Path\n" \
               "Path(os.environ['QA_TRACE']).write_text(json.dumps({'argv':sys.argv[1:]," \
               "'path':os.environ['PATH'],'theme':os.environ.get('GTK_THEME')," \
               "'selected':os.environ.get('OOONANA_THEME')}))\n"
        for app in ("chromium", "nemo", "geany"):
            executable = bin_dir / app
            executable.write_text(stub)
            executable.chmod(0o700)
        inherited = dict(os.environ, **self.env, PATH=str(bin_dir) + ":" + os.environ["PATH"],
                         OOONANA_THEME="dark", OOONANA_THEME_INHERITED="dark",
                         QA_TRACE=str(trace), OOONANA_BROWSER_DBUS="1",
                         XDG_STATE_HOME=str(self.base / "state"))
        inherited.pop("OOONANA_THEME_OVERRIDE", None)
        for app, argument in (("browser", "https://example.invalid/?two words"),
                              ("files", str(self.base / "folder with spaces")),
                              ("editor", "file with spaces.txt")):
            marker = '"$ROOTFS/usr/bin/ooonana-' + app + '" <<\'EOF\'\n'
            launcher = self.base / app
            launcher.write_text(SOURCE.split(marker, 1)[1].split("\nEOF", 1)[0])
            for gtk, expected in (("Adwaita:dark", "Adwaita"), ("Custom theme's dark", "Custom theme's dark")):
                subprocess.run(["sh", str(launcher), argument], env=dict(inherited, GTK_THEME=gtk),
                               check=True, capture_output=True, text=True, timeout=10)
                actual = json.loads(trace.read_text())
                self.assertEqual(actual["path"], inherited["PATH"])
                self.assertEqual(actual["theme"], expected)
                self.assertEqual(actual["selected"], "light")
                self.assertEqual(actual["argv"][-1], argument)

    def test_atomic_writer_private_user_and_readable_system_modes(self):
        directory = self.base / "system"
        writer = "write_theme() {" + HELPER.split("write_theme() {", 1)[1].split('\ncase "${1:-env}"', 1)[0]
        writer = writer.replace("theme_dir=/etc/ooonana", "theme_dir=" + shlex.quote(str(directory)))
        for uid, target, mode in ((0, directory / "theme", 0o644), (1000, self.user, 0o600)):
            script = "set -eu\nid() { printf '%s\\n' " + str(uid) + "; }\n" + writer + "\nwrite_theme light\n"
            subprocess.run(["sh", "-c", script], env=self.env, check=True, capture_output=True, timeout=5)
            self.assertEqual(target.read_text(), "light\n")
            self.assertEqual(target.stat().st_mode & 0o777, mode)
            if uid == 0:
                self.assertEqual(target.parent.stat().st_mode & 0o777, 0o755)
            self.assertFalse(list(target.parent.glob(".theme.*")))


if __name__ == "__main__":
    unittest.main()
