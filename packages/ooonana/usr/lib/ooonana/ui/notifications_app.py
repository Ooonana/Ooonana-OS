#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import GLib, Gtk, Pango, apply_theme, button, card, header, label, page_intro, run, run_async, run_async_task  # noqa: E402
from notification_utils import NotificationState, notification_age, parse_history, read_history  # noqa: E402
from ui_preferences import load_preferences, save_preferences


class NotificationsWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Ooonana Notifications")
        self.set_default_size(760, 560)
        self.closed = False
        self.refreshing = False
        self.service_available = False
        self.records = []
        self.state = NotificationState()
        bar = header(self, "Notification center", "Desktop messages", "dialog-information-symbolic")
        bar.pack_end(button("Refresh", "view-refresh-symbolic", lambda *_: self.refresh()))
        self.clear_button = button("Clear all", "edit-clear-symbolic", lambda *_: self.perform(["history-clear"]))
        self.clear_button.set_sensitive(False)
        bar.pack_end(self.clear_button)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        root.set_border_width(20)
        self.add(root)
        root.pack_start(page_intro("Notifications", "Recent desktop messages from this session."), False, False, 0)
        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.pause = Gtk.CheckButton.new_with_label("Do Not Disturb")
        self.pause_handler = self.pause.connect("toggled", self.pause_changed)
        controls.pack_start(self.pause, False, False, 0)
        self.status = label("Loading notifications...", "muted")
        controls.pack_end(self.status, False, False, 0)
        root.pack_start(controls, False, False, 0)
        self.remember = Gtk.CheckButton.new_with_label("Remember messages viewed here")
        self.remember.set_active(load_preferences()["remember_notifications"])
        self.remember.set_tooltip_text("Opt-in. Saves up to 80 messages collected by this center privately on this account. Turning off deletes saved history. Messages received while closed are collected when you reopen it.")
        self.remember.connect("toggled", self.remember_changed)
        root.pack_start(self.remember, False, False, 0)
        self.list = Gtk.ListBox()
        self.list.set_selection_mode(Gtk.SelectionMode.NONE)
        self.list.set_activate_on_single_click(False)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_overlay_scrolling(False)
        scroll.add(self.list)
        root.pack_start(scroll, True, True, 0)
        self.connect("destroy", self.on_destroy)
        self.connect("focus-in-event", lambda *_: (GLib.idle_add(self.refresh), False)[1])
        self.refresh(collect_popups=True)
        GLib.timeout_add_seconds(5, self.periodic_refresh)

    def on_destroy(self, *_args):
        self.closed = True
        Gtk.main_quit()

    def periodic_refresh(self):
        if self.closed:
            return False
        self.refresh()
        return True

    def refresh(self, collect_popups=False):
        if self.closed or self.refreshing:
            return
        self.refreshing = True

        def task():
            if collect_popups:
                run(["dunstctl", "close-all"], timeout=3)
            rc, text = read_history()
            _pause_rc, paused = run(["dunstctl", "is-paused"], timeout=3)
            return rc, (text, paused.strip() == "true")

        def done(rc, result):
            self.refreshing = False
            if self.closed:
                return
            if not isinstance(result, tuple) or len(result) != 2:
                rc, result = 1, ("", False)
            text, paused = result
            live = parse_history(text) if rc == 0 else []
            self.service_available = rc == 0
            try:
                self.records = self.state.merge(live, self.remember.get_active())
                if self.is_active():
                    self.state.mark_read(live)
            except OSError:
                self.records = [{**record, "archived": False} for record in live]
            self.pause.handler_block(self.pause_handler)
            self.pause.set_active(paused)
            self.pause.handler_unblock(self.pause_handler)
            self.pause.set_sensitive(rc == 0)
            self.clear_button.set_sensitive(bool(self.records))
            self.status.set_text(f"{len(self.records)} messages" if rc == 0 else "Saved history · service unavailable")
            for child in self.list.get_children():
                child.destroy()
            if not self.records:
                empty = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
                empty.set_border_width(24)
                empty.pack_start(label("No notifications yet", "page-title"), False, False, 0)
                empty.pack_start(label("Desktop app notifications appear here. Opening this center collects visible popups into history.", "muted"), False, False, 0)
                self.list.add(empty)
            groups = {}
            for record in self.records:
                groups.setdefault(record["app"], []).append(record)
            for app, records in groups.items():
                heading = label(f"{app}  ·  {len(records)}", "card-title", wrap=False)
                heading.set_ellipsize(Pango.EllipsizeMode.END)
                heading.set_margin_top(14)
                heading.set_margin_bottom(6)
                self.list.add(heading)
                for record in records:
                    self.add_notification(record)
            self.list.show_all()

        run_async_task(task, done)

    def add_notification(self, record):
        widget = card(record["summary"])
        widget.set_margin_top(6)
        widget.set_margin_bottom(6)
        heading = widget.get_children()[0].get_children()[0]
        heading.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        heading.set_max_width_chars(64)
        info = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        app = label(record["app"], "muted", wrap=False)
        app.set_ellipsize(Pango.EllipsizeMode.END)
        app.set_max_width_chars(40)
        info.pack_start(app, True, True, 0)
        age = "Earlier session" if record.get("archived") else notification_age(record["timestamp"])
        info.pack_end(label(age, "muted", wrap=False), False, False, 0)
        widget.pack_start(info, False, False, 0)
        if record["body"]:
            body = label(record["body"])
            body.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
            body.set_max_width_chars(64)
            body.set_selectable(True)
            widget.pack_start(body, False, False, 0)
        remove = button("Remove", "edit-delete-symbolic", lambda *_: self.remove_record(record))
        remove.set_halign(Gtk.Align.END)
        widget.pack_start(remove, False, False, 0)
        self.list.add(widget)

    def remember_changed(self, widget):
        try:
            save_preferences(remember_notifications=widget.get_active())
            if not widget.get_active():
                self.state.clear_saved()
        except OSError as exc:
            self.status.set_text(f"Could not save preference: {exc}")
            return
        self.refresh()

    def remove_record(self, record):
        if record.get("archived"):
            try:
                self.state.forget(record)
            except OSError:
                self.status.set_text("Could not remove saved message")
                return
            self.refresh()
        else:
            self.perform(["history-rm", str(record["id"])], record)

    def pause_changed(self, widget):
        self.perform(["set-paused", "true" if widget.get_active() else "false"])

    def perform(self, arguments, removed_record=None):
        if arguments[0] == "history-clear" and not self.service_available:
            try:
                self.state.clear_saved()
            except OSError:
                self.status.set_text("Could not clear saved history")
                return
            self.refresh()
            return
        self.clear_button.set_sensitive(False)
        self.pause.set_sensitive(False)

        def done(rc, _output):
            if not self.closed:
                if rc == 0 and removed_record:
                    try:
                        self.state.forget(removed_record)
                    except OSError:
                        self.status.set_text("Could not remove saved message")
                if rc == 0 and arguments[0] == "history-clear":
                    try:
                        self.state.clear_saved()
                    except OSError:
                        self.status.set_text("Could not clear saved history")
                if rc != 0:
                    self.status.set_text("Notification action failed")
                self.refresh()

        run_async(["dunstctl", *arguments], done, timeout=3)


if __name__ == "__main__":
    if "--dry-run" in sys.argv:
        print("OOONANA_NOTIFICATIONS_GUI_OK")
    else:
        apply_theme()
        window = NotificationsWindow()
        window.show_all()
        Gtk.main()
