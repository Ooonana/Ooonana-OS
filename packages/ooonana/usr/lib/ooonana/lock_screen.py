"""Small launch policy; actual keyboard grab/password verification stay i3lock/PAM."""
import os
import hashlib
import re
import stat
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).parent / "ui"))
from ui_preferences import config_path, load_preferences, resolved_theme
from lock_readiness import READY, NO_SECRET, UNKNOWN, account_status


def live_account_status():
    try:
        if Path("/etc/ooonana/system-mode").read_text()[:32].strip() == "installed":
            return READY  # Installed/custom PAM remains authoritative, no shadow precheck.
    except OSError:
        pass
    uid = os.getuid()
    if uid == 0:
        import pwd
        return account_status(Path("/etc/shadow"), pwd.getpwuid(uid).pw_name)
    check = ["/usr/bin/python3", "-I", "/usr/lib/ooonana/lock_readiness.py", str(uid)]
    for authority in (["sudo", "-n", "--"], ["doas", "-n"]):
        try:
            result = subprocess.run(authority + check, stdin=subprocess.DEVNULL,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3).returncode
            if result in (READY, NO_SECRET):
                return result
        except (OSError, subprocess.SubprocessError):
            pass
    return UNKNOWN


def refuse_lock(status):
    detail = ("Live account has no usable local password. Set account password through Ooonana Setup before locking."
              if status == NO_SECRET else "Cannot confirm live account can unlock. Check account password and administrator access before locking.")
    print(detail + " Screen has not been secured.", file=sys.stderr)
    try:
        subprocess.run(["notify-send", "--app-name=Ooonana", "--urgency=critical", "--", "Lock unavailable", detail],
                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
    except (OSError, subprocess.SubprocessError):
        pass
    return 1


def command():
    return ["i3lock", "--color", "f5f5f7" if resolved_theme() == "light" else "101317",
            "--show-keyboard-layout", "--show-failed-attempts"]


def soften_lines(pixels, lines, length, line_stride, pixel_stride, channels):
    """Box blur along one axis with edge extension and a running sum."""
    radius = 3
    size = 2 * radius + 1
    softened = bytearray(len(pixels))
    for line in range(lines):
        for channel in range(channels):
            start = line * line_stride + channel
            total = sum(pixels[start + min(max(offset, 0), length - 1) * pixel_stride]
                        for offset in range(-radius, radius + 1))
            for position in range(length):
                softened[start + position * pixel_stride] = total // size
                add = min(position + radius + 1, length - 1)
                remove = max(position - radius, 0)
                total += pixels[start + add * pixel_stride] - pixels[start + remove * pixel_stride]
    return softened


def prepare_wallpaper(source, destination):
    """Keep a bounded, local raster so moving the original file is harmless."""
    import gi
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf, GLib

    if not source.is_file() or source.stat().st_size > 64 * 1024 * 1024:
        raise ValueError("Choose a readable image under 64 MiB.")
    try:
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(source), 1024, 1024, True)
        pixbuf = pixbuf.apply_embedded_orientation()
        width, height = pixbuf.get_width(), pixbuf.get_height()
        scale = min(1, 240 / max(width, height))
        width, height = max(1, round(width * scale)), max(1, round(height * scale))
        pixbuf = pixbuf.scale_simple(width, height, GdkPixbuf.InterpType.HYPER)
        channels, stride = pixbuf.get_n_channels(), pixbuf.get_rowstride()
        raw = pixbuf.get_pixels()
        row = width * channels
        pixels = b"".join(raw[start:start + row] for start in range(0, height * stride, stride))
        horizontal = soften_lines(pixels, height, width, row, channels, channels)
        blurred = soften_lines(horizontal, width, height, channels, row, channels)
        blur = GdkPixbuf.Pixbuf.new_from_bytes(GLib.Bytes.new(bytes(blurred)), GdkPixbuf.Colorspace.RGB,
                                             pixbuf.get_has_alpha(), 8, width, height, row)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(prefix=destination.name + ".", dir=destination.parent, delete=False) as staged:
            temporary = Path(staged.name)
        try:
            blur.savev(str(temporary), "png", [], [])
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
    except GLib.Error as error:
        raise ValueError("Could not decode this image.") from error


