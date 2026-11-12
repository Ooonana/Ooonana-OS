#!/usr/bin/env python3
"""Native GTK -> actual Ooonana CLI -> owned real CPU API, no mocked response."""
import argparse
import json
import os
from pathlib import Path
import sys
import time
import urllib.request

if os.getuid() == 0 or os.environ.get("OOONANA_GUI_TEST_DISPLAY") != "1" or os.environ.get("OOONANA_TRANSPORT_ISOLATED") != "1":
    raise SystemExit("Require owned nonroot transport/display")
parser = argparse.ArgumentParser()
parser.add_argument("--source", type=Path, required=True)
parser.add_argument("--qa", type=Path, required=True)
parser.add_argument("--port", type=int, required=True)
parser.add_argument("--model", required=True)
parser.add_argument("--memory-error", action="store_true")
args = parser.parse_args()
source, qa = args.source.resolve(), args.qa.resolve()
assert qa.is_relative_to(Path("/var/tmp"))
home = qa / "home/gui"
home.mkdir(mode=0o700, exist_ok=True)
os.environ.update(HOME=str(home), XDG_STATE_HOME=str(home / "state"), XDG_CONFIG_HOME=str(home / "config"),
    PATH=str(source / "packages/ooonana/usr/bin") + ":" + os.environ["PATH"],
    OOONANA_AI_CONFIG=str(home / "ai.env"), GDK_BACKEND="x11", GTK_THEME="Adwaita:dark", NO_AT_BRIDGE="1")
Path(os.environ["OOONANA_AI_CONFIG"]).write_text(
    f"OOONANA_AI_PROVIDER=openvino\nOOONANA_OPENVINO_BASE_URL=http://127.0.0.1:{args.port}/v1\n"
    f"OOONANA_OPENVINO_MODEL={args.model}\nOOONANA_AI_MAX_TOKENS=128\nOOONANA_AI_TEMPERATURE=0\n")
sys.path.insert(0, str(source / "packages/ooonana/usr/lib/ooonana/ui"))
from common import Gdk, Gtk, apply_theme
from ai_app import AiWindow


def spin(predicate, timeout=120):
    deadline = time.monotonic() + timeout
    while not predicate():
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        assert time.monotonic() < deadline, "Real GTK/engine timeout"
        time.sleep(0.01)


def health():
    with urllib.request.urlopen(f"http://127.0.0.1:{args.port}/health", timeout=5) as response:
        return json.load(response)


def send(text):
    window.composer.get_buffer().set_text(text)
    window.send_prompt()
    assert window.request is not None and window.phase_title == "Waiting for backend"


apply_theme()
window = AiWindow()
window.show_all()
try:
    spin(lambda: args.model in window.model_label.get_text(), timeout=15)
    assert window.provider_combo.get_active_id() == "openvino"
    window.new_chat()
    send("Count integers from one to fifty. Write every number.")
    if args.memory_error:
        spin(lambda: window.request is None)
        result = window.current["messages"][-1]
        assert result["role"] == "system" and "RAM" in result["content"], result
        assert not health()["loaded"]
        print("NATIVE_GUI_REAL_LOW_MEMORY_OK", flush=True)
    else:
        spin(lambda: window.phase_title == "Generating reply")
        assert window.request is not None, "No visible streaming before completion"
        window.send_button.clicked()
        spin(lambda: window.request is None)
        assert "cancelled" in window.current["messages"][-1]["content"].lower()
        assert health()["loaded"]
        config = Path(os.environ["OOONANA_AI_CONFIG"])
        config.write_text(config.read_text().replace("MAX_TOKENS=128", "MAX_TOKENS=12"))
        send("Say hello briefly.")
        spin(lambda: window.request is None)
        result = window.current["messages"][-1]
        assert result["role"] == "assistant" and result["content"].strip(), result
        assert window.phase_label.get_text() == "Ready" and health()["loaded"]
        settled = time.monotonic() + 0.5
        spin(lambda: time.monotonic() >= settled)
        window.scroll_bottom()
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        Gdk.Display.get_default().sync()
        screen = Gdk.get_default_root_window()
        Gdk.pixbuf_get_from_window(screen, 0, 0, screen.get_width(), screen.get_height()).savev(str(home / "native-ai-engine.png"), "png", [], [])
        print("NATIVE_GUI_REAL_STREAM_CANCEL_REUSE_OK", flush=True)
finally:
    window.disconnect_by_func(window.closed)
    window.closed()
    window.destroy()
