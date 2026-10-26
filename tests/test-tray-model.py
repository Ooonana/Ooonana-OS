#!/usr/bin/env python3
"""Toolkit-free indicator input limits; never touches a live bus/display."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages/ooonana/usr/lib/ooonana"))
import tray_model as model


class TrayModel(unittest.TestCase):
    def test_legacy_dock_wire_guards(self):
        self.assertEqual(model.dock_request(33, 32, [0, 0, 12345, 0, 0]), 12345)
        for kind, wire, values in ((32, 32, [0, 0, 1, 0, 0]), (33, 8, [0, 0, 1, 0, 0]),
                (33, 32, None), (33, 32, []), (33, 32, [0, 1, 1, 0, 0]),
                (33, 32, [0, 0, 0, 0, 0]), (33, 32, [0, 0, -1, 0, 0]),
                (33, 32, [0, 0, 2**32, 0, 0]), (33, 32, [0, 0, True, 0, 0])):
            self.assertIsNone(model.dock_request(kind, wire, values))
        self.assertEqual(model.MAX_LEGACY_ITEMS, 32)

    def test_registration_forms(self):
        self.assertEqual(model.address("/org/blueman/sni", ":1.20"), (":1.20", "/org/blueman/sni"))
        self.assertEqual(model.address("org.example.Tray"), ("org.example.Tray", "/StatusNotifierItem"))
        self.assertEqual(model.address(":1.22/a"), (":1.22", "/a"))
        for bad in ("", "$(id)", "org.bad/foo-bar", "org.bad//path", "../foo", "org.bad/../x", "/a\0", "x" * 2000):
            with self.assertRaises(ValueError): model.address(bad, ":1.20")

    def test_properties_plain_text_no_arbitrary_menu_paths(self):
        props = model.properties({"Title": "Long\nname\x01", "Menu": "/bad/../path", "ItemIsMenu": "true", "ToolTip": ("", [], "Title", "<b>plain</b>")})
        self.assertEqual(props["Title"], "Longname")
        self.assertEqual(props["Menu"], "")
        self.assertFalse(props["ItemIsMenu"])
        self.assertIn("<b>plain</b>", props["ToolTip"])
        self.assertEqual(len(model.properties({"Title": "x" * 10000})["Title"]), 512)

    def test_argb_pixmap_bounds(self):
        self.assertEqual(model.pixmap([(1, 1, bytes([255, 10, 20, 30]))]), (1, 1, bytes([10, 20, 30, 255])))
        self.assertIsNone(model.pixmap([(257, 1, bytes(1028)), (1, 1, b"x"), (-1, 1, b"")]))
        self.assertIsNone(model.pixmap([(1, 1, [-1, 0, 0, 0])]))

    def test_native_menu_semantics_and_limits(self):
        node = model.menu_nodes((0, {}, [(1, {"label": "_Connect", "enabled": False}, []),
                                        (2, {"label": "Hidden", "visible": False}, []),
                                        (3, {"toggle-type": "checkmark", "toggle-state": 1}, []),
                                        (1, {"label": "Duplicate"}, [])]))
        self.assertEqual([child["id"] for child in node["children"]], [1, 3])
        self.assertFalse(node["children"][0]["enabled"])
        self.assertTrue(node["children"][1]["checked"])
        many = model.menu_nodes((0, {}, [(i, {"label": "x"}, []) for i in range(1, 500)]))
        self.assertEqual(len(many["children"]), 127)
        self.assertIsNone(model.menu_nodes(("invalid", {}, [])))


if __name__ == "__main__":
    unittest.main()
