#!/usr/bin/env python3
"""Frame palette/resource ownership and color-only IPC; no display needed."""
import importlib.util
import ast
import os
from pathlib import Path
import re
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana"))
import desktop_theme as theme


class Server:
    def __init__(self, original=None, conflict=False):
        self.original = self.value = original
        self.conflict = conflict
        self.closed = False
    def read(self, name):
        return b"/private/i3.sock" if name == "I3_SOCKET_PATH" else self.value
    def replace(self, _name, expected, value):
        if self.conflict or self.value != expected:
            return False
        self.value = value
        return True
    def close(self):
        self.closed = True


class FrameTheme(unittest.TestCase):
    def test_owned_styles_round_client_owned_outer_frames_not_ssd_join(self):
        builder = (ROOT / "scripts/build-full-i3-rootfs.sh").read_text()
        module = ast.parse((ROOT / "packages/ooonana/usr/lib/ooonana/ui/common.py").read_text())
        native = ast.literal_eval(next(node.value for node in module.body
            if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "CSS" for target in node.targets))).decode()
        rules = ("window.background, dialog.background, messagedialog.background { border-radius: 0; }",
                 "window.csd, window.solid-csd { border-radius: 14px; }",
                 "window.maximized headerbar, window.fullscreen headerbar { border-radius: 0; }")
        for rule in rules:
            self.assertEqual(builder.count(rule), 2, "Generated and fallback styles must agree")
            self.assertIn(rule, native)
        self.assertIn("corner-radius = 14;", builder, "Compositor still owns outer SSD corners")

    def test_merge_retains_unowned_comments_and_continuations(self):
        source = (b'! custom resource\r\nXft.dpi: 144\r\ncustom.value: long\\\n'
                  b'ooonana.i3.focused.text: continuation-not-a-key\n'
                  b'ooonana.i3.focused.background: #123456\n'
                  b'ooonana.i3.future: keep\nTerm*foreground: #fff')
        result = theme.merge_resources(source, "light")
        self.assertIn(b'custom.value: long\\\nooonana.i3.focused.text: continuation-not-a-key\n', result)
        self.assertIn(b'! custom resource\r\nXft.dpi: 144\r\n', result)
        self.assertIn(b'ooonana.i3.future: keep\nTerm*foreground: #fff\n', result)
        self.assertNotIn(b'#123456', result)
        self.assertEqual(theme.merge_resources(result, "light"), result)
        self.assertIn(b'ooonana.i3.focused.background: #1b1f26', theme.merge_resources(result, "dark"))

    def test_bounded_malformed_and_unfinished_resources_refused(self):
        for source in (b'x' * (theme.LIMIT + 1), b'custom: trailing\\', b'custom: trailing\\\n', b'custom: nul\0'):
            with self.assertRaises(ValueError):
                theme.merge_resources(source, "light")

    def test_config_contract_and_readable_text_both_themes(self):
        config = (ROOT / "branding/i3/config").read_text()
        self.assertTrue(theme.managed_config(config))
        self.assertFalse(theme.managed_config(config.replace("set_from_resource $oa_text", "# custom palette")))
        self.assertFalse(theme.managed_config("# my custom desktop"))
        def luminance(color):
            rgb = [int(color[i:i+2], 16) / 255 for i in (1, 3, 5)]
            return sum((v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4) * w
                       for v, w in zip(rgb, (.2126, .7152, .0722)))
        for palette in theme.PALETTES.values():
            for background, text, _indicator in palette.values():
                a, b = sorted((luminance(background), luminance(text)))
                self.assertGreaterEqual((b+.05)/(a+.05), 4.5)

    def test_update_only_owned_config_restore_resources_on_error(self):
        config = (ROOT / "branding/i3/config").read_text()
        for managed, fails in ((False, False), (True, False), (True, True)):
            server = Server(b'Xft.dpi: 144\n')
            with patch.dict(os.environ, DISPLAY=":private"), patch.object(theme, "XResources", return_value=server), \
                 patch.object(theme.i3_events, "request", return_value={"config": config if managed else "# custom"}), \
                 patch.object(theme, "refresh_frames", side_effect=ValueError("fixture rejection") if fails else None) as reload:
                if fails:
                    with self.assertRaises(ValueError):
                        theme.apply_frames("light")
                    self.assertEqual(server.value, server.original)
                else:
                    self.assertTrue(theme.apply_frames("light"))
                    self.assertEqual(reload.call_count, int(managed))
                    self.assertFalse(theme.apply_frames("light"), "Unchanged apply must not update again")
                self.assertTrue(server.closed)

    def test_no_display_or_conflicting_writer_never_reloads(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(theme, "XResources") as connection:
            self.assertFalse(theme.apply_frames("dark"))
            connection.assert_not_called()
        server = Server(conflict=True)
        with patch.dict(os.environ, DISPLAY=":private"), patch.object(theme, "XResources", return_value=server), \
             patch.object(theme, "refresh_frames") as reload:
            with self.assertRaises(ValueError):
                theme.apply_frames("light")
            reload.assert_not_called()
            self.assertIsNone(server.value)
            self.assertTrue(server.closed)

    def test_legacy_running_wm_never_receives_reload_or_unknown_command(self):
        for version in ({}, {"ooonana_frame_theme_api": True}, {"ooonana_frame_theme_api": 2}):
            with patch.object(theme.i3_events, "request", return_value=version), patch.object(theme.socket, "socket") as connection:
                with self.assertRaises(ValueError):
                    theme.refresh_frames("/private/i3.sock", "light")
                connection.assert_not_called()

    def test_native_packet_changes_only_palette_not_configuration(self):
        with patch.object(theme.i3_events, "request", return_value={"ooonana_frame_theme_api": 1}), \
             patch.object(theme, "socket"), patch.object(theme.i3_events, "send") as send, \
             patch.object(theme.i3_events, "receive", return_value=(0, [{"success": True}])):
            theme.refresh_frames("/private/i3.sock", "light")
            self.assertEqual(send.call_args.args[1:], (0, b"ooonana_frame_theme light"))

    def test_native_bad_reply_is_not_reported_as_success(self):
        for reply in ((7, [{"success": True}]), (0, None), (0, []),
                      (0, [None]), (0, [{"success": 1}]), (0, [{"success": False}])):
            with patch.object(theme.i3_events, "request", return_value={"ooonana_frame_theme_api": 1}), \
                 patch.object(theme, "socket"), patch.object(theme.i3_events, "send"), \
                 patch.object(theme.i3_events, "receive", return_value=reply):
                with self.assertRaises(ValueError):
                    theme.refresh_frames("/private/i3.sock", "light")

    def test_native_and_resource_palettes_match_without_reload(self):
        spec = importlib.util.spec_from_file_location("frame_patcher", ROOT / "scripts/patch-i3-controls.py")
        patcher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(patcher)
        for native, selected in (("paper", "light"), ("graphite", "dark")):
            body = patcher.FRAME_THEME_C.split(native + "[4][3] = {", 1)[1].split("};", 1)[0]
            colors = re.findall(r'"(#[0-9a-f]{6})"', body)
            self.assertEqual(colors, [color for row in theme.PALETTES[selected].values() for color in row])
        for forbidden in ("load_configuration(", "free_configuration(", "cmd_reload(", "parse_command(" ):
            self.assertNotIn(forbidden, patcher.FRAME_THEME_C)


if __name__ == "__main__":
    unittest.main()
