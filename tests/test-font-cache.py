#!/usr/bin/env python3
"""Epoch repair and subsequent boot fast path, inside owned temporary paths."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class FontCacheTests(unittest.TestCase):
    def check_cache(self, epoch, cached, expected):
        with tempfile.TemporaryDirectory(prefix="ooonana-font-cache-") as directory:
            work = Path(directory)
            fonts, cache, tools = (work / name for name in ("fonts", "cache", "bin"))
            for path in (fonts, cache, tools):
                path.mkdir()
            log = work / "calls"
            if cached:
                (cache / "fixture.cache-9").write_text("existing")
            os.utime(fonts, (epoch, epoch))
            helper = tools / "fc-cache"
            helper.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >>"$CALLS"\n'
                              'printf cached >"$CACHE_DIR/fixture.cache-9"\n')
            helper.chmod(0o755)
            text = (ROOT / "scripts/build-full-i3-rootfs.sh").read_text()
            body = text.split("refresh_font_caches() {", 1)[1].split("\n}\n", 1)[0]
            body = body.replace("/usr/share/fonts", str(fonts)).replace("/var/cache/fontconfig", str(cache))
            script = "refresh_font_caches() {" + body + "\n}\nrefresh_font_caches\n"
            env = {**os.environ, "PATH": str(tools) + ":" + os.environ["PATH"],
                   "CALLS": str(log), "CACHE_DIR": str(cache)}
            subprocess.run(["sh", "-c", script], env=env, check=True)
            stamp = fonts.stat().st_mtime_ns
            subprocess.run(["sh", "-c", script], env=env, check=True)
            self.assertEqual(log.read_text().splitlines() if log.exists() else [],
                             [line.replace("FONTS", str(fonts)) for line in expected])
            self.assertEqual(fonts.stat().st_mtime_ns, stamp, "Ordinary boot rewrote font timestamp")
            self.assertNotEqual(stamp, 0)

    def test_epoch_tree_with_existing_cache_is_repaired_once(self):
        self.check_cache(0, True, ["-f FONTS"])

    def test_existing_nonzero_tree_keeps_fast_path(self):
        self.check_cache(1730000000, True, [])

    def test_missing_cache_is_generated_once(self):
        self.check_cache(1730000000, False, ["FONTS"])


if __name__ == "__main__":
    unittest.main()
