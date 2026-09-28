from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable

from openvino_chat.settings import CONFIG_PATH
from openvino_chat.computer_schema import SPECS, capabilities


KEYS = {"enter", "escape", "tab", "shift+tab", "up", "down", "left", "right",
        "home", "end", "pageup", "pagedown", "ctrl+a", "ctrl+c", "ctrl+s", "ctrl+z", "backspace", "delete", "space"}
MUTATIONS = {"click", "type", "type_text", "keys", "scroll", "focus", "secondary", "drag", "launch"}


def validate_action(args: dict) -> None:
    action = args.get("action")
    allowed = {operation: set(properties) for operation, _, properties, _ in SPECS.values()}
    if not isinstance(action, str) or action not in allowed:
        raise ValueError("Unknown computer action")
    if set(args) - allowed[action] - {"action"}:
        raise ValueError("Arguments do not match computer action")
    required = next(required for operation, _, _, required in SPECS.values() if operation == action)
    if set(required) - set(args):
        raise ValueError("Missing required computer arguments: " + ", ".join(sorted(set(required) - set(args))))
    if action == "launch" and (not isinstance(args.get("app"), str) or not args["app"]):
        raise ValueError("launch needs app ID returned by computer_list_apps")
    if "query" in args and (not isinstance(args["query"], str) or len(args["query"]) > 200):
        raise ValueError("query must be text up to 200 characters")
    if action not in {"list", "apps", "capabilities", "launch"} and (type(args.get("window")) is not int or args["window"] <= 0):
        raise ValueError("window must be an ID returned by list")
    if action not in {"list", "apps", "capabilities", "launch", "window", "inspect"} and not isinstance(args.get("snapshot"), str):
        raise ValueError("Fresh snapshot required; inspect window first")
    if action == "click":
        if args.get("button", "left") not in {"left", "right", "middle"} or type(args.get("click_count", 1)) is not int or args.get("click_count", 1) not in {1, 2}:
            raise ValueError("click requires left/right/middle and click_count 1 or 2")
        has_element = "element" in args
        if has_element and ("x" in args or "y" in args):
            raise ValueError("Use element OR screenshot coordinates, not both")
        if not has_element and not all(type(args.get(k)) is int and args[k] >= 0 for k in ("x", "y")):
            raise ValueError("click needs element ID or screenshot x and y")
    if "element" in args and (type(args["element"]) is not int or args["element"] < 0):
        raise ValueError("Invalid element ID")
    if action in {"type", "type_text"} and ("element" not in args or not isinstance(args.get("text"), str) or len(args["text"]) > 10000):
        raise ValueError("type needs element ID and literal text (up to 10000 characters)")
    if action == "keys" and args.get("keys") not in KEYS:
        raise ValueError("Unsupported key/chord")
    if action == "scroll" and (args.get("direction") not in {"up", "down", "left", "right"} or type(args.get("amount", 1)) is not int or not 1 <= args.get("amount", 1) <= 5):
        raise ValueError("scroll needs up/down/left/right and amount 1..5")
    if action == "secondary" and ("element" not in args or args.get("operation") not in {"invoke", "toggle", "select", "expand", "collapse", "scroll_into_view"}):
        raise ValueError("secondary needs element and an advertised operation")
    if action == "drag" and not all(type(args.get(k)) is int and 0 <= args[k] <= 32767 for k in ("x", "y", "to_x", "to_y")):
        raise ValueError("drag needs screenshot-relative x/y/to_x/to_y coordinates")
    for key in ("include_text", "include_screenshot"):
        if key in args and type(args[key]) is not bool:
            raise ValueError(f"{key} must be boolean")


