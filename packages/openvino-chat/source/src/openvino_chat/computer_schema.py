"""Public desktop tools and their mapping to the shared computer controller."""
from __future__ import annotations

from copy import deepcopy


WINDOW = {"type": "integer", "minimum": 1, "description": "Exact window ID from computer_list_windows. Not a title, PID, or guessed handle."}
SNAPSHOT = {"type": "string", "description": "Exact fresh snapshot id from computer_get_window_state; one mutation consumes it. Reinspect after acting."}
ELEMENT = {"type": "integer", "minimum": 0, "description": "Element ID from that snapshot. Prefer this over coordinates; check its actions list."}
TEXT = {"type": "string", "description": "Literal text, up to 10000 characters; never key syntax, passwords, or secret tokens."}
QUERY = {"type": "string", "description": "Optional case-insensitive app name, window title, or process-name filter; plain text, not regex."}
POINT = {"type": "integer", "minimum": 0, "maximum": 32767, "description": "Pixel coordinate relative to captured window, not desktop. Requires fresh screenshot and vision support."}
BASE = {"window": WINDOW, "snapshot": SNAPSHOT}

# name: (controller action, description, properties, required)
SPECS = {
    "computer_capabilities": ("capabilities", "Describe OpenVINO desktop-control support and limits without interacting. This controls Windows apps, NOT OpenVINO inference devices. Background actions never move user's mouse; unsupported operations fail explicitly.", {}, []),
    "computer_list_windows": ("list", "Find currently visible desktop windows by title or process basename, such as chrome.exe. Returns window IDs, titles, PIDs, process names. First call for an already-open app. No mouse or focus change. Requires approval.", {"query": QUERY}, []),
    "computer_list_apps": ("apps", "List Start-menu and registered App Paths entries. Catalog is incomplete: no match does not prove an app is absent or closed. Check computer_list_windows for running apps. Requires approval.", {"query": QUERY}, []),
    "computer_launch_app": ("launch", "Request launch of an app ID returned by computer_list_apps, without arbitrary command arguments. Then list windows and inspect newly opened app. Launch may focus new app, never moves mouse. Requires approval.", {"app": {"type": "string", "description": "Exact installed app ID from latest computer_list_apps result; not an invented executable or shell command."}}, ["app"]),
    "computer_get_window": ("window", "Refresh title, PID and bounds for one previously listed window. Does not produce actionable element IDs; use computer_get_window_state next. Requires approval.", {"window": WINDOW}, ["window"]),
    "computer_get_window_state": ("inspect", "Observe accessibility text, element IDs, supported actions and snapshot id. No mouse/focus change. Include screenshot only when needed. Prefer returned element actions for background control. Requires approval.", {"window": WINDOW, "include_text": {"type": "boolean", "description": "Include accessible text and controls; defaults true."}, "include_screenshot": {"type": "boolean", "description": "Capture window without activating it; defaults false. Some apps cannot capture in background."}, "query": QUERY}, ["window"]),
    "computer_screenshot": ("screenshot", "Capture selected window without activating it. Returns image and same snapshot id with capture attached; it does not refresh element freshness. Capture may be unsupported/blank for some apps. Text-only models cannot infer pixels. Requires approval.", BASE, ["window", "snapshot"]),
    "computer_click": ("click", "Activate observed element in background using its supported action. For Win32 controls, screenshot coordinates support left/right/middle and double click. Never moves physical mouse. Dispatched input is not proof of task success: inspect afterward. Requires approval.", {**BASE, "element": ELEMENT, "x": POINT, "y": POINT, "button": {"type": "string", "enum": ["left", "right", "middle"], "description": "Mouse button; default left. UIA element actions support single left click only."}, "click_count": {"type": "integer", "minimum": 1, "maximum": 2, "description": "1 or 2; defaults 1. Double-click requires supported native message control."}}, ["window", "snapshot"]),
    "computer_type_text": ("type_text", "Insert literal text into observed editable control without global typing/focus changes. Uses native selection when available; otherwise appends through Value pattern. Use set_value to replace all text. Requires approval.", {**BASE, "element": ELEMENT, "text": TEXT}, ["window", "snapshot", "element", "text"]),
    "computer_set_value": ("type", "Replace ALL contents of an observed editable control with literal text via accessibility Value pattern. Not append. Password/read-only controls blocked. Requires approval.", {**BASE, "element": ELEMENT, "text": TEXT}, ["window", "snapshot", "element", "text"]),
    "computer_press_key": ("keys", "Send supported background key to observed native control, or Enter to invokable button. Arbitrary global chords are NOT supported; modifier shortcuts may be unavailable. Never injects global keyboard input. Inspect result. Requires approval.", {**BASE, "element": ELEMENT, "keys": {"type": "string", "description": "One key: enter, escape, tab, up, down, left, right, home, end, pageup, pagedown, backspace, delete, space. ctrl+a/ctrl+z supported only in native Edit controls; other chords fail explicitly."}}, ["window", "snapshot", "element", "keys"]),
    "computer_scroll": ("scroll", "Scroll observed scrollable element up/down/left/right using Scroll pattern or supported native messages, without moving mouse. Amount is 1..5 small increments. Requires approval.", {**BASE, "element": ELEMENT, "direction": {"type": "string", "enum": ["up", "down", "left", "right"], "description": "Scroll direction."}, "amount": {"type": "integer", "minimum": 1, "maximum": 5, "description": "Small increments, defaults 1."}}, ["window", "snapshot", "element", "direction"]),
    "computer_drag": ("drag", "Dispatch window-relative drag to supported Win32 native controls using background messages. Does NOT move user's pointer. OLE drag/drop and apps needing physical input are unsupported. Must inspect afterward; message delivery alone is not success. Requires approval.", {**BASE, "x": POINT, "y": POINT, "to_x": POINT, "to_y": POINT}, ["window", "snapshot", "x", "y", "to_x", "to_y"]),
    "computer_perform_secondary_action": ("secondary", "Perform an exact action advertised by an observed element: invoke, toggle, select, expand, collapse, scroll_into_view. No guessed actions. Uses background accessibility patterns. Requires approval.", {**BASE, "element": ELEMENT, "operation": {"type": "string", "enum": ["invoke", "toggle", "select", "expand", "collapse", "scroll_into_view"], "description": "One action from element.actions returned by state inspection."}}, ["window", "snapshot", "element", "operation"]),
    "computer_activate_window": ("focus", "Explicitly bring observed window to foreground. This changes keyboard focus, unlike other background actions, but does not move mouse. Only use when user needs window visible. Requires approval.", BASE, ["window", "snapshot"]),
}

