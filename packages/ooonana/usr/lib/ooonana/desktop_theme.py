"""Managed i3 frame resources; preserve other X resources and live window state."""
import ctypes
import os
import re
import socket
import sys

import i3_events

LIMIT = 1024 * 1024
MARKER = "# Ooonana managed frame palette v1"
PALETTES = {
    "dark": {"focused": ("#1b1f26", "#ffb21a", "#ffb21a"),
             "unfocused": ("#101317", "#b4bdc8", "#414957"),
             "focused_inactive": ("#171b21", "#b4bdc8", "#414957"),
             "urgent": ("#3b2324", "#ff675c", "#ff675c")},
    "light": {"focused": ("#ffffff", "#805600", "#805600"),
              "unfocused": ("#e9edf1", "#55616e", "#adb7c2"),
              "focused_inactive": ("#f5f5f7", "#55616e", "#adb7c2"),
              "urgent": ("#fae9e7", "#9e2929", "#9e2929")},
}


def resources(theme):
    return {f"ooonana.i3.{state}.{role}": color
            for state, colors in PALETTES[theme].items()
            for role, color in zip(("background", "text", "indicator"), colors)}


def merge_resources(original, theme):
    """Replace only twelve owned logical records, retaining comments/continuations."""
    original = original or b""
    if len(original) > LIMIT or b"\0" in original or original.rstrip(b"\r\n").endswith(b"\\"):
        raise ValueError("X resources too large or ending in an unfinished continuation")
    values = resources(theme)
    owned = {key.encode() for key in values}
    kept, group = [], []
    for line in original.splitlines(keepends=True):
        group.append(line)
        body = line.rstrip(b"\r\n")
        if (len(body) - len(body.rstrip(b"\\"))) % 2 and line.endswith(b"\n"):
            continue
        match = re.match(rb"\s*([^!#\s:]+)\s*:", group[0])
        if not match or match.group(1) not in owned:
            kept.extend(group)
        group = []
    if group:
        raise ValueError("Unfinished X resource record")
    content = b"".join(kept)
    if content and not content.endswith(b"\n"):
        content += b"\n"
    content += b"".join(f"{key}: {color}\n".encode() for key, color in values.items())
    if len(content) > LIMIT:
        raise ValueError("Merged X resources exceed safe limit")
    return content


class XResources:
    def __init__(self):
        self.lib = ctypes.CDLL("libX11.so.6")
        pointer, ulong = ctypes.c_void_p, ctypes.c_ulong
        self.lib.XOpenDisplay.argtypes = [ctypes.c_char_p]
        self.lib.XOpenDisplay.restype = pointer
        self.lib.XDefaultRootWindow.argtypes = [pointer]
        self.lib.XDefaultRootWindow.restype = ulong
        self.lib.XInternAtom.argtypes = [pointer, ctypes.c_char_p, ctypes.c_int]
        self.lib.XInternAtom.restype = ulong
        self.lib.XGetWindowProperty.argtypes = [pointer, ulong, ulong, ctypes.c_long, ctypes.c_long,
            ctypes.c_int, ulong, ctypes.POINTER(ulong), ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ulong), ctypes.POINTER(ulong), ctypes.POINTER(pointer)]
        self.lib.XGetWindowProperty.restype = ctypes.c_int
        self.lib.XChangeProperty.argtypes = [pointer, ulong, ulong, ulong, ctypes.c_int,
                                           ctypes.c_int, pointer, ctypes.c_int]
        self.lib.XDeleteProperty.argtypes = [pointer, ulong, ulong]
        for name in ("XCloseDisplay", "XGrabServer", "XUngrabServer", "XFlush"):
            getattr(self.lib, name).argtypes = [pointer]
        self.lib.XSync.argtypes = [pointer, ctypes.c_int]
        self.lib.XFree.argtypes = [pointer]
        self.display = self.lib.XOpenDisplay(None)
        if not self.display:
            raise OSError("X11 display unavailable")
        self.root = self.lib.XDefaultRootWindow(self.display)

    def close(self):
        self.lib.XCloseDisplay(self.display)

    def read(self, name):
        atom = self.lib.XInternAtom(self.display, name.encode(), 1)
        if not atom:
            return None
        kind, size, count, remaining, data = ctypes.c_ulong(), ctypes.c_int(), ctypes.c_ulong(), ctypes.c_ulong(), ctypes.c_void_p()
        result = self.lib.XGetWindowProperty(self.display, self.root, atom, 0, LIMIT // 4,
            0, 0, ctypes.byref(kind), ctypes.byref(size), ctypes.byref(count), ctypes.byref(remaining), ctypes.byref(data))
        try:
            accepted = (31,)
            if name == "I3_SOCKET_PATH":
                accepted += (self.lib.XInternAtom(self.display, b"UTF8_STRING", 1),)
            if result or remaining.value or (kind.value and (kind.value not in accepted or size.value != 8)):
                raise ValueError(name + " unavailable, oversized or not a text property")
            return ctypes.string_at(data, count.value) if kind.value else None
        finally:
            if data:
                self.lib.XFree(data)

    def replace(self, name, expected, content):
        # Compare-and-swap only. Never overwrite another resource writer.
        self.lib.XGrabServer(self.display)
        try:
            if self.read(name) != expected:
                return False
            atom = self.lib.XInternAtom(self.display, name.encode(), 0)
            if content is None:
                self.lib.XDeleteProperty(self.display, self.root, atom)
            else:
                buffer = ctypes.create_string_buffer(content)
                self.lib.XChangeProperty(self.display, self.root, atom, 31, 8, 0, buffer, len(content))
            self.lib.XSync(self.display, 0)
            return True
        finally:
            self.lib.XUngrabServer(self.display)
            self.lib.XFlush(self.display)


