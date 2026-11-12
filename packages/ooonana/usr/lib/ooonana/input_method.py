"""Unprivileged X11 IME setup; preserve existing input preferences and profiles."""
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import time

MODULE = Path("/usr/lib/gtk-3.0/3.0.0/immodules/im-fcitx5.so")
PROFILE = Path("/usr/share/ooonana/input-method-profile")


def selected(environment=None):
    environment = os.environ if environment is None else environment
    choices = {"GTK_IM_MODULE": "fcitx", "QT_IM_MODULE": "fcitx", "XMODIFIERS": "@im=fcitx"}
    return all(environment.get(name, value) in ("", value) for name, value in choices.items())


def ensure_profile(config=None, source=PROFILE):
    config = Path(config or os.environ.get("XDG_CONFIG_HOME", Path.home()/".config"))/"fcitx5"
    config.mkdir(parents=True, exist_ok=True)
    target = config/"profile"
    if os.path.lexists(target):
        return False
    data = source.read_bytes()
    descriptor, temporary = tempfile.mkstemp(prefix=".profile-", dir=config)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, target)  # Publish complete default without replacement.
        except FileExistsError:
            return False
    finally:
        Path(temporary).unlink(missing_ok=True)
    return True


def environment():
    if not selected() or not shutil.which("fcitx5"):
        return {}
    if not MODULE.is_file():
        raise OSError("Fcitx GTK3 module unavailable")
    values = {"GTK_IM_MODULE": "fcitx", "QT_IM_MODULE": "fcitx", "XMODIFIERS": "@im=fcitx"}
    if not os.environ.get("GTK_IM_MODULE_FILE"):
        query = next((str(path) for path in (Path("/usr/bin/gtk-query-immodules-3.0"),
            Path("/usr/lib/gtk-3.0/gtk-query-immodules-3.0")) if path.is_file()), None)
        if not query:
            raise OSError("GTK3 input module query unavailable")
        result = subprocess.run([query, str(MODULE)], capture_output=True, timeout=5, check=True)
        if b'"fcitx"' not in result.stdout or len(result.stdout) > 65536:
            raise OSError("GTK3 input module registration failed")
        cache = Path(os.environ.get("XDG_CACHE_HOME", Path.home()/".cache"))/"ooonana"
        cache.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=".input-method-", dir=cache)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(result.stdout)
            target = cache/"gtk3-input-method.cache"
            os.replace(temporary, target)
        finally:
            Path(temporary).unlink(missing_ok=True)
        values["GTK_IM_MODULE_FILE"] = str(target)
    return values


def ready():
    result = subprocess.run(["fcitx5-remote", "--check"], capture_output=True, text=True, timeout=2)
    # No focused input context is state 0, not a failed service. --check
    # queries the current owner without starting a competing D-Bus service.
    return result.returncode == 0 and result.stdout.strip() in ("0", "1", "2")


def start():
    ensure_profile()
    if ready():
        return 0
    # Never --replace: an existing input-method session belongs to its user.
    result = subprocess.run(["fcitx5", "-d", "--disable=clipboard"], stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=4)
    if result.returncode:
        return result.returncode
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        if ready():
            return 0
        time.sleep(.05)
    raise OSError("Fcitx service did not become ready")


def main():
    try:
        if sys.argv[1:] in (["--env"], ["--json-env"]):
            values = environment()
            if sys.argv[1:] == ["--json-env"]:
                print(json.dumps(values))
            else:
                for name, value in values.items():
                    print("export " + name + "=" + shlex.quote(value))
            return 0
        if sys.argv[1:] == ["--start"]:
            if not selected():
                return 0
            if os.getuid() == 0 or not os.environ.get("DISPLAY") or not os.environ.get("DBUS_SESSION_BUS_ADDRESS"):
                raise OSError("Input method needs an unprivileged X11 desktop and session bus")
            if not shutil.which("fcitx5"):
                raise OSError("Fcitx5 unavailable")
            return start()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print("Input method unavailable: " + str(error), file=sys.stderr)
        return 1
    print("usage: ooonana-input-method --env|--json-env|--start", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
