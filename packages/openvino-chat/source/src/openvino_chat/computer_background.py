"""Window-scoped operations. Never use SendInput, SetCursorPos or global keys."""
from __future__ import annotations

import ctypes


class UnsupportedBackground(RuntimeError):
    pass


def pattern(control, name):
    try:
        return getattr(control, "iface_" + name)
    except Exception:
        return None


def actions(control) -> list[str]:
    result = []
    for interface, names in (
        ("invoke", ["invoke"]), ("toggle", ["toggle"]), ("selection_item", ["select"]),
        ("expand_collapse", ["expand", "collapse"]), ("scroll_item", ["scroll_into_view"]),
        ("scroll", ["scroll"]), ("value", ["set_value", "type_text"]),
    ):
        value = pattern(control, interface)
        if value is not None:
            if interface == "value" and control.element_info.control_type not in {"Edit", "ComboBox", "Document"}:
                continue
            if interface == "value" and bool(value.CurrentIsReadOnly):
                continue
            result.extend(names)
    kind = native_kind(control)
    if kind:
        result.extend(["native_click", "native_drag", "native_keys"])
        if kind in {"edit", "listbox", "syslistview32", "systreeview32", "scrollbar"} or kind.startswith("richedit"):
            result.append("native_scroll")
    return result


def observed_state(control) -> tuple[str | None, dict]:
    value, state = None, {}
    interface = pattern(control, "value")
    if interface is not None:
        value = str(interface.CurrentValue)[:10000]
        state["read_only"] = bool(interface.CurrentIsReadOnly)
    for name, property_name, key in (("toggle", "CurrentToggleState", "toggle"),
                                     ("selection_item", "CurrentIsSelected", "selected"),
                                     ("expand_collapse", "CurrentExpandCollapseState", "expanded")):
        interface = pattern(control, name)
        if interface is not None:
            state[key] = int(getattr(interface, property_name))
    return value, state


def native_kind(control) -> str:
    if not getattr(control, "handle", None):
        return ""
    name = str(getattr(control.element_info, "class_name", "")).lower()
    if name.startswith("windowsforms10."):
        name = name.split(".")[1]
    allowed = {"button", "edit", "combobox", "listbox", "syslistview32", "systreeview32", "systabcontrol32", "scrollbar"}
    return name if name in allowed or name.startswith("richedit") else ""


def perform(control, operation: str) -> None:
    operations = {"invoke": ("invoke", "Invoke"), "toggle": ("toggle", "Toggle"),
                  "select": ("selection_item", "Select"), "expand": ("expand_collapse", "Expand"),
                  "collapse": ("expand_collapse", "Collapse"), "scroll_into_view": ("scroll_item", "ScrollIntoView")}
    interface, method = operations[operation]
    value = pattern(control, interface)
    if value is None:
        raise UnsupportedBackground(f"Element does not support {operation}. Inspect its actions list; physical input was not used.")
    getattr(value, method)()


def replace_text(control, text: str, append: bool = False) -> None:
    if control.element_info.control_type not in {"Edit", "ComboBox", "Document"}:
        raise UnsupportedBackground("Target is not an editable text control")
    value = pattern(control, "value")
    if value is None or value.CurrentIsReadOnly:
        raise UnsupportedBackground("Editable Value pattern unavailable/read-only; text was not sent.")
    if append and native_kind(control) in {"edit", "richedit20w", "richedit50w"}:
        buffer = ctypes.create_unicode_buffer(text)
        send(control.handle, 0x00C2, 1, ctypes.addressof(buffer))  # EM_REPLACESEL, marshalled by Windows.
    else:
        value.SetValue((str(value.CurrentValue) if append else "") + text)


def send(hwnd: int, message: int, wparam: int = 0, lparam: int = 0) -> int:
    from ctypes import wintypes
    import win32gui
    if hwnd in {0, -1, 0xffff} or not win32gui.IsWindow(hwnd):
        raise UnsupportedBackground("Invalid/broadcast window handle; no message sent")
    fn = ctypes.windll.user32.SendMessageTimeoutW
    fn.argtypes = [wintypes.HWND, wintypes.UINT, ctypes.c_size_t, ctypes.c_ssize_t,
                   wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_size_t)]
    fn.restype = ctypes.c_ssize_t
    result = ctypes.c_size_t()
    if not fn(hwnd, message, wparam, lparam, 0x22, 1000, ctypes.byref(result)):
        raise UnsupportedBackground("Target rejected or timed out on background message. Reinspect; no physical-input fallback.")
    return result.value


def validate_native_target(window, control) -> None:
    if native_kind(control):
        import win32gui
        if not win32gui.IsWindow(control.handle) or win32gui.GetAncestor(control.handle, 2) != window.handle:
            raise UnsupportedBackground("Native control is outside approved window; no message sent")


def native_point(window, controls, x: int, y: int):
    import win32gui
    rect = window.rectangle()
    screen = (rect.left + x, rect.top + y)
    choices = []
    for control, _depth in controls:
        box = control.rectangle()
        if native_kind(control) and control.is_visible() and control.is_enabled() and box.left <= screen[0] < box.right and box.top <= screen[1] < box.bottom:
            if win32gui.GetAncestor(control.handle, 2) == window.handle:
                choices.append(((box.right - box.left) * (box.bottom - box.top), control))
    if not choices:
        raise UnsupportedBackground("No supported native control at screenshot coordinate. Use an advertised element action or an isolated desktop.")
    control = min(choices, key=lambda item: item[0])[1]
    return control, win32gui.ScreenToClient(control.handle, screen)