DEFINITIONS = [
    {"type": "function", "function": {"name": name, "description": description,
      "parameters": {"type": "object", "properties": deepcopy(properties), "required": required, "additionalProperties": False}}}
    for name, (_action, description, properties, required) in SPECS.items()
]


def action_args(name: str, args: dict) -> dict:
    return {**args, "action": SPECS[name][0]}


def capabilities() -> dict:
    return {
        "platform": "Windows", "input_mode": "background-first; physical pointer never moved",
        "permissions": "Ask by default; human can confirm session/Always access. Alt+Shift+S stops current work and pauses queue. Auto access requires registered shortcut. /computer ask revokes it.",
        "tools": list(SPECS), "agent_cursor": "visual click-through marker, not a second OS pointer",
        "supported": ["UIA invoke/toggle/select/expand/collapse/value/scroll", "Win32 message clicks, text, limited keys and drag", "installed-app discovery and launch", "window metadata and background capture"],
        "limits": ["Not identical to Codex runtime", "Some apps reject background input/capture", "No OLE drag/drop or arbitrary global keyboard shortcuts", "No secure desktop, elevation, passwords or self-approval", "Full independent input across all apps requires isolated Windows session or VM"],
        "workflow": "list windows -> get window state -> one supported action -> get window state to verify; app not running: list apps -> launch -> list windows",
    }
