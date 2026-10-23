"""Bounded, toolkit-free StatusNotifier input normalization."""
import re

MAX_ITEMS = 64


def text(value, limit=256):
    return " ".join("".join(char for char in value if char.isprintable()).split())[:limit] if isinstance(value, str) else ""


def address(value, sender=None):
    if not isinstance(value, str) or len(value) > 1024:
        raise ValueError("Invalid indicator address")
    if value.startswith("/"):
        bus, path = sender, value
    else:
        bus, separator, tail = value.partition("/")
        path = "/" + tail if separator else "/StatusNotifierItem"
    if not isinstance(bus, str) or len(bus) > 255 or not re.fullmatch(r"(?::[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)+|[A-Za-z_-][A-Za-z0-9_-]*(?:\.[A-Za-z_-][A-Za-z0-9_-]*)+)", bus):
        raise ValueError("Invalid indicator service")
    if path != "/" and not re.fullmatch(r"(?:/[A-Za-z0-9_]+)+", path):
        raise ValueError("Invalid indicator object path")
    return bus, path


def properties(values):
    result = {key: text(values.get(key), 512 if key == "Title" else 256)
              for key in ("Title", "Id", "IconName", "AttentionIconName", "Status")}
    result["ItemIsMenu"] = values.get("ItemIsMenu") is True
    menu = values.get("Menu")
    result["Menu"] = menu if isinstance(menu, str) and len(menu) <= 1024 and re.fullmatch(r"(?:/[A-Za-z0-9_]+)+", menu) else ""
    tip = values.get("ToolTip")
    result["ToolTip"] = text(tip[2], 512) + ("\n" + text(tip[3], 2048) if len(tip) > 3 else "") if isinstance(tip, (tuple, list)) and len(tip) >= 3 else ""
    return result


def pixmap(values, desired=24):
    candidates = []
    if not isinstance(values, (tuple, list)):
        return None
    for value in values[:16]:
        if not isinstance(value, (tuple, list)) or len(value) != 3:
            continue
        width, height, data = value
        if type(width) is not int or type(height) is not int or not 1 <= width <= 256 or not 1 <= height <= 256:
            continue
        if not isinstance(data, (bytes, bytearray, list, tuple)) or len(data) != width * height * 4:
            continue
        try:
            raw = bytes(data)
        except (TypeError, ValueError):
            continue
        candidates.append((abs(max(width, height) - desired), width, height, raw))
    if not candidates:
        return None
    _, width, height, raw = min(candidates, key=lambda value: value[0])
    rgba = bytearray(len(raw))
    rgba[0::4], rgba[1::4], rgba[2::4], rgba[3::4] = raw[1::4], raw[2::4], raw[3::4], raw[0::4]
    return width, height, bytes(rgba)


def menu_nodes(node, remaining=None, depth=0):
    """Truncate foreign menus, reject duplicate IDs, retain native item semantics."""
    if remaining is None:
        remaining = {"count": 128, "ids": set()}
    if hasattr(node, "unpack"):
        node = node.unpack()
    if depth > 3 or remaining["count"] <= 0 or not isinstance(node, (list, tuple)) or len(node) != 3:
        return None
    identifier, props, children = node
    if type(identifier) is not int or not -(2**31) <= identifier < 2**31 or identifier in remaining["ids"] or not isinstance(props, dict):
        return None
    remaining["count"] -= 1; remaining["ids"].add(identifier)
    props = {key: value.unpack() if hasattr(value, "unpack") else value for key, value in props.items()}
    if props.get("visible", True) is False:
        return None
    return {"id": identifier, "label": text(props.get("label"), 256), "enabled": props.get("enabled", True) is True,
            "separator": props.get("type") == "separator", "toggle": props.get("toggle-type", "") if props.get("toggle-type") in ("checkmark", "radio") else "",
            "checked": props.get("toggle-state") == 1,
            "children": [result for child in children[:128] if (result := menu_nodes(child, remaining, depth + 1))]
                        if isinstance(children, (list, tuple)) else []}
