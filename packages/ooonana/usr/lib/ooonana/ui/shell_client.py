"""Fast panel/dock IPC before importing GTK or constructing any application UI."""
import hashlib
import os
import subprocess
import sys


def application_id():
    display = hashlib.sha256(os.environ.get("DISPLAY", "default").encode()).hexdigest()[:16]
    return "org.ooonana.Shell.x" + display


def main(kind, panel=False):
    if kind not in ("apps", "notifications", "controls", "audio", "brightness", "wifi", "bluetooth", "power"):
        return 2
    identity = application_id()
    try:
        # Use the existing GLib client without loading Python GTK/GI. Some
        # sessions take over a second just to import the introspection runtime.
        reply = subprocess.run(["gdbus", "call", "--session", "--dest", identity,
                                "--object-path", "/" + identity.replace(".", "/"),
                                "--method", "org.gtk.Actions.Activate", "toggle",
                                "[<('" + kind + "', '" + ("left" if panel else "") + "')>]", "{}"],
                               capture_output=True, text=True, timeout=2)
        if reply.returncode == 0:
            return 0
        # Missing primary is normal. Never replay a possibly delivered toggle.
        if not any(name in reply.stderr for name in ("org.freedesktop.DBus.Error.ServiceUnknown", "org.freedesktop.DBus.Error.NameHasNoOwner")):
            print("Desktop flyout unavailable: " + reply.stderr.strip(), file=sys.stderr)
            return 1
    except (OSError, subprocess.TimeoutExpired) as error:
        print("Desktop flyout unavailable: " + str(error), file=sys.stderr)
        return 1
    from shell_flyout import run_shell
    return run_shell(kind, panel)
