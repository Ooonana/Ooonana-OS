#!/usr/bin/python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import Gtk, apply_theme, button, flow_row, header, label, load_preferences, run_async


class HealthWindow(Gtk.Window):
    def __init__(self, updates=False):
        super().__init__(title="Ooonana Updates" if updates else "Ooonana Health")
        self.pending = False
        self.closed = False
        self.set_default_size(820, 590)
        header(self, self.get_title(), "Read-only checks. No audio playback or disk probing.", "utilities-system-monitor-symbolic")
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        root.set_border_width(22)
        self.add(root)
        self.actions = [button(title, image, callback) for title, image, callback in (
            ("Health snapshot", "view-refresh-symbolic", lambda *_: self.check(False)),
            ("Update status", "system-software-update-symbolic", lambda *_: self.check(True)),
            ("Upgrade review", "document-properties-symbolic", self.review),
            ("Refresh repository", "folder-download-symbolic", self.refresh_repo))]
        controls = flow_row(self.actions, max_children=4, min_children=2)
        root.pack_start(controls, False, False, 0)
        root.pack_start(label("Major OS upgrades require explicit approval. Security updates require repository markings. Changed configuration stays intact; new defaults use .ooonana-new.", "muted"), False, False, 0)
        feedback = Gtk.Box(spacing=8)
        self.spinner = Gtk.Spinner()
        feedback.pack_start(self.spinner, False, False, 0)
        self.status = label("Ready", "muted")
        feedback.pack_start(self.status, True, True, 0)
        root.pack_start(feedback, False, False, 0)
        self.view = Gtk.TextView(editable=False, cursor_visible=False)
        self.view.set_monospace(True)
        self.view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.view.set_left_margin(18)
        self.view.set_top_margin(18)
        self.view.set_right_margin(18)
        self.view.set_bottom_margin(18)
        scroll = Gtk.ScrolledWindow()
        scroll.add(self.view)
        root.pack_start(scroll, True, True, 0)
        self.connect("destroy", self.on_destroy)
        self.check(updates)

    def on_destroy(self, *_args):
        self.closed = True
        self.spinner.stop()
        if Gtk.main_level():
            Gtk.main_quit()

    def request(self, command, title, timeout):
        if self.closed or self.pending:
            return
        self.pending = True
        for action in self.actions:
            action.set_sensitive(False)
        self.status.set_text(title + "...")
        context = self.status.get_style_context()
        for tone in ("status-good", "status-bad"):
            context.remove_class(tone)
        context.add_class("muted")
        if not load_preferences()["reduce_motion"]:
            self.spinner.start()
        self.view.get_buffer().set_text(title + "...")

        def done(rc, output):
            if self.closed:
                return
            self.pending = False
            self.spinner.stop()
            for action in self.actions:
                action.set_sensitive(True)
            self.status.set_text(title + (f": failed (exit {rc})" if rc else ": complete"))
            context = self.status.get_style_context()
            for tone in ("muted", "status-good", "status-bad"):
                context.remove_class(tone)
            context.add_class("status-bad" if rc else "status-good")
            self.view.get_buffer().set_text(output or (f"Command failed ({rc})" if rc else "No output."))

        run_async(command, done, timeout=timeout)

    def check(self, updates=False):
        command = ["ooonana", "update-status"] if updates else ["ooonana-health", "--json"]
        self.request(command, "Update status" if updates else "Health snapshot", 30)

    def refresh_repo(self, *_args):
        if self.closed or self.pending:
            return
        dialog = Gtk.MessageDialog(transient_for=self, modal=True, message_type=Gtk.MessageType.QUESTION, buttons=Gtk.ButtonsType.OK_CANCEL, text="Refresh repository metadata?")
        dialog.format_secondary_text("Downloads metadata only. Does not install packages. Administration password may be requested.")
        dialog.set_default_response(Gtk.ResponseType.CANCEL)
        accepted = dialog.run() == Gtk.ResponseType.OK
        dialog.destroy()
        if accepted:
            self.request(["ooonana", "update"], "Repository refresh", 180)

    def review(self, *_args):
        self.request(["ooonana", "upgrade", "--dry-run"], "Upgrade review", 45)


if __name__ == "__main__":
    apply_theme()
    window = HealthWindow(updates="--updates" in sys.argv)
    window.show_all()
    Gtk.main()
