"""User-session idle locking and conservative login1 suspend requests.

No password input/authentication here: vendor i3lock owns grabs and PAM.
No kernel writes, privilege escalation or inhibitor overrides.
"""
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import threading

sys.path.insert(0, str(Path(__file__).parent / "ui"))
from ui_preferences import load_preferences


def lock_session():
    try:
        # Vendor i3lock's parent exits successfully only after its grabs exist.
        result = subprocess.run(["ooonana-lock"], stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=12)
        return result.returncode, (result.stdout + result.stderr).strip()
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, "Lock could not be confirmed: " + str(exc)


class IdleInfo(C.Structure):
    _fields_ = [("window", C.c_ulong), ("state", C.c_int), ("kind", C.c_int),
                ("until", C.c_ulong), ("idle", C.c_ulong), ("mask", C.c_ulong)]


class IdleDisplay:
    def __init__(self):
        self.display = None
        self.x = C.CDLL("libX11.so.6")
        self.saver = C.CDLL("libXss.so.1")
        self.x.XOpenDisplay.argtypes = [C.c_char_p]; self.x.XOpenDisplay.restype = C.c_void_p
        self.x.XDefaultRootWindow.argtypes = [C.c_void_p]; self.x.XDefaultRootWindow.restype = C.c_ulong
        self.x.XDefaultScreen.argtypes = [C.c_void_p]; self.x.XDefaultScreen.restype = C.c_int
        self.x.XInternAtom.argtypes = [C.c_void_p, C.c_char_p, C.c_int]; self.x.XInternAtom.restype = C.c_ulong
        self.x.XGetSelectionOwner.argtypes = [C.c_void_p, C.c_ulong]; self.x.XGetSelectionOwner.restype = C.c_ulong
        self.x.XCloseDisplay.argtypes = [C.c_void_p]
        self.saver.XScreenSaverQueryInfo.argtypes = [C.c_void_p, C.c_ulong, C.POINTER(IdleInfo)]
        self.saver.XScreenSaverQueryInfo.restype = C.c_int
        self.display = self.x.XOpenDisplay(None)
        if not self.display:
            raise OSError("X11 session unavailable")
        self.root = self.x.XDefaultRootWindow(self.display)
        self.wm = self.x.XInternAtom(self.display, f"WM_S{self.x.XDefaultScreen(self.display)}".encode(), False)
        self.idle_ms()  # Refuse missing extensions rather than inventing idle time.

    def idle_ms(self):
        info = IdleInfo()
        if not self.saver.XScreenSaverQueryInfo(self.display, self.root, C.byref(info)):
            raise OSError("X11 idle counter unavailable")
        return int(info.idle)

    def has_window_manager(self):
        return bool(self.x.XGetSelectionOwner(self.display, self.wm))

    def close(self):
        if self.display:
            self.x.XCloseDisplay(self.display)
            self.display = None


class IdlePolicy:
    """One attempt per idle period; input or a policy change rearms it."""
    def __init__(self):
        self.minutes, self.attempted = None, False

    def due(self, idle_ms, minutes):
        if minutes != self.minutes:
            self.minutes, self.attempted = minutes, False
        if not minutes or idle_ms < minutes * 60_000:
            self.attempted = False
            return False
        if self.attempted:
            return False
        self.attempted = True
        return True


