#!/usr/bin/env python3
"""Real Settings -> sudo/askpass/PAM -> signed local metadata, fault and retry."""
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages/ooonana/usr/lib/ooonana/ui"))
from common import Gdk, GLib, Gtk, apply_theme
from settings_app import SettingsWindow

assert os.getuid() == 1000 and os.environ.get("OOONANA_GUI_TEST_DISPLAY") == "1"
assert os.environ.get("OOONANA_GUI_TEST_ADMIN_POLICY") == "1"
assert subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode != 0
output = Path(sys.argv[1])
output.mkdir(parents=True, exist_ok=True)
repo, cache, sources = (output / name for name in ("repo", "cache", "sources"))
repo.mkdir(); sources.mkdir()
key = output / "qa-only.key"
subprocess.run(["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(key)],
               check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
key.chmod(0o600)
(repo / "qa-metadata.pkg").write_text('OOONANA_PKG_ID="qa-metadata"\nOOONANA_PKG_VERSION="1"\n'
                                   'OOONANA_PKG_KIND="profile"\nOOONANA_PKG_SUMMARY="Private metadata fixture"\n')
subprocess.run(["python3", "-B", str(ROOT / "scripts/index-repo-fast.py"), "--repo", str(repo), "--sign-key", str(key)], check=True)
for name, value in dict(OOONANA_REPO_DIR=repo, OOONANA_SOURCES_DIR=sources, OOONANA_CACHE_DIR=cache,
                        OOONANA_STATE_DIR=output / "state", OOONANA_REPO_VERIFY_KEY=repo / "repo.pub",
                        OOONANA_REQUIRE_SIGNED_REPOS="1").items():
    os.environ[name] = str(value)
assert subprocess.run(["sudo", "-n", "/usr/bin/ooonana", "update"], capture_output=True).returncode != 0
config = output / "i3.conf"
config.write_text("\n".join(line for line in (ROOT / "branding/i3/config").read_text().splitlines()
                           if not line.startswith("exec")) + "\n")
wm = subprocess.Popen(["i3", "-c", str(config)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def settle():
    while Gtk.events_pending():
        Gtk.main_iteration_do(False)
    time.sleep(0.01)


window = None
try:
    deadline = time.monotonic() + 8
    while subprocess.run(["i3-msg", "-t", "get_tree"], capture_output=True).returncode:
        assert time.monotonic() < deadline
        time.sleep(0.03)
    Gtk.Settings.get_default().set_property("gtk-xft-dpi", int(96 * 1024 * float(os.environ["OOONANA_GUI_TEXT_SCALE"])))
    apply_theme()
    window = SettingsWindow()
    window.show_all()
    window.sidebar.select_row(window.sidebar.get_row_at_index(4))

    def descendants(widget):
        yield widget
        if isinstance(widget, Gtk.Container):
            for child in widget.get_children():
                yield from descendants(child)

    trigger = next(item for item in descendants(window)
                   if isinstance(item, Gtk.Button) and item.get_label() == "Refresh metadata")
    for name, failed in (("success", False), ("corrupt-index", True), ("retry", False)):
        index = repo / "index.tsv"
        original = index.read_bytes()
        if failed:
            index.write_bytes(original + b"tampered\n")
        answered, errors = [], []
        deadline = time.monotonic() + 28

        def interact():
            dialog = next((item for item in Gtk.Window.list_toplevels()
                           if isinstance(item, Gtk.MessageDialog) and item.get_visible()), None)
            if dialog is not None:
                assert dialog.get_transient_for() is window
                errors.append(dialog)
                dialog.response(Gtk.ResponseType.CLOSE)
            if not answered:
                found = subprocess.run(["xdotool", "search", "--onlyvisible", "--name", "^Authorize( administration)?$"], capture_output=True, text=True)
                if found.returncode == 0 and found.stdout.strip():
                    subprocess.run(["xdotool", "windowfocus", found.stdout.splitlines()[0]], check=True)
                    subprocess.run(["xdotool", "type", "--clearmodifiers", "--file", "-"],
                                   input="Ooonana-private-admin-QA-20261026", text=True, check=True)
                    subprocess.run(["xdotool", "key", "--clearmodifiers", "Return"], check=True)
                    answered.append(True)
            return window.metadata_pending and time.monotonic() < deadline

        watcher = GLib.timeout_add(60, interact)
        trigger.clicked()
        assert window.metadata_pending and not trigger.get_sensitive()
        while window.metadata_pending and time.monotonic() < deadline:
            settle()
        if GLib.MainContext.default().find_source_by_id(watcher):
            GLib.source_remove(watcher)
        index.write_bytes(original)
        assert not window.metadata_pending and trigger.get_sensitive(), name + ": metadata request did not finish"
        assert len(answered) == 1, name + ": real authentication missing"
        assert bool(errors) == failed, name + ": incorrect error dialog"
        status = window.status_widgets["metadata"].get_text()
        assert ("failed" in status.lower()) == failed, status
        if not failed:
            assert "qa-metadata" in (cache / "index.tsv").read_text()
            assert (cache / "index.tsv").stat().st_uid == 0, "Expected privileged cache write"
        assert not list((output / "state").rglob("qa-metadata.pkg")), "Metadata refresh installed package"
        root = Gdk.get_default_root_window()
        Gdk.pixbuf_get_from_window(root, 0, 0, root.get_width(), root.get_height()).savev(str(output / (name + ".png")), "png", [], [])
        print("SETTINGS_ADMIN_PASS", name, flush=True)
    print("SETTINGS_ADMIN_UI_OK actual authorization, signed metadata, tamper refusal, retry; no install", flush=True)
finally:
    if window is not None:
        window.destroy()
    wm.terminate()
    wm.wait(timeout=5)