def packed(point) -> int:
    return (int(point[0]) & 0xffff) | ((int(point[1]) & 0xffff) << 16)


def click(control, button="left", count=1, point=None) -> str:
    if button == "left" and count == 1 and point is None:
        for operation in ("invoke", "toggle", "select", "expand"):
            if operation in actions(control):
                perform(control, operation)
                return "UIA " + operation
    if not native_kind(control):
        raise UnsupportedBackground("Element has no compatible background click. Physical cursor was not moved.")
    if point is None:
        import win32gui
        left, top, right, bottom = win32gui.GetClientRect(control.handle)
        point = ((right - left) // 2, (bottom - top) // 2)
    down, up, double, flag = {"left": (0x201, 0x202, 0x203, 1), "right": (0x204, 0x205, 0x206, 2), "middle": (0x207, 0x208, 0x209, 16)}[button]
    pressed = False
    try:
        pressed = True
        send(control.handle, down, flag, packed(point))
        send(control.handle, up, 0, packed(point))
        pressed = False
        if count == 2:
            pressed = True
            send(control.handle, double, flag, packed(point))
            send(control.handle, up, 0, packed(point))
            pressed = False
    finally:
        if pressed:
            send(control.handle, up, 0, packed(point))
    return "native messages dispatched; verify observable result"


def keys(control, key: str) -> None:
    if key == "enter" and "invoke" in actions(control):
        return perform(control, "invoke")
    kind = native_kind(control)
    if not kind:
        raise UnsupportedBackground("Background keys unavailable for this control; no global keyboard input was sent.")
    if key == "ctrl+a" and (kind == "edit" or kind.startswith("richedit")):
        send(control.handle, 0x00B1, 0, -1)  # EM_SETSEL
        return
    if key == "ctrl+z" and (kind == "edit" or kind.startswith("richedit")):
        send(control.handle, 0x00C7)  # EM_UNDO
        return
    values = {"enter": 13, "escape": 27, "tab": 9, "up": 38, "down": 40, "left": 37,
              "right": 39, "home": 36, "end": 35, "pageup": 33, "pagedown": 34,
              "backspace": 8, "delete": 46, "space": 32}
    if key not in values:
        raise UnsupportedBackground("This shortcut requires shared keyboard state. Use a semantic action or isolated session; no global keys sent.")
    value = values[key]
    send(control.handle, 0x100, value, 1)
    try:
        if value in {8, 9, 13, 32}:
            send(control.handle, 0x102, value, 1)
    finally:
        send(control.handle, 0x101, value, 0xC0000001)


def scroll(control, direction: str, amount: int) -> None:
    value = pattern(control, "scroll")
    if value is not None:
        horizontal = direction in {"left", "right"}
        delta = 1 if direction in {"up", "left"} else 4  # UIA small decrement/increment; 2 = no amount.
        for _ in range(amount):
            value.Scroll(delta if horizontal else 2, 2 if horizontal else delta)
        return
    if not native_kind(control):
        raise UnsupportedBackground("Scroll pattern/native scrolling unavailable. Cursor was not moved.")
    for _ in range(amount):
        send(control.handle, 0x114 if direction in {"left", "right"} else 0x115,
             0 if direction in {"up", "left"} else 1)


def drag(control, start, end) -> None:
    if not native_kind(control):
        raise UnsupportedBackground("Background drag requires native message control. OLE drag/drop is unsupported.")
    send(control.handle, 0x201, 1, packed(start))
    try:
        for step in range(1, 9):
            point = (round(start[0] + (end[0] - start[0]) * step / 8), round(start[1] + (end[1] - start[1]) * step / 8))
            send(control.handle, 0x200, 1, packed(point))
    finally:
        send(control.handle, 0x202, 0, packed(end))


def capture(window, target):
    import win32gui
    import win32ui
    from ctypes import wintypes
    from PIL import Image
    rect = window.rectangle()
    width, height = rect.right - rect.left, rect.bottom - rect.top
    if not (0 < width <= 8192 and 0 < height <= 8192):
        raise UnsupportedBackground("Unsupported capture dimensions")
    dc = win32gui.GetWindowDC(window.handle)
    source = win32ui.CreateDCFromHandle(dc)
    memory = source.CreateCompatibleDC()
    bitmap = win32ui.CreateBitmap()
    old = None
    try:
        bitmap.CreateCompatibleBitmap(source, width, height)
        old = memory.SelectObject(bitmap)
        fn = ctypes.windll.user32.PrintWindow
        fn.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
        fn.restype = wintypes.BOOL
        if not fn(window.handle, memory.GetSafeHdc(), 0):
            raise UnsupportedBackground("App does not support background capture. No foreground/screen-scraping fallback used.")
        picture = Image.frombuffer("RGB", (width, height), bitmap.GetBitmapBits(True), "raw", "BGRX", 0, 1)
        if all(low == high for low, high in picture.getextrema()):
            raise UnsupportedBackground("Background capture returned blank image. Use accessibility state instead.")
        picture.save(target)
        return width, height
    finally:
        if old is not None:
            memory.SelectObject(old)
        win32gui.DeleteObject(bitmap.GetHandle())
        memory.DeleteDC()
        win32gui.ReleaseDC(window.handle, dc)
