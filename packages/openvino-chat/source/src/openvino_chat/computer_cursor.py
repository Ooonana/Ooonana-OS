"""Non-activating, click-through agent marker. This is not the OS pointer."""
from __future__ import annotations

import os
import time
from contextlib import contextmanager


@contextmanager
def marker(point):
    handle = None
    shown = False
    try:
        if point is not None and os.name == "nt":
            import win32api
            import win32con
            import win32gui

            def paint(hwnd, message, wparam, lparam):
                if message == win32con.WM_NCHITTEST:
                    return win32con.HTTRANSPARENT
                if message == win32con.WM_MOUSEACTIVATE:
                    return win32con.MA_NOACTIVATE
                if message == win32con.WM_PAINT:
                    dc, info = win32gui.BeginPaint(hwnd)
                    background = win32gui.CreateSolidBrush(0)
                    brush = win32gui.CreateSolidBrush(win32api.RGB(255, 174, 50))
                    pen = win32gui.CreatePen(win32con.PS_SOLID, 2, win32api.RGB(255, 255, 255))
                    win32gui.FillRect(dc, (0, 0, 34, 40), background)
                    old_brush, old_pen = win32gui.SelectObject(dc, brush), win32gui.SelectObject(dc, pen)
                    win32gui.Polygon(dc, [(3, 3), (6, 30), (13, 22), (20, 35), (25, 32), (18, 19), (29, 18)])
                    win32gui.SelectObject(dc, old_brush)
                    win32gui.SelectObject(dc, old_pen)
                    for obj in (background, brush, pen):
                        win32gui.DeleteObject(obj)
                    win32gui.EndPaint(hwnd, info)
                    return 0
                return win32gui.DefWindowProc(hwnd, message, wparam, lparam)

            name = "OpenVINOAgentMarker" + str(os.getpid())
            cls = win32gui.WNDCLASS()
            cls.lpfnWndProc, cls.lpszClassName = paint, name
            cls.hInstance = win32api.GetModuleHandle(None)
            win32gui.RegisterClass(cls)
            style = (win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT | win32con.WS_EX_NOACTIVATE |
                     win32con.WS_EX_TOOLWINDOW | win32con.WS_EX_TOPMOST)
            handle = win32gui.CreateWindowEx(style, name, "OpenVINO agent cursor", win32con.WS_POPUP,
                                             int(point[0]) - 3, int(point[1]) - 3, 34, 40, 0, 0, cls.hInstance, None)
            win32gui.SetLayeredWindowAttributes(handle, 0, 255, win32con.LWA_COLORKEY)
            win32gui.ShowWindow(handle, win32con.SW_SHOWNOACTIVATE)
            win32gui.UpdateWindow(handle)
            shown = True
    except Exception:
        # Marker rendering is cosmetic, never an excuse to send physical input.
        pass
    try:
        yield shown
        if handle is not None:
            time.sleep(.25)
    finally:
        if handle is not None:
            import win32gui
            win32gui.DestroyWindow(handle)
