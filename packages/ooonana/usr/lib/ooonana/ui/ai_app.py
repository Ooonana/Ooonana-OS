#!/usr/bin/env python3
import os
import sys
import json
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import (  # noqa: E402
    Gtk,
    Pango,
    apply_theme,
    button,
    card,
    command_exists,
    flow_row,
    header,
    icon,
    label,
    launch,
    run,
    run_async,
    run_async_task,
    ask_text,
    Gdk,
    GLib,
)
from chat_store import ChatStore  # noqa: E402
from chat_widgets import ChatRequest, apply_ai_theme, message_widget, sidebar_button  # noqa: E402
from ui_preferences import transition_ms  # noqa: E402
from memory_status import available_ram, memory_caption
from storage_health import storage_health


def status_field(output, field, default=""):
    prefix = field + ":"
    return next((line.split(":", 1)[1].strip() for line in output.splitlines() if line.startswith(prefix)), default)


def offline_stage_labels(package, runtime, model_count, api_running):
    return (
        ("1 · App", "Installed" if package else "Install package"),
        ("2 · Runtime", "Available" if runtime else "Setup required"),
        ("3 · Model files", f"{model_count} downloaded" if model_count else "Download required"),
        ("4 · Local API", "Running" if api_running else "Stopped / unverified"),
    )


