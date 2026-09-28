from __future__ import annotations

import concurrent.futures
import hmac
import importlib.util
import json
import logging
from logging.handlers import RotatingFileHandler
import os
import re
import secrets
import subprocess
import sys
import threading
import time
import webbrowser
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable
from urllib.parse import parse_qs, urlsplit

from openvino_chat.media import MEDIA_EXTENSIONS
from openvino_chat.settings import CONFIG_PATH
from openvino_chat.tasks import has_visible_tasks
from openvino_chat.visuals import QUACK_PORTRAIT, QUACK_PORTRAIT_SMALL


ASSETS = Path(__file__).with_name("web")
MAX_JSON_BYTES = 1024 * 1024
MAX_UPLOAD_BYTES = 256 * 1024 * 1024
KEYS = {"enter", "escape", "up", "down", "left", "right", "home", "end", "pageup", "pagedown",
        "c-home", "c-end", "f1", "f2", "f3", "f4", "f6", "d", "i", "u", "n", "s", "r", "y", "a"}
MENU_FIELDS = (
    ("approval", "_approval_menu_active", "_approval_index"),
    ("model", "_model_menu_active", "_model_menu_index"),
    ("session", "_session_menu_active", "_session_menu_index"),
    ("kv", "_kv_menu_active", "_kv_menu_index"),
    ("thinking", "_thinking_menu_active", "_thinking_menu_index"),
    ("sampling", "_sampling_menu_active", "_sampling_menu_index"),
    ("permission", "_permission_menu_active", "_permission_menu_index"),
    ("timeline", "_timeline_menu_active", "_timeline_index"),
)


def character_geometry(source: str) -> tuple[list[str], dict[str, float]]:
    """Keep ASCII silhouette; overlay round eyes and a separate ASCII bill."""
    lines = source.splitlines()
    row = next(i for i, line in enumerate(lines) if "%" in line)
    eyes = list(re.finditer(r"\.%%=|=%%\.|%#|#%", lines[row]))
    left, right = [(eye.start() + eye.end()) / 2 for eye in eyes]
    width = max(map(len, lines))
    for i in range(row, row + 2):
        line = lines[i]
        lines[i] = line[:int(left) - 2] + " " * (int(right) + 3 - (int(left) - 2)) + line[int(right) + 3:]
    return lines, {"left": left / width * 100, "right": right / width * 100,
                   "eyes_y": (row + .5) / len(lines) * 100,
                   "beak_x": (left + right) / 2 / width * 100,
                   "beak_y": (row + 1.35) / len(lines) * 100,
                   "beak_width": (right - left) * .9 / width * 100}


