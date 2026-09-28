"""Application-owned global stop shortcut; never replaces another app's binding."""
from __future__ import annotations

import os
import threading


class EmergencyHotkey:
    def __init__(self, callback) -> None:
        self.callback = callback
        self.available = False
        self.error = "not registered"
        self._ready = threading.Event()
        self._shutdown = threading.Event()
        self._thread = None
        self._thread_id = 0

    def start(self) -> None:
        if os.name != "nt" or self._thread is not None:
            return
        self._ready.clear()
        self._shutdown.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="openvino-stop-hotkey")
        self._thread.start()
        self._ready.wait(2)

    def _run(self) -> None:
        import ctypes
        from ctypes import wintypes
        registered = False
        try:
            user32 = ctypes.windll.user32
            user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
            user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
            self._thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
            message = wintypes.MSG()
            user32.PeekMessageW(ctypes.byref(message), None, 0, 0, 0)
            registered = bool(user32.RegisterHotKey(None, 1, 0x4005, ord("S")))
            self.available = registered and not self._shutdown.is_set()
            self.error = "" if self.available else "Alt+Shift+S unavailable or already used by another app"
            self._ready.set()
            if not self.available:
                return
            while not self._shutdown.is_set():
                status = user32.GetMessageW(ctypes.byref(message), None, 0, 0)
                if status <= 0:
                    if status < 0:
                        self.error = "Global stop message loop failed"
                    break
                if message.message == 0x312:  # WM_HOTKEY
                    self.callback()
        except Exception as exc:
            self.error = f"Global stop unavailable: {exc}"
        finally:
            self.available = False
            self._ready.set()
            if registered:
                user32.UnregisterHotKey(None, 1)

    def stop(self) -> None:
        self._shutdown.set()
        self.available = False
        if self._thread and self._thread.is_alive():
            import ctypes
            ctypes.windll.user32.PostThreadMessageW(self._thread_id, 0x12, 0, 0)
            self._thread.join(timeout=2)
        self.available = False
        if self._thread is not None and not self._thread.is_alive():
            self._thread = None
