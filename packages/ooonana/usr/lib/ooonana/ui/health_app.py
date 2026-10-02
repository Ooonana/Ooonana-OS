#!/usr/bin/python3
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import Gtk, apply_theme, button, header, label, message, run_async


class HealthWindow(Gtk.Window):
    def __init__(self, updates=False):
        super().__init__(title="Ooonana Updates" if updates else "Ooonana Health")
        self.set_default_size(820, 590)
        header(self, self.get_title(), "Read-only checks. No audio playback or disk probing.", "utilities-system-monitor-symbolic")
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        root.set_border_width(22)
        self.add(root)
        controls = Gtk.Box(spacing=10)
        controls.pack_start(button("Health snapshot", "view-refresh-symbolic", lambda *_: self.check(False)), False, False, 0)
        controls.pack_start(button("Update status", "system-software-update-symbolic", lambda *_: self.check(True)), False, False, 0)
        controls.pack_end(button("Refresh repository", "folder-download-symbolic", self.refresh_repo), False, False, 0)
        root.pack_start(controls, False, False, 0)
        root.pack_start(label("Major OS upgrades require explicit approval. Security updates require repository markings. Changed configuration stays intact; new defaults use .ooonana-new.", "muted"), False, False, 0)
        self.view = Gtk.TextView(editable=False, cursor_visible=False)
        self.view.set_monospace(True)
        self.view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.view.set_left_margin(18)
        self.view.set_top_margin(18)
        scroll = Gtk.ScrolledWindow()
        scroll.add(self.view)
        root.pack_start(scroll, True, True, 0)
        controls.pack_end(button("Upgrade review", "document-properties-symbolic", self.review), False, False, 0)
        self.connect("destroy", Gtk.main_quit)
        self.check(updates)

    def check(self, updates=False):
        self.view.get_buffer().set_text("Checking...")
        command = ["ooonana", "update-status"] if updates else ["ooonana-health", "--json"]
        run_async(command, lambda rc, output: self.view.get_buffer().set_text(output or f"Check unavailable ({rc})"), timeout=30)

    def refresh_repo(self, *_args):
        dialog = Gtk.MessageDialog(transient_for=self, modal=True, message_type=Gtk.MessageType.QUESTION, buttons=Gtk.ButtonsType.OK_CANCEL, text="Refresh repository metadata?")
        dialog.format_secondary_text("Downloads metadata only. Does not install packages. Administration password may be requested.")
        accepted = dialog.run() == Gtk.ResponseType.OK
        dialog.destroy()
        if accepted:
            run_async(["ooonana", "update"], lambda rc, output: self.view.get_buffer().set_text(output or f"Refresh unavailable ({rc})"), timeout=180)

    def review(self, *_args):
        run_async(["ooonana", "upgrade", "--dry-run"], lambda rc, output: self.view.get_buffer().set_text(output or f"Review unavailable ({rc})"), timeout=45)


if __name__ == "__main__":
    apply_theme()
    window = HealthWindow(updates="--updates" in sys.argv)
    window.show_all()
    Gtk.main()