def lock_wallpaper():
    saved = config_path().with_name("lock-wallpaper.png")
    if saved.is_file():
        return saved
    source = Path("/usr/share/ooonana/wallpapers/ooonana-notes.jpg")
    if not source.is_file():
        return None
    cache = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))) / "ooonana/lock-default-v2.png"
    try:
        if not cache.is_file() or cache.stat().st_mtime < source.stat().st_mtime:
            prepare_wallpaper(source, cache)
        return cache
    except (OSError, ValueError, ImportError):
        return None


def set_lock_wallpaper(source):
    try:
        prepare_wallpaper(Path(source), config_path().with_name("lock-wallpaper.png"))
        title, detail, result = "Lock screen updated", "This image will appear next time you lock.", 0
    except (OSError, ValueError, ImportError) as error:
        title, detail, result = "Lock screen unchanged", str(error), 1
        print(detail, file=sys.stderr)
    try:
        subprocess.run(["notify-send", "-a", "Ooonana Files", "-h", "boolean:suppress-sound:true",
                        "--", title, detail], check=False, timeout=3)
    except (OSError, subprocess.SubprocessError):
        pass
    return result


def quiet_background_streams():
    # The ready parent exits after grabs, but its daemon keeps inherited pipes
    # open. GUI/suspend callers must receive EOF without waiting for unlock.
    sys.stdout.flush()
    sys.stderr.flush()
    with open(os.devnull, "wb") as sink:
        for descriptor in (1, 2):
            if not os.isatty(descriptor):
                os.dup2(sink.fileno(), descriptor)


def claim_display():
    import fcntl
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", str(Path.home() / ".local/state"))) / "ooonana"
    runtime.mkdir(parents=True, exist_ok=True)
    if runtime.is_symlink() or runtime.stat().st_uid != os.getuid():
        raise OSError("Unsafe session lock directory")
    display = re.sub(r"\.0$", "", os.environ.get("DISPLAY", "default"))
    name = hashlib.sha256(display.encode()).hexdigest()[:16]
    descriptor = os.open(runtime / f"screen-lock-{name}.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1:
            raise OSError("Unsafe session lock file")
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Keep ownership in vendor's forked/foreground locker until it exits.
        os.set_inheritable(descriptor, True)
        return descriptor
    except Exception:
        os.close(descriptor)
        raise


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--set-wallpaper":
        return set_lock_wallpaper(sys.argv[2])
    if sys.argv[1:] not in ([], ["--foreground"]):
        print("usage: ooonana-lock [--foreground | --set-wallpaper IMAGE]", file=sys.stderr)
        return 2
    status = live_account_status()
    if status != READY:
        return refuse_lock(status)
    try:
        descriptor = claim_display()
    except BlockingIOError:
        print("Another lock request is active; no new locker submitted.", file=sys.stderr)
        return 75
    except OSError:
        print("Lock unavailable: session ownership could not be secured.", file=sys.stderr)
        return 1
    try:
        args = command() + (["--nofork"] if sys.argv[1:] else [])
        wallpaper = lock_wallpaper()
        if not sys.argv[1:]:
            quiet_background_streams()
        os.execvpe("i3lock", args, {**os.environ, "OOONANA_LOCK_VISUALS": "1",
                                   "OOONANA_LOCK_WALLPAPER": str(wallpaper) if wallpaper else "",
                                   "OOONANA_LOCK_REDUCE_MOTION": "1" if load_preferences()["reduce_motion"] else "0"})
    except OSError:
        print("Lock unavailable: i3lock could not start. Screen has not been secured.", file=sys.stderr)
        return 127
    finally:
        # Real exec never returns; this also closes descriptors on launch errors.
        if descriptor is not None:
            os.close(descriptor)


if __name__ == "__main__":
    raise SystemExit(main())
