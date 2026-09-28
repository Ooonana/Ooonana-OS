from __future__ import annotations

import json
import hashlib
import ntpath
from contextlib import redirect_stdout, nullcontext
import os
import re
import sys
import subprocess
from pathlib import Path
from collections import deque

from openvino_chat import computer_background as background
from openvino_chat.computer_cursor import marker


def _rect(control) -> list[int]:
    value = control.rectangle()
    return [value.left, value.top, value.right, value.bottom]


def _protected(window, exclude_pid: int) -> bool:
    title = window.window_text()
    return window.process_id() in {os.getpid(), exclude_pid} or bool(re.search(
        r"^(OpenVINO (?:Chat|/ Quack|agent cursor)|Quack\s*\|\s*OpenVINO|Windows Security|User Account Control)(?:$|\s|\|)", title, re.I))


def _process_basename(pid: int) -> str:
    """Read executable identity only; protected/exited processes remain unknown."""
    try:
        import ctypes
        from ctypes import wintypes
        import win32api

        query = ctypes.WinDLL("kernel32", use_last_error=True).QueryFullProcessImageNameW
        query.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                          ctypes.POINTER(wintypes.DWORD)]
        query.restype = wintypes.BOOL
        handle = win32api.OpenProcess(0x1000, False, pid)
        try:
            buffer = ctypes.create_unicode_buffer(32768)
            size = wintypes.DWORD(len(buffer))
            return ntpath.basename(buffer.value) if query(int(handle), 0, buffer, ctypes.byref(size)) else ""
        finally:
            win32api.CloseHandle(handle)
    except Exception:
        return ""


def _controls(window, status=None):
    status = status if status is not None else {}
    pending = deque([(window, 0)])
    count = 0
    while pending and count < 800:
        control, depth = pending.popleft()
        count += 1
        yield control, depth
        try:
            children = control.children()
        except Exception:
            status["truncated"] = True
            continue
        remaining = max(0, 800 - count - len(pending)) if depth < 18 else 0
        if len(children) > remaining:
            status["truncated"] = True
        pending.extend((child, depth + 1) for child in children[:remaining])


def _info(control, index, depth):
    info = control.element_info
    runtime_id = list(info.runtime_id or [])
    try:
        password = bool(info.element.CurrentIsPassword)
    except Exception:
        password = True
    supported = [] if password or not runtime_id else background.actions(control)
    value, state = (None, {}) if password else background.observed_state(control)
    return {"element": index, "name": "[password field]" if password else control.window_text()[:240],
            "role": info.control_type, "depth": depth, "rect": _rect(control),
            "enabled": control.is_enabled(), "password": password,
            "actions": supported,
            "value": value, "state": state,
            "runtime_id": runtime_id}


