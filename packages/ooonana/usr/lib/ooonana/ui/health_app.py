#!/usr/bin/python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import Gdk, Gtk, Pango, apply_theme, button, fit_dialog, flow_row, header, label, load_preferences, more_actions, run_async
from health_summary import format_snapshot


class HealthWindow(Gtk.Window):
    def __init__(self, updates=False):
        super().__init__(title="Ooonana Updates" if updates else "Ooonana Health")
        self.pending = False
        self.closed = False
        self.raw_output = ""
        self.summary_output = None
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
        self.more_button = more_actions(self.actions[2:], "Upgrade review and repository refresh")
        controls = flow_row([*self.actions[:2], self.more_button], max_children=3, min_children=2)
        root.pack_start(controls, False, False, 0)
        policy = Gtk.Expander(label="Update policy and configuration")
        policy.add(label("Major OS upgrades require explicit approval. Security updates require repository markings. Changed configuration stays intact; new defaults use .ooonana-new.", "muted"))
        root.pack_start(policy, False, False, 0)
        feedback = Gtk.Box(spacing=8)
        self.spinner = Gtk.Spinner()
        feedback.pack_start(self.spinner, False, False, 0)
        self.status = label("Ready", "muted")
        self.status.set_line_wrap(True)
        self.status.set_lines(2)
        self.status.set_ellipsize(Pango.EllipsizeMode.END)
        feedback.pack_start(self.status, True, True, 0)
        self.raw_toggle = Gtk.ToggleButton(label="Raw output")
        self.raw_toggle.set_tooltip_text("Show exact diagnostic output, including fields not in the summary.")
        self.raw_toggle.connect("toggled", lambda *_: self.show_result())
        self.raw_toggle.set_sensitive(False)
        feedback.pack_end(self.raw_toggle, False, False, 0)
        self.copy_button = button("Copy", "edit-copy-symbolic", lambda *_: Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(self.raw_output, -1))
        self.copy_button.set_tooltip_text("Copy exact diagnostic output")
        self.copy_button.set_sensitive(False)
        feedback.pack_end(self.copy_button, False, False, 0)
        root.pack_start(feedback, False, False, 0)
        self.view = Gtk.TextView(editable=False, cursor_visible=False)
        self.view.set_monospace(True)
        self.view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.view.set_left_margin(18)
        self.view.set_top_margin(18)
        self.view.set_right_margin(18)
        self.view.set_bottom_margin(18)
        self.heading_tag = self.view.get_buffer().create_tag("health-section", weight=Pango.Weight.BOLD)
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

    def show_result(self):
        raw = self.raw_toggle.get_active() or self.summary_output is None
        self.view.set_monospace(raw)
        self.view.set_pixels_above_lines(0 if raw else 2)
        buffer = self.view.get_buffer()
        output = self.raw_output if raw else self.summary_output
        buffer.set_text(output)
        if not raw:
            for number, line in enumerate(output.splitlines()):
                if line in {"System", "Memory", "Service endpoints", "Detected device nodes", "Commands", "Scope"}:
                    start = buffer.get_iter_at_line(number)
                    end = start.copy()
                    end.forward_to_line_end()
                    buffer.apply_tag(self.heading_tag, start, end)

    def request(self, command, title, timeout, admin=False):
        if self.closed or self.pending:
            return
        self.pending = True
        for action in self.actions:
            action.set_sensitive(False)
        self.more_button.set_sensitive(False)
        self.raw_toggle.set_sensitive(False)
        self.copy_button.set_sensitive(False)
        self.raw_toggle.set_active(False)
        self.status.set_text(title + "...")
        context = self.status.get_style_context()
        for tone in ("status-good", "status-bad", "status-warn"):
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
            self.more_button.set_sensitive(True)
            self.raw_output = output or (f"Command failed ({rc})" if rc else "No output.")
            formatted = format_snapshot(output) if rc == 0 and command == ["ooonana-health", "--json"] else None
            self.summary_output = formatted[0] if formatted else None
            tone = "status-bad" if rc else "status-good"
            status = title + (f": failed (exit {rc})" if rc else ": complete")
            if command == ["ooonana-health", "--json"] and rc == 0:
                if formatted is None:
                    status, tone = "Snapshot returned unrecognized data. Raw output shown.", "status-warn"
                elif formatted[1]:
                    count = len(formatted[1])
                    status = f"Snapshot collected · {count} {'item needs' if count == 1 else 'items need'} attention"
                    tone = "status-warn"
                else:
                    status = "Snapshot collected · service endpoints ready"
            self.status.set_text(status)
            self.status.set_tooltip_text(status)
            context = self.status.get_style_context()
            for previous in ("muted", "status-good", "status-bad", "status-warn"):
                context.remove_class(previous)
            context.add_class(tone)
            self.raw_toggle.set_sensitive(formatted is not None)
            self.copy_button.set_sensitive(bool(output))
            self.show_result()

        run_async(command, done, timeout=timeout, admin=admin)

    def check(self, updates=False):
        command = ["ooonana", "update-status"] if updates else ["ooonana-health", "--json"]
        self.request(command, "Update status" if updates else "Health snapshot", 30)

    def refresh_repo(self, *_args):
        if self.closed or self.pending:
            return
        dialog = Gtk.MessageDialog(transient_for=self, modal=True, message_type=Gtk.MessageType.QUESTION, buttons=Gtk.ButtonsType.NONE, text="Refresh repository metadata?")
        fit_dialog(dialog, 560)
        dialog.format_secondary_text("Downloads metadata only. Does not install packages. Administration password may be requested.")
        dialog.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Refresh metadata", Gtk.ResponseType.OK)
        dialog.set_default_response(Gtk.ResponseType.CANCEL)
        accepted = dialog.run() == Gtk.ResponseType.OK
        dialog.destroy()
        if accepted:
            self.request(["ooonana", "update"], "Repository refresh", 180, admin=True)

    def review(self, *_args):
        self.request(["ooonana", "upgrade", "--dry-run"], "Upgrade review", 45)


if __name__ == "__main__":
    apply_theme()
    window = HealthWindow(updates="--updates" in sys.argv)
    window.show_all()
    Gtk.main()
