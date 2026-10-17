"""Shared wireless UI lifecycle. Backend operations keep their own authority."""
from pathlib import Path

from common import GLib, Gtk, Pango, fit_dialog, header, label
from ui_preferences import transition_ms


class WirelessWindowState:
    def init_wireless_state(self):
        self.closed = False
        self.busy = False
        self.dialog_open = False
        self.progress_source = 0
        self.services_ready = False

    def can_act(self):
        return not (self.closed or self.busy or self.dialog_open)

    def show_detail(self, text):
        if self.closed:
            return
        self.detail.set_text(text)
        self.detail.set_tooltip_text(text)
        self.detail.get_accessible().set_description(text)

    def set_busy(self, busy, text=""):
        if self.closed:
            return
        self.busy = busy
        self.update_controls()
        if self.progress_source:
            GLib.source_remove(self.progress_source)
            self.progress_source = 0
        self.progress.hide()
        if busy:
            self.show_detail(text)
            # Indeterminate work, never a made-up completion percentage.
            if transition_ms():
                self.progress.show()
                self.progress.set_show_text(False)
                self.progress.pulse()
                self.progress_source = GLib.timeout_add(100, self.pulse_progress)
        else:
            self.on_selection_changed(self.tree.get_selection())

    def pulse_progress(self):
        if self.closed or not self.busy:
            self.progress_source = 0
            return False
        self.progress.pulse()
        return True

    def confirm_action(self, title, explanation, action):
        if not self.can_act():
            return False
        self.dialog_open = True
        dialog = Gtk.Dialog(title=title, transient_for=self, modal=True)
        dialog.set_destroy_with_parent(True)
        header(dialog, title, "", "dialog-warning-symbolic")
        fit_dialog(dialog, 560, 200)
        content = label(explanation)
        content.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        content.set_margin_start(16)
        content.set_margin_end(16)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_valign(Gtk.Align.START)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.add(content)
        dialog.get_content_area().pack_start(scroll, True, True, 0)
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button(action, Gtk.ResponseType.OK).get_style_context().add_class("destructive-action")
        dialog.set_default_response(Gtk.ResponseType.CANCEL)
        dialog.show_all()
        try:
            accepted = dialog.run() == Gtk.ResponseType.OK
        finally:
            dialog.destroy()
            self.dialog_open = False
        return accepted and not self.closed

    def on_destroy(self, *_args):
        self.closed = True
        if self.progress_source:
            GLib.source_remove(self.progress_source)
            self.progress_source = 0
        if Gtk.main_level():
            Gtk.main_quit()


class LocalFileButton(Gtk.Button):
    """Native local-file chooser inside a display-bounded, scrollable dialog."""
    def __init__(self, title):
        super().__init__()
        self.title = title
        self.filename = None
        self.dialog_open = False
        self.closed = False
        self.caption = Gtk.Label(label=title, xalign=0)
        self.caption.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        self.caption.set_max_width_chars(24)
        self.add(self.caption)
        self.set_hexpand(True)
        self.connect("clicked", self.choose)
        self.connect("destroy", self.on_destroy)

    def on_destroy(self, *_args):
        self.closed = True

    def get_filename(self):
        return self.filename

    def set_filename(self, filename):
        self.filename = str(filename) if filename else None
        self.caption.set_text(Path(self.filename).name if self.filename else self.title)
        self.set_tooltip_text(self.filename or self.title)
        return True

    def choose(self, *_args):
        if self.closed or self.dialog_open:
            return
        self.dialog_open = True
        dialog = Gtk.Dialog(title=self.title, transient_for=self.get_toplevel(), modal=True)
        dialog.set_destroy_with_parent(True)
        header(dialog, self.title, "", "document-open-symbolic")
        fit_dialog(dialog, 780, 420)
        dialog.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Open", Gtk.ResponseType.OK)
        dialog.set_default_response(Gtk.ResponseType.CANCEL)
        chooser = Gtk.FileChooserWidget(action=Gtk.FileChooserAction.OPEN)
        chooser.set_local_only(True)
        chooser.get_accessible().set_name(self.title)
        if self.filename:
            chooser.set_filename(self.filename)
        accept = dialog.get_widget_for_response(Gtk.ResponseType.OK)
        accept.set_sensitive(False)
        chooser.connect("selection-changed", lambda *_: accept.set_sensitive(bool(chooser.get_filename())))
        chooser.connect("file-activated", lambda *_: dialog.response(Gtk.ResponseType.OK))
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_overlay_scrolling(False)
        scroll.add(chooser)
        dialog.get_content_area().pack_start(scroll, True, True, 0)
        dialog.show_all()
        try:
            selected = chooser.get_filename() if dialog.run() == Gtk.ResponseType.OK else None
        finally:
            dialog.destroy()
            self.dialog_open = False
        if selected and not self.closed:
            self.set_filename(selected)