class AiWindow(Gtk.Window):
    ACTIONS = [
        ("New chat", "document-new-symbolic", "new"),
        ("Offline Intel", "computer-symbolic", "offline"),
        ("Status", "emblem-system-symbolic", "status"),
        ("Tools", "applications-engineering-symbolic", "tools"),
        ("Tasks", "view-list-symbolic", "tasks"),
        ("Sessions", "document-open-recent-symbolic", "sessions"),
        ("Desktop", "video-display-symbolic", "desktop"),
        ("Permissions", "security-high-symbolic", "permissions"),
        ("Logs", "text-x-log-symbolic", "logs"),
        ("Setup", "preferences-system-symbolic", "setup"),
    ]

    def __init__(self):
        super().__init__(title="Ooonana AI")
        self.set_default_size(1080, 680)
        self.set_size_request(740, 500)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.transcript_path = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "ooonana/ai-chat-gui.txt"
        self.store = ChatStore(self.transcript_path.with_name("ai-chats.json"))
        self.current = self.store.threads[0] if self.store.threads else self.store.new()
        self.request = None
        self.phase_timer = 0
        self.phase_started = None
        self.phase_title = ""
        self.user_tag, self.ai_tag, self.meta_tag = "user", "assistant", "system"
        self.headerbar = header(self, "Ooonana AI", "", None)
        self.sidebar_toggle = Gtk.ToggleButton()
        self.sidebar_toggle.set_image(icon("view-sidebar-symbolic"))
        self.sidebar_toggle.set_tooltip_text("Show chats and tools")
        self.sidebar_toggle.get_accessible().set_name("Show chats and tools")
        self.sidebar_toggle.get_style_context().add_class("window-control")
        self.sidebar_toggle.set_valign(Gtk.Align.CENTER)
        self.sidebar_toggle.set_no_show_all(True)
        self.headerbar.pack_end(self.sidebar_toggle)
        apply_ai_theme(self)
        root = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.add(root)
        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.sidebar_box = sidebar
        sidebar.set_border_width(16)
        sidebar.set_size_request(228, -1)
        sidebar.get_style_context().add_class("ai-sidebar")
        self.new_button = sidebar_button("New chat", "list-add-symbolic", lambda *_: self.new_chat(), primary=True)
        sidebar.pack_start(self.new_button, False, False, 0)
        self.search = Gtk.SearchEntry()
        self.search.set_placeholder_text("Search chats")
        self.search.connect("search-changed", lambda *_: self.refresh_chats())
        sidebar.pack_start(self.search, False, False, 0)
        sidebar.pack_start(label("Recent", "muted", wrap=False), False, False, 6)
        self.chat_list = Gtk.ListBox()
        self.chat_list.connect("row-selected", self.select_chat)
        chats_scroll = Gtk.ScrolledWindow()
        chats_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        chats_scroll.add(self.chat_list)
        sidebar.pack_start(chats_scroll, True, True, 0)
        sidebar.pack_start(Gtk.Separator(), False, False, 0)
        sidebar.pack_start(sidebar_button("Offline setup", "folder-download-symbolic", lambda *_: self.offline_dialog()), False, False, 0)
        sidebar.pack_start(sidebar_button("Tools", "applications-engineering-symbolic", self.tools_menu), False, False, 0)
        sidebar.pack_start(sidebar_button("Settings", "preferences-system-symbolic", lambda *_: self.sidebar_action("setup")), False, False, 0)
        self.sidebar_revealer = Gtk.Revealer()
        self.sidebar_revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_RIGHT)
        self.sidebar_revealer.set_transition_duration(transition_ms())
        self.sidebar_revealer.add(sidebar)
        self.sidebar_revealer.set_reveal_child(True)
        root.pack_start(self.sidebar_revealer, False, False, 0)
        self.sidebar_toggle.connect("toggled", lambda widget: self.sidebar_revealer.set_reveal_child(widget.get_active()))
        main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        self.main_box = main
        main.set_border_width(22)
        root.pack_start(main, True, True, 0)
        provider_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        provider_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.provider_combo = Gtk.ComboBoxText()
        self.provider_combo.append("nim", "NVIDIA NIM")
        self.provider_combo.append("gemini", "Google Gemini")
        self.provider_combo.append("openvino", "Offline Intel")
        self.provider_combo.set_active_id("nim")
        self.provider_combo.connect("changed", self.change_provider)
        provider_box.pack_start(self.provider_combo, False, False, 0)
        self.provider_label = label("Checking provider", "muted", wrap=False)
        self.provider_label.set_no_show_all(True)
        self.model_label = label("Choose model", "muted", wrap=False)
        self.model_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.model_label.set_max_width_chars(34)
        model_button = Gtk.Button()
        model_button.add(self.model_label)
        model_button.set_relief(Gtk.ReliefStyle.NONE)
        model_button.get_style_context().add_class("ai-utility")
        model_button.get_style_context().add_class("ai-model")
        model_button.set_tooltip_text("Choose model. Offline model loading happens in Offline setup.")
        model_button.connect("clicked", self.choose_model)
        provider_box.pack_start(model_button, False, False, 0)
        provider_row.pack_start(provider_box, False, False, 0)
        self.activity = Gtk.Spinner()
        provider_row.pack_end(self.activity, False, False, 0)
        indicators = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        self.phase_label = label("Ready", "muted", wrap=False)
        self.phase_label.set_max_width_chars(24)
        self.phase_label.set_ellipsize(Pango.EllipsizeMode.END)
        indicators.pack_start(self.phase_label, False, False, 0)
        self.memory_label = label("RAM unavailable", "muted", wrap=False)
        self.memory_label.set_max_width_chars(24)
        self.memory_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.memory_label.set_tooltip_text("Available RAM includes cgroup limits. Swap is excluded. Availability is not a model-load guarantee.")
        self.memory_label.set_no_show_all(True)
        indicators.pack_start(self.memory_label, False, False, 0)
        self.storage_label = label("", "muted", wrap=False)
        self.storage_label.set_max_width_chars(28)
        self.storage_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.storage_label.set_no_show_all(True)
        indicators.pack_start(self.storage_label, False, False, 0)
        provider_row.pack_end(indicators, False, False, 0)
        remove = button("", "user-trash-symbolic", self.delete_chat)
        remove.set_valign(Gtk.Align.CENTER)
        remove.set_tooltip_text("Delete current chat")
        remove.get_accessible().set_name("Delete current chat")
        provider_row.pack_end(remove, False, False, 0)
        main.pack_start(provider_row, False, False, 0)
        self.messages = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        self.messages.set_valign(Gtk.Align.START)
        self.messages.set_margin_top(8)
        self.messages.set_margin_bottom(18)
        self.message_scroll = Gtk.ScrolledWindow()
        self.message_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.message_scroll.add(self.messages)
        main.pack_start(self.message_scroll, True, True, 0)
        composer_card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        composer_card.get_style_context().add_class("ai-composer")
        attachment = button("", "mail-attachment-symbolic", self.attach_text)
        attachment.set_tooltip_text("Attach text file into editable message; sends only when you press Send")
        attachment.get_accessible().set_name("Attach text file")
        attachment.set_valign(Gtk.Align.CENTER)
        composer_card.pack_start(attachment, False, False, 0)
        self.composer = Gtk.TextView()
        self.composer.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.composer.set_left_margin(10)
        self.composer.set_right_margin(10)
        self.composer.set_top_margin(14)
        self.composer.set_bottom_margin(14)
        self.composer.get_accessible().set_name("Message Ooonana")
        self.composer.connect("key-press-event", self.composer_key)
        composer_scroll = Gtk.ScrolledWindow()
        self.composer_scroll = composer_scroll
        composer_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        composer_scroll.set_size_request(-1, 76)
        composer_scroll.add(self.composer)
        composer_overlay = Gtk.Overlay()
        composer_overlay.add(composer_scroll)
        self.composer_placeholder = label("Message Ooonana", "muted", wrap=False)
        self.composer_placeholder.set_halign(Gtk.Align.START)
        self.composer_placeholder.set_valign(Gtk.Align.START)
        self.composer_placeholder.set_margin_left(10)
        self.composer_placeholder.set_margin_top(14)
        composer_overlay.add_overlay(self.composer_placeholder)
        composer_overlay.set_overlay_pass_through(self.composer_placeholder, True)
        self.composer.get_buffer().connect("changed", lambda buffer: self.composer_placeholder.set_visible(buffer.get_char_count() == 0))
        composer_card.pack_start(composer_overlay, True, True, 0)
        self.send_button = button("", "media-playback-start-symbolic", self.send_prompt, "suggested-action")
        self.send_button.set_tooltip_text("Send message")
        self.send_button.get_accessible().set_name("Send message")
        self.send_button.set_valign(Gtk.Align.CENTER)
        composer_card.pack_end(self.send_button, False, False, 0)
        main.pack_start(composer_card, False, False, 0)
        hint = label("Enter to send • Shift+Enter for newline", "muted", wrap=False)
        hint.get_style_context().add_class("ai-hint")
        main.pack_start(hint, False, False, 0)
        self.connect("destroy", self.closed)
        self.wide = None
        self.layout_mode = None
        self.connect("size-allocate", self.resized)
        self.resized(self, self.get_default_size())
        self.load_transcript()
        self.refresh_model()
        self.set_focus(self.composer)

    def append(self, heading, body, tag):
        self.store.append(self.current, tag, body.strip(), heading)
        self.render_messages(animated=True)
        self.refresh_chats()

    def load_transcript(self):
        if self.store.load_error:
            self.current["messages"].append(dict(role="system", content="Saved history unreadable. Original file preserved; new conversation stays unsaved until history is repaired.", heading="History"))
        if not self.current["messages"] and self.transcript_path.exists():
            text = self.transcript_path.read_text(encoding="utf-8", errors="replace")
            self.store.append(self.current, "system", text[-32000:], "Legacy transcript")
        self.refresh_chats()
        self.render_messages()

    def save_transcript(self):
        self.store.save()

    def render_messages(self, animated=False):
        for child in self.messages.get_children():
            self.messages.remove(child)
        if not self.current["messages"]:
            empty = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            empty.set_margin_top(110)
            empty.pack_start(label("Message Ooonana", "page-title", wrap=False), False, False, 0)
            empty.pack_start(label("Choose provider and model, then start chatting.", "muted"), False, False, 0)
            self.messages.pack_start(empty, False, False, 0)
        for index, item in enumerate(self.current["messages"]):
            widget = message_widget(item)
            if animated and index == len(self.current["messages"]) - 1:
                reveal = Gtk.Revealer()
                reveal.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
                reveal.set_transition_duration(transition_ms())
                reveal.add(widget)
                widget = reveal
                GLib.idle_add(lambda child=reveal: (child.set_reveal_child(True), False)[1])
            self.messages.pack_start(widget, False, False, 0)
        self.messages.show_all()
        GLib.idle_add(self.scroll_bottom)
        if animated:
            GLib.timeout_add(transition_ms() + 20, self.scroll_bottom)

    def scroll_bottom(self):
        adjustment = self.message_scroll.get_vadjustment()
        adjustment.set_value(max(0, adjustment.get_upper() - adjustment.get_page_size()))
        return False

    def refresh_chats(self):
        self.chat_list.handler_block_by_func(self.select_chat)
        for child in self.chat_list.get_children():
            self.chat_list.remove(child)
        search = self.search.get_text().casefold()
        for thread in sorted(self.store.threads, key=lambda item: item["updated"], reverse=True):
            if search and search not in thread["title"].casefold():
                continue
            row = Gtk.ListBoxRow()
            row.thread = thread
            title = label(thread["title"], wrap=False)
            title.set_max_width_chars(20)
            title.set_ellipsize(Pango.EllipsizeMode.END)
            row.add(title)
            row.set_tooltip_text(thread["title"])
            self.chat_list.add(row)
            if thread is self.current:
                self.chat_list.select_row(row)
        self.chat_list.show_all()
        self.chat_list.handler_unblock_by_func(self.select_chat)

    def select_chat(self, _list, row):
        if row:
            self.current = row.thread
            self.render_messages()

    def new_chat(self):
        self.current = self.store.new()
        self.refresh_chats()
        self.render_messages()
        self.composer.grab_focus()

    def delete_chat(self, *_args):
        if self.request:
            return
        dialog = Gtk.MessageDialog(transient_for=self, modal=True, message_type=Gtk.MessageType.QUESTION, buttons=Gtk.ButtonsType.OK_CANCEL, text="Delete current chat?")
        accepted = dialog.run() == Gtk.ResponseType.OK
        dialog.destroy()
        if accepted:
            self.store.threads.remove(self.current)
            self.current = self.store.threads[0] if self.store.threads else self.store.new()
            self.store.save()
            self.refresh_chats()
            self.render_messages()

    def composer_key(self, _widget, event):
        if event.keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter) and not event.state & (Gdk.ModifierType.SHIFT_MASK | Gdk.ModifierType.CONTROL_MASK):
            if not self.request:
                self.send_prompt()
            return True
        return False

    def closed(self, *_args):
        if self.phase_timer:
            GLib.source_remove(self.phase_timer)
            self.phase_timer = 0
        if self.request:
            self.request.cancel()
        if Gtk.main_level():
            Gtk.main_quit()

    def update_memory(self):
        memory = available_ram()
        self.memory_label.set_text(memory_caption(memory))
        style = self.memory_label.get_style_context()
        (style.add_class if memory and memory["low"] else style.remove_class)("status-warn")
        self.memory_label.set_visible(self.provider_combo.get_active_id() == "openvino")
        health = storage_health()
        caption = "Storage read-only · save work" if health.get("readonly") else (
            f"USB {'critical' if health['level'] == 'critical' else 'low space'} · {health['free'] / 1024**3:.1f} GiB"
            if "free" in health and health["level"] in ("low", "critical") else health["caption"])
        self.storage_label.set_text(caption)
        self.storage_label.set_tooltip_text(health["caption"] + ". Offline runtime/models need saved storage; no automatic cleanup.")
        self.storage_label.set_visible(health["level"] in ("low", "critical"))
        style = self.storage_label.get_style_context()
        style.remove_class("status-warn")
        style.remove_class("status-bad")
        style.add_class("status-bad" if health["level"] == "critical" else "status-warn")

    def set_phase(self, title=None):
        if self.phase_timer:
            GLib.source_remove(self.phase_timer)
            self.phase_timer = 0
        self.phase_title = title or ""
        self.phase_started = time.monotonic() if title else None
        self.phase_label.set_text(title or "Ready")
        self.phase_label.set_tooltip_text("Elapsed request time, not estimated progress. Stop cancels only this request.")
        self.update_memory()
        if title:
            self.activity.start()
            self.phase_timer = GLib.timeout_add_seconds(1, self.phase_tick)
        else:
            self.activity.stop()

    def phase_tick(self):
        if self.phase_started is None:
            return False
        elapsed = int(time.monotonic() - self.phase_started)
        self.phase_label.set_text(f"{self.phase_title} · {elapsed}s")
        if elapsed % 5 == 0:
            self.update_memory()
        return True

    def resized(self, _widget, allocation):
        wide = allocation.width >= 1300
        compact = allocation.width < 760
        mode = "wide" if wide else "compact" if compact else "normal"
        if mode == self.layout_mode:
            return
        self.layout_mode = mode
        self.wide = wide
        self.sidebar_toggle.set_visible(compact)
        self.sidebar_toggle.set_active(not compact)
        self.sidebar_revealer.set_reveal_child(not compact)
        style = self.get_style_context()
        (style.add_class if wide else style.remove_class)("ai-wide")
        self.sidebar_box.set_size_request(336 if wide else 228, -1)
        self.sidebar_box.set_border_width(22 if wide else 16)
        self.main_box.set_border_width(0)
        self.main_box.set_margin_left(32 if wide else 22)
        self.main_box.set_margin_right(32 if wide else 22)
        self.main_box.set_margin_top(16)
        self.main_box.set_margin_bottom(22)
        self.composer_scroll.set_size_request(-1, 90 if wide else 76)

    def tools_menu(self, widget):
        menu = Gtk.Menu()
        for title, _icon, action in self.ACTIONS:
            if action in {"new", "offline", "setup"}:
                continue
            item = Gtk.MenuItem(label=title)
            item.connect("activate", lambda _item, value=action: self.sidebar_action(value))
            menu.append(item)
        menu.show_all()
        menu.popup_at_widget(widget, Gdk.Gravity.NORTH_EAST, Gdk.Gravity.SOUTH_EAST, None)

    def choose_model(self, *_args):
        model = ask_text(self, "Choose model", "Model ID or saved alias. For local model loading, use Offline setup.")
        if model:
            self.run_action("Model", ["model", "set", model])

    def attach_text(self, *_args):
        chooser = Gtk.FileChooserDialog(title="Attach text file", transient_for=self, action=Gtk.FileChooserAction.OPEN)
        chooser.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Insert text", Gtk.ResponseType.OK)
        if chooser.run() == Gtk.ResponseType.OK:
            path = Path(chooser.get_filename())
            try:
                if path.stat().st_size > 32000:
                    raise ValueError("Text attachment limited to 32 KB.")
                content = path.read_text(encoding="utf-8")
                if "\0" in content:
                    raise ValueError("Text files only.")
                buffer = self.composer.get_buffer()
                buffer.insert_at_cursor(f"\nFile: {path.name}\n```text\n{content}\n```\n")
            except (OSError, UnicodeError, ValueError) as error:
                self.append("Attachment", str(error), self.meta_tag)
        chooser.destroy()

    def refresh_model(self):
        self.provider_label.set_text("provider: checking...")
        self.model_label.set_text("model: checking...")

        def task():
            _provider_rc, provider = run(["ooonana-ai", "provider"], timeout=5)
            _model_rc, model = run(["ooonana-ai", "model"], timeout=5)
            return 0, (provider, model)

        def done(_rc, values):
            provider, model = values
            active = status_field(provider, "active", "nim")
            provider_name = status_field(provider, "label", active.upper())
            model_name = status_field(model, "active", "Default model")
            suffix = " · setup needed" if status_field(provider, "key") == "missing" else ""
            self.provider_label.set_text(provider_name + suffix)
            self.model_label.set_text(model_name.rsplit("/", 1)[-1])
            self.model_label.set_tooltip_text(model_name)
            self.provider_combo.handler_block_by_func(self.change_provider)
            self.provider_combo.set_active_id(active)
            self.provider_combo.handler_unblock_by_func(self.change_provider)
            self.update_memory()

        run_async_task(task, done)

    def change_provider(self, combo):
        provider = combo.get_active_id()
        if not provider:
            return

        def done(rc, output):
            self.append(
                "Provider",
                output or (f"Using {provider}." if rc == 0 else "Provider change failed."),
                self.ai_tag if rc == 0 else self.meta_tag,
            )
            self.refresh_model()
            if rc == 0 and provider == "openvino":
                self.offline_dialog()

        run_async(["ooonana-ai", "provider", "set", provider], done, timeout=15)

    def clear_composer(self, *_args):
        self.composer.get_buffer().set_text("")

    def send_prompt(self, *_args):
        if self.request:
            self.request.cancel()
            return
        buffer = self.composer.get_buffer()
        prompt = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True).strip()
        if not prompt:
            return
        if len(prompt.encode("utf-8")) > 32000:
            self.append("Message", "Message limited to 32 KB. Shorten attachment or split request.", self.meta_tag)
            return
        context = json.dumps(ChatStore.context(self.current), ensure_ascii=False)
        thread = self.current
        buffer.set_text("")
        self.append("You", prompt, self.user_tag)
        self.send_button.set_image(icon("media-playback-stop-symbolic"))
        self.send_button.set_tooltip_text("Stop request; shared API stays running")
        self.send_button.get_accessible().set_name("Stop request")
        self.set_phase("Waiting for backend")

        def done(rc, output):
            self.request = None
            if not self.get_visible():
                return False
            self.send_button.set_image(icon("media-playback-start-symbolic"))
            self.send_button.set_tooltip_text("Send message")
            self.send_button.get_accessible().set_name("Send message")
            self.set_phase()
            text = output.strip() or ("No response returned." if rc == 0 else f"Request failed ({rc}). Open Settings to check provider.")
            self.store.append(thread, "assistant" if rc == 0 else "system", text, "Ooonana" if rc == 0 else "Request")
            if self.current is thread:
                self.render_messages(animated=True)
            self.refresh_chats()
            return False

        self.request = ChatRequest(["ooonana-ai", "ask", "--no-agent", "--no-env", "--no-history", "--no-stream", "--context-stdin", "--", prompt], context, done)

    def run_action(self, title, args):
        self.set_phase(title)

        def done(rc, output):
            self.set_phase()
            self.append(
                title,
                output or ("Done." if rc == 0 else f"Failed with exit status {rc}"),
                self.ai_tag if rc == 0 else self.meta_tag,
            )
            self.refresh_model()

        run_async(["ooonana-ai", *args], done, timeout=120)

    def offline_status(self):
        if not Path("/usr/bin/openvino").exists():
            return "Package: missing\n\nInstall openvino-chat from Ooonana repo."
        doctor_rc, doctor = run(["openvino", "doctor"], timeout=30)
        api_rc, api = run(["openvino", "api", "status"], timeout=20)
        return (
            "OpenVINO local AI\n\n"
            + (doctor or f"Doctor exit: {doctor_rc}")
            + "\n\n"
            + (api or f"API status exit: {api_rc}")
            + "\n\nModels download once. Inference then works offline."
        )

    def offline_terminal(self, title, command):
        launch(
            [
                "ooonana-theme-env",
                "xterm",
                "-title",
                title,
                "-e",
                "sh",
                "-lc",
                command + "; printf '\nPress Enter to close.'; read answer",
            ]
        )

    def start_offline_api(self, device):
        model_name = "qwen3.5-9b-int4-ov"
        model = f"/root/.openvino/models/{model_name}"
        self.set_phase("Loading model")

        def started(rc, output):
            if rc != 0:
                self.set_phase()
                self.append("Offline Intel", output or "OpenVINO API failed.", self.meta_tag)
                return

            def selected(select_rc, select_output):
                self.set_phase()
                self.append(
                    "Offline Intel",
                    (output + "\n" + select_output).strip(),
                    self.ai_tag if select_rc == 0 else self.meta_tag,
                )
                self.refresh_model()

            def select_provider():
                rc, text = run(["ooonana-ai", "provider", "set", "openvino"], timeout=15)
                if rc != 0:
                    return rc, text
                return run(["ooonana-ai", "model", "set", model_name], timeout=15)

            run_async_task(select_provider, selected)

        run_async(
            ["openvino", "--model-dir", model, "api", "start", "--device", device],
            started,
            timeout=180,
        )

    def offline_dialog(self):
        dialog = Gtk.Dialog(title="Offline Intel AI", transient_for=self, flags=0)
        dialog.set_default_size(720, 540)
        header(dialog, "Offline AI setup", "App, runtime, model files, then local API", "system-search-symbolic")
        dialog.add_button("Close", Gtk.ResponseType.CLOSE)
        content = dialog.get_content_area()
        content.set_spacing(14)
        content.set_border_width(18)
        stages = Gtk.Grid(column_spacing=12, row_spacing=12)
        stages.set_column_homogeneous(True)
        stage_values = []
        for index, (title, _value) in enumerate(offline_stage_labels(False, False, 0, False)):
            widget = card(title)
            value = label("Checking...", "muted")
            stage_values.append(value)
            widget.pack_start(value, False, False, 0)
            stages.attach(widget, index % 2, index // 2, 1, 1)
        content.pack_start(stages, False, False, 0)
        content.pack_start(label("App package does not include runtime or model weights. A running API is not proof that model loading succeeded. Check available RAM before downloading.", "muted"), False, False, 0)
        content.pack_start(label(memory_caption(available_ram()) + " · swap excluded; load estimate checked by backend.", "muted"), False, False, 0)
        content.pack_start(flow_row([
            button(name, callback=lambda _widget, response=response: dialog.response(response))
            for name, response in (("Install package", 1), ("Setup runtime", 2), ("Download Qwen model", 3), ("Start GPU", 4), ("Stop API", 5), ("Refresh runtime", 6))
        ], 3), False, False, 0)
        view = Gtk.TextView()
        view.set_editable(False)
        view.set_cursor_visible(False)
        view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        view.set_left_margin(16)
        view.set_right_margin(16)
        view.set_top_margin(16)
        status_buffer = view.get_buffer()
        status_buffer.set_text("Checking OpenVINO runtime...")
        scroll = Gtk.ScrolledWindow()
        scroll.add(view)
        scroll.set_min_content_height(110)
        details = Gtk.Expander.new("Diagnostics")
        details.add(scroll)
        content.pack_start(details, True, True, 0)
        dialog.show_all()

        def status_task():
            diagnostics = self.offline_status()
            data_home = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share")))
            runtime_root = Path(os.environ.get("OOONANA_OPENVINO_STATE_DIR", str(data_home / "ooonana-openvino"))) / "rootfs"
            model_root = Path(os.environ.get("OPENVINO_MODEL_ROOT", str(Path(os.environ.get("OOONANA_OPENVINO_HOME", str(Path.home() / ".openvino"))) / "models")))
            models = len({file.parent for pattern in ("*/*.xml", "*/*/*.xml") for file in model_root.glob(pattern)})
            api = diagnostics.lower()
            running = "running" in api and "not running" not in api and "stopped" not in api
            ready = (runtime_root / ".ooonana-openvino-ready").is_file() and (runtime_root / "opt/openvino-venv/bin/python").exists()
            ready = ready and "runtime outdated" not in api and "runtime missing" not in api
            values = offline_stage_labels(command_exists("openvino"), ready, models, running)
            return 0, (diagnostics, values)

        def status_done(_rc, output):
            if not dialog.get_visible():
                return
            if _rc != 0 or not isinstance(output, tuple) or len(output) != 2:
                status_buffer.set_text(str(output))
                for widget in stage_values:
                    widget.set_text("Check unavailable")
                return
            diagnostics, values = output
            status_buffer.set_text(diagnostics)
            for widget, (_title, text) in zip(stage_values, values):
                widget.set_text(text)

        run_async_task(status_task, status_done)
        response = dialog.run()
        dialog.destroy()
        if response == 1:
            self.offline_terminal(
                "Install Ooonana Offline AI",
                "ooonana get openvino-chat && openvino setup",
            )
        elif response == 2:
            self.offline_terminal("Setup OpenVINO runtime", "openvino setup")
        elif response == 3:
            self.offline_terminal("Download Qwen OpenVINO model", "openvino download qwen3.5")
        elif response == 4:
            self.start_offline_api("GPU")
        elif response == 5:
            run_async(["openvino", "api", "stop"], lambda _rc, _output: None, timeout=30)
        elif response == 6:
            self.offline_terminal("Refresh OpenVINO runtime", "OOONANA_OPENVINO_REFRESH_DEPENDENCIES=1 openvino setup")

    def sidebar_action(self, action):
        if action == "new":
            self.new_chat()
        elif action == "offline":
            self.offline_dialog()
        elif action in ("status", "tools", "tasks", "sessions", "desktop"):
            self.run_action(action.title(), [action])
        elif action == "permissions":
            self.append(
                "Permissions",
                "Chat and read-only context are allowed. Shell and desktop actions require explicit commands. "
                "System changes run through Ooonana admin policy, never through root desktop session.",
                self.meta_tag,
            )
        elif action == "logs":
            log = Path.home() / ".local/state/ooonana/ai-app.log"
            text = log.read_text(encoding="utf-8", errors="replace")[-12000:] if log.exists() else "No AI log yet."
            self.append("Logs", text, self.meta_tag)
        elif action == "setup":
            launch(
                [
                    "ooonana-theme-env",
                    "xterm",
                    "-title",
                    "Ooonana AI Setup",
                    "-e",
                    "ooonana-ai",
                    "setup",
                ]
            )


def main():
    if "--dry-run" in sys.argv:
        print("native GTK Ooonana AI")
        print("layout: sidebar chat transcript composer provider model offline actions")
        print("actions: new offline status tools tasks sessions desktop permissions logs setup")
        print("offline: install runtime model GPU CPU local API")
        print("OOONANA_AI_NATIVE_OK")
        return 0
    apply_theme()
    window = AiWindow()
    window.show_all()
    Gtk.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
