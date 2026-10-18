#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import GLib, Gtk, Pango, apply_theme, button, card, header, label, run, run_async, run_async_task  # noqa: E402
from notification_utils import NotificationState, notification_age, parse_history, read_history, record_key  # noqa: E402
from ui_preferences import load_preferences, save_preferences


class NotificationsWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Ooonana Notifications")
        self.set_default_size(760, 560)
        self.closed = False
        self.refreshing = False
        self.service_available = False
        self.action_pending = False
        self.action_error = ""
        self.action_detail = ""
        self.storage_error = ""
        self.storage_detail = ""
        self.pause_known = False
        self.render_signature = None
        self.render_version = 0
        self.render_allocation_handler = 0
        self.remove_buttons = []
        self.age_labels = []
        self.message_controls = {}
        self.expanded_messages = set()
        self.records = []
        self.state = NotificationState()
        bar = header(self, "Notification center", "Desktop messages", "dialog-information-symbolic")
        self.refresh_button = button("Refresh", "view-refresh-symbolic", lambda *_: self.refresh())
        bar.pack_end(self.refresh_button)
        self.clear_button = button("Clear all", "edit-clear-symbolic", lambda *_: self.perform(["history-clear"]))
        self.clear_button.set_sensitive(False)
        bar.pack_end(self.clear_button)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        root.set_border_width(20)
        self.add(root)
        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.pause = Gtk.CheckButton.new_with_label("Do Not Disturb")
        self.pause_handler = self.pause.connect("toggled", self.pause_changed)
        self.pause.set_sensitive(False)
        controls.pack_start(self.pause, False, False, 0)
        self.status = label("Loading notifications...", "muted")
        self.status.set_line_wrap(False)
        self.status.set_ellipsize(Pango.EllipsizeMode.END)
        self.status.set_max_width_chars(28)
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
        self.scroll = scroll
        root.pack_start(scroll, True, True, 0)
        self.connect("destroy", self.on_destroy)
        self.connect("focus-in-event", lambda *_: (GLib.idle_add(self.refresh), False)[1])
        self.refresh(collect_popups=True)
        self.timer_id = GLib.timeout_add_seconds(5, self.periodic_refresh)

    def on_destroy(self, *_args):
        self.closed = True
        if self.render_allocation_handler:
            self.list.disconnect(self.render_allocation_handler)
            self.render_allocation_handler = 0
        if self.timer_id:
            GLib.source_remove(self.timer_id)
            self.timer_id = 0
        if Gtk.main_level():
            Gtk.main_quit()

    def periodic_refresh(self):
        if self.closed:
            return False
        self.refresh()
        return True

    def refresh(self, collect_popups=False):
        if self.closed or self.refreshing or self.action_pending:
            return
        focus_before = self.get_focus()
        self.refreshing = True
        self.update_actions()
        focus_loading = self.get_focus()

        def task():
            if collect_popups:
                run(["dunstctl", "close-all"], timeout=3)
            rc, text = read_history()
            pause_rc, paused = run(["dunstctl", "is-paused"], timeout=3)
            return rc, (text, paused.strip() == "true" if pause_rc == 0 else None)

        def done(rc, result):
            self.refreshing = False
            if self.closed:
                return
            if not isinstance(result, tuple) or len(result) != 2:
                rc, result = 1, ("", None)
            text, paused = result
            live = parse_history(text) if rc == 0 else []
            self.service_available = rc == 0
            self.storage_error = self.storage_detail = ""
            try:
                self.records = self.state.merge(live, self.remember.get_active())
            except OSError as exc:
                self.records = self.state.snapshot(live, self.remember.get_active())
                self.storage_error = "History not saved"
                self.storage_detail = str(exc)
            if self.is_active():
                try:
                    self.state.mark_read(live)
                except OSError as exc:
                    if not self.storage_error:
                        self.storage_error = "Read status not saved"
                    self.storage_detail += ("\n" if self.storage_detail else "") + str(exc)
            self.pause_known = isinstance(paused, bool)
            if self.pause_known:
                self.pause.handler_block(self.pause_handler)
                self.pause.set_active(paused)
                self.pause.handler_unblock(self.pause_handler)
            self.pause.set_tooltip_text(None if self.pause_known else "Do Not Disturb status unavailable. Refresh to retry.")
            count = len(self.records)
            summary = (f"{count} {'message' if count == 1 else 'messages'}" if rc == 0 else
                       "Saved history · service unavailable" if self.records else "Service unavailable")
            error = self.action_error or self.storage_error
            self.status.set_text(error + " · " + summary if error else summary)
            self.status.set_tooltip_text("\n\n".join(value for value in
                (summary, self.action_detail, self.storage_detail) if value))
            context = self.status.get_style_context()
            context.remove_class("status-bad")
            if error or rc != 0:
                context.add_class("status-bad")
            preserve_focus = focus_before if self.get_focus() is focus_loading else None
            self.render_records(preserve_focus)
            self.update_actions()
            if preserve_focus and self.get_focus() is focus_loading and preserve_focus.get_mapped():
                preserve_focus.grab_focus()

        run_async_task(task, done)

    def update_actions(self):
        ready = not (self.refreshing or self.action_pending)
        self.refresh_button.set_sensitive(ready)
        self.pause.set_sensitive(ready and self.service_available and self.pause_known)
        self.clear_button.set_sensitive(ready and bool(self.records))
        for control, record in self.remove_buttons:
            control.set_sensitive(ready and (record.get("archived") or self.service_available))

    def render_records(self, preserve_focus=None):
        signature = tuple((record_key(item), item.get("archived", False)) for item in self.records)
        signature = (signature, self.service_available if not self.records else None)
        if signature == self.render_signature:
            for control, record in self.age_labels:
                control.set_text("Earlier session" if record.get("archived") else notification_age(record["timestamp"]))
            return
        self.render_signature = signature
        self.render_version += 1
        if self.render_allocation_handler:
            self.list.disconnect(self.render_allocation_handler)
            self.render_allocation_handler = 0
        version = self.render_version
        previous_focus = preserve_focus or self.get_focus()
        focus_token = next((token for token, control in self.message_controls.items() if control is previous_focus), None)
        def reading_anchor(control):
            return control.get_label_widget() if isinstance(control, Gtk.Expander) else control
        old_anchor = reading_anchor(previous_focus) if focus_token else None
        anchor_offset = old_anchor.translate_coordinates(self.scroll, 0, 0) if old_anchor else None
        previous_scroll = self.scroll.get_vadjustment().get_value()
        self.remove_buttons = []
        self.age_labels = []
        self.message_controls = {}
        for child in self.list.get_children():
            child.destroy()
        if not self.records:
            empty = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            empty.set_border_width(24)
            empty.pack_start(label("No notifications yet" if self.service_available else "Notification service unavailable", "card-title"), False, False, 0)
            empty.pack_start(label(
                "Desktop messages appear here. Opening this center collects visible popups into history."
                if self.service_available else "Refresh to retry when the desktop notification service returns.", "muted"), False, False, 0)
            self.list.add(empty)
        groups = {}
        for record in self.records:
            groups.setdefault(record["app"], []).append(record)
        for app, records in groups.items():
            heading = label(f"{app}  ·  {len(records)}", "card-title", wrap=False)
            heading.set_ellipsize(Pango.EllipsizeMode.END)
            heading.set_max_width_chars(40)
            heading.set_tooltip_text(app)
            heading.set_margin_top(8)
            heading.set_margin_bottom(6)
            self.list.add(heading)
            for record in records:
                self.add_notification(record)
        self.expanded_messages.intersection_update(record_key(item) for item in self.records)
        def restore():
            if self.closed or self.render_version != version:
                return False
            adjustment = self.scroll.get_vadjustment()
            adjustment.set_value(min(previous_scroll, max(0, adjustment.get_upper() - adjustment.get_page_size())))
            if focus_token and self.get_focus() is focus_after_render:
                control = self.message_controls.get(focus_token)
                if control is None or not control.get_mapped():
                    control = self.message_controls.get((focus_token[0], "remove"))
                if control is None:
                    control = self.remove_buttons[0][0] if self.remove_buttons else self.refresh_button
                anchor = reading_anchor(control)
                position = anchor.translate_coordinates(self.scroll, 0, 0)
                if anchor_offset is not None and position is not None:
                    adjustment.set_value(adjustment.get_value() + position[1] - anchor_offset[1])
                control.grab_focus()
            return False

        def allocated(_list, _allocation):
            # New rows must have real allocations before translating reading
            # coordinates; an immediate idle can otherwise see (-1, -1).
            if self.render_allocation_handler:
                self.list.disconnect(self.render_allocation_handler)
                self.render_allocation_handler = 0
            GLib.idle_add(restore)
        self.render_allocation_handler = self.list.connect_after("size-allocate", allocated)
        self.list.show_all()
        focus_after_render = self.get_focus()

    def add_notification(self, record):
        widget = card(record["summary"])
        widget.set_margin_top(6)
        widget.set_margin_bottom(6)
        heading = widget.get_children()[0].get_children()[0]
        heading.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        heading.set_max_width_chars(64)
        heading.set_lines(2)
        heading.set_ellipsize(Pango.EllipsizeMode.END)
        heading.set_tooltip_text(record["summary"])
        info = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        app = label(record["app"], "muted", wrap=False)
        app.set_ellipsize(Pango.EllipsizeMode.END)
        app.set_max_width_chars(40)
        app.set_tooltip_text(record["app"])
        info.pack_start(app, True, True, 0)
        age = "Earlier session" if record.get("archived") else notification_age(record["timestamp"])
        age_label = label(age, "muted", wrap=False)
        self.age_labels.append((age_label, record))
        remove = button("Remove", "edit-delete-symbolic", lambda *_: self.remove_record(record))
        self.remove_buttons.append((remove, record))
        self.message_controls[(record_key(record), "remove")] = remove
        info.pack_end(remove, False, False, 0)
        info.pack_end(age_label, False, False, 0)
        widget.pack_start(info, False, False, 0)
        if record["body"]:
            long_body = len(record["body"]) > 240 or record["body"].count("\n") >= 2
            preview = " ".join(record["body"].splitlines())[:240].rstrip() + "…" if long_body else record["body"]
            body = label(preview)
            body.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
            body.set_max_width_chars(64)
            body.set_lines(2)
            body.set_ellipsize(Pango.EllipsizeMode.END)
            body.set_selectable(True)
            self.message_controls[(record_key(record), "body")] = body
            widget.pack_start(body, False, False, 0)
            if long_body:
                key = record_key(record)
                expander = Gtk.Expander(label="Show full message")
                expander.get_accessible().set_name("Full message: " + record["summary"])
                full_text = label(record["body"])
                full_text.set_selectable(True)
                self.message_controls[(key, "details")] = expander
                self.message_controls[(key, "full-body")] = full_text
                expander.add(full_text)
                body.set_no_show_all(True)
                def expanded(control, _property, preview=body, identity=key):
                    active = control.get_expanded()
                    preview.set_visible(not active)
                    if active:
                        self.expanded_messages.add(identity)
                    else:
                        self.expanded_messages.discard(identity)
                expander.connect("notify::expanded", expanded)
                expander.set_expanded(key in self.expanded_messages)
                body.set_visible(not expander.get_expanded())
                widget.pack_start(expander, False, False, 0)
        self.list.add(widget)

    def remember_changed(self, widget):
        self.action_error = self.action_detail = ""
        try:
            save_preferences(remember_notifications=widget.get_active())
        except OSError as exc:
            # Reflect the stored preference even if an atomic save failed
            # after replacing its target, rather than assuming old/new state.
            widget.handler_block_by_func(self.remember_changed)
            widget.set_active(load_preferences()["remember_notifications"])
            widget.handler_unblock_by_func(self.remember_changed)
            self.action_error = "Could not save preference"
            self.action_detail = str(exc)
            self.status.set_text(self.action_error)
            self.status.set_tooltip_text(self.action_detail)
            self.status.get_style_context().add_class("status-bad")
            return
        if not widget.get_active():
            try:
                self.state.clear_saved()
            except OSError as exc:
                self.action_error = "Saved history could not be removed"
                self.action_detail = str(exc)
                self.status.set_text(self.action_error)
                self.status.set_tooltip_text(self.action_detail)
                self.status.get_style_context().add_class("status-bad")
        self.refresh()

    def remove_record(self, record):
        if self.closed or self.action_pending or self.refreshing:
            return
        if record.get("archived"):
            try:
                self.state.forget(record)
            except OSError as exc:
                self.show_action_error("Could not remove saved message", str(exc))
                return
            self.action_error = self.action_detail = ""
            self.refresh()
        else:
            self.perform(["history-rm", str(record["id"])], record)

    def pause_changed(self, widget):
        self.perform(["set-paused", "true" if widget.get_active() else "false"])

    def show_action_error(self, message, detail):
        self.action_error, self.action_detail = message, detail
        self.status.set_text(message)
        self.status.set_tooltip_text(detail or message)
        self.status.get_style_context().add_class("status-bad")

    def perform(self, arguments, removed_record=None):
        if self.closed or self.action_pending or self.refreshing:
            return
        if arguments[0] == "history-clear" and not self.service_available:
            try:
                self.state.clear_saved()
            except OSError as exc:
                self.show_action_error("Could not clear saved history", str(exc))
                return
            self.action_error = self.action_detail = ""
            self.refresh()
            return
        self.action_pending = True
        self.action_error = self.action_detail = ""
        self.update_actions()

        def done(rc, output):
            if not self.closed:
                self.action_pending = False
                if rc == 0 and removed_record:
                    try:
                        self.state.forget(removed_record)
                    except OSError as exc:
                        self.show_action_error("Could not remove saved message", str(exc))
                if rc == 0 and arguments[0] == "history-clear":
                    try:
                        self.state.clear_saved()
                    except OSError as exc:
                        self.show_action_error("Could not clear saved history", str(exc))
                if rc != 0:
                    self.action_error = "Action failed"
                    self.action_detail = output or "Notification action failed. Refresh, then retry."
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
