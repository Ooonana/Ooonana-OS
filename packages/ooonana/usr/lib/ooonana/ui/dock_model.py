"""Pure dock grouping/selection policy; no app launches, X11 or saved history."""
import json
import re

from ui_preferences import write_json

NATIVE_TITLES = {"Ooonana " + name for name in (
    "AI", "Settings", "Control Center", "Wi-Fi", "Bluetooth", "Task Manager", "Health", "Updates",
    "Setup", "Notifications", "Packages", "Music", "Controls", "Sound", "Brightness", "Power", "Spotlight")}

PREFERRED_CLASSES = {
    "terminal": {"xterm", "uxterm"}, "browser": {"chromium", "chromium-browser"},
    "files": {"nemo"}, "editor": {"geany"},
}


def app_groups(items, nodes, pin_for):
    by_window = {node.get("window"): item for item in items
                 if (node := nodes.get(item[0], {})).get("window")}
    groups, hints = {}, {}
    for item in items:
        owner, seen = item, set()
        # Dialogs belong to their actual parent, not a second generic GTK app.
        while owner[0] not in seen:
            seen.add(owner[0])
            props = nodes.get(owner[0], {}).get("window_properties") or {}
            parent = by_window.get(props.get("transient_for"))
            if parent is None or parent[0] in seen:
                break
            owner = parent
        props = nodes.get(owner[0], {}).get("window_properties") or {}
        klass = owner[4] if len(owner) > 4 else ""
        pin = pin_for(owner)
        role = str(props.get("window_role", ""))
        if pin in ("apps", "music", "tasks", "openvino") or klass in PREFERRED_CLASSES.get(pin, ()):
            key, hint = pin, ""
        elif klass == "ooonanaapp" and role.startswith("ooonana-"):
            key, hint = role, role.replace("-", " ").title()
        elif klass == "ooonanaapp" and owner[1] in NATIVE_TITLES:
            # Existing windows from before stable native roles were introduced.
            key, hint = owner[1].casefold().replace(" ", "-"), owner[1]
        elif klass:
            key, hint = "class:" + klass, str(props.get("class") or klass)
        else:
            key, hint = "window:" + str(owner[0]), owner[1]
        groups.setdefault(key, []).append(item)
        hints[key] = hint
    return groups, hints


def visible_groups(groups, pins, width):
    """Prefer running apps over idle launchers; overflow only when space runs out."""
    # 48px targets +4px gaps, 12px frame, separator, 12px screen clearance.
    capacity = max(2, (width - 44) // 52)
    keys = pins + [key for key in groups if key not in pins]
    if len(keys) <= capacity:
        return keys, []
    visible = list(keys)
    for key in list(reversed(visible)):
        if len(visible) <= capacity - 1:
            break
        if key != "apps" and not groups.get(key):
            visible.remove(key)
    visible = visible[:capacity - 1]
    return visible + ["other"], [key for key in keys if key not in visible]


def click_target(items, recent):
    """App click raises one existing window; never minimizes or restores siblings."""
    focused = next((item for item in items if item[2]), None)
    if focused:
        return focused
    candidates = [item for item in items if not item[3]] or items
    return next((item for identifier in recent for item in candidates if item[0] == identifier),
                candidates[0] if candidates else None)


def stable_key(key):
    return (isinstance(key, str) and 0 < len(key) <= 256 and key.isprintable()
            and (key.startswith("class:") and len(key) > 6
                 or re.fullmatch(r"ooonana-[a-z0-9-]+", key)
                 or key in {"terminal", "browser", "files", "editor", "music", "openvino", "tasks"}))


class PinStore:
    """Atomic per-user app IDs/order only. Never persist windows, commands or PIDs."""
    def __init__(self, path, defaults):
        self.path, self.records, self.order = path, list(defaults), []
        self.error, self.load_failed = "", False
        try:
            with path.open(encoding="utf-8") as stream:
                raw = stream.read(65537)
            if len(raw) > 65536:
                raise ValueError("Dock preferences too large")
            data = json.loads(raw)
            if not isinstance(data, dict) or type(data.get("version")) is not int or data["version"] != 1:
                raise ValueError("Unsupported dock preferences")
            self.records, self.order = self.validate(data.get("pins"), data.get("order"))
        except FileNotFoundError:
            pass
        except (OSError, ValueError, TypeError, RecursionError) as exc:
            self.error, self.load_failed = str(exc), True

    @staticmethod
    def validate(records, order):
        if not isinstance(records, list) or len(records) > 64 or not isinstance(order, list) or len(order) > 128:
            raise ValueError("Invalid dock layout")
        result, seen = [], set()
        for record in records:
            if not isinstance(record, dict) or not stable_key(record.get("key")) or record["key"] in seen:
                raise ValueError("Invalid/duplicate dock pin")
            key, desktop = record["key"], record.get("desktop")
            if desktop is not None and (not isinstance(desktop, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,240}\.desktop", desktop)):
                raise ValueError("Invalid dock application ID")
            if key.startswith(("class:", "ooonana-")) and desktop is None:
                raise ValueError("Pinned app needs a desktop launcher")
            seen.add(key)
            result.append({"key": key, **({"desktop": desktop} if desktop else {})})
        if len(set(order)) != len(order) or not all(stable_key(key) for key in order):
            raise ValueError("Invalid running-app order")
        return result, list(order)

    def save(self, records, order=None):
        try:
            if self.load_failed:
                raise ValueError("Repair dock.json and restart dock before saving; unreadable preferences retained")
            records, order = self.validate(records, self.order if order is None else order)
            write_json(self.path, {"version": 1, "pins": records, "order": order})
        except (OSError, ValueError, TypeError) as exc:
            self.error = str(exc)
            return False
        self.records, self.order, self.error = records, order, ""
        return True