def _start_apps() -> list[dict]:
    command = "[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new(); @(Get-StartApps | Select-Object Name,AppID) | ConvertTo-Json -Compress"
    result = subprocess.run(["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command],
                            capture_output=True, text=True, encoding="utf-8", timeout=10,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode:
        raise RuntimeError("Installed-app catalog unavailable: " + result.stderr[:500])
    values = json.loads(result.stdout.lstrip("\ufeff") or "[]")
    if isinstance(values, dict):
        values = [values]
    if not isinstance(values, list):
        raise ValueError("Invalid Start-menu catalog")
    return [{"app": item["AppID"], "name": item["Name"], "source": "Start menu"}
            for item in values if isinstance(item, dict)
            and isinstance(item.get("AppID"), str) and item["AppID"]
            and isinstance(item.get("Name"), str) and item["Name"]]


def _registered_executable(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    if value.startswith('"') and value.endswith('"'):
        value = value[1:-1]
    # App Paths defaults are paths, never command lines or shell expressions.
    if ('"' in value or any(c in value for c in '\r\n\x00')
            or not re.match(r"^[A-Za-z]:[\\/]", value)
            or ntpath.splitext(value)[1].casefold() != ".exe"):
        return None
    path = ntpath.normpath(value)
    return path if Path(path).is_file() else None


def _app_paths(status: dict) -> list[dict]:
    import winreg

    apps = []
    subkey = r"Software\Microsoft\Windows\CurrentVersion\App Paths"
    for hive_name, hive in (("HKCU", winreg.HKEY_CURRENT_USER), ("HKLM", winreg.HKEY_LOCAL_MACHINE)):
        for bits, view in ((64, winreg.KEY_WOW64_64KEY), (32, winreg.KEY_WOW64_32KEY)):
            source = f"{hive_name} App Paths ({bits}-bit)"
            try:
                with winreg.OpenKey(hive, subkey, 0, winreg.KEY_READ | view) as root:
                    count = winreg.QueryInfoKey(root)[0]
                    if count > 4096:
                        status["unavailable_sources"].append(source + ": truncated")
                    for index in range(min(count, 4096)):
                        try:
                            name = winreg.EnumKey(root, index)
                            if not name.casefold().endswith(".exe"):
                                continue
                            with winreg.OpenKey(root, name, 0, winreg.KEY_READ | view) as entry:
                                value, kind = winreg.QueryValueEx(entry, None)
                            if kind not in (winreg.REG_SZ, winreg.REG_EXPAND_SZ):
                                continue
                            if kind == winreg.REG_EXPAND_SZ:
                                value = winreg.ExpandEnvironmentStrings(value)
                            executable = _registered_executable(value)
                            if executable is None:
                                continue
                            identity = ntpath.normcase(executable)
                            apps.append({"app": "app-path:" + hashlib.sha256(identity.encode("utf-8")).hexdigest(),
                                         "name": ntpath.splitext(name)[0], "executable": executable,
                                         "source": source})
                        except (OSError, ValueError, TypeError):
                            status["unavailable_sources"].append(source + ": unreadable entry")
                    status["sources"].append(source)
            except OSError:
                status["unavailable_sources"].append(source)
    return apps


def _catalog(status: dict | None = None) -> list[dict]:
    status = status if status is not None else {}
    status.update(sources=[], unavailable_sources=[])
    apps = []
    try:
        apps.extend(_start_apps())
        status["sources"].append("Start menu")
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
        status["unavailable_sources"].append("Start menu")
    try:
        apps.extend(_app_paths(status))
    except (ImportError, OSError):
        status["unavailable_sources"].append("App Paths registry")
    unique = {}
    for app in apps:
        key = ("exe", ntpath.normcase(app["executable"])) if "executable" in app else ("id", app["app"].casefold())
        unique.setdefault(key, app)
    status["unavailable_sources"] = list(dict.fromkeys(status["unavailable_sources"]))
    return sorted(unique.values(), key=lambda item: (item["name"].casefold(), item["app"]))


def _capture(window, payload):
    root = Path(payload["image_root"])
    root.mkdir(parents=True, exist_ok=True)
    target = root / f"window-{payload['exclude_pid']}.png"
    width, height = background.capture(window, target)
    return {"image": str(target), "width": width, "height": height, "capture": "PrintWindow; window not activated"}


def execute(payload: dict, desktop=None) -> dict:
    from openvino_chat.computer import validate_action
    args = payload["args"]
    validate_action(args)
    action = args["action"]
    if action == "capabilities":
        from openvino_chat.computer_schema import capabilities
        return capabilities()
    if action in {"apps", "launch"}:
        status = {}
        apps = _catalog(status)
        if action == "apps":
            query = args.get("query", "").casefold()
            matches = [item for item in apps if query in item["name"].casefold()]
            return {"apps": matches[:200], "truncated": len(matches) > 200,
                    "scope": "Start-menu registrations and existing local App Paths executables (HKCU/HKLM, 32/64-bit); not a full installed-app inventory",
                    "note": "No match means not discovered, not absent or closed. Portable/unregistered apps and unavailable sources may be missing. Use computer_list_windows for already running apps.",
                    **status}
        app = next((item for item in apps if item["app"] == args["app"]), None)
        if app is None or (payload.get("app_name") and app["name"] != payload["app_name"]):
            raise ValueError("App registration changed or is unavailable in current catalog. List apps again; this does not prove app absent.")
        command = [app["executable"]] if "executable" in app else ["explorer.exe", "shell:AppsFolder\\" + app["app"]]
        subprocess.Popen(command, shell=False, stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"app": app["app"], "requested": "launch", "verified": False, "next": "List windows, inspect exact launched app, then verify launch."}
    if desktop is None:
        try:
            from pywinauto import Desktop
        except ImportError:
            raise RuntimeError("Computer tools require pywinauto; run setup again") from None
        desktop = Desktop(backend="uia")
    windows = []
    for candidate in desktop.windows():
        try:
            if candidate.handle and candidate.is_visible() and not _protected(candidate, payload["exclude_pid"]):
                windows.append(candidate)
        except Exception:
            continue
    if action == "list":
        query = args.get("query", "").casefold()
        matches = []
        processes = {}
        for window in windows:
            try:
                title, pid = window.window_text(), window.process_id()
                if pid not in processes:
                    processes[pid] = _process_basename(pid)
                process = processes[pid]
                if query in title.casefold() or query in process.casefold():
                    matches.append({"window": window.handle, "title": title[:240],
                                    "pid": pid, "process": process})
            except Exception:
                continue
        return {"windows": matches[:80], "truncated": len(matches) > 80,
                "note": "Visible, unprotected windows only. Process basename may be unavailable; no match does not prove app absent or closed."}
    window = next((w for w in windows if w.handle == args["window"]), None)
    if window is None:
        raise ValueError("Window unavailable or protected. List windows again.")
    identity = {"pid": window.process_id(), "title": window.window_text(), "rect": _rect(window),
                "runtime_id": list(window.element_info.runtime_id or [])}
    if action == "window":
        return {"window": window.handle, "pid": identity["pid"], "title": identity["title"], "rect": identity["rect"], "next": "Get window state for element IDs and snapshot."}
    traversal = {}
    controls = list(_controls(window, traversal))
    for control, _depth in controls:
        if control.element_info.control_type == "Document" and re.search(r"^(OpenVINO Chat|Quack\s*\|\s*OpenVINO)$", control.window_text(), re.I):
            raise ValueError("OpenVINO's own embedded GUI is protected from computer control")
    if action == "inspect":
        elements = []
        for index, (control, depth) in enumerate(controls):
            try:
                elements.append(_info(control, index, depth))
            except Exception:
                traversal["truncated"] = True
                continue
        page_document_observed = any(item["role"] == "Document" for item in elements)
        query = args.get("query", "").casefold()
        elements = [item for item in elements if query in item["name"].casefold() and (item["name"] or item["actions"] or item["element"] == 0)]
        elements.sort(key=lambda item: (not bool(item["actions"]), item["element"]))
        result = {"window": window.handle, "title": identity["title"], "identity": identity,
                  "elements": elements[:160], "truncated": bool(traversal.get("truncated")) or len(elements) > 160,
                  "input_mode": "background; no physical mouse movement",
                  "note": "Choose advertised element action, then inspect again. Query filters a bounded tree; truncated means incomplete, not absent. Change app view or scroll observed container and inspect again. Password fields redacted."}
        process = _process_basename(identity["pid"]).casefold()
        if process in {"chrome.exe", "msedge.exe", "firefox.exe"}:
            result["page_document_observed"] = page_document_observed
            if not page_document_observed:
                result["note"] += " No browser page document appeared in this bounded snapshot. Do not claim page content, search results, or reviews from this observation."
        if args.get("include_screenshot"):
            result.update(_capture(window, payload))
        return result
    snapshot = payload["snapshot"]
    if identity != snapshot["identity"]:
        raise ValueError("Window moved or changed since observation. Inspect again.")
    selected = None
    if "element" in args:
        previous = next((item for item in snapshot["elements"] if item["element"] == args["element"]), None)
        if not previous or previous["password"] or not previous["runtime_id"]:
            raise ValueError("Element unavailable or protected")
        for index, (control, depth) in enumerate(controls):
            try:
                runtime_id = list(control.element_info.runtime_id or [])
            except Exception:
                continue
            if runtime_id == previous["runtime_id"]:
                current = _info(control, index, depth)
                if any(current.get(key) != previous.get(key) for key in ("name", "role", "rect", "password", "actions", "value", "state")):
                    raise ValueError("Element changed. Inspect again.")
                can_scroll_into_view = (action == "secondary" and args.get("operation") == "scroll_into_view"
                                        and "scroll_into_view" in current["actions"])
                if not current["enabled"] or (not control.is_visible() and not can_scroll_into_view):
                    raise ValueError("Element is not interactable")
                selected = control
                break
        if selected is None:
            raise ValueError("Element disappeared. Inspect again.")
    if selected is not None:
        current = _info(selected, previous["element"], previous["depth"])
        if any(current.get(key) != previous.get(key) for key in ("name", "role", "rect", "password", "runtime_id", "actions", "value", "state")):
            raise ValueError("Element changed while focusing. Inspect again.")
    if action == "screenshot":
        return {"window": window.handle, **_capture(window, payload)}
    if action == "focus":
        window.set_focus()
        return {"window": window.handle, "requested": "activate", "focus_changed": True, "next": "Inspect to verify window state."}
    rect = _rect(window)
    point, local_point = None, None
    if "x" in args:
        if not (args["x"] < rect[2] - rect[0] and args["y"] < rect[3] - rect[1]):
            raise ValueError("Coordinates outside selected window")
        selected, local_point = background.native_point(window, controls, args["x"], args["y"])
        if _info(selected, 0, 0)["password"]:
            raise ValueError("Password/unknown protection state at coordinate; input blocked")
        point = (rect[0] + args["x"], rect[1] + args["y"])
    elif selected is not None:
        box = _rect(selected)
        point = ((box[0] + box[2]) // 2, (box[1] + box[3]) // 2)
    backend = "UIA background"
    if selected is not None:
        background.validate_native_target(window, selected)
    with (nullcontext(True) if payload.get("persistent_cursor") else marker(point)) as marker_shown:
        if action == "click":
            backend = background.click(selected, args.get("button", "left"), args.get("click_count", 1), local_point)
        elif action in {"type", "type_text"}:
            if selected is None:
                raise ValueError("Observe editable element first")
            background.replace_text(selected, args["text"], append=action == "type_text")
        elif action == "keys":
            if selected is None:
                raise background.UnsupportedBackground("Background keys require observed element ID; shared keyboard focus is not used.")
            background.keys(selected, args["keys"])
        elif action == "scroll":
            background.scroll(selected or window, args["direction"], args.get("amount", 1))
        elif action == "secondary":
            if args["operation"] not in previous.get("actions", []):
                raise ValueError("Operation not advertised in snapshot; inspect again")
            background.perform(selected, args["operation"])
        elif action == "drag":
            if not (args["to_x"] < rect[2] - rect[0] and args["to_y"] < rect[3] - rect[1]):
                raise ValueError("Drag endpoint outside selected window")
            import win32gui
            end = win32gui.ScreenToClient(selected.handle, (rect[0] + args["to_x"], rect[1] + args["to_y"]))
            background.drag(selected, local_point, end)
            backend = "native drag messages; OLE drag/drop unsupported"
    return {"window": window.handle, "requested": action, "backend": backend, "verified": False,
            "agent_marker_shown": bool(marker_shown),
            "global_input_injected": False, "next": "Get window state and verify observed result before reporting success."}


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read(2 * 1024 * 1024))
        with redirect_stdout(sys.stderr):
            result = execute(payload)
    except Exception as exc:
        result = {"error": str(exc)}
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
