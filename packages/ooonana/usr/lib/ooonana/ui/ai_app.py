#!/usr/bin/env python3
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    Gtk,
    apply_theme,
    button,
    header,
    icon,
    label,
    launch,
    run,
    run_async,
)
from gi.repository import GdkPixbuf  # noqa: E402


class AiWindow(Gtk.Window):
    ACTIONS = [
        ("New chat", "document-new-symbolic", "new"),
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
        self.set_default_size(1120, 720)
        self.set_size_request(860, 560)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.transcript_path = (
            Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
            / "ooonana/ai-chat-gui.txt"
        )
        self.transcript_path.parent.mkdir(parents=True, exist_ok=True)

        self.headerbar = header(
            self,
            "Ooonana AI",
            "Local desktop workbench",
            "system-search-symbolic",
        )
        self.provider_label = label("provider: checking", "muted")
        self.model_label = label("model: checking", "muted")
        header_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        header_box.pack_start(self.provider_label, False, False, 0)
        header_box.pack_start(self.model_label, False, False, 0)
        self.headerbar.pack_end(header_box)

        root = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.add(root)

        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        sidebar.set_border_width(10)
        sidebar.set_size_request(220, -1)
        sidebar.get_style_context().add_class("sidebar")
        brand = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        logo_path = "/usr/share/ooonana/logo.png"
        if Path(logo_path).exists():
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                logo_path, 52, 36, True
            )
            image = Gtk.Image.new_from_pixbuf(pixbuf)
        else:
            image = icon("system-search-symbolic", Gtk.IconSize.DIALOG)
        brand.pack_start(image, False, False, 0)
        brand.pack_start(label("Ooonana AI", "card-title"), True, True, 0)
        sidebar.pack_start(brand, False, False, 8)

        for title, icon_name, action in self.ACTIONS:
            sidebar.pack_start(
                button(
                    title,
                    icon_name,
                    lambda _widget, name=action: self.sidebar_action(name),
                ),
                False,
                False,
                0,
            )
        sidebar.pack_end(
            button("Terminal", "utilities-terminal-symbolic", lambda *_: launch(["ooonana-theme-env", "xterm"])),
            False,
            False,
            0,
        )
        root.pack_start(sidebar, False, False, 0)

        main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        main.set_border_width(18)
        root.pack_start(main, True, True, 0)

        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title_box.pack_start(label("Chat", "page-title"), True, True, 0)
        self.activity = Gtk.Spinner()
        title_box.pack_end(self.activity, False, False, 0)
        main.pack_start(title_box, False, False, 0)
        main.pack_start(
            label(
                "Ask questions, run tools, inspect tasks, or control approved desktop actions.",
                "page-subtitle",
            ),
            False,
            False,
            0,
        )

        self.transcript = Gtk.TextView()
        self.transcript.set_editable(False)
        self.transcript.set_cursor_visible(False)
        self.transcript.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.transcript.set_left_margin(16)
        self.transcript.set_right_margin(16)
        self.transcript.set_top_margin(14)
        self.transcript.set_bottom_margin(14)
        buffer = self.transcript.get_buffer()
        self.user_tag = buffer.create_tag(
            "user", foreground="#ffb21a", weight=700, pixels_above_lines=10
        )
        self.ai_tag = buffer.create_tag(
            "assistant", foreground="#f7ead0", pixels_above_lines=10
        )
        self.meta_tag = buffer.create_tag(
            "meta", foreground="#9ba5b4", style=2, pixels_above_lines=6
        )
        scroll = Gtk.ScrolledWindow()
        scroll.set_shadow_type(Gtk.ShadowType.IN)
        scroll.add(self.transcript)
        main.pack_start(scroll, True, True, 0)

        composer_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        composer_card.get_style_context().add_class("card")
        self.composer = Gtk.TextView()
        self.composer.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.composer.set_left_margin(10)
        self.composer.set_right_margin(10)
        self.composer.set_top_margin(8)
        self.composer.set_bottom_margin(8)
        composer_scroll = Gtk.ScrolledWindow()
        composer_scroll.set_size_request(-1, 100)
        composer_scroll.add(self.composer)
        composer_card.pack_start(composer_scroll, True, True, 0)
        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        controls.pack_start(label("Enter message, then Send", "muted"), True, True, 0)
        controls.pack_start(
            button("Clear", "edit-clear-symbolic", self.clear_composer),
            False,
            False,
            0,
        )
        self.send_button = button(
            "Send", "mail-send-symbolic", self.send_prompt, "suggested-action"
        )
        controls.pack_start(self.send_button, False, False, 0)
        composer_card.pack_start(controls, False, False, 0)
        main.pack_start(composer_card, False, False, 0)

        self.connect("destroy", Gtk.main_quit)
        self.load_transcript()
        self.refresh_model()

    def append(self, heading, body, tag):
        buffer = self.transcript.get_buffer()
        end = buffer.get_end_iter()
        timestamp = datetime.now().strftime("%H:%M")
        buffer.insert_with_tags(end, f"\n{heading}  {timestamp}\n", tag)
        end = buffer.get_end_iter()
        buffer.insert_with_tags(end, body.strip() + "\n", self.ai_tag)
        mark = buffer.create_mark(None, buffer.get_end_iter(), False)
        self.transcript.scroll_to_mark(mark, 0.1, True, 0.0, 1.0)
        self.save_transcript()

    def load_transcript(self):
        if self.transcript_path.exists():
            text = self.transcript_path.read_text(encoding="utf-8", errors="replace")
            self.transcript.get_buffer().set_text(text[-60000:])
        else:
            self.append(
                "Ooonana",
                "Ready. Provider setup, tools, tasks, desktop context, and chat live here.",
                self.ai_tag,
            )

    def save_transcript(self):
        buffer = self.transcript.get_buffer()
        text = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True)
        self.transcript_path.write_text(text, encoding="utf-8")

    def refresh_model(self):
        _provider_rc, provider = run(["ooonana-ai", "provider"], timeout=5)
        _model_rc, model = run(["ooonana-ai", "model"], timeout=5)
        self.provider_label.set_text(f"provider: {provider.splitlines()[-1] if provider else 'auto'}")
        self.model_label.set_text(f"model: {model.splitlines()[-1] if model else 'default'}")

    def clear_composer(self, *_args):
        self.composer.get_buffer().set_text("")

    def send_prompt(self, *_args):
        buffer = self.composer.get_buffer()
        prompt = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), True).strip()
        if not prompt:
            return
        buffer.set_text("")
        self.append("You", prompt, self.user_tag)
        self.send_button.set_sensitive(False)
        self.activity.start()

        def done(rc, output):
            self.send_button.set_sensitive(True)
            self.activity.stop()
            if rc == 0:
                self.append("Ooonana", output or "Done.", self.ai_tag)
            else:
                self.append(
                    "Ooonana",
                    (output or f"Command failed with exit status {rc}")
                    + "\n\nOpen Setup to configure provider and API key.",
                    self.meta_tag,
                )

        run_async(["ooonana-ai", "ask", prompt], done, timeout=300)

    def run_action(self, title, args):
        self.activity.start()

        def done(rc, output):
            self.activity.stop()
            self.append(
                title,
                output or ("Done." if rc == 0 else f"Failed with exit status {rc}"),
                self.ai_tag if rc == 0 else self.meta_tag,
            )
            self.refresh_model()

        run_async(["ooonana-ai", *args], done, timeout=120)

    def sidebar_action(self, action):
        if action == "new":
            self.transcript.get_buffer().set_text("")
            self.append("Ooonana", "New chat started.", self.ai_tag)
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
        print("layout: sidebar chat transcript composer provider model actions")
        print("actions: new status tools tasks sessions desktop permissions logs setup")
        print("OOONANA_AI_NATIVE_OK")
        return 0
    apply_theme()
    window = AiWindow()
    window.show_all()
    Gtk.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
