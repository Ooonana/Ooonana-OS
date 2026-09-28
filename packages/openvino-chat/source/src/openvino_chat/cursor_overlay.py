"""Persistent visual marker in an isolated renderer; never injects input."""
from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time


def _latest(commands: queue.Queue, command: dict) -> None:
    try:
        commands.put_nowait(command)
    except queue.Full:
        try:
            commands.get_nowait()
        except queue.Empty:
            pass
        commands.put_nowait(command)


class PersistentCursor:
    def __init__(self) -> None:
        self._process = None
        self._commands = None
        self._writer = None
        self._lock = threading.Lock()

    def show(self, point: tuple[int, int], label: str = "working") -> bool:
        if (not isinstance(point, tuple) or len(point) != 2
                or any(type(value) is not int or not -(2**30) < value < 2**30 for value in point)
                or not isinstance(label, str) or os.name != "nt"):
            return False
        with self._lock:
            if self._process is not None and self._process.poll() is not None:
                self._close()
            if self._process is None and not self._start():
                return False
            _latest(self._commands, {"op": "show", "point": list(point),
                                     "label": " ".join(label.split())[:40]})
            return True

    def _start(self) -> bool:
        try:
            process = subprocess.Popen(
                [sys.executable, "-B", "-m", "openvino_chat.cursor_overlay", str(os.getpid())],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, encoding="utf-8", bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
        except (OSError, ValueError):
            return False
        self._process = process
        ready = threading.Event()
        accepted = []

        def handshake() -> None:
            try:
                accepted.append(json.loads(process.stdout.readline(256)) == {"ready": True})
            except (OSError, ValueError):
                pass
            finally:
                ready.set()

        threading.Thread(target=handshake, daemon=True, name="cursor-ready").start()
        if not ready.wait(2.0) or not accepted or not accepted[0] or process.poll() is not None:
            self._close()
            return False
        commands = queue.Queue(maxsize=1)
        self._commands = commands

        def write_commands() -> None:
            try:
                while True:
                    command = commands.get()
                    process.stdin.write(json.dumps(command, ensure_ascii=True) + "\n")
                    process.stdin.flush()
                    if command["op"] == "close":
                        break
            except (OSError, ValueError):
                pass
            finally:
                try:
                    process.stdin.close()
                except (OSError, ValueError):
                    pass

        self._writer = threading.Thread(target=write_commands, daemon=True, name="cursor-commands")
        self._writer.start()
        return True

    def close(self) -> None:
        with self._lock:
            self._close()

    def _close(self) -> None:
        process, commands, writer = self._process, self._commands, self._writer
        self._process = self._commands = self._writer = None
        if process is None:
            return
        if commands is not None:
            _latest(commands, {"op": "close"})
        try:
            process.wait(timeout=0.3)
        except subprocess.TimeoutExpired:
            try:
                process.terminate()
                process.wait(timeout=0.3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=0.3)
        finally:
            if writer is not None:
                writer.join(timeout=0.1)
            # Do not wait on a pipe lock held by a blocked daemon reader/writer.
            if process.poll() is not None and (writer is None or not writer.is_alive()):
                for pipe in (process.stdin, process.stdout):
                    try:
                        pipe.close()
                    except (OSError, ValueError):
                        pass


def _read_commands(stream, commands: queue.Queue, ended: threading.Event) -> None:
    try:
        while True:
            line = stream.readline(4096)
            if not line or len(line) >= 4096:
                break
            command = json.loads(line)
            if not isinstance(command, dict):
                break
            if command.get("op") == "close":
                break
            point, label = command.get("point"), command.get("label")
            if (command.get("op") != "show" or not isinstance(point, list) or len(point) != 2
                    or any(type(v) is not int or not -(2**30) < v < 2**30 for v in point)
                    or not isinstance(label, str)):
                break
            _latest(commands, {"point": point, "label": " ".join(label.split())[:40]})
    except (OSError, ValueError):
        pass
    finally:
        ended.set()


def _render(parent_pid: int) -> int:
    import ctypes
    import win32api
    import win32con as c
    import win32event
    import win32gui as g

    # UIA rectangles use physical pixels; avoid DPI virtualization of the marker.
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except AttributeError:
        ctypes.windll.user32.SetProcessDPIAware()
    parent = win32api.OpenProcess(0x00100000, False, parent_pid)
    hwnd = None
    name = "OpenVINOPersistentCursor" + str(os.getpid())
    label = "working"
    registered = False

    def paint(window, message, wparam, lparam):
        if message == c.WM_NCHITTEST:
            return c.HTTRANSPARENT
        if message == c.WM_MOUSEACTIVATE:
            return c.MA_NOACTIVATE
        if message == c.WM_PAINT:
            dc, info = g.BeginPaint(window)
            brush = pen = None
            old_brush = old_pen = old_font = None
            try:
                g.FillRect(dc, (0, 0, 300, 44), g.GetStockObject(c.BLACK_BRUSH))
                brush = g.CreateSolidBrush(win32api.RGB(255, 185, 55))
                pen = g.CreatePen(c.PS_SOLID, 2, win32api.RGB(255, 255, 255))
                old_brush, old_pen = g.SelectObject(dc, brush), g.SelectObject(dc, pen)
                g.Polygon(dc, [(3, 3), (6, 30), (13, 22), (20, 36), (26, 32), (19, 19), (30, 18)])
                g.SetBkMode(dc, c.OPAQUE)
                g.SetBkColor(dc, win32api.RGB(35, 35, 35))
                g.SetTextColor(dc, win32api.RGB(255, 255, 255))
                old_font = g.SelectObject(dc, g.GetStockObject(c.DEFAULT_GUI_FONT))
                g.DrawText(dc, " OpenVINO: " + label + " ", -1, (38, 9, 296, 37),
                           c.DT_SINGLELINE | c.DT_VCENTER | c.DT_END_ELLIPSIS | c.DT_NOPREFIX)
            finally:
                for old in (old_font, old_pen, old_brush):
                    if old is not None:
                        g.SelectObject(dc, old)
                for obj in (pen, brush):
                    if obj is not None:
                        g.DeleteObject(obj)
                g.EndPaint(window, info)
            return 0
        return g.DefWindowProc(window, message, wparam, lparam)

    try:
        cls = g.WNDCLASS()
        cls.lpfnWndProc, cls.lpszClassName = paint, name
        cls.hInstance = win32api.GetModuleHandle(None)
        g.RegisterClass(cls)
        registered = True
        style = c.WS_EX_LAYERED | c.WS_EX_TRANSPARENT | c.WS_EX_NOACTIVATE | c.WS_EX_TOOLWINDOW | c.WS_EX_TOPMOST
        hwnd = g.CreateWindowEx(style, name, "OpenVINO agent cursor", c.WS_POPUP,
                                0, 0, 300, 44, 0, 0, cls.hInstance, None)
        g.SetLayeredWindowAttributes(hwnd, 0, 255, c.LWA_COLORKEY)
        commands = queue.Queue(maxsize=1)
        ended = threading.Event()
        threading.Thread(target=_read_commands, args=(sys.stdin, commands, ended), daemon=True).start()
        print(json.dumps({"ready": True}), flush=True)
        while not ended.is_set() and win32event.WaitForSingleObject(parent, 0) == c.WAIT_TIMEOUT:
            if g.PumpWaitingMessages():
                break
            try:
                command = commands.get_nowait()
            except queue.Empty:
                time.sleep(0.02)
                continue
            label = command["label"]
            x, y = command["point"]
            g.SetWindowPos(hwnd, c.HWND_TOPMOST, x - 3, y - 3, 300, 44, c.SWP_NOACTIVATE | c.SWP_SHOWWINDOW)
            g.InvalidateRect(hwnd, None, False)
            g.UpdateWindow(hwnd)
        return 0
    finally:
        if hwnd is not None:
            g.DestroyWindow(hwnd)
        if registered:
            g.UnregisterClass(name, cls.hInstance)
        win32api.CloseHandle(parent)


def main() -> int:
    try:
        if os.name != "nt" or len(sys.argv) != 2:
            return 1
        return _render(int(sys.argv[1]))
    except Exception:
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