class GuiBridge:
    """Browser adapter. All mutations run on the existing TUI event loop."""

    def __init__(self, mediator: Any) -> None:
        self.ui = mediator
        self._transcript = ""
        self._transcript_version = 0
        self._transcript_patch = ""
        self._transcript_replace = True
        self._speech_cache: dict[str, str] = {}

    def format_speech(self, text: str) -> str:
        if text not in self._speech_cache:
            from openvino_chat.tui import _has_terminal_markup, _render_terminal_markup

            if len(self._speech_cache) >= 64:
                self._speech_cache.clear()
            self._speech_cache[text] = _render_terminal_markup(text, width=76).rstrip() if _has_terminal_markup(text) else text
        return self._speech_cache[text]

    def on_ui(self, callback: Callable[[], Any]) -> Any:
        app = self.ui._app
        loop = getattr(app, "loop", None)
        if loop is None or loop.is_closed():
            raise RuntimeError("Terminal event loop is not available")
        future: concurrent.futures.Future[Any] = concurrent.futures.Future()

        def run() -> None:
            if not future.set_running_or_notify_cancel():
                return
            try:
                future.set_result(app.context.copy().run(callback))
            except Exception as exc:
                future.set_exception(exc)

        loop.call_soon_threadsafe(run)
        try:
            return future.result(timeout=5)
        except concurrent.futures.TimeoutError:
            future.cancel()
            raise RuntimeError("Terminal is not responding") from None

    def menu(self) -> dict[str, Any] | None:
        ui = self.ui
        kind = next((name for name, active, _ in MENU_FIELDS if getattr(ui, active)), None)
        if kind is None:
            return None
        index_field = next(field for name, _, field in MENU_FIELDS if name == kind)
        menu: dict[str, Any] = {"kind": kind, "id": f"{kind}:{ui._dialog_revision}",
                                "selected": getattr(ui, index_field)}
        if kind == "approval":
            computer = ui._approval_request_name == "computer"
            menu.update(title="Permission required", text=ui._approval_request_name + "\n" +
                        (getattr(ui, "_approval_context", "") + "\n" if getattr(ui, "_approval_context", "") else "") +
                        json.dumps(ui._approval_request_args, ensure_ascii=False, indent=2),
                        computer=computer,
                        warning="Computer control can expose private data or change other apps. Auto-allow needs confirmation. Alt+Shift+S stops current work; /computer ask revokes access." if computer else "Session/always choices allow ALL file and shell tools, not only this request.",
                        items=[{"name": text, "disabled": computer and index > 1 and not ui.computer_auto_stop_available} for index, text in enumerate(("Deny", "Allow once", "Allow session", "Always allow"))],
                        actions=[{"key": "enter", "label": "Confirm selected choice"}, {"key": "escape", "label": "Deny"}])
            if ui._approval_pending_auto:
                menu.update(title="Enable automatic computer control?", confirmation=True,
                            items=[{"name":"Cancel"},{"name":"Confirm " + ui._approval_pending_auto + " access"}])
        elif kind == "model":
            menu.update(title="Models", items=ui._model_menu_items,
                        actions=[{"key": k, "label": v} for k, v in (("enter", "Select and load"), ("i", "Install"), ("u", "Unload"), ("d", "Delete"), ("escape", "Cancel"))])
        elif kind == "session":
            menu.update(title="Sessions", items=ui._session_menu_items,
                        actions=[{"key": k, "label": v} for k, v in (("enter", "Resume"), ("n", "New"), ("s", "Save"), ("d", "Delete"), ("escape", "Cancel"))])
        elif kind == "timeline":
            with ui._timeline_lock:
                menu["items"] = [asdict(entry) for entry in ui._timeline_entries]
            menu.update(title="Tool timeline", retrying=ui._timeline_retry_active,
                        actions=[{"key": k, "label": v} for k, v in (("enter", "Expand / collapse"), ("r", "Retry selected"), ("escape", "Close"))])
        elif kind == "sampling":
            from openvino_chat.tui import _SAMPLING_FIELDS

            menu.update(title="Custom sampling", items=[{"name": name, "value": ui._sampling_menu_values.get(name),
                        "step": step, "min": low, "max": high} for name, step, low, high in _SAMPLING_FIELDS],
                        actions=[{"key": "enter", "label": "Save"}, {"key": "r", "label": "Reset"}, {"key": "escape", "label": "Cancel"}])
        else:
            prefix = "thinking" if kind == "thinking" else kind
            values = getattr(ui, f"_{prefix}_menu_values")
            current = getattr(ui, f"_{prefix}_menu_current")
            title = ui._thinking_menu_kind.title() if kind == "thinking" else "KV cache" if kind == "kv" else "Permissions"
            menu.update(title=title, items=[{"name": value, "active": value == current} for value in values],
                        actions=[{"key": "enter", "label": "Apply"}, {"key": "escape", "label": "Cancel"}])
        return menu

    def snapshot(self, since: int = -1) -> dict[str, Any]:
        ui = self.ui
        transcript = ui.chat_buffer.render_conversation()
        if transcript != self._transcript:
            self._transcript_replace = not transcript.startswith(self._transcript)
            self._transcript_patch = transcript if self._transcript_replace else transcript[len(self._transcript):]
            self._transcript = transcript
            self._transcript_version += 1
        change = None
        if since != self._transcript_version:
            incremental = since == self._transcript_version - 1 and not self._transcript_replace
            change = {"replace": not incremental, "text": self._transcript_patch if incremental else transcript}
        user, speech = ui.chat_buffer.quack_dialogue(full=True)
        tasks = ui.tasks_text()
        paragraphs = [self.format_speech(part) for part in re.split(r"\n\s*\n", speech) if part.strip()] if ui._duck_theme else []
        with ui._status_lock:
            status = ui._status_value
        with ui._timeline_lock:
            timeline = [asdict(entry) for entry in ui._timeline_entries]
        character = {}
        faces = {}
        if ui._duck_theme:
            for name, source in (("large", QUACK_PORTRAIT), ("small", QUACK_PORTRAIT_SMALL)):
                lines, faces[name] = character_geometry(source)
                character[name] = "\n".join(ui._quack_art_line(line, i, source.splitlines()) for i, line in enumerate(lines))
        ready = ui._busy.is_set() and ui._request_event.is_set() and not ui._any_menu_active()
        return {"mode": "gui" if ui._gui_active else "tui", "duck": ui._duck_theme, "ready": ready,
                "input": ui._input_area.text, "input_version": ui._input_revision,
                "cursor": ui._input_area.buffer.cursor_position,
                "transcript_version": self._transcript_version, "transcript": change,
                "user": user, "speech": speech, "speech_parts": paragraphs,
                "speech_formatted": self.format_speech(speech) if ui._reply_reader_open else "",
                "character": character, "faces": faces,
                "operation": "awaiting permission" if ui._approval_menu_active else ui._operation_label or "ready", "detail": ui._operation_detail,
                "elapsed": max(0, int(time.monotonic() - ui._operation_started)) if ui._operation_label else 0,
                "status": status, "notice": ui._notice_text(), "menu": self.menu(), "timeline": timeline,
                "sidepanel": ui._side_panel_enabled, "tab": ui._side_tab, "tasks": tasks if has_visible_tasks(tasks) else "",
                "visual": {"kind": ui._visual_panel_kind, "text": ui._visual_panel_text},
                "help": ui._help_document, "reader": ui._reply_reader_open,
                "attachments": ui._attachments, "attachment_state": ui._attachment_state,
                "queue": ui.queue_snapshot(), "queue_paused": ui._queue_paused,
                "stop_hotkey": ui.computer_auto_stop_available}

    def dispatch(self, body: dict[str, Any]) -> dict[str, Any]:
        ui = self.ui
        action = body.get("action")
        menu = self.menu()
        if action == "frontend":
            if body.get("mode") not in {"gui", "tui"}:
                raise ValueError("Unknown frontend")
            ui._gui_active = body["mode"] == "gui"
            ui.invalidate()
            return {"ok": True}
        if not ui._gui_active:
            raise ValueError("Terminal is active. Switch to GUI first.")
        if action == "approval":
            if not menu or menu["kind"] != "approval" or body.get("menu_id") != menu["id"]:
                raise ValueError("Permission request changed. Review current action.")
            decision = body.get("decision")
            allowed = {"deny", "once", "session", "always"}
            if decision not in allowed:
                raise ValueError("Approval scope not allowed for this action")
            if ui._approval_request_name == "computer" and decision in {"session", "always"} and not ui.computer_auto_stop_available:
                raise ValueError("Auto-allow unavailable: Alt+Shift+S shortcut could not be registered")
            ui._finish_tool_approval(decision)
        elif action == "queue":
            item_id = body.get("id")
            if item_id is not None and type(item_id) is not int:
                raise ValueError("Invalid queue ID")
            ui.queue_action(body.get("operation"), item_id)
        elif action in {"draft", "submit"}:
            if menu:
                raise ValueError("Answer open dialog first")
            text = body.get("text")
            if not isinstance(text, str) or len(text) > 250_000:
                raise ValueError("Invalid input")
            cursor = body.get("cursor", len(text))
            if isinstance(cursor, bool) or not isinstance(cursor, int):
                raise ValueError("Invalid cursor")
            ui._input_area.text = text
            ui._input_area.buffer.cursor_position = max(0, min(len(text), cursor))
            if action == "submit":
                if text.strip().lower() == "/tui":
                    ui._input_area.text = ""
                    ui._gui_active = False
                elif text.strip().lower() == "/computer stop":
                    ui._input_area.text = ""
                    ui.emergency_stop()
                elif not ui._busy.is_set() or not ui._request_event.is_set():
                    if not ui._queue_command(text):
                        ui.enqueue_input(text)
                        ui._input_area.text = ""
                else:
                    ui.submit_input(use_palette=False)
        elif action in {"key", "select"}:
            key = body.get("key")
            if action == "key" and (not isinstance(key, str) or key not in KEYS):
                raise ValueError("Unsupported key")
            if menu:
                if body.get("menu_id") != menu["id"]:
                    raise ValueError("Dialog changed. Review current choices.")
                if "index" in body:
                    index = body["index"]
                    if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(menu["items"]):
                        raise ValueError("Invalid selection")
                    if menu["items"][index].get("disabled"):
                        raise ValueError("Computer actions require Allow once")
                    field = next(field for kind, _, field in MENU_FIELDS if kind == menu["kind"])
                    setattr(ui, field, index)
                if action == "select":
                    ui.invalidate()
                    return {"ok": True}
            elif body.get("menu_id"):
                raise ValueError("Dialog already closed")
            elif action == "select":
                raise ValueError("No dialog open")
            elif len(key) == 1 or key == "enter":
                raise ValueError("This key requires a dialog")
            if menu and menu["kind"] == "sampling" and key == "enter":
                from openvino_chat.cli import _normalize_custom_sampling

                values = body.get("values", ui._sampling_menu_values)
                if not isinstance(values, dict):
                    raise ValueError("Invalid sampling values")
                ui._sampling_menu_values = _normalize_custom_sampling(values)
            from prompt_toolkit.keys import KEY_ALIASES

            terminal_key = KEY_ALIASES.get(key, key)
            bindings = [binding for binding in ui._app.key_bindings.get_bindings_for_keys((terminal_key,)) if binding.filter()]
            if not bindings:
                raise ValueError("Action not available right now")
            bindings[-1].handler(SimpleNamespace(app=ui._app))
        elif action == "tab":
            if menu or body.get("tab") not in {"chat", "tools", "charts"}:
                raise ValueError("Tab unavailable")
            ui._side_tab = body["tab"]
        elif action == "dismiss_visual":
            if menu:
                raise ValueError("Answer dialog first")
            ui.clear_visual_panel()
        else:
            raise ValueError("Unknown GUI action")
        ui.invalidate()
        return {"ok": True, "input_version": ui._input_revision}


