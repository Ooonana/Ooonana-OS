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
    run_async_task,
)
from gi.repository import GdkPixbuf  # noqa: E402


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
            "Cloud and offline Intel workbench",
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

        provider_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        provider_row.pack_start(label("Provider", "muted"), False, False, 0)
        self.provider_combo = Gtk.ComboBoxText()
        self.provider_combo.append("nim", "NVIDIA NIM")
        self.provider_combo.append("gemini", "Google Gemini")
        self.provider_combo.append("openvino", "OpenVINO Local")
        self.provider_combo.set_active_id("nim")
        self.provider_combo.connect("changed", self.change_provider)
        provider_row.pack_start(self.provider_combo, False, False, 0)
        provider_row.pack_start(
            button("Offline setup", "computer-symbolic", lambda *_: self.offline_dialog()),
            False,
            False,
            0,
        )
        main.pack_start(provider_row, False, False, 0)

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
        self.provider_label.set_text("provider: checking...")
        self.model_label.set_text("model: checking...")

        def task():
            _provider_rc, provider = run(["ooonana-ai", "provider"], timeout=5)
            _model_rc, model = run(["ooonana-ai", "model"], timeout=5)
            return 0, (provider, model)

        def done(_rc, values):
            provider, model = values
            self.provider_label.set_text(f"provider: {provider.splitlines()[-1] if provider else 'auto'}")
            self.model_label.set_text(f"model: {model.splitlines()[-1] if model else 'default'}")
            active = next(
                (line.split(":", 1)[1].strip() for line in provider.splitlines() if line.startswith("active:")),
                "nim",
            )
            self.provider_combo.handler_block_by_func(self.change_provider)
            self.provider_combo.set_active_id(active)
            self.provider_combo.handler_unblock_by_func(self.change_provider)

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
        model = str(Path.home() / ".openvino/models/gemma-4-e2b-it-qat-int4-ov")
        self.activity.start()

        def started(rc, output):
            if rc != 0:
                self.activity.stop()
                self.append("Offline Intel", output or "OpenVINO API failed.", self.meta_tag)
                return

            def selected(select_rc, select_output):
                self.activity.stop()
                self.append(
                    "Offline Intel",
                    (output + "\n" + select_output).strip(),
                    self.ai_tag if select_rc == 0 else self.meta_tag,
                )
                self.refresh_model()

            run_async(
                ["ooonana-ai", "provider", "set", "openvino"],
                selected,
                timeout=15,
            )

        run_async(
            ["openvino", "--model-dir", model, "api", "start", "--device", device],
            started,
            timeout=180,
        )

    def offline_dialog(self):
        dialog = Gtk.Dialog(title="Offline Intel AI", transient_for=self, flags=0)
        dialog.set_default_size(720, 480)
        dialog.add_button("Close", Gtk.ResponseType.CLOSE)
        dialog.add_button("Install package", 1)
        dialog.add_button("Setup runtime", 2)
        dialog.add_button("Download tiny model", 3)
        dialog.add_button("Start GPU", 4)
        dialog.add_button("Start NPU", 5)
        dialog.add_button("Stop API", 6)
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
        dialog.get_content_area().pack_start(scroll, True, True, 0)
        dialog.show_all()

        def status_task():
            return 0, self.offline_status()

        def status_done(_rc, output):
            status_buffer.set_text(output)

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
            self.offline_terminal("Download tiny OpenVINO model", "openvino download tiny")
        elif response == 4:
            self.start_offline_api("GPU")
        elif response == 5:
            self.start_offline_api("NPU")
        elif response == 6:
            self.run_action("Offline Intel", ["provider", "set", "nim"])
            run_async(["openvino", "api", "stop"], lambda _rc, _output: None, timeout=30)

    def sidebar_action(self, action):
        if action == "new":
            self.transcript.get_buffer().set_text("")
            self.append("Ooonana", "New chat started.", self.ai_tag)
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
        print("offline: install runtime model GPU NPU local API")
        print("OOONANA_AI_NATIVE_OK")
        return 0
    apply_theme()
    window = AiWindow()
    window.show_all()
    Gtk.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