class ComputerController:
    """Short-lived UIA worker isolates hangs and keeps desktop control cancellable."""

    def __init__(self, worker: Callable | None = None) -> None:
        self._worker = worker or self._run_worker
        self._windows: set[int] = set()
        self._window_names: dict[int, str] = {}
        self._snapshot: dict | None = None
        self._snapshot_time = 0.0
        self.allow_coordinates = False
        self._apps: dict[str, str] = {}
        self._cursor = None
        self._cursor_enabled = worker is None
        self._cursor_point = None
        self._window_rects: dict[int, list[int]] = {}

    def close_cursor(self) -> None:
        cursor, self._cursor = self._cursor, None
        self._cursor_point = None
        if cursor is not None:
            try:
                cursor.close()
            except Exception:
                pass

    def _show_cursor(self, point, label: str) -> bool:
        if not self._cursor_enabled:
            return False
        point = point or self._cursor_point
        if point is None:
            return False
        try:
            if self._cursor is None:
                from openvino_chat.cursor_overlay import PersistentCursor
                self._cursor = PersistentCursor()
            shown = self._cursor.show(point, label)
            if shown:
                self._cursor_point = point
            return shown
        except Exception:
            return False

    def _cursor_target(self, args: dict, snapshot: dict | None):
        rect = self._window_rects.get(args.get("window"))
        if snapshot and snapshot.get("window") == args.get("window"):
            rect = snapshot.get("identity", {}).get("rect") or rect
            if "element" in args and args.get("operation") != "scroll_into_view":
                element = next((item for item in snapshot.get("elements", []) if item["element"] == args["element"]), {})
                box = element.get("rect")
                if box:
                    return ((box[0] + box[2]) // 2, (box[1] + box[3]) // 2)
            if "x" in args and rect:
                return (rect[0] + args["x"], rect[1] + args["y"])
        return (rect[0] + 18, rect[1] + 32) if rect else None

    def available_tools(self) -> set[str]:
        names = {"computer_capabilities", "computer_list_windows", "computer_list_apps"}
        if self._apps:
            names.add("computer_launch_app")
        if self._windows:
            names.update({"computer_get_window", "computer_get_window_state"})
        snapshot = self._snapshot
        if not snapshot or time.monotonic() - self._snapshot_time > 60:
            return names
        names.update({"computer_screenshot", "computer_activate_window"})
        actions = {action for element in snapshot.get("elements", [])
                   if not element.get("password") and element.get("enabled", True)
                   for action in element.get("actions", [])}
        if actions & {"invoke", "toggle", "select", "expand", "native_click"}:
            names.add("computer_click")
        if actions & {"invoke", "toggle", "select", "expand", "collapse", "scroll_into_view"}:
            names.add("computer_perform_secondary_action")
        if "set_value" in actions:
            names.add("computer_set_value")
        if "type_text" in actions:
            names.add("computer_type_text")
        if "native_keys" in actions:
            names.add("computer_press_key")
        if actions & {"scroll", "native_scroll"}:
            names.add("computer_scroll")
        if snapshot.get("image") and self.allow_coordinates:
            names.add("computer_click")
            if "native_drag" in actions:
                names.add("computer_drag")
        return names

    def describe(self, args: dict) -> str:
        if args["action"] == "apps":
            return "Read Start-menu and registered App Paths names and IDs; catalog may be incomplete."
        if args["action"] == "launch":
            return "Launch observed app: " + self._apps.get(args["app"], "unknown")
        if args["action"] == "list":
            return "Read titles and IDs of visible Windows apps."
        label = self._window_names.get(args.get("window"), "not observed")
        target = f"Observed window: {label} (ID {args.get('window')})"
        if self._snapshot and "element" in args:
            entry = next((e for e in self._snapshot["elements"] if e["element"] == args["element"]), None)
            if entry:
                target += f"\nObserved control: {entry['role']} / {entry['name']}"
        return target

    def preflight(self, args: dict) -> None:
        validate_action(args)
        action = args["action"]
        if action == "launch" and args["app"] not in self._apps:
            raise ValueError("App not in latest app catalog. Call computer_list_apps first.")
        if action not in {"list", "apps", "launch", "capabilities"} and args["window"] not in self._windows:
            raise ValueError("Window not in latest window list. Call computer list first.")
        snapshot = self._snapshot
        if action not in {"list", "apps", "launch", "capabilities", "window", "inspect"}:
            if not snapshot or args["snapshot"] != snapshot["id"] or args["window"] != snapshot["window"] or time.monotonic() - self._snapshot_time > 60:
                raise ValueError("Snapshot is stale. Inspect again; never reuse old element IDs.")
            if "x" in args and not snapshot.get("image"):
                raise ValueError("Coordinate click requires screenshot snapshot")
            if "x" in args and not self.allow_coordinates:
                raise ValueError("Coordinate clicks require a vision-capable model. Use inspect and element IDs.")
            if "element" in args:
                target = next((item for item in snapshot["elements"] if item["element"] == args["element"]), None)
                if target is None or target.get("password"):
                    raise ValueError("Element unavailable or protected. Inspect again.")

    def run(self, args: dict, stopped: Callable[[], bool] = lambda: False) -> tuple[str, tuple[Path, ...]]:
        self.preflight(args)
        if stopped():
            raise RuntimeError("interrupted")
        action = args["action"]
        if action == "capabilities":
            return json.dumps(capabilities()), ()
        snapshot = self._snapshot
        config = Path(os.environ.get("OPENVINO_CHAT_CONFIG", CONFIG_PATH)).expanduser()
        point = self._cursor_target(args, snapshot)
        shown = self._show_cursor(point, action)
        payload = {"args": args, "snapshot": snapshot, "exclude_pid": os.getpid(),
                   "persistent_cursor": shown,
                   "app_name": self._apps.get(args.get("app", "")),
                   "image_root": str(config.parent / "attachments" / "computer")}
        # A mutation consumes its observation even if the OS rejects it.
        if action in MUTATIONS or action in {"list", "inspect", "screenshot"}:
            self._snapshot = None
        try:
            result = self._worker(payload, stopped)
        except BaseException:
            self.close_cursor()
            raise
        if action == "list":
            self._windows = {item["window"] for item in result["windows"]}
            self._window_names = {item["window"]: item["title"] for item in result["windows"]}
        elif action == "apps":
            self._apps = {item["app"]: item["name"] for item in result["apps"]}
        elif action == "inspect":
            if not args.get("include_text", True):
                result["elements"] = []
            result["id"] = secrets.token_urlsafe(12)
            self._snapshot = result
            self._snapshot_time = time.monotonic()
            if result.get("title"):
                self._window_names[args["window"]] = result["title"]
        elif action == "screenshot":
            snapshot["image"] = result["image"]
            self._snapshot = snapshot
            result["snapshot"] = snapshot["id"]
        rect = result.get("identity", {}).get("rect") or result.get("rect")
        if rect and args.get("window"):
            self._window_rects[args["window"]] = rect
        self._show_cursor(point or self._cursor_target(args, self._snapshot), "waiting")
        public = {key: value for key, value in result.items() if key not in {"identity"}}
        if "elements" in public:
            public["elements"] = [{key: value for key, value in item.items() if key != "runtime_id"} for item in public["elements"]]
            if not args.get("include_text", True):
                public.pop("elements")
        media = (Path(result["image"]),) if result.get("image") else ()
        return json.dumps(public, ensure_ascii=False), media

    @staticmethod
    def _run_worker(payload: dict, stopped: Callable[[], bool]) -> dict:
        if os.name != "nt":
            raise RuntimeError("Computer-use tool currently supports Windows only")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        environment = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
        process = subprocess.Popen([sys.executable, "-B", "-m", "openvino_chat.computer_worker"],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, encoding="utf-8", creationflags=flags, env=environment)
        request = json.dumps(payload, ensure_ascii=False)
        deadline = time.monotonic() + 15
        try:
            while True:
                import ctypes
                key_down = lambda key: bool(ctypes.windll.user32.GetAsyncKeyState(key) & 0x8000)
                if stopped() or key_down(0x77) or all(key_down(key) for key in (0x12, 0x10, ord("S"))):
                    raise RuntimeError("interrupted")
                if time.monotonic() > deadline:
                    raise RuntimeError("Computer action timed out. Inspect current window before retrying.")
                try:
                    output, error = process.communicate(request, timeout=.1)
                    break
                except subprocess.TimeoutExpired:
                    request = None
            if process.returncode:
                raise RuntimeError(error.strip()[:1200] or "Computer worker failed")
            result = json.loads(output)
            if "error" in result:
                raise RuntimeError(result["error"])
            return result
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()