class GuiServer:
    def __init__(self, mediator: Any, *, port: int = 0, idle_timeout: float = 15) -> None:
        self.bridge = GuiBridge(mediator)
        self.token = secrets.token_urlsafe(32)
        self.last_seen = time.monotonic()
        self.idle_timeout = idle_timeout
        self._stop = threading.Event()
        self.desktop_process: subprocess.Popen | None = None
        self._desktop_reader: threading.Thread | None = None
        self._desktop_closed = threading.Event()
        self._diagnostic_handler = None
        self._diagnostic_lock = threading.Lock()
        self.http = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
        self.http.daemon_threads = True
        self.http.gui = self
        self.origin = f"http://127.0.0.1:{self.http.server_port}"
        self.thread = threading.Thread(target=self.http.serve_forever, name="openvino-gui", daemon=True)
        self.watchdog = threading.Thread(target=self._watch, name="openvino-gui-watch", daemon=True)

    @property
    def url(self) -> str:
        page = "duck.html" if self.bridge.ui._duck_theme else "openvino.html"
        return self.origin + "/" + page + "#token=" + self.token

    @property
    def diagnostic_path(self) -> Path:
        config = Path(os.environ.get("OPENVINO_CHAT_CONFIG", CONFIG_PATH)).expanduser()
        return config.parent / "reports" / "gui-diagnostics.jsonl"

    def _diagnostic(self, event: str, **fields) -> None:
        try:
            with self._diagnostic_lock:
                if self._diagnostic_handler is None:
                    self.diagnostic_path.parent.mkdir(parents=True, exist_ok=True)
                    self._diagnostic_handler = RotatingFileHandler(self.diagnostic_path, maxBytes=131072, backupCount=1, encoding="utf-8")
                message = json.dumps({"time": time.time(), "event": event, **fields}, ensure_ascii=False)
                message = message.replace(self.token, "[redacted]")
                self._diagnostic_handler.emit(logging.LogRecord("openvino.gui", logging.ERROR, "", 0, message, (), None))
        except OSError:
            pass

    def _read_desktop_errors(self, process, closed_event) -> None:
        try:
            while True:
                line = process.stderr.readline(4096)
                if not line:
                    break
                if line.strip() == "OPENVINO_GUI_CLOSED":
                    closed_event.set()
                    continue
                self._diagnostic("desktop_stderr", message=line.rstrip()[:4096])
        except (OSError, ValueError):
            pass
        finally:
            process.stderr.close()

    def start(self, *, open_browser: bool = True, frontend: str = "desktop") -> str:
        self.thread.start()
        self.watchdog.start()
        self.activate(open_browser=open_browser, frontend=frontend)
        return self.url

    def activate(self, *, open_browser: bool = True, frontend: str = "desktop") -> None:
        self.last_seen = time.monotonic()
        self.bridge.ui._gui_active = True
        self.bridge.ui.invalidate()
        if not open_browser:
            return
        if frontend == "desktop" and importlib.util.find_spec("webview") is not None:
            if self.desktop_process is not None and self.desktop_process.poll() is None:
                return
            self.desktop_process = subprocess.Popen(
                [sys.executable, "-B", "-m", "openvino_chat.desktop"], stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            self._desktop_closed = threading.Event()
            self._desktop_reader = threading.Thread(target=self._read_desktop_errors, args=(self.desktop_process, self._desktop_closed), daemon=True, name="openvino-desktop-errors")
            self._desktop_reader.start()
            self.desktop_process.stdin.write(self.url + "\n")
            self.desktop_process.stdin.close()
            return
        if frontend == "desktop":
            notice = ("Browser GUI opened; native desktop window unavailable in Linux runtime."
                      if os.name != "nt" else
                      "Desktop runtime missing; browser opened. Run setup to install desktop support.")
            self.bridge.ui.show_notice(notice)
        if not webbrowser.open(self.url, new=1):
            self.bridge.ui._gui_active = False
            raise RuntimeError("Browser could not open GUI")

    def stop(self) -> None:
        self._stop.set()
        if self.desktop_process is not None and self.desktop_process.poll() is None:
            self.desktop_process.terminate()
            self.desktop_process.wait(timeout=5)
        if self.thread.is_alive():
            self.http.shutdown()
        self.http.server_close()
        if self.thread.ident is not None:
            self.thread.join(timeout=2)
        if self.watchdog.ident is not None:
            self.watchdog.join(timeout=1)
        if self._desktop_reader is not None:
            self._desktop_reader.join(timeout=1)
        with self._diagnostic_lock:
            if self._diagnostic_handler is not None:
                self._diagnostic_handler.close()
                self._diagnostic_handler = None

    def _watch(self) -> None:
        while not self._stop.wait(1):
            if self.desktop_process is not None and self.desktop_process.poll() is not None:
                process = self.desktop_process
                self.desktop_process = None
                if self._desktop_reader is not None:
                    self._desktop_reader.join(timeout=.5)
                if process.returncode == 0 and self._desktop_closed.is_set():
                    self.bridge.ui._gui_active = False
                    self._diagnostic("desktop_closed", exit_code=0)
                    continue
                if self.bridge.ui._gui_active:
                    self._diagnostic("unexpected_desktop_exit", exit_code=process.returncode,
                                     operation=self.bridge.ui._operation_label)
                    try:
                        self.activate(frontend="browser")
                        self.bridge.on_ui(lambda: self.bridge.ui.show_notice(f"Desktop exited ({process.returncode}); browser opened. Diagnostics: {self.diagnostic_path}"))
                    except RuntimeError:
                        self.bridge.ui._gui_active = False
                        return
            if self.desktop_process is None and self.bridge.ui._gui_active and time.monotonic() - self.last_seen > self.idle_timeout:
                try:
                    def fallback() -> None:
                        if time.monotonic() - self.last_seen > self.idle_timeout:
                            self.bridge.ui._gui_active = False
                            self.bridge.ui.show_notice("GUI disconnected. Terminal control restored.")
                    self.bridge.on_ui(fallback)
                except RuntimeError:
                    return


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args: Any) -> None:
        pass

    @property
    def gui(self) -> GuiServer:
        return self.server.gui

    def _check_host(self) -> bool:
        if self.headers.get("Host") != self.gui.origin.removeprefix("http://"):
            self._json(403, {"error": "Invalid host"})
            return False
        return True

    def _authorized(self) -> bool:
        if not self._check_host():
            return False
        origin = self.headers.get("Origin")
        token = self.headers.get("X-OpenVINO-Token", "")
        if (origin is not None and origin != self.gui.origin) or not hmac.compare_digest(token, self.gui.token):
            self._json(403, {"error": "GUI access denied"})
            return False
        return True

    def _headers(self, status: int, content_type: str, length: int) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
        self.end_headers()

    def _json(self, status: int, payload: Any) -> None:
        if status >= 400 and self.command == "POST":
            self._discard_small_body()
        data = json.dumps(payload, ensure_ascii=False, allow_nan=False, default=str).encode("utf-8")
        try:
            self._headers(status, "application/json; charset=utf-8", len(data))
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionError):
            pass

    def do_GET(self) -> None:
        path = urlsplit(self.path)
        assets = {"/": "openvino.html", "/openvino.html": "openvino.html", "/duck.html": "duck.html", "/duck.css": "duck.css", "/duck.js": "duck.js"}
        if path.path in assets:
            if not self._check_host():
                return
            source = ASSETS / assets[path.path]
            try:
                data = source.read_bytes()
            except OSError:
                self._json(404, {"error": "GUI assets missing. Reinstall app."})
                return
            content_type = {".html": "text/html", ".css": "text/css", ".js": "text/javascript"}[source.suffix]
            try:
                self._headers(200, content_type + "; charset=utf-8", len(data))
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionError):
                pass
            return
        if not self._authorized():
            return
        try:
            if path.path == "/health":
                self.gui.last_seen = time.monotonic()
                # Liveness must not wait behind rendering or tool work on the UI loop.
                self._json(200, {
                    "mode": "gui" if self.gui.bridge.ui._gui_active else "tui",
                    "permission_pending": self.gui.bridge.ui._approval_menu_active,
                })
            elif path.path == "/state":
                since = int(parse_qs(path.query).get("since", ["-1"])[0])
                self.gui.last_seen = time.monotonic()
                self._json(200, self.gui.bridge.on_ui(lambda: self.gui.bridge.snapshot(since)))
            elif path.path == "/commands":
                from openvino_chat.cli import COMMAND_SPECS

                self._json(200, [asdict(spec) for spec in COMMAND_SPECS])
            else:
                self._json(404, {"error": "Not found"})
        except ValueError as exc:
            self._json(400, {"error": str(exc)})
        except RuntimeError as exc:
            self._json(503, {"error": str(exc)})

    def do_POST(self) -> None:
        try:
            self._remaining_body = max(0, int(self.headers.get("Content-Length", "0")))
        except ValueError:
            self._remaining_body = 0
        if not self._authorized():
            return
        try:
            self.connection.settimeout(30)
            if self.headers.get("Transfer-Encoding"):
                raise ValueError("Chunked requests unsupported")
            length = int(self.headers.get("Content-Length", "-1"))
            self._remaining_body = max(0, length)
            path = urlsplit(self.path)
            if path.path == "/upload":
                self._upload(path.query, length)
                return
            if path.path != "/action" or not 0 < length <= MAX_JSON_BYTES:
                raise ValueError("Invalid request path or size")
            def invalid_constant(_value: str) -> None:
                raise ValueError("Non-finite JSON number")
            body = json.loads(self._read_body(length), parse_constant=invalid_constant)
            if not isinstance(body, dict):
                raise ValueError("Expected JSON object")
            result = self.gui.bridge.on_ui(lambda: self.gui.bridge.dispatch(body))
            self._json(200, result)
        except (ValueError, TypeError, UnicodeError) as exc:
            self._discard_small_body()
            self._json(400, {"error": str(exc)})
        except (RuntimeError, OSError) as exc:
            self._json(503, {"error": str(exc)})

    def _read_body(self, size: int) -> bytes:
        data = self.rfile.read(size)
        self._remaining_body -= len(data)
        return data

    def _discard_small_body(self) -> None:
        # Unread request bytes can make Windows reset the connection before the error arrives.
        if 0 < getattr(self, "_remaining_body", 0) <= MAX_JSON_BYTES:
            try:
                self.connection.settimeout(1)
                self._read_body(self._remaining_body)
            except OSError:
                pass

    def _upload(self, query: str, length: int) -> None:
        if not 0 < length <= MAX_UPLOAD_BYTES:
            raise ValueError("Attachment must be between 1 byte and 256 MiB")
        name = parse_qs(query).get("name", [""])[0]
        name = re.sub(r"[^A-Za-z0-9._-]", "_", re.split(r"[/\\]", name)[-1])[-100:]
        if Path(name).suffix.lower() not in MEDIA_EXTENSIONS:
            raise ValueError("Unsupported attachment type")
        def ready() -> bool:
            ui = self.gui.bridge.ui
            return ui._gui_active and ui._busy.is_set() and ui._request_event.is_set() and not ui._any_menu_active()
        if not self.gui.bridge.on_ui(ready):
            raise ValueError("Wait for current action before attaching files")
        root = Path(os.environ.get("OPENVINO_CHAT_CONFIG", CONFIG_PATH)).expanduser().parent / "attachments" / "gui"
        root.mkdir(parents=True, exist_ok=True)
        target = root.resolve() / (secrets.token_hex(12) + "_" + name)
        try:
            with target.open("xb") as stream:
                remaining = length
                while remaining:
                    chunk = self._read_body(min(65536, remaining))
                    if not chunk:
                        raise ValueError("Incomplete upload")
                    stream.write(chunk)
                    remaining -= len(chunk)
        except Exception:
            target.unlink(missing_ok=True)
            raise
        self._json(201, {"path": str(target), "name": name})