def managed_config(config):
    return (isinstance(config, str) and MARKER in config
            and all(re.search(r"(?m)^set_from_resource\s+\$\S+\s+" + re.escape(name) + r"\s+#[0-9a-fA-F]{6}\s*$", config)
                    for name in resources("dark")))


def refresh_frames(path, theme):
    version = i3_events.request(path, 7)
    if (not isinstance(version, dict) or type(version.get("ooonana_frame_theme_api")) is not int
            or version["ooonana_frame_theme_api"] != 1):
        raise ValueError("Running WM needs the color-only frame update")
    with socket.socket(socket.AF_UNIX) as connection:
        connection.settimeout(3)
        connection.connect(path)
        # Never reload/restart: ordinary config reload resets runtime gaps/modes.
        i3_events.send(connection, 0, ("ooonana_frame_theme " + theme).encode("ascii"))
        kind, reply = i3_events.receive(connection)
        if kind != 0 or not isinstance(reply, list) or not reply or any(not isinstance(item, dict) or item.get("success") is not True for item in reply):
            raise ValueError("Desktop refused frame palette update")


def apply_frames(theme):
    if not os.environ.get("DISPLAY"):
        return False
    server = XResources()
    try:
        previous = server.read("RESOURCE_MANAGER")
        current = merge_resources(previous, theme)
        if current == previous:
            return False
        if not server.replace("RESOURCE_MANAGER", previous, current):
            raise ValueError("X resources changed during theme update; retry when idle")
        try:
            # Root property identifies THIS display's WM, not a stale I3SOCK.
            root_socket = server.read("I3_SOCKET_PATH")
            if root_socket:
                path = os.fsdecode(root_socket.rstrip(b"\0"))
                if not os.path.isabs(path) or "\0" in path:
                    raise ValueError("Invalid display WM socket")
                config = i3_events.request(path, 9)
                if isinstance(config, dict) and managed_config(config.get("config")):
                    refresh_frames(path, theme)
                else:
                    print("Theme: custom or older frame colors retained.", file=sys.stderr)
        except (OSError, ValueError, EOFError):
            server.replace("RESOURCE_MANAGER", current, previous)
            raise
        return True
    finally:
        server.close()


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in PALETTES:
        raise SystemExit("Expected dark or light")
    try:
        apply_frames(sys.argv[1])
    except (OSError, ValueError, EOFError) as error:
        print("Theme: window frames retained; " + str(error) + ". Reopen desktop when ready.", file=sys.stderr)