def notify_failure(detail):
    try:
        subprocess.run(["notify-send", "--app-name=Ooonana", "--urgency=critical",
            "-h", "boolean:suppress-sound:true", "--", "Automatic lock unavailable",
            detail or "Screen has not been secured. Use Lock or check account password."],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
    except (OSError, subprocess.SubprocessError):
        pass


def watch():
    import fcntl
    if not os.environ.get("DISPLAY") or os.getuid() == 0:
        return 1
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", str(Path.home() / ".local/state"))) / "ooonana"
    runtime.mkdir(parents=True, exist_ok=True)
    if runtime.is_symlink() or runtime.stat().st_uid != os.getuid():
        return 1
    name = hashlib.sha256(os.environ["DISPLAY"].encode()).hexdigest()[:16]
    descriptor = os.open(runtime / f"idle-lock-{name}.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    info = os.fstat(descriptor)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1:
        os.close(descriptor)
        return 1
    with os.fdopen(descriptor, "a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0
        display = IdleDisplay()
        stop = threading.Event()
        for signum in (signal.SIGTERM, signal.SIGINT):
            signal.signal(signum, lambda *_: stop.set())
        policy, absent, locker = IdlePolicy(), 0, None
        try:
            while not stop.is_set():
                # Allow an i3 restart, but leave when the desktop session ends.
                absent = 0 if display.has_window_manager() else absent + 1
                if absent >= 3:
                    return 0
                if locker is not None:
                    if locker.poll() is None:
                        stop.wait(5)
                        continue
                    if locker.returncode not in (0, 75):
                        notify_failure("Automatic locker failed. Screen has not been confirmed secured; check account password.")
                    locker = None
                minutes = load_preferences()["idle_lock_minutes"]
                if minutes and policy.due(display.idle_ms(), minutes):
                    # Keep our own foreground handle until unlock. Do not spawn
                    # another locker or report failure while this one is active.
                    try:
                        locker = subprocess.Popen(["ooonana-lock", "--foreground"], stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    except OSError as exc:
                        notify_failure(str(exc))
                elif not minutes:
                    return 0  # Disabled policy leaves no resident poller.
                stop.wait(5)
        finally:
            display.close()
    return 0


class LoginManager:
    def __init__(self):
        from gi.repository import Gio, GLib
        self.Gio, self.GLib = Gio, GLib
        self.bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        # Pin the current owner; replacement services must be checked anew.
        self.owner = self.bus.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus",
            "org.freedesktop.DBus", "GetNameOwner", GLib.Variant("(s)", ("org.freedesktop.login1",)),
            GLib.VariantType.new("(s)"), Gio.DBusCallFlags.NO_AUTO_START, 2000, None).unpack()[0]

    def call(self, method, arguments=None):
        return self.bus.call_sync(self.owner, "/org/freedesktop/login1", "org.freedesktop.login1.Manager",
            method, arguments, None, self.Gio.DBusCallFlags.NO_AUTO_START, 5000, None).unpack()

    def can_suspend(self):
        result = self.call("CanSuspend")
        return result[0] if len(result) == 1 and isinstance(result[0], str) else "unavailable"

    def suspend(self):
        self.call("Suspend", self.GLib.Variant("(b)", (False,)))


def suspend(manager=None, locker=lock_session):
    try:
        manager = manager or LoginManager()
        state = manager.can_suspend()
        if state != "yes":
            return 1, ("Suspend needs prior system authorization; no lock or sleep submitted." if state == "challenge" else
                       "Suspend unavailable or inhibited; no lock or sleep submitted.")
        rc, detail = locker()
        if rc:
            return rc, "Suspend refused: lock was not confirmed. " + detail
        if manager.can_suspend() != "yes":
            return 1, "Suspend permission changed; session stays locked. Unlock normally to retry."
        manager.suspend()
        return 0, "Suspend submitted after lock confirmation. Unlock normally after wake."
    except Exception as exc:
        return 1, "Suspend unavailable; no unguarded sleep fallback. " + str(exc)


def main():
    args = sys.argv[1:]
    try:
        if args == ["--suspend"]:
            rc, detail = suspend()
            print(detail)
            return rc
        if args == ["--status"]:
            try:
                state = LoginManager().can_suspend()
            except Exception:
                state = "unavailable"
            print(json.dumps({"idle_lock_minutes": load_preferences()["idle_lock_minutes"], "suspend": state}))
            return 0
        if args == ["--watch", "--background"]:
            if os.getuid() == 0:
                print("Automatic locking belongs to the unprivileged desktop session.", file=sys.stderr)
                return 1
            if not load_preferences()["idle_lock_minutes"]:
                return 0
            from lock_screen import READY, live_account_status, refuse_lock
            readiness = live_account_status()
            if readiness != READY:
                return refuse_lock(readiness)
            display = IdleDisplay()
            try:
                if not display.has_window_manager():
                    print("Automatic locking needs a running X11 window manager.", file=sys.stderr)
                    return 1
            finally:
                display.close()
            subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--watch"], start_new_session=True,
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return 0
        if args == ["--watch"]:
            return watch()
    except (OSError, ValueError) as exc:
        print("Session control unavailable: " + str(exc), file=sys.stderr)
        return 1
    print("usage: ooonana-session --status|--suspend|--watch [--background]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
